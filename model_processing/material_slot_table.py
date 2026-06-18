#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared RC-visible material slot table helpers."""

from model_processing.material_index_assigner import assign_material_sub_indices
from model_processing.material_manifest import material_manifest_materials


def build_material_slot_records(
    materials,
    existing_submaterial_names=None,
    material_manifest_info=None,
):
    """Return assigned material records after manifest resolution."""
    resolved_materials = material_manifest_materials(materials, material_manifest_info)
    return assign_material_sub_indices(resolved_materials, existing_submaterial_names or [])


def _default_slot():
    return {"name": "Default", "textures": {}, "is_default": True, "sub_index": 0}


def _placeholder_slot(slot_index):
    return {
        "name": "unassigned",
        "original_name": "unassigned",
        "sub_index": slot_index,
        "textures": {},
        "is_dummy": True,
        "assignment_reason": "slot_gap",
    }


def material_slot_from_record(record):
    """Return the exporter-facing material dict for one assigned record."""
    material = record["material"].copy()
    material["name"] = record["clean_name"]
    material["original_name"] = record["original_name"]
    material["sub_index"] = record["sub_index"]
    material["assignment_reason"] = record["reason"]
    material["source_order"] = record["source_order"]
    material["fbx_material_id"] = record.get("fbx_material_id")
    material["deleted"] = record["deleted"]
    material["diagnostics"] = record.get("diagnostics", [])
    return material


def build_expanded_material_slot_table(
    materials,
    existing_submaterial_names=None,
    material_manifest_info=None,
    include_default=True,
    fill_gaps=True,
):
    """
    Build a zero-based RC material slot table for MTL/export consumers.

    Deleted records keep their request-side `sub_index = -1` in the assigned
    records, but they are not emitted into the expanded MTL slot table.
    """
    if not materials and include_default:
        return [_default_slot()]

    records = build_material_slot_records(
        materials,
        existing_submaterial_names=existing_submaterial_names,
        material_manifest_info=material_manifest_info,
    )
    used_records = [record for record in records if record["sub_index"] >= 0]
    if not used_records:
        return []

    slot_count = max(record["sub_index"] for record in used_records) + 1
    material_slots = [None] * slot_count
    for record in used_records:
        material_slots[record["sub_index"]] = material_slot_from_record(record)

    if fill_gaps:
        for slot_index, slot in enumerate(material_slots):
            if slot is None:
                material_slots[slot_index] = _placeholder_slot(slot_index)
    else:
        material_slots = [slot for slot in material_slots if slot is not None]

    return material_slots
