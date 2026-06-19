#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CryEngine-style material sub-index assignment helpers."""

import os
import xml.etree.ElementTree as ET

from model_processing.rc_material_policy import RC_MAX_SUB_MATERIALS, normalize_rc_sub_index
from model_processing.material_texture_resolver import clean_material_name, iter_model_materials


def parse_mtl_submaterial_names(mtl_file_path):
    """Return sub-material names from an existing CryEngine .mtl in child order."""
    if not mtl_file_path:
        return []
    if not os.path.exists(mtl_file_path):
        return []

    try:
        root = ET.parse(mtl_file_path).getroot()
    except (OSError, ET.ParseError) as e:
        print(f"Warning: Could not parse existing MTL '{mtl_file_path}': {e}")
        return []

    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return []

    names = []
    for material in list(sub_materials):
        if material.tag == "Material":
            names.append(material.get("Name", ""))
    return names


def _coerce_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_fbx_material_id(material, fallback_order=None):
    """
    Return a 1-based FBX material id when known.

    CryEngine's editor exposes material ids as 1-based values. The generated
    CGF stores polygon material ids as zero-based `MeshSubset.nMatID` values.
    """
    for key in ("id", "material_id", "fbx_material_id", "fbx_id"):
        value = _coerce_int(material.get(key))
        if value is not None and value >= 1:
            return value

    index = _coerce_int(material.get("index"))
    if index is not None and index >= 0:
        return index + 1

    if fallback_order is not None:
        return fallback_order + 1

    return None


def is_deleted_material(material):
    if material.get("deleted", False):
        return True
    sub_index = _coerce_int(material.get("sub_index"))
    return sub_index is not None and sub_index < 0


def is_dummy_material(record):
    name = record["clean_name"]
    material = record["material"]
    return bool(material.get("is_dummy", False) or material.get("dummy", False) or not name)


def _first_free_index(occupied):
    index = 0
    while index in occupied:
        index += 1
    return index


def _assign_sub_index(record, sub_index, reason):
    normalized = normalize_rc_sub_index(sub_index)
    record["sub_index"] = normalized
    if normalized != int(sub_index):
        record["reason"] = f"{reason}_out_of_range"
        record["requested_sub_index"] = int(sub_index)
        return
    record["reason"] = reason


def _known_polygon_usage(material):
    for key in ("polygon_count", "face_count", "used_polygon_count"):
        value = _coerce_int(material.get(key))
        if value is not None:
            return value > 0

    for key in ("used_by_polygons", "is_used", "used"):
        value = material.get(key)
        if value is not None:
            return bool(value)

    return None


def _fbx_slot(record):
    fbx_id = record.get("fbx_material_id")
    if fbx_id is None or fbx_id < 1:
        return None
    return fbx_id - 1


def diagnose_material_record(record):
    diagnostics = []
    fbx_slot = _fbx_slot(record)
    polygon_usage = _known_polygon_usage(record["material"])
    material_names = record["material"].get("material_names", [])
    requested_sub_index = record.get("requested_sub_index")

    if requested_sub_index is not None:
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "rc_sub_index_out_of_range_deleted",
                "material": record["clean_name"],
                "fbx_slot": fbx_slot,
                "sub_index": record["sub_index"],
                "requested_sub_index": requested_sub_index,
                "max_sub_materials": RC_MAX_SUB_MATERIALS,
                "assignment_reason": record["reason"],
                "message": (
                    "RC normalizes material sub_index values greater than or equal to "
                    "MAX_SUB_MATERIALS to -1. This makes the material behave like a delete entry, "
                    "so geometry using that source material can disappear instead of mapping to a high slot."
                ),
            }
        )

    if record["material"].get("slot_name_conflict", False):
        diagnostics.append(
            {
                "severity": "warning",
                "code": "material_slot_name_conflict",
                "material": record["clean_name"],
                "fbx_slot": fbx_slot,
                "sub_index": record["sub_index"],
                "material_names": material_names,
                "mesh_names": record["material"].get("mesh_names", []),
                "message": (
                    "Multiple material names were found for the same FBX material slot across meshes. "
                    "Local mesh slot ids and global FBX material identities can diverge; keep request/MTL slot order "
                    "aligned to the exported FBX material table."
                ),
            }
        )

    if record["deleted"] and fbx_slot is not None and polygon_usage is not False:
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "deleted_known_fbx_slot_usage_unknown",
                "material": record["clean_name"],
                "fbx_slot": fbx_slot,
                "sub_index": record["sub_index"],
                "message": (
                    "Deleted material has a known FBX slot. RC does not remove geometry material ids "
                    "for slots still used by the FBX; preserve a placeholder unless polygon usage proves it is unused."
                ),
            }
        )

    if (
        not record["deleted"]
        and fbx_slot is not None
        and record["sub_index"] is not None
        and record["sub_index"] >= 0
        and record["sub_index"] != fbx_slot
        and polygon_usage is not False
    ):
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "sub_index_differs_from_fbx_slot_usage_unknown",
                "material": record["clean_name"],
                "fbx_slot": fbx_slot,
                "sub_index": record["sub_index"],
                "assignment_reason": record["reason"],
                "message": (
                    "Assigned sub_index differs from the known FBX slot. RC keeps geometry material ids "
                    "aligned to FBX slots, so this can point polygons at the wrong material unless the slot is unused."
                ),
            }
        )

    return diagnostics


def attach_material_diagnostics(records):
    for record in records:
        record["diagnostics"] = diagnose_material_record(record)
    return records


def _normalized_records(materials):
    records = []
    seen_names = set()

    for order, (material_name, material) in enumerate(iter_model_materials(materials)):
        clean_name = clean_material_name(material_name)
        if clean_name in seen_names:
            print(f"Skipping exact duplicate material name: {material_name}")
            continue

        seen_names.add(clean_name)
        records.append(
            {
                "original_name": material_name,
                "clean_name": clean_name,
                "material": material,
                "source_order": order,
                "fbx_material_id": get_fbx_material_id(material, order),
                "deleted": is_deleted_material(material),
                "sub_index": None,
                "requested_sub_index": None,
                "reason": "",
                "diagnostics": [],
            }
        )

    return records


def assign_material_sub_indices(materials, existing_submaterial_names=None):
    """
    Assign CryEngine sub-material indices.

    This follows the editor behavior documented from MeshImporter:

    1. Deleted materials receive `sub_index = -1`.
    2. Explicit non-auto `sub_index` values reserve their slots.
    3. Auto materials preserve FBX material id as `id - 1` when free.
    4. Auto materials reuse matching existing .mtl submaterial names as fallback.
    5. Remaining materials are sorted dummy-first, then by name, and fill gaps.
    """
    records = _normalized_records(materials)
    existing_lookup = {
        clean_material_name(name): index
        for index, name in enumerate(existing_submaterial_names or [])
        if name is not None
    }
    occupied = set()

    for record in records:
        material = record["material"]
        explicit_index = _coerce_int(material.get("sub_index"))
        auto_assigned = bool(material.get("auto_assigned", material.get("ui_autoflag", True)))

        if record["deleted"]:
            record["sub_index"] = -1
            record["reason"] = "deleted"
            continue

        if explicit_index is not None and explicit_index >= 0 and not auto_assigned:
            _assign_sub_index(record, explicit_index, "explicit")
            if record["sub_index"] >= 0:
                occupied.add(record["sub_index"])

    for record in records:
        if record["sub_index"] is not None:
            continue

        fbx_id = record["fbx_material_id"]
        preferred_index = fbx_id - 1 if fbx_id is not None and fbx_id >= 1 else None
        if preferred_index is not None and preferred_index not in occupied:
            _assign_sub_index(record, preferred_index, "fbx_material_id")
            if record["sub_index"] >= 0:
                occupied.add(record["sub_index"])

    for record in records:
        if record["sub_index"] is not None:
            continue

        existing_index = existing_lookup.get(record["clean_name"])
        if existing_index is not None and existing_index not in occupied:
            _assign_sub_index(record, existing_index, "existing_mtl_name")
            if record["sub_index"] >= 0:
                occupied.add(record["sub_index"])

    remaining = [record for record in records if record["sub_index"] is None]
    remaining.sort(key=lambda record: (not is_dummy_material(record), record["clean_name"].lower()))

    for record in remaining:
        index = _first_free_index(occupied)
        _assign_sub_index(record, index, "first_free")
        if record["sub_index"] >= 0:
            occupied.add(record["sub_index"])

    attach_material_diagnostics(records)
    return records


def material_records_by_name(records):
    return {record["clean_name"]: record for record in records}
