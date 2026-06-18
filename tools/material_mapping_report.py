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
    }


def write_material_mapping_report(report, report_path):
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return report_path
