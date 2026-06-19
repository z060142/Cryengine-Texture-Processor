#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run RC import and gate the generated material/texture evidence reports."""

import os

from output_formats.texture_output_diagnostics import (
    build_texture_output_report_from_paths,
    write_texture_output_report,
)
from tools.material_mapping_report import build_material_mapping_report, write_material_mapping_report
from tools.mtl_schema_report import build_mtl_schema_report, write_mtl_schema_report
from utils.rc_import_runner import RCImportResult


def _with_failure(rc_result, error):
    return RCImportResult(
        success=False,
        command=rc_result.command,
        json_path=rc_result.json_path,
        expected_output_path=rc_result.expected_output_path,
        returncode=rc_result.returncode,
        stdout=rc_result.stdout,
        stderr=rc_result.stderr,
        error=error,
    )


def _default_report_path(json_path, suffix):
    return os.path.splitext(json_path)[0] + suffix


def run_rc_import_with_gates(
    runner,
    json_path,
    source_fbx_path,
    mtl_path,
    rc_exe_path="",
    original_source_fbx_path="",
    texture_output_dir="",
    material_report_path="",
    mtl_schema_gate_path="",
    texture_output_gate_path="",
):
    rc_result = runner.run(json_path, source_fbx_path=source_fbx_path)
    material_report_path = material_report_path or _default_report_path(json_path, ".material_report.json")
    mtl_schema_gate_path = mtl_schema_gate_path or _default_report_path(json_path, ".mtl_schema_gate.json")
    texture_output_gate_path = texture_output_gate_path or _default_report_path(json_path, ".texture_output_gate.json")

    material_report = None
    mtl_schema_report = None
    texture_output_report = None

    try:
        material_report = build_material_mapping_report(
            json_path,
            mtl_path,
            expected_output_path=rc_result.expected_output_path,
            rc_exe_path=rc_exe_path,
            source_fbx_path=original_source_fbx_path or source_fbx_path,
            copied_fbx_path=source_fbx_path,
            rc_returncode=rc_result.returncode,
        )
        if mtl_path:
            mtl_schema_report = build_mtl_schema_report([mtl_path])
            write_mtl_schema_report(mtl_schema_report, mtl_schema_gate_path)
            material_report["mtl_schema_gate"] = mtl_schema_report.get("gate", {})
            material_report["mtl_schema_gate_path"] = mtl_schema_gate_path
        if texture_output_dir:
            texture_output_report = build_texture_output_report_from_paths(
                [texture_output_dir],
                source="direct_rc_export_texture_output_gate",
            )
            write_texture_output_report(texture_output_report, texture_output_gate_path)
            material_report["texture_output_gate"] = texture_output_report
            material_report["texture_output_gate_path"] = texture_output_gate_path
        write_material_mapping_report(material_report, material_report_path)
    except Exception as e:
        return {
            "rc_result": _with_failure(rc_result, f"Failed to write RC gate reports: {e}"),
            "material_report_path": "",
            "mtl_schema_gate_path": "",
            "texture_output_gate_path": "",
            "material_report": material_report,
            "mtl_schema_gate": (mtl_schema_report or {}).get("gate", {}),
            "texture_output_gate": texture_output_report or {},
        }

    gated_result = rc_result
    if gated_result.success and material_report.get("summary", {}).get("action_required"):
        gated_result = _with_failure(gated_result, f"Material mapping report requires action: {material_report_path}")
    if gated_result.success and mtl_schema_report is not None and not mtl_schema_report["gate"]["summary"]["ok"]:
        gated_result = _with_failure(gated_result, f"MTL schema gate failed: {mtl_schema_gate_path}")
    if gated_result.success and texture_output_report is not None and not texture_output_report["summary"]["ok"]:
        gated_result = _with_failure(gated_result, f"Texture output gate failed: {texture_output_gate_path}")

    return {
        "rc_result": gated_result,
        "material_report_path": material_report_path,
        "mtl_schema_gate_path": mtl_schema_gate_path if mtl_schema_report is not None else "",
        "texture_output_gate_path": texture_output_gate_path if texture_output_report is not None else "",
        "material_report": material_report,
        "mtl_schema_gate": (mtl_schema_report or {}).get("gate", {}),
        "texture_output_gate": texture_output_report or {},
    }
