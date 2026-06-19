#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create material-slot evidence reports for RC smoke outputs."""

import json
import os
import xml.etree.ElementTree as ET

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from model_processing.evidence_coercion import coerce_center_x, coerce_request_sub_index
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
    return coerce_request_sub_index(value)


def _normalize_request_material_rows(
    raw_materials,
    invalid_collection_error="invalid_request_materials_collection",
    invalid_row_error="invalid_request_material_row",
):
    if not isinstance(raw_materials, list):
        return [
            {
                "order": None,
                "name": "",
                "sub_index": None,
                "physicalize": "",
                "ok": False,
                "errors": [invalid_collection_error],
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
                    "errors": [invalid_row_error],
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


def load_request_materials(json_path):
    payload = _read_json(json_path)
    request = payload.get("request", payload) if isinstance(payload, dict) else {}
    raw_materials = request.get("materials", []) if isinstance(request, dict) else []
    return _normalize_request_material_rows(raw_materials)


def _request_read_error_entry(json_path, error):
    return {
        "order": None,
        "name": "",
        "sub_index": None,
        "physicalize": "",
        "ok": False,
        "errors": ["invalid_request_json"],
        "path": json_path,
        "read_error": error,
    }


def _load_request_materials_for_report(json_path):
    try:
        return load_request_materials(json_path), ""
    except (json.JSONDecodeError, OSError, ValueError) as e:
        read_error = str(e)
        return [_request_read_error_entry(json_path, read_error)], read_error


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


def _coerce_mtl_slot_index(value):
    return coerce_material_slot(value)


def _valid_mtl_slots(mtl_slots):
    slots = []
    if not isinstance(mtl_slots, list):
        return slots
    for slot in mtl_slots:
        if not isinstance(slot, dict):
            continue
        slot_index = _coerce_mtl_slot_index(slot.get("slot"))
        if slot_index is None:
            continue
        normalized = dict(slot)
        normalized["slot"] = slot_index
        slots.append(normalized)
    return slots


def _invalid_mtl_entries(mtl_slots):
    entries = []
    if not isinstance(mtl_slots, list):
        return [
            {
                "ok": False,
                "order": None,
                "error": "invalid_mtl_slots_collection",
                "slot": None,
                "name": "",
                "collection_type": type(mtl_slots).__name__,
            }
        ]
    for order, slot in enumerate(mtl_slots):
        if not isinstance(slot, dict):
            entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_mtl_slot_row",
                    "slot": None,
                    "name": "",
                    "row_type": type(slot).__name__,
                }
            )
            continue
        slot_index = _coerce_mtl_slot_index(slot.get("slot"))
        if slot_index is None:
            entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_mtl_slot_index",
                    "slot": slot.get("slot"),
                    "name": slot.get("name", ""),
                    "slot_type": type(slot.get("slot")).__name__,
                }
            )
    return entries


def evaluate_material_slot_alignment(request_materials, mtl_slots):
    valid_mtl_slots = _valid_mtl_slots(mtl_slots)
    invalid_mtl_entries = _invalid_mtl_entries(mtl_slots)
    slots_by_index = {slot["slot"]: slot for slot in valid_mtl_slots}
    checks = []
    ok = not invalid_mtl_entries
    for entry in invalid_mtl_entries:
        checks.append(
            {
                "ok": False,
                "type": entry["error"],
                "slot": entry.get("slot"),
                "name": entry.get("name", ""),
                "order": entry.get("order"),
                "row_type": entry.get("row_type"),
                "collection_type": entry.get("collection_type"),
                "slot_type": entry.get("slot_type"),
            }
        )

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
                        "path": material.get("path"),
                        "read_error": material.get("read_error"),
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
                    "path": material.get("path"),
                    "read_error": material.get("read_error"),
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
    return coerce_center_x(subset.get("center"))


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
            "invalid_mtl_entries": [],
            "polygon_verification": "",
            "polygon_checks_skipped": False,
            "polygon_count": 0,
        }

    valid_request_materials = _valid_request_materials(request_materials)
    invalid_request_entries = _invalid_request_entries(request_materials)
    valid_mtl_slots = _valid_mtl_slots(mtl_slots)
    invalid_mtl_entries = _invalid_mtl_entries(mtl_slots)
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
    mtl_slots_by_index = {slot["slot"]: slot for slot in valid_mtl_slots}

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

    polygon_verification = manifest.get("polygon_verification", "subset_center_heuristic")
    skip_polygon_checks = polygon_verification == "material_table_only"
    if skip_polygon_checks:
        actual_by_polygon = {}
        subset_entries = []
        duplicate_polygons = []
        invalid_subset_entries = []
    else:
        actual_by_polygon, subset_entries, duplicate_polygons, invalid_subset_entries = _fixture_polygon_actual_ids(
            manifest,
            cgf_material_summary,
        )
    polygon_checks = []
    if skip_polygon_checks:
        pass
    elif raw_polygons is not None and not isinstance(raw_polygons, list):
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

    if not skip_polygon_checks:
        polygon_iter = iter_manifest_polygon_rows(manifest)
    else:
        polygon_iter = ()

    for order, polygon in polygon_iter:
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
        and not invalid_mtl_entries
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
        "invalid_mtl_entries": invalid_mtl_entries,
        "polygon_verification": polygon_verification,
        "polygon_checks_skipped": skip_polygon_checks,
        "polygon_count": len(raw_polygons) if isinstance(raw_polygons, list) else 0,
    }


def _is_unassigned_slot_name(name):
    normalized = coerce_material_name(name).strip().lower()
    return normalized in {"<unassigned>", "unassigned"}


def _unassigned_slot_diagnostic(slot, request_name, mtl_name, material_ids):
    used = slot in material_ids
    max_used_slot = max(material_ids) if material_ids else -1
    request_unassigned = _is_unassigned_slot_name(request_name)
    mtl_unassigned = _is_unassigned_slot_name(mtl_name)
    source = []
    if request_unassigned:
        source.append("request")
    if mtl_unassigned:
        source.append("mtl")
    if used:
        diagnostic_type = "used_unassigned_material"
        ok = False
    elif slot > max_used_slot:
        diagnostic_type = "trailing_unassigned_placeholder"
        ok = True
    else:
        diagnostic_type = "gap_unassigned_placeholder"
        ok = True

    return {
        "ok": ok,
        "type": diagnostic_type,
        "slot": slot,
        "request_name": request_name,
        "mtl_slot_name": mtl_name,
        "source": source,
        "used_by_cgf": used,
        "max_used_material_id": max_used_slot,
    }


def _evaluate_unassigned_slots(material_ids, request_materials, mtl_slots_by_index):
    request_by_index = {}
    for material in _valid_request_materials(request_materials):
        slot = _coerce_request_sub_index(material.get("sub_index"))
        if slot is None or slot < 0:
            continue
        request_by_index[slot] = coerce_material_name(material.get("name", ""))

    candidate_slots = set()
    for slot, name in request_by_index.items():
        if _is_unassigned_slot_name(name):
            candidate_slots.add(slot)
    for slot, mtl_slot in mtl_slots_by_index.items():
        if _is_unassigned_slot_name(mtl_slot.get("name", "")):
            candidate_slots.add(slot)

    diagnostics = []
    for slot in sorted(candidate_slots):
        diagnostics.append(
            _unassigned_slot_diagnostic(
                slot,
                request_by_index.get(slot, ""),
                mtl_slots_by_index.get(slot, {}).get("name", ""),
                material_ids,
            )
        )
    return diagnostics


def evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots):
    material_ids = cgf_material_summary.get("material_ids", []) if cgf_material_summary else []
    request_names_by_index = {}
    for material in _valid_request_materials(request_materials):
        slot = _coerce_request_sub_index(material.get("sub_index"))
        if slot is not None and slot >= 0:
            request_names_by_index[slot] = coerce_material_name(material.get("name", ""))
    request_slots = {
        _coerce_request_sub_index(material.get("sub_index"))
        for material in _valid_request_materials(request_materials)
        if _coerce_request_sub_index(material.get("sub_index")) is not None
    }
    mtl_slots_by_index = {slot["slot"]: slot for slot in _valid_mtl_slots(mtl_slots)}
    unassigned_slot_diagnostics = _evaluate_unassigned_slots(material_ids, request_materials, mtl_slots_by_index)
    unassigned_slot_diagnostics_ok = all(diagnostic["ok"] for diagnostic in unassigned_slot_diagnostics)
    checks = []
    ok = unassigned_slot_diagnostics_ok

    for material_id in material_ids:
        in_request = material_id in request_slots
        in_mtl = material_id in mtl_slots_by_index
        mtl_slot_name = mtl_slots_by_index.get(material_id, {}).get("name", "")
        request_name = request_names_by_index.get(material_id, "")
        used_unassigned = _is_unassigned_slot_name(request_name) or _is_unassigned_slot_name(mtl_slot_name)
        check_ok = in_request and in_mtl
        if used_unassigned:
            check_ok = False
        ok = ok and check_ok
        checks.append(
            {
                "ok": check_ok,
                "material_id": material_id,
                "in_request": in_request,
                "in_mtl": in_mtl,
                "mtl_slot_name": mtl_slot_name,
                "used_unassigned": used_unassigned,
            }
        )

    return {
        "ok": ok,
        "checks": checks,
        "material_ids": material_ids,
        "unassigned_slot_diagnostics": unassigned_slot_diagnostics,
        "unassigned_slot_diagnostics_ok": unassigned_slot_diagnostics_ok,
    }


def _extract_cgf_import_settings_materials(cgf_material_summary):
    import_settings = cgf_material_summary.get("import_settings", []) if isinstance(cgf_material_summary, dict) else []
    if not import_settings:
        return [], "missing_cgf_import_settings", {}
    if not isinstance(import_settings, list):
        return [], "invalid_cgf_import_settings_collection", {"collection_type": type(import_settings).__name__}

    first_entry = None
    for entry in import_settings:
        if isinstance(entry, dict):
            first_entry = entry
            break
    if first_entry is None:
        return [], "invalid_cgf_import_settings_entry", {}

    json_error = first_entry.get("json_error", "")
    if json_error:
        return [], "invalid_cgf_import_settings_json", {"json_error": json_error}

    payload = first_entry.get("json")
    if not isinstance(payload, dict):
        return [], "invalid_cgf_import_settings_json_root", {"root_type": type(payload).__name__}

    request = payload.get("request", payload)
    raw_materials = request.get("materials", []) if isinstance(request, dict) else []
    materials = _normalize_request_material_rows(
        raw_materials,
        invalid_collection_error="invalid_cgf_import_settings_materials_collection",
        invalid_row_error="invalid_cgf_import_settings_material_row",
    )
    return materials, "", {
        "chunk_id": first_entry.get("chunk_id"),
        "version": first_entry.get("version"),
        "material_count": len(raw_materials) if isinstance(raw_materials, list) else None,
    }


def _valid_cgf_mtl_name_sub_materials(cgf_material_summary):
    raw_material_chunks = cgf_material_summary.get("materials", []) if isinstance(cgf_material_summary, dict) else []
    if not isinstance(raw_material_chunks, list):
        return []

    sub_materials = []
    for chunk in raw_material_chunks:
        if not isinstance(chunk, dict):
            continue
        raw_sub_materials = chunk.get("sub_materials", [])
        if not isinstance(raw_sub_materials, list):
            continue
        for sub_material in raw_sub_materials:
            if not isinstance(sub_material, dict):
                continue
            slot = coerce_material_slot(sub_material.get("slot"))
            name = coerce_material_name(sub_material.get("name", ""))
            if slot is None or not name:
                continue
            normalized = dict(sub_material)
            normalized["slot"] = slot
            normalized["name"] = name
            sub_materials.append(normalized)
    return sub_materials


def _request_materials_equal(left, right):
    left_valid = _valid_request_materials(left)
    right_valid = _valid_request_materials(right)
    max_len = max(len(left_valid), len(right_valid))
    checks = []
    ok = len(left_valid) == len(right_valid)
    for index in range(max_len):
        left_material = left_valid[index] if index < len(left_valid) else None
        right_material = right_valid[index] if index < len(right_valid) else None
        if left_material is None or right_material is None:
            ok = False
            checks.append(
                {
                    "ok": False,
                    "type": "material_count_mismatch",
                    "order": index,
                    "request_name": left_material.get("name", "") if left_material else "",
                    "import_settings_name": right_material.get("name", "") if right_material else "",
                }
            )
            continue

        request_name = coerce_material_name(left_material.get("name", ""))
        import_name = coerce_material_name(right_material.get("name", ""))
        request_sub_index = _coerce_request_sub_index(left_material.get("sub_index"))
        import_sub_index = _coerce_request_sub_index(right_material.get("sub_index"))
        request_physicalize = left_material.get("physicalize", "")
        import_physicalize = right_material.get("physicalize", "")
        check_ok = (
            request_name == import_name
            and request_sub_index == import_sub_index
            and request_physicalize == import_physicalize
        )
        ok = ok and check_ok
        checks.append(
            {
                "ok": check_ok,
                "type": "request_import_settings_match" if check_ok else "request_import_settings_mismatch",
                "order": index,
                "request_name": request_name,
                "import_settings_name": import_name,
                "request_sub_index": request_sub_index,
                "import_settings_sub_index": import_sub_index,
                "request_physicalize": request_physicalize,
                "import_settings_physicalize": import_physicalize,
            }
        )
    return {"ok": ok, "checks": checks}


def _classify_extra_import_settings_slot(slot, material, cgf_sub_material_count):
    name = coerce_material_name(material.get("name", ""))
    trailing = slot >= cgf_sub_material_count
    unassigned = _is_unassigned_slot_name(name)
    ok = trailing and unassigned
    return {
        "ok": ok,
        "type": "trailing_unassigned_slot_omitted_from_cgf" if ok else "missing_cgf_mtl_name_slot",
        "sub_index": slot,
        "name": name,
        "physicalize": material.get("physicalize", ""),
        "trailing": trailing,
        "unassigned": unassigned,
        "cgf_mtl_name_sub_material_count": cgf_sub_material_count,
    }


def _evaluate_import_settings_vs_cgf_mtl_name(import_settings_materials, cgf_material_summary):
    cgf_sub_materials = _valid_cgf_mtl_name_sub_materials(cgf_material_summary)
    import_by_index = {
        _coerce_request_sub_index(material.get("sub_index")): material
        for material in _valid_request_materials(import_settings_materials)
        if _coerce_request_sub_index(material.get("sub_index")) is not None
        and _coerce_request_sub_index(material.get("sub_index")) >= 0
    }
    cgf_by_index = {entry["slot"]: entry for entry in cgf_sub_materials}
    checks = []
    ok = True

    for slot in sorted(cgf_by_index):
        cgf_entry = cgf_by_index[slot]
        import_entry = import_by_index.get(slot)
        import_name = coerce_material_name(import_entry.get("name", "")) if import_entry else ""
        cgf_name = cgf_entry.get("name", "")
        check_ok = import_entry is not None and import_name == cgf_name
        ok = ok and check_ok
        checks.append(
            {
                "ok": check_ok,
                "type": "cgf_mtl_name_match" if check_ok else "cgf_mtl_name_mismatch",
                "sub_index": slot,
                "import_settings_name": import_name,
                "cgf_mtl_name": cgf_name,
            }
        )

    extra_import_settings_slots = []
    for slot in sorted(import_by_index):
        if slot in cgf_by_index:
            continue
        material = import_by_index[slot]
        extra_import_settings_slots.append(
            _classify_extra_import_settings_slot(slot, material, len(cgf_sub_materials))
        )

    ok = ok and all(slot["ok"] for slot in extra_import_settings_slots)

    return {
        "ok": ok,
        "checks": checks,
        "extra_import_settings_slots": extra_import_settings_slots,
        "extra_import_settings_slots_ok": all(slot["ok"] for slot in extra_import_settings_slots),
        "cgf_mtl_name_sub_material_count": len(cgf_sub_materials),
    }


def evaluate_cgf_import_settings_roundtrip(cgf_material_summary, request_materials, mtl_slots):
    import_settings_materials, import_settings_error, import_settings_meta = _extract_cgf_import_settings_materials(
        cgf_material_summary,
    )
    invalid_request_entries = _invalid_request_entries(request_materials)
    invalid_import_settings_entries = _invalid_request_entries(import_settings_materials)
    request_vs_import_settings = _request_materials_equal(request_materials, import_settings_materials)
    import_settings_vs_mtl = evaluate_material_slot_alignment(import_settings_materials, mtl_slots)
    import_settings_vs_cgf_mtl_name = _evaluate_import_settings_vs_cgf_mtl_name(
        import_settings_materials,
        cgf_material_summary,
    )
    import_settings_material_id_alignment = evaluate_cgf_material_ids(
        cgf_material_summary,
        import_settings_materials,
        mtl_slots,
    )
    ok = (
        not import_settings_error
        and not invalid_request_entries
        and not invalid_import_settings_entries
        and request_vs_import_settings["ok"]
        and import_settings_vs_mtl["ok"]
        and import_settings_vs_cgf_mtl_name["ok"]
        and import_settings_material_id_alignment["ok"]
    )

    return {
        "ok": ok,
        "import_settings_present": not import_settings_error,
        "import_settings_error": import_settings_error,
        "import_settings_meta": import_settings_meta,
        "import_settings_materials": import_settings_materials,
        "invalid_request_entries": invalid_request_entries,
        "invalid_import_settings_entries": invalid_import_settings_entries,
        "request_vs_import_settings": request_vs_import_settings,
        "import_settings_vs_mtl": import_settings_vs_mtl,
        "import_settings_vs_cgf_mtl_name": import_settings_vs_cgf_mtl_name,
        "import_settings_material_id_alignment": import_settings_material_id_alignment,
    }


def build_material_mapping_report(
    json_path,
    mtl_path,
    expected_output_path="",
    rc_exe_path="",
    source_fbx_path="",
    copied_fbx_path="",
    rc_returncode=None,
):
    request_materials, request_read_error = _load_request_materials_for_report(json_path)
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
        "request_read_error": request_read_error,
        "request_materials": request_materials,
        "mtl_slots": mtl_slots,
        "mtl_read_error": mtl_read_error,
        "mtl_cryasset_details": cryasset_details,
        "mtl_cryasset_read_error": cryasset_read_error,
        "alignment": alignment,
        "cgf_material_id_alignment": evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots),
        "cgf_import_settings_alignment": evaluate_cgf_import_settings_roundtrip(
            cgf_material_summary,
            request_materials,
            mtl_slots,
        ),
        "source_fixture_manifest": fixture_manifest_path,
        "fixture_material_semantic_alignment": evaluate_fixture_material_semantics(
            fixture_manifest,
            cgf_material_summary,
            request_materials,
            mtl_slots,
        ),
    }


def build_existing_output_material_report(
    cgf_path,
    mtl_path,
    json_path="",
    source_fbx_path="",
):
    cgf_path = cgf_path or ""
    mtl_path = mtl_path or ""
    json_path = json_path or ""

    output_exists = bool(cgf_path and os.path.exists(cgf_path))
    output_size = os.path.getsize(cgf_path) if output_exists else 0
    cgf_material_summary = {}
    cgf_read_error = ""
    if output_exists:
        try:
            cgf_material_summary = read_cgf_material_summary(cgf_path)
        except Exception as e:
            cgf_read_error = str(e)

    if json_path:
        request_materials, request_read_error = _load_request_materials_for_report(json_path)
        request_source = {
            "type": "request_json",
            "path": json_path,
            "error": request_read_error,
        }
    else:
        request_materials, import_settings_error, import_settings_meta = _extract_cgf_import_settings_materials(
            cgf_material_summary,
        )
        request_read_error = import_settings_error
        request_source = {
            "type": "cgf_import_settings",
            "path": cgf_path,
            "error": import_settings_error,
            "import_settings_meta": import_settings_meta,
        }

    mtl_slots, mtl_read_error = _load_mtl_slots_for_report(mtl_path)
    cryasset_path = f"{mtl_path}.cryasset" if mtl_path else ""
    cryasset_details, cryasset_read_error = _load_cryasset_details_for_report(cryasset_path)
    alignment = evaluate_material_slot_alignment(request_materials, mtl_slots)
    fixture_manifest_path = discover_fixture_manifest(source_fbx_path, "")
    fixture_manifest = load_fixture_manifest(fixture_manifest_path)

    return {
        "paths": {
            "json": json_path,
            "mtl": mtl_path,
            "mtl_cryasset": cryasset_path if os.path.exists(cryasset_path) else "",
            "expected_output": cgf_path,
            "rc_exe": "",
            "source_fbx": source_fbx_path,
            "copied_fbx": "",
        },
        "request_source": request_source,
        "rc": {
            "returncode": None,
            "output_exists": output_exists,
            "output_size": output_size,
        },
        "cgf_material_summary": cgf_material_summary,
        "cgf_read_error": cgf_read_error,
        "request_read_error": request_read_error,
        "request_materials": request_materials,
        "mtl_slots": mtl_slots,
        "mtl_read_error": mtl_read_error,
        "mtl_cryasset_details": cryasset_details,
        "mtl_cryasset_read_error": cryasset_read_error,
        "alignment": alignment,
        "cgf_material_id_alignment": evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots),
        "cgf_import_settings_alignment": evaluate_cgf_import_settings_roundtrip(
            cgf_material_summary,
            request_materials,
            mtl_slots,
        ),
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
