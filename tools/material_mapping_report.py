#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create material-slot evidence reports for RC smoke outputs."""

import json
import os
import xml.etree.ElementTree as ET

from utils.cgf_material_reader import read_cgf_material_summary


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_request_materials(json_path):
    payload = _read_json(json_path)
    request = payload.get("request", payload)
    materials = []
    for order, material in enumerate(request.get("materials", [])):
        materials.append(
            {
                "order": order,
                "name": material.get("name", ""),
                "sub_index": material.get("sub_index"),
                "physicalize": material.get("physicalize", ""),
            }
        )
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


def discover_fixture_manifest(source_fbx_path="", copied_fbx_path=""):
    for fbx_path in (source_fbx_path, copied_fbx_path):
        if not fbx_path:
            continue
        candidate = os.path.splitext(fbx_path)[0] + ".fixture_manifest.json"
        if os.path.exists(candidate):
            return candidate
    return ""


def load_fixture_manifest(manifest_path):
    if not manifest_path or not os.path.exists(manifest_path):
        return {}
    return _read_json(manifest_path)


def evaluate_material_slot_alignment(request_materials, mtl_slots):
    slots_by_index = {slot["slot"]: slot for slot in mtl_slots}
    checks = []
    ok = True

    for material in request_materials:
        sub_index = material.get("sub_index")
        if sub_index is None or sub_index < 0:
            checks.append(
                {
                    "ok": True,
                    "type": "deleted_or_unassigned",
                    "name": material.get("name", ""),
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
                    "name": material.get("name", ""),
                    "sub_index": sub_index,
                }
            )
            continue

        names_match = material.get("name", "") == slot.get("name", "")
        ok = ok and names_match
        checks.append(
            {
                "ok": names_match,
                "type": "slot_name_match" if names_match else "slot_name_mismatch",
                "name": material.get("name", ""),
                "sub_index": sub_index,
                "mtl_slot_name": slot.get("name", ""),
            }
        )

    return {"ok": ok, "checks": checks}


def _request_names_by_sub_index(request_materials):
    names_by_index = {}
    for material in request_materials:
        sub_index = material.get("sub_index")
        if sub_index is None or sub_index < 0:
            continue
        names_by_index.setdefault(sub_index, []).append(material.get("name", ""))
    return names_by_index


def _duplicate_values(values):
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(value for value, count in counts.items() if count > 1)


def _fixture_polygon_actual_ids(manifest, cgf_material_summary):
    center_lookup = {}
    for polygon in manifest.get("polygons", []):
        if "center_x" in polygon:
            center_lookup[round(float(polygon["center_x"]), 4)] = int(polygon["polygon"])

    actual_by_polygon = {}
    subset_entries = []
    duplicate_polygons = []
    for mesh in cgf_material_summary.get("meshes", []) if cgf_material_summary else []:
        for subset in mesh.get("subsets", []):
            center = subset.get("center") or []
            if not center:
                continue
            center_x = round(float(center[0]), 4)
            polygon = center_lookup.get(center_x)
            if polygon is None:
                polygon = int(round(float(center[0]) / 3.0))
            if polygon in actual_by_polygon:
                duplicate_polygons.append(polygon)
            actual_by_polygon[polygon] = int(subset.get("material_id"))
            subset_entries.append(
                {
                    "mesh_chunk_id": mesh.get("chunk_id"),
                    "subset": subset.get("subset"),
                    "polygon": polygon,
                    "center": subset.get("center"),
                    "material_id": int(subset.get("material_id")),
                }
            )

    return actual_by_polygon, subset_entries, duplicate_polygons


def evaluate_fixture_material_semantics(manifest, cgf_material_summary, request_materials, mtl_slots):
    if not manifest:
        return {}

    request_names_by_index = _request_names_by_sub_index(request_materials)
    request_sub_indices = [
        material.get("sub_index")
        for material in request_materials
        if material.get("sub_index") is not None and material.get("sub_index") >= 0
    ]
    request_names = [material.get("name", "") for material in request_materials]
    mtl_slots_by_index = {slot["slot"]: slot for slot in mtl_slots}

    material_checks = []
    ok = True
    for material in manifest.get("materials", []):
        slot = int(material.get("slot"))
        expected_name = material.get("name", "")
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

    actual_by_polygon, subset_entries, duplicate_polygons = _fixture_polygon_actual_ids(manifest, cgf_material_summary)
    polygon_checks = []
    for polygon in manifest.get("polygons", []):
        polygon_index = int(polygon["polygon"])
        expected_cgf_id = int(polygon.get("expected_cgf_material_id", polygon.get("material_slot", 0)))
        expected_name = polygon.get("material_name", "")
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
    ok = ok and not duplicate_polygons and not duplicate_request_names and not duplicate_request_sub_indices

    return {
        "ok": ok,
        "fixture_kind": manifest.get("fixture_kind", ""),
        "material_checks": material_checks,
        "polygon_checks": polygon_checks,
        "duplicate_polygons": duplicate_polygons,
        "duplicate_request_material_names": duplicate_request_names,
        "duplicate_request_sub_indices": duplicate_request_sub_indices,
        "subset_entries": subset_entries,
    }


def evaluate_cgf_material_ids(cgf_material_summary, request_materials, mtl_slots):
    material_ids = cgf_material_summary.get("material_ids", []) if cgf_material_summary else []
    request_slots = {material.get("sub_index") for material in request_materials if material.get("sub_index") is not None}
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
    mtl_slots = load_mtl_slots(mtl_path)
    cryasset_path = f"{mtl_path}.cryasset" if mtl_path else ""
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
        "mtl_cryasset_details": load_cryasset_details(cryasset_path),
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
