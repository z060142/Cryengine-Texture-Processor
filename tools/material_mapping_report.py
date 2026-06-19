#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create material-slot evidence reports for RC smoke outputs."""

import json
import math
import os
import xml.etree.ElementTree as ET

from model_processing.material_manifest import (
    coerce_material_name,
    coerce_material_slot,
    coerce_polygon_index,
    discover_material_manifest,
    iter_manifest_material_rows,
    iter_manifest_polygon_rows,
    load_material_manifest,
)
from model_processing.rc_material_policy import RC_MAX_SUB_MATERIALS
from utils.cgf_material_reader import read_cgf_material_summary


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _coerce_request_sub_index(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= -1 else None
    if isinstance(value, str):
        text = value.strip()
        if text == "-1":
            return -1
        if not text or not all("0" <= char <= "9" for char in text):
            return None
        return int(text)
    return None


def load_request_materials(json_path):
    payload = _read_json(json_path)
    request = payload.get("request", payload) if isinstance(payload, dict) else {}
    raw_materials = request.get("materials", []) if isinstance(request, dict) else []
    if not isinstance(raw_materials, list):
        return [
            {
                "order": None,
                "name": "",
                "sub_index": None,
                "physicalize": "",
                "ok": False,
                "errors": ["invalid_request_materials_collection"],
                "collection_type": type(raw_materials).__name__,
            }
        ]

    materials = []
    for order, material in enumerate(raw_materials):
        if not isinstance(material, dict):
            materials.append(
                {
                    "order": order,
                    "name": "",
                    "sub_index": None,
                    "physicalize": "",
                    "ok": False,
                    "errors": ["invalid_request_material_row"],
                    "row_type": type(material).__name__,
                }
            )
            continue

        raw_name = material.get("name", "")
        name = coerce_material_name(raw_name)
        raw_sub_index = material.get("sub_index")
        sub_index = _coerce_request_sub_index(raw_sub_index)
        errors = []
        entry = {
            "order": order,
            "name": name,
            "sub_index": sub_index,
            "physicalize": material.get("physicalize", ""),
        }
        if not name:
            errors.append("invalid_request_material_name")
            entry["raw_name"] = raw_name
            entry["name_type"] = type(raw_name).__name__
        if raw_sub_index is not None and sub_index is None:
            errors.append("invalid_request_sub_index")
            entry["raw_sub_index"] = raw_sub_index
            entry["sub_index_type"] = type(raw_sub_index).__name__
        if errors:
            entry["ok"] = False
            entry["errors"] = errors
        materials.append(entry)
    return materials


def load_mtl_slots(mtl_path):
    if not mtl_path or not os.path.exists(mtl_path):
        return []

    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return []

    slots = []
    for slot, material in enumerate(list(sub_materials)):
        if material.tag != "Material":
            continue
        slots.append(
            {
                "slot": slot,
                "name": material.get("Name", ""),
                "shader": material.get("Shader", ""),
                "surface_type": material.get("SurfaceType", ""),
            }
        )
    return slots


def load_cryasset_details(cryasset_path):
    if not cryasset_path or not os.path.exists(cryasset_path):
        return {}

    root = ET.parse(cryasset_path).getroot()
    details = {}
    details_elem = root.find("Details")
    if details_elem is None:
        return details

    for detail in list(details_elem):
        name = detail.get("name")
        if name:
            details[name] = detail.text or ""
    return details


def _load_mtl_slots_for_report(mtl_path):
    try:
        return load_mtl_slots(mtl_path), ""
    except (ET.ParseError, OSError, ValueError) as e:
        return [], str(e)


def _load_cryasset_details_for_report(cryasset_path):
    try:
        return load_cryasset_details(cryasset_path), ""
    except (ET.ParseError, OSError, ValueError) as e:
        return {}, str(e)


def discover_fixture_manifest(source_fbx_path="", copied_fbx_path=""):
    return discover_material_manifest(source_fbx_path, copied_fbx_path)


def load_fixture_manifest(manifest_path):
    return load_material_manifest(manifest_path)


def evaluate_material_slot_alignment(request_materials, mtl_slots):
    slots_by_index = {slot["slot"]: slot for slot in mtl_slots}
    checks = []
    ok = True

    for material in request_materials:
        if not isinstance(material, dict):
            ok = False
            checks.append(
                {
                    "ok": False,
                    "type": "invalid_request_material_row",
                    "name": "",
                    "sub_index": None,
                    "row_type": type(material).__name__,
                }
            )
            continue
        material_errors = material.get("errors") or []
        if material_errors:
            ok = False
            for error in material_errors:
                checks.append(
                    {
                        "ok": False,
                        "type": error,
                        "name": material.get("name", ""),
                        "sub_index": material.get("raw_sub_index", material.get("sub_index")),
                        "order": material.get("order"),
                        "row_type": material.get("row_type"),
                        "collection_type": material.get("collection_type"),
                        "name_type": material.get("name_type"),
                        "sub_index_type": material.get("sub_index_type"),
                    }
                )
            continue
        raw_sub_index = material.get("sub_index")
        sub_index = _coerce_request_sub_index(raw_sub_index)
        name = coerce_material_name(material.get("name", ""))
        if not name:
            ok = False
            checks.append(
                {
                    "ok": False,
                    "type": "invalid_request_material_name",
                    "name": material.get("name", ""),
                    "sub_index": raw_sub_index,
                    "order": material.get("order"),
                    "name_type": type(material.get("name", "")).__name__,
                }
            )
            continue
        if raw_sub_index is not None and sub_index is None:
            ok = False
            checks.append(
                {
                    "ok": False,
                    "type": "invalid_request_sub_index",
                    "name": name,
                    "sub_index": raw_sub_index,
                    "order": material.get("order"),
                    "sub_index_type": type(raw_sub_index).__name__,
                }
            )
            continue
        if sub_index is None or sub_index < 0:
            checks.append(
                {
                    "ok": True,
                    "type": "deleted_or_unassigned",
                    "name": name,
                    "sub_index": sub_index,
                }
            )
            continue

        slot = slots_by_index.get(sub_index)
        if slot is None:
            ok = False
            checks.append(
                {
                    "ok": False,
                    "type": "missing_mtl_slot",
                    "name": name,
                    "sub_index": sub_index,
                }
            )
            continue

        names_match = name == slot.get("name", "")
        ok = ok and names_match
        checks.append(
            {
                "ok": names_match,
                "type": "slot_name_match" if names_match else "slot_name_mismatch",
                "name": name,
                "sub_index": sub_index,
                "mtl_slot_name": slot.get("name", ""),
            }
        )

    return {"ok": ok, "checks": checks}


def _request_names_by_sub_index(request_materials):
    names_by_index = {}
    for material in request_materials:
        if not isinstance(material, dict) or material.get("errors"):
            continue
        sub_index = _coerce_request_sub_index(material.get("sub_index"))
        if sub_index is None or sub_index < 0:
            continue
        name = coerce_material_name(material.get("name", ""))
        if not name:
            continue
        names_by_index.setdefault(sub_index, []).append(name)
    return names_by_index


def _valid_request_materials(request_materials):
    materials = []
    for material in request_materials:
        if not isinstance(material, dict) or material.get("errors"):
            continue
        name = coerce_material_name(material.get("name", ""))
        raw_sub_index = material.get("sub_index")
        sub_index = _coerce_request_sub_index(raw_sub_index)
        if not name:
            continue
        if raw_sub_index is not None and sub_index is None:
            continue
        materials.append(material)
    return materials


def _invalid_request_entries(request_materials):
    entries = []
    for order, material in enumerate(request_materials):
        if not isinstance(material, dict):
            entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_request_material_row",
                    "row_type": type(material).__name__,
                    "name": "",
                    "sub_index": None,
                }
            )
            continue
        for error in material.get("errors") or []:
            entries.append(
                {
                    "ok": False,
                    "order": material.get("order", order),
                    "error": error,
                    "name": material.get("name", ""),
                    "sub_index": material.get("raw_sub_index", material.get("sub_index")),
                    "row_type": material.get("row_type"),
                    "collection_type": material.get("collection_type"),
                    "name_type": material.get("name_type"),
                    "sub_index_type": material.get("sub_index_type"),
                }
            )
        if material.get("errors"):
            continue
        name = coerce_material_name(material.get("name", ""))
        if not name:
            entries.append(
                {
                    "ok": False,
                    "order": material.get("order", order),
                    "error": "invalid_request_material_name",
                    "name": material.get("name", ""),
                    "sub_index": material.get("sub_index"),
                    "name_type": type(material.get("name", "")).__name__,
                }
            )
        raw_sub_index = material.get("sub_index")
        if raw_sub_index is not None and _coerce_request_sub_index(raw_sub_index) is None:
            entries.append(
                {
                    "ok": False,
                    "order": material.get("order", order),
                    "error": "invalid_request_sub_index",
                    "name": name,
                    "sub_index": raw_sub_index,
                    "sub_index_type": type(raw_sub_index).__name__,
                }
            )
    return entries


def _duplicate_values(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(value for value, count in counts.items() if count > 1)


def _coerce_cgf_subset_center_x(subset):
    center = subset.get("center")
    if not isinstance(center, (list, tuple)) or not center:
        return None
    try:
        center_x = float(center[0])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(center_x):
        return None
    return round(center_x, 4)


def _invalid_subset_entry(mesh, subset, error, **extra):
    return {
        "mesh_chunk_id": mesh.get("chunk_id") if isinstance(mesh, dict) else None,
        "subset": subset.get("subset") if isinstance(subset, dict) else None,
        "center": subset.get("center") if isinstance(subset, dict) else None,
        "material_id": subset.get("material_id") if isinstance(subset, dict) else None,
        "ok": False,
        "error": error,
        **extra,
    }


def _fixture_polygon_actual_ids(manifest, cgf_material_summary):
    center_lookup = {}
    for _, polygon in iter_manifest_polygon_rows(manifest):
        if "center_x" in polygon:
            polygon_index = coerce_polygon_index(polygon.get("polygon"))
            if polygon_index is None:
                continue
            center_x = _coerce_cgf_subset_center_x({"center": [polygon.get("center_x")]})
            if center_x is None:
                continue
            center_lookup[center_x] = polygon_index

    actual_by_polygon = {}
    subset_entries = []
    invalid_subset_entries = []
    duplicate_polygons = []
    raw_meshes = cgf_material_summary.get("meshes", []) if isinstance(cgf_material_summary, dict) else []
    if not isinstance(raw_meshes, list):
        return actual_by_polygon, subset_entries, duplicate_polygons, [
            {
                "mesh_chunk_id": None,
                "subset": None,
                "center": None,
                "material_id": None,
                "ok": False,
                "error": "invalid_cgf_meshes_collection",
                "collection_type": type(raw_meshes).__name__,
            }
        ]
    for mesh_order, mesh in enumerate(raw_meshes):
        if not isinstance(mesh, dict):
            invalid_subset_entries.append(
                {
                    "mesh_chunk_id": None,
                    "subset": None,
                    "center": None,
                    "material_id": None,
                    "ok": False,
                    "error": "invalid_cgf_mesh_row",
                    "mesh_order": mesh_order,
                    "row_type": type(mesh).__name__,
                }
            )
            continue
        raw_subsets = mesh.get("subsets", [])
        if raw_subsets is None:
            raw_subsets = []
        if not isinstance(raw_subsets, list):
            invalid_subset_entries.append(
                {
                    "mesh_chunk_id": mesh.get("chunk_id"),
                    "subset": None,
                    "center": None,
                    "material_id": None,
                    "ok": False,
                    "error": "invalid_cgf_mesh_subsets_collection",
                    "collection_type": type(raw_subsets).__name__,
                }
            )
            continue
        for subset_order, subset in enumerate(raw_subsets):
            if not isinstance(subset, dict):
                invalid_subset_entries.append(
                    {
                        "mesh_chunk_id": mesh.get("chunk_id"),
                        "subset": None,
                        "center": None,
                        "material_id": None,
                        "ok": False,
                        "error": "invalid_cgf_subset_row",
                        "subset_order": subset_order,
                        "row_type": type(subset).__name__,
                    }
                )
                continue
            center_x = _coerce_cgf_subset_center_x(subset)
            if center_x is None:
                invalid_subset_entries.append(
                    _invalid_subset_entry(
                        mesh,
                        subset,
                        "invalid_cgf_subset_center",
                        subset_order=subset_order,
                        center_type=type(subset.get("center")).__name__,
                    )
                )
                continue
            material_id = coerce_material_slot(subset.get("material_id"))
            if material_id is None:
                invalid_subset_entries.append(
                    _invalid_subset_entry(
                        mesh,
                        subset,
                        "invalid_cgf_subset_material_id",
                        subset_order=subset_order,
                        material_id_type=type(subset.get("material_id")).__name__,
                    )
                )
                continue
            polygon = center_lookup.get(center_x)
            if polygon is None:
                polygon = int(round(center_x / 3.0))
            if polygon in actual_by_polygon:
                duplicate_polygons.append(polygon)
            actual_by_polygon[polygon] = material_id
            subset_entries.append(
                {
                    "mesh_chunk_id": mesh.get("chunk_id"),
                    "subset": subset.get("subset"),
                    "polygon": polygon,
                    "center": subset.get("center"),
                    "material_id": material_id,
                }
            )

    return actual_by_polygon, subset_entries, duplicate_polygons, invalid_subset_entries


def evaluate_fixture_material_semantics(manifest, cgf_material_summary, request_materials, mtl_slots):
    if not manifest:
        return {}
    if not isinstance(manifest, dict):
        return {
            "ok": False,
            "manifest_kind": "",
            "material_checks": [
                {
                    "ok": False,
                    "slot": None,
                    "expected_name": "",
                    "request_names": [],
                    "mtl_slot_name": "",
                    "request_ok": False,
                    "mtl_ok": False,
                    "error": "invalid_manifest_root",
                    "root_type": type(manifest).__name__,
                }
            ],
            "polygon_checks": [],
            "duplicate_polygons": [],
            "duplicate_request_material_names": [],
            "duplicate_request_sub_indices": [],
            "subset_entries": [],
            "invalid_subset_entries": [],
            "invalid_request_entries": [],
        }

    valid_request_materials = _valid_request_materials(request_materials)
    invalid_request_entries = _invalid_request_entries(request_materials)
    request_names_by_index = _request_names_by_sub_index(request_materials)
    request_sub_indices = [
        _coerce_request_sub_index(material.get("sub_index"))
        for material in valid_request_materials
        if _coerce_request_sub_index(material.get("sub_index")) is not None
        and _coerce_request_sub_index(material.get("sub_index")) >= 0
    ]
    request_names = [
        coerce_material_name(material.get("name", ""))
        for material in valid_request_materials
        if coerce_material_name(material.get("name", ""))
    ]
    mtl_slots_by_index = {slot["slot"]: slot for slot in mtl_slots}

    material_checks = []
    ok = True
    raw_materials = manifest.get("materials") if isinstance(manifest, dict) else None
    raw_polygons = manifest.get("polygons") if isinstance(manifest, dict) else None
    if raw_materials is not None and not isinstance(raw_materials, list):
        ok = False
        material_checks.append(
            {
                "ok": False,
                "slot": None,
                "expected_name": "",
                "request_names": [],
                "mtl_slot_name": "",
                "request_ok": False,
                "mtl_ok": False,
                "error": "invalid_manifest_materials_collection",
                "collection_type": type(raw_materials).__name__,
            }
        )
    elif isinstance(raw_materials, list):
        for order, material in enumerate(raw_materials):
            if not isinstance(material, dict):
                ok = False
                material_checks.append(
                    {
                        "ok": False,
                        "slot": None,
                        "expected_name": "",
                        "request_names": [],
                        "mtl_slot_name": "",
                        "request_ok": False,
                        "mtl_ok": False,
                        "error": "invalid_manifest_material_row",
                        "manifest_order": order,
                        "row_type": type(material).__name__,
                    }
                )

    for _, material in iter_manifest_material_rows(manifest):
        raw_slot = material.get("slot")
        slot = coerce_material_slot(raw_slot)
        raw_expected_name = material.get("name", "")
        expected_name = coerce_material_name(raw_expected_name)
        if not expected_name:
            ok = False
            material_checks.append(
                {
                    "ok": False,
                    "slot": raw_slot,
                    "expected_name": raw_expected_name,
                    "request_names": [],
                    "mtl_slot_name": "",
                    "request_ok": False,
                    "mtl_ok": False,
                    "error": "invalid_manifest_material_name",
                    "name_type": type(raw_expected_name).__name__,
                }
            )
            continue
        if slot is None:
            ok = False
            material_checks.append(
                {
                    "ok": False,
                    "slot": raw_slot,
                    "expected_name": expected_name,
                    "request_names": [],
                    "mtl_slot_name": "",
                    "request_ok": False,
                    "mtl_ok": False,
                    "error": "invalid_manifest_material_slot",
                }
            )
            continue
        if slot >= RC_MAX_SUB_MATERIALS:
            ok = False
            material_checks.append(
                {
                    "ok": False,
                    "slot": slot,
                    "expected_name": expected_name,
                    "request_names": request_names_by_index.get(slot, []),
                    "mtl_slot_name": mtl_slots_by_index.get(slot, {}).get("name", ""),
                    "request_ok": False,
                    "mtl_ok": False,
                    "max_sub_materials": RC_MAX_SUB_MATERIALS,
                    "error": "manifest_material_slot_out_of_rc_range",
                }
            )
            continue
        request_names_for_slot = request_names_by_index.get(slot, [])
        mtl_slot_name = mtl_slots_by_index.get(slot, {}).get("name", "")
        request_ok = request_names_for_slot == [expected_name]
        mtl_ok = mtl_slot_name == expected_name
        check_ok = request_ok and mtl_ok
        ok = ok and check_ok
        material_checks.append(
            {
                "ok": check_ok,
                "slot": slot,
                "expected_name": expected_name,
                "request_names": request_names_for_slot,
                "mtl_slot_name": mtl_slot_name,
                "request_ok": request_ok,
                "mtl_ok": mtl_ok,
            }
        )

    actual_by_polygon, subset_entries, duplicate_polygons, invalid_subset_entries = _fixture_polygon_actual_ids(
        manifest,
        cgf_material_summary,
    )
    polygon_checks = []
    if raw_polygons is not None and not isinstance(raw_polygons, list):
        ok = False
        polygon_checks.append(
            {
                "ok": False,
                "polygon": None,
                "expected_cgf_material_id": None,
                "actual_cgf_material_id": None,
                "expected_name": "",
                "request_names_for_actual_id": [],
                "mtl_name_for_actual_id": "",
                "cgf_id_ok": False,
                "error": "invalid_manifest_polygons_collection",
                "collection_type": type(raw_polygons).__name__,
            }
        )
    elif isinstance(raw_polygons, list):
        for order, polygon in enumerate(raw_polygons):
            if not isinstance(polygon, dict):
                ok = False
                polygon_checks.append(
                    {
                        "ok": False,
                        "polygon": None,
                        "expected_cgf_material_id": None,
                        "actual_cgf_material_id": None,
                        "expected_name": "",
                        "request_names_for_actual_id": [],
                        "mtl_name_for_actual_id": "",
                        "cgf_id_ok": False,
                        "error": "invalid_manifest_polygon_row",
                        "polygon_order": order,
                        "row_type": type(polygon).__name__,
                    }
                )

    for order, polygon in iter_manifest_polygon_rows(manifest):
        raw_polygon_index = polygon.get("polygon")
        polygon_index = coerce_polygon_index(raw_polygon_index)
        if polygon_index is None:
            ok = False
            polygon_checks.append(
                {
                    "ok": False,
                    "polygon": raw_polygon_index,
                    "expected_cgf_material_id": None,
                    "actual_cgf_material_id": None,
                    "expected_name": "",
                    "request_names_for_actual_id": [],
                    "mtl_name_for_actual_id": "",
                    "cgf_id_ok": False,
                    "error": "invalid_manifest_polygon_index",
                    "polygon_order": order,
                    "index_type": type(raw_polygon_index).__name__,
                }
            )
            continue
        raw_expected_cgf_id = polygon.get("expected_cgf_material_id", polygon.get("material_slot", 0))
        expected_cgf_id = coerce_material_slot(raw_expected_cgf_id)
        raw_expected_name = polygon.get("material_name", "")
        expected_name = coerce_material_name(raw_expected_name)
        if not expected_name:
            ok = False
            polygon_checks.append(
                {
                    "ok": False,
                    "polygon": polygon_index,
                    "expected_cgf_material_id": raw_expected_cgf_id,
                    "actual_cgf_material_id": None,
                    "expected_name": raw_expected_name,
                    "request_names_for_actual_id": [],
                    "mtl_name_for_actual_id": "",
                    "cgf_id_ok": False,
                    "error": "invalid_manifest_polygon_material_name",
                    "name_type": type(raw_expected_name).__name__,
                }
            )
            continue
        if expected_cgf_id is None:
            ok = False
            polygon_checks.append(
                {
                    "ok": False,
                    "polygon": polygon_index,
                    "expected_cgf_material_id": raw_expected_cgf_id,
                    "actual_cgf_material_id": None,
                    "expected_name": expected_name,
                    "request_names_for_actual_id": [],
                    "mtl_name_for_actual_id": "",
                    "cgf_id_ok": False,
                    "error": "invalid_manifest_polygon_slot",
                }
            )
            continue
        if expected_cgf_id >= RC_MAX_SUB_MATERIALS:
            ok = False
            polygon_checks.append(
                {
                    "ok": False,
                    "polygon": polygon_index,
                    "expected_cgf_material_id": expected_cgf_id,
                    "actual_cgf_material_id": None,
                    "expected_name": expected_name,
                    "request_names_for_actual_id": [],
                    "mtl_name_for_actual_id": "",
                    "cgf_id_ok": False,
                    "max_sub_materials": RC_MAX_SUB_MATERIALS,
                    "error": "manifest_polygon_slot_out_of_rc_range",
                }
            )
            continue
        actual_cgf_id = actual_by_polygon.get(polygon_index)
        actual_request_names = request_names_by_index.get(actual_cgf_id, []) if actual_cgf_id is not None else []
        actual_mtl_name = mtl_slots_by_index.get(actual_cgf_id, {}).get("name", "") if actual_cgf_id is not None else ""
        cgf_id_ok = actual_cgf_id == expected_cgf_id
        semantic_ok = cgf_id_ok and actual_request_names == [expected_name] and actual_mtl_name == expected_name
        ok = ok and semantic_ok
        polygon_checks.append(
            {
                "ok": semantic_ok,
                "polygon": polygon_index,
                "expected_cgf_material_id": expected_cgf_id,
                "actual_cgf_material_id": actual_cgf_id,
                "expected_name": expected_name,
                "request_names_for_actual_id": actual_request_names,
                "mtl_name_for_actual_id": actual_mtl_name,
                "cgf_id_ok": cgf_id_ok,
            }
        )

    duplicate_request_names = _duplicate_values(request_names)
    duplicate_request_sub_indices = _duplicate_values(request_sub_indices)
    ok = (
        ok
        and not duplicate_polygons
        and not duplicate_request_names
        and not duplicate_request_sub_indices
        and not invalid_subset_entries
        and not invalid_request_entries
    )

    return {
        "ok": ok,
        "manifest_kind": manifest.get("fixture_kind", manifest.get("manifest_kind", "")),
        "material_checks": material_checks,
        "polygon_checks": polygon_checks,
        "duplicate_polygons": duplicate_polygons,
        "duplicate_request_material_names": duplicate_request_names,
        "duplicate_request_sub_indices": duplicate_request_sub_indices,
        "subset_entries": subset_entries,
        "invalid_subset_entries": invalid_subset_entries,
        "invalid_request_entries": invalid_request_entries,
    }


def evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots):
    material_ids = cgf_material_summary.get("material_ids", []) if cgf_material_summary else []
    request_slots = {
        _coerce_request_sub_index(material.get("sub_index"))
        for material in _valid_request_materials(request_materials)
        if _coerce_request_sub_index(material.get("sub_index")) is not None
    }
    mtl_slots_by_index = {slot["slot"]: slot for slot in mtl_slots}
    checks = []
    ok = True

    for material_id in material_ids:
        in_request = material_id in request_slots
        in_mtl = material_id in mtl_slots_by_index
        check_ok = in_request and in_mtl
        ok = ok and check_ok
        checks.append(
            {
                "ok": check_ok,
                "material_id": material_id,
                "in_request": in_request,
                "in_mtl": in_mtl,
                "mtl_slot_name": mtl_slots_by_index.get(material_id, {}).get("name", ""),
            }
        )

    return {"ok": ok, "checks": checks, "material_ids": material_ids}


def build_material_mapping_report(
    json_path,
    mtl_path,
    expected_output_path="",
    rc_exe_path="",
    source_fbx_path="",
    copied_fbx_path="",
    rc_returncode=None,
):
    request_materials = load_request_materials(json_path)
    mtl_slots, mtl_read_error = _load_mtl_slots_for_report(mtl_path)
    cryasset_path = f"{mtl_path}.cryasset" if mtl_path else ""
    cryasset_details, cryasset_read_error = _load_cryasset_details_for_report(cryasset_path)
    alignment = evaluate_material_slot_alignment(request_materials, mtl_slots)
    fixture_manifest_path = discover_fixture_manifest(source_fbx_path, copied_fbx_path)
    fixture_manifest = load_fixture_manifest(fixture_manifest_path)

    output_exists = bool(expected_output_path and os.path.exists(expected_output_path))
    output_size = os.path.getsize(expected_output_path) if output_exists else 0
    cgf_material_summary = {}
    cgf_read_error = ""
    if output_exists:
        try:
            cgf_material_summary = read_cgf_material_summary(expected_output_path)
        except Exception as e:
            cgf_read_error = str(e)

    return {
        "paths": {
            "json": json_path,
            "mtl": mtl_path,
            "mtl_cryasset": cryasset_path if os.path.exists(cryasset_path) else "",
            "expected_output": expected_output_path,
            "rc_exe": rc_exe_path,
            "source_fbx": source_fbx_path,
            "copied_fbx": copied_fbx_path,
        },
        "rc": {
            "returncode": rc_returncode,
            "output_exists": output_exists,
            "output_size": output_size,
        },
        "cgf_material_summary": cgf_material_summary,
        "cgf_read_error": cgf_read_error,
        "request_materials": request_materials,
        "mtl_slots": mtl_slots,
        "mtl_read_error": mtl_read_error,
        "mtl_cryasset_details": cryasset_details,
        "mtl_cryasset_read_error": cryasset_read_error,
        "alignment": alignment,
        "cgf_material_id_alignment": evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots),
        "source_fixture_manifest": fixture_manifest_path,
        "fixture_material_semantic_alignment": evaluate_fixture_material_semantics(
            fixture_manifest,
            cgf_material_summary,
            request_materials,
            mtl_slots,
        ),
    }


def write_material_mapping_report(report, report_path):
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return report_path
