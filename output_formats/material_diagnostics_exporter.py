#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write sidecar material-slot diagnostic reports."""

import json
import os

from model_processing.material_index_assigner import assign_material_sub_indices


def _record_to_report_item(record):
    fbx_id = record.get("fbx_material_id")
    fbx_slot = fbx_id - 1 if fbx_id is not None and fbx_id >= 1 else None
    return {
        "name": record["clean_name"],
        "original_name": record["original_name"],
        "source_order": record["source_order"],
        "fbx_material_id": fbx_id,
        "fbx_slot": fbx_slot,
        "sub_index": record["sub_index"],
        "assignment_reason": record["reason"],
        "deleted": record["deleted"],
        "polygon_count": record["material"].get("polygon_count"),
        "used_by_polygons": record["material"].get("used_by_polygons"),
        "mesh_names": record["material"].get("mesh_names", []),
        "diagnostics": record.get("diagnostics", []),
    }


def build_material_diagnostics_report(
    materials,
    existing_submaterial_names=None,
    source_model="",
    artifact_kind="model",
):
    records = assign_material_sub_indices(materials, existing_submaterial_names)
    material_items = [_record_to_report_item(record) for record in records]
    diagnostics = []
    for item in material_items:
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
):
    report = build_material_diagnostics_report(
        materials,
        existing_submaterial_names=existing_submaterial_names,
        source_model=source_model,
        artifact_kind=artifact_kind,
    )
    output_path = os.path.join(output_dir, output_filename)
    return write_material_diagnostics_report(report, output_path)
