#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write sidecar material-slot diagnostic reports."""

import json
import os
from collections import Counter

from model_processing.material_index_assigner import build_omitted_material_diagnostics
from model_processing.material_manifest import material_manifest_table_diagnostics
from model_processing.material_slot_table import build_material_slot_records
from model_processing.rc_material_policy import rc_physicalize_diagnostics, resolve_rc_physicalize
from output_formats.cryengine_mtl_schema import (
    exported_material_shader_policy,
    exported_mtl_flags_policy,
    exported_texture_map_policy,
)


AUTHORITATIVE_TEXTURE_SOURCE_MODES = {"", "blender"}


def _texture_source_modes(texture_ref_evidence):
    return sorted(
        {
            item.get("source_mode", "")
            for item in texture_ref_evidence or []
            if item.get("source_mode", "") not in AUTHORITATIVE_TEXTURE_SOURCE_MODES
        }
    )


def _texture_evidence_diagnostics(report_item):
    degraded_modes = _texture_source_modes(report_item.get("texture_ref_evidence", []))
    if not degraded_modes:
        return []

    return [
        {
            "severity": "warning",
            "code": "degraded_texture_reference_source",
            "material": report_item["name"],
            "fbx_slot": report_item["fbx_slot"],
            "sub_index": report_item["sub_index"],
            "source_modes": degraded_modes,
            "texture_ref_evidence": report_item.get("texture_ref_evidence", []),
            "message": (
                "Texture references for this material include degraded filesystem-scan evidence. "
                "Treat them as recovery data, not authoritative FBX/Blender material bindings."
            ),
        }
    ]


def _record_to_report_item(record):
    fbx_id = record.get("fbx_material_id")
    fbx_slot = fbx_id - 1 if fbx_id is not None and fbx_id >= 1 else None
    physicalize_resolution = resolve_rc_physicalize(record["material"], fallback_name=record["original_name"])
    mtl_shader_policy = exported_material_shader_policy(record["material"].get("textures", {}))
    mtl_flags_policy = exported_mtl_flags_policy()["sub_material"]
    mtl_texture_map_policy = exported_texture_map_policy(record["material"].get("textures", {}))
    return {
        "name": record["clean_name"],
        "original_name": record["original_name"],
        "source_order": record["source_order"],
        "fbx_material_id": fbx_id,
        "fbx_slot": fbx_slot,
        "sub_index": record["sub_index"],
        "requested_sub_index": record.get("requested_sub_index"),
        "assignment_reason": record["reason"],
        "physicalize": physicalize_resolution["value"],
        "physicalize_source": physicalize_resolution["source"],
        "requested_physicalize": physicalize_resolution.get("raw_value", ""),
        "deleted": record["deleted"],
        "polygon_count": record["material"].get("polygon_count"),
        "used_by_polygons": record["material"].get("used_by_polygons"),
        "mesh_names": record["material"].get("mesh_names", []),
        "material_names": record["material"].get("material_names", []),
        "slot_name_conflict": record["material"].get("slot_name_conflict", False),
        "case_insensitive_name_conflict": record.get("case_insensitive_name_conflict", False),
        "case_insensitive_material_names": record.get("case_insensitive_material_names", []),
        "duplicate_sub_index_conflict": record.get("duplicate_sub_index_conflict", False),
        "duplicate_sub_index_material_names": record.get("duplicate_sub_index_material_names", []),
        "texture_ref_evidence": record["material"].get("texture_ref_evidence", []),
        "mtl_flags_policy": mtl_flags_policy,
        "mtl_texture_map_policy": mtl_texture_map_policy,
        "mtl_shader_policy": mtl_shader_policy,
        "diagnostics": [
            *record.get("diagnostics", []),
            *rc_physicalize_diagnostics(record["clean_name"], physicalize_resolution),
        ],
    }


def _counter_to_sorted_dict(counter):
    return {key: counter[key] for key in sorted(counter)}


def _mtl_shader_policy_summary(material_items):
    token_counts = Counter()
    gen_mask_policy_counts = Counter()
    string_gen_mask_source_counts = Counter()
    public_params_policy_counts = Counter()
    public_param_counts = Counter()

    for item in material_items:
        policy = item.get("mtl_shader_policy", {})
        token_counts.update(policy.get("tokens", []))
        gen_mask_policy_counts.update([policy.get("gen_mask_policy", "")])
        string_gen_mask_source_counts.update([policy.get("string_gen_mask_source", "")])
        public_params_policy_counts.update([policy.get("public_params_policy", "")])
        public_param_counts.update(policy.get("public_params", {}).keys())

    return {
        "material_count": len(material_items),
        "token_counts": _counter_to_sorted_dict(token_counts),
        "gen_mask_policy_counts": _counter_to_sorted_dict(gen_mask_policy_counts),
        "string_gen_mask_source_counts": _counter_to_sorted_dict(string_gen_mask_source_counts),
        "public_params_policy_counts": _counter_to_sorted_dict(public_params_policy_counts),
        "public_param_counts": _counter_to_sorted_dict(public_param_counts),
    }


def _mtl_flags_policy_summary(material_items):
    sub_material_flag_counts = Counter()
    sub_material_flag_name_counts = Counter()

    for item in material_items:
        policy = item.get("mtl_flags_policy", {})
        sub_material_flag_counts.update([policy.get("mtl_flags", "")])
        sub_material_flag_name_counts.update(policy.get("analysis", {}).get("names", []))

    export_policy = exported_mtl_flags_policy()
    return {
        "material_count": len(material_items),
        "root_material": export_policy["root_material"],
        "sub_material_flag_counts": _counter_to_sorted_dict(sub_material_flag_counts),
        "sub_material_flag_name_counts": _counter_to_sorted_dict(sub_material_flag_name_counts),
        "source_evidence": export_policy["source_evidence"],
    }


def _mtl_texture_map_policy_summary(material_items):
    input_texture_type_counts = Counter()
    exported_ce_map_counts = Counter()
    skipped_reason_counts = Counter()
    expected_suffix_counts = Counter()
    suffix_status_counts = Counter()

    for item in material_items:
        policy = item.get("mtl_texture_map_policy", {})
        for entry in policy.get("entries", []):
            input_texture_type_counts.update([entry.get("texture_type", "")])
            suffix_analysis = entry.get("suffix_analysis", {})
            suffix_status_counts.update([suffix_analysis.get("suffix_status", "")])
            if entry.get("exported"):
                exported_ce_map_counts.update([entry.get("ce_map_type", "")])
                expected_suffix = suffix_analysis.get("expected_suffix", "")
                if expected_suffix:
                    expected_suffix_counts.update([expected_suffix])
            else:
                skipped_reason_counts.update([entry.get("reason", "")])

    return {
        "material_count": len(material_items),
        "input_texture_type_counts": _counter_to_sorted_dict(input_texture_type_counts),
        "exported_ce_map_counts": _counter_to_sorted_dict(exported_ce_map_counts),
        "skipped_reason_counts": _counter_to_sorted_dict(skipped_reason_counts),
        "expected_suffix_counts": _counter_to_sorted_dict(expected_suffix_counts),
        "suffix_status_counts": _counter_to_sorted_dict(suffix_status_counts),
        "source_evidence": exported_texture_map_policy({})["source_evidence"],
    }


def build_material_diagnostics_report(
    materials,
    existing_submaterial_names=None,
    source_model="",
    artifact_kind="model",
    material_manifest_info=None,
    source_materials=None,
):
    records = build_material_slot_records(
        materials,
        existing_submaterial_names,
        material_manifest_info=material_manifest_info,
    )
    material_items = [_record_to_report_item(record) for record in records]
    source_materials = materials if source_materials is None else source_materials
    diagnostics = [
        {
            **diagnostic,
            "assignment_reason": diagnostic.get("assignment_reason", "omitted_source_material"),
            "original_name": diagnostic.get("material", ""),
            "mesh_names": diagnostic.get("mesh_names", []),
            "material_names": diagnostic.get("material_names", []),
            "slot_name_conflict": diagnostic.get("slot_name_conflict", False),
            "texture_ref_evidence": diagnostic.get("texture_ref_evidence", []),
        }
        for diagnostic in build_omitted_material_diagnostics(source_materials, records)
    ]
    diagnostics.extend(material_manifest_table_diagnostics(material_manifest_info))
    for item in material_items:
        item["diagnostics"] = [
            *item["diagnostics"],
            *_texture_evidence_diagnostics(item),
        ]
        for diagnostic in item["diagnostics"]:
            diagnostics.append(
                {
                    **diagnostic,
                    "source_order": item["source_order"],
                    "assignment_reason": diagnostic.get("assignment_reason", item["assignment_reason"]),
                    "original_name": item["original_name"],
                    "polygon_count": item["polygon_count"],
                    "used_by_polygons": item["used_by_polygons"],
                    "mesh_names": item["mesh_names"],
                    "material_names": item["material_names"],
                    "slot_name_conflict": item["slot_name_conflict"],
                    "case_insensitive_name_conflict": item["case_insensitive_name_conflict"],
                    "case_insensitive_material_names": item["case_insensitive_material_names"],
                    "duplicate_sub_index_conflict": item["duplicate_sub_index_conflict"],
                    "duplicate_sub_index_material_names": item["duplicate_sub_index_material_names"],
                    "texture_ref_evidence": item["texture_ref_evidence"],
                }
            )

    hazard_count = sum(1 for diagnostic in diagnostics if diagnostic.get("severity") == "hazard")
    return {
        "source_model": source_model,
        "artifact_kind": artifact_kind,
        "summary": {
            "material_count": len(material_items),
            "diagnostic_count": len(diagnostics),
            "hazard_count": hazard_count,
        },
        "mtl_flags_policy_summary": _mtl_flags_policy_summary(material_items),
        "mtl_texture_map_policy_summary": _mtl_texture_map_policy_summary(material_items),
        "mtl_shader_policy_summary": _mtl_shader_policy_summary(material_items),
        "materials": material_items,
        "diagnostics": diagnostics,
    }


def write_material_diagnostics_report(report, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return output_path


def export_material_diagnostics(
    materials,
    output_dir,
    output_filename,
    existing_submaterial_names=None,
    source_model="",
    artifact_kind="model",
    material_manifest_info=None,
    source_materials=None,
):
    report = build_material_diagnostics_report(
        materials,
        existing_submaterial_names=existing_submaterial_names,
        source_model=source_model,
        artifact_kind=artifact_kind,
        material_manifest_info=material_manifest_info,
        source_materials=source_materials,
    )
    output_path = os.path.join(output_dir, output_filename)
    return write_material_diagnostics_report(report, output_path)
