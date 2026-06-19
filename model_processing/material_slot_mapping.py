#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compact material slot mapping contract for diagnostics and UI surfaces."""

from collections import Counter

from model_processing.evidence_coercion import coerce_request_sub_index
from model_processing.rc_material_policy import RC_MAX_SUB_MATERIALS


SLOT_MAPPING_RULES = [
    {
        "id": "request_sub_index_is_final_slot",
        "summary": "materials[].sub_index is the final CryEngine sub-material id written by RC.",
        "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
    },
    {
        "id": "mtl_child_order_matches_final_slots",
        "summary": "MTL SubMaterials child order follows the final sub_index table; gaps are placeholders.",
        "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
    },
    {
        "id": "cgf_subset_material_id_indexes_final_slots",
        "summary": "CGF MeshSubset material_id indexes the final CGF material table, not subset order.",
        "evidence": "docs/refactor_phase9_controlled_blender_material_fixture.md",
    },
    {
        "id": "raw_fbx_id_is_one_based",
        "summary": "Known FBX material ids are one-based; raw FBX slot is fbx_material_id - 1.",
        "evidence": "model_processing/material_index_assigner.py",
    },
    {
        "id": "sub_index_limit",
        "summary": f"sub_index values 0..{RC_MAX_SUB_MATERIALS - 1} are supported; higher values normalize to -1.",
        "evidence": "docs/refactor_phase55_rc_sub_index_limit_policy.md",
    },
]


MATERIAL_SLOT_ASSIGNMENT_POLICY = {
    "schema": "cryengine_material_slot_assignment.v1",
    "rc_request_material_fields": {
        "name": {
            "required": True,
            "type": "string",
            "meaning": "Source FBX scene material name. RC matches this name to the imported FBX material table.",
            "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
        },
        "physicalize": {
            "required": True,
            "type": "enum",
            "values": ["no", "default", "obstruct", "no_collide", "proxy_only"],
            "meaning": "CryEngine physicalization policy stored with the final material slot.",
            "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
        },
        "sub_index": {
            "required": True,
            "type": "integer",
            "valid_values": {"min": -1, "max": RC_MAX_SUB_MATERIALS - 1},
            "meaning": "Final CryEngine sub-material id. Non-negative values become MTL slots and CGF material ids.",
            "evidence": "docs/refactor_phase55_rc_sub_index_limit_policy.md",
        },
    },
    "slot_identity": {
        "raw_fbx_slot": "fbx_material_id - 1 when a one-based FBX material id is known.",
        "final_sub_index": "request.materials[].sub_index for non-deleted materials.",
        "mtl_slot": "SubMaterials child order after expanding the final_sub_index table and filling gaps.",
        "cgf_material_id": "MeshSubset material_id after RC remaps FBX material names through final_sub_index.",
    },
    "assignment_priority": [
        {
            "id": "explicit_sub_index",
            "condition": "material has sub_index >= 0 and auto_assigned/ui_autoflag is false",
            "result": "reserve that exact final slot unless it is outside the RC range",
        },
        {
            "id": "fbx_material_id",
            "condition": "material has a known FBX id and its zero-based slot is free",
            "result": "use fbx_material_id - 1 as final_sub_index",
        },
        {
            "id": "existing_mtl_name",
            "condition": "material name exists in an existing MTL and that child-order slot is free",
            "result": "reuse the existing MTL slot",
        },
        {
            "id": "first_free",
            "condition": "no explicit, FBX, or existing-MTL slot was available",
            "result": "fill the first free final slot after sorting dummy materials first, then by name",
        },
    ],
    "placeholder_policy": {
        "slot_gaps": {
            "name": "unassigned",
            "assignment_reason": "slot_gap",
            "meaning": "Generated MTL placeholder for missing intermediate final slots.",
        },
        "trailing_unassigned": {
            "name": "<unassigned>",
            "assignment_reason": "trailing_unassigned_placeholder",
            "meaning": (
                "Optional trailing request/MTL placeholder expected in CE-authored assets. "
                "It may be absent from the CGF MtlName table when no mesh subset uses it."
            ),
        },
    },
    "hazards": [
        {
            "code": "rc_duplicate_sub_index_overwrites_material",
            "meaning": "Multiple request materials target the same final slot; the later RC material can overwrite slot state.",
        },
        {
            "code": "rc_sub_index_out_of_range_deleted",
            "meaning": f"sub_index >= {RC_MAX_SUB_MATERIALS} normalizes to -1, so matching source faces can be deleted.",
        },
        {
            "code": "rc_case_insensitive_material_name_collision",
            "meaning": "RC name matching is case-insensitive, so names that differ only by case cannot be targeted safely.",
        },
        {
            "code": "deleted_known_fbx_slot_usage_unknown",
            "meaning": "Deleting a known FBX slot is unsafe unless polygon usage proves it is unused.",
        },
        {
            "code": "rc_omitted_source_material_faces_deleted",
            "meaning": "When request materials are present, source materials omitted from the request can lose their faces.",
        },
    ],
    "minimal_request_example": {
        "request": {
            "source_filename": "asset.fbx",
            "output_ext": "cgf",
            "material_filename": "asset",
            "materials": [
                {"name": "Body", "physicalize": "no", "sub_index": 0},
                {"name": "Glass", "physicalize": "no", "sub_index": 1},
                {"name": "<unassigned>", "physicalize": "no", "sub_index": 2},
            ],
        }
    },
}


def exported_material_slot_mapping_schema():
    return {
        "schema": "cryengine_material_slot_mapping.v1",
        "rules": SLOT_MAPPING_RULES,
        "assignment_policy": MATERIAL_SLOT_ASSIGNMENT_POLICY,
    }


def _counter_to_sorted_dict(counter):
    return {key: counter[key] for key in sorted(counter)}


def _coerce_final_slot(value):
    slot = coerce_request_sub_index(value)
    if slot is None or slot < 0:
        return None
    return slot


def _mapping_status(item, final_slot):
    if final_slot is not None and not item.get("deleted", False):
        return "emitted_final_slot"
    if item.get("requested_sub_index") is not None:
        return "out_of_range_deleted"
    if item.get("deleted", False):
        return "deleted"
    return "not_emitted"


def build_material_slot_mapping_contract(material_items):
    mappings = []
    final_slots = []
    reason_counts = Counter()
    status_counts = Counter()
    duplicate_final_slot_count = 0

    for item in material_items or []:
        final_slot = _coerce_final_slot(item.get("sub_index"))
        status = _mapping_status(item, final_slot)
        assignment_reason = item.get("assignment_reason", "")
        reason_counts.update([assignment_reason or "unknown"])
        status_counts.update([status])
        if final_slot is not None:
            final_slots.append(final_slot)
        if item.get("duplicate_sub_index_conflict", False):
            duplicate_final_slot_count += 1

        mappings.append(
            {
                "name": item.get("name", ""),
                "original_name": item.get("original_name", ""),
                "source_order": item.get("source_order"),
                "fbx_material_id": item.get("fbx_material_id"),
                "raw_fbx_slot": item.get("fbx_slot"),
                "final_sub_index": final_slot,
                "mtl_slot": final_slot,
                "cgf_material_id": final_slot,
                "requested_sub_index": item.get("requested_sub_index"),
                "assignment_reason": assignment_reason,
                "status": status,
                "deleted": item.get("deleted", False),
                "duplicate_final_slot": item.get("duplicate_sub_index_conflict", False),
                "duplicate_final_slot_material_names": item.get("duplicate_sub_index_material_names", []),
            }
        )

    unique_final_slots = sorted(set(final_slots))
    final_slot_count = max(unique_final_slots) + 1 if unique_final_slots else 0
    gap_slots = [slot for slot in range(final_slot_count) if slot not in unique_final_slots]

    return {
        "schema": "cryengine_material_slot_mapping.v1",
        "rules": SLOT_MAPPING_RULES,
        "summary": {
            "material_count": len(mappings),
            "emitted_material_count": status_counts.get("emitted_final_slot", 0),
            "deleted_material_count": status_counts.get("deleted", 0),
            "out_of_range_deleted_count": status_counts.get("out_of_range_deleted", 0),
            "duplicate_final_slot_count": duplicate_final_slot_count,
            "final_slot_count": final_slot_count,
            "gap_slot_count": len(gap_slots),
            "gap_slots": gap_slots,
            "assignment_reason_counts": _counter_to_sorted_dict(reason_counts),
            "status_counts": _counter_to_sorted_dict(status_counts),
        },
        "mappings": mappings,
    }
