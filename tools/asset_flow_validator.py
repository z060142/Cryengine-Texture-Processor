#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run practical asset-flow validation cases and write a pass/fail report."""

import argparse
import json
import os
import re
import time
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from core.batch_processor import BatchProcessor
from core.texture_manager import TextureManager
from output_formats.texture_output_diagnostics import build_texture_output_report_from_paths
from tools.blender_material_inspector import inspect_fbx_materials
from tools.material_report_summary import compact_material_report_summary, load_report
from tools.rc_smoke_test import (
    discover_default_rc,
    load_external_material_texture_evidence,
    material_specs_from_manifest_path,
    run_rc_smoke_test,
)


def _safe_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "asset")).strip("._")
    return safe or "asset"


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def _md_bool(value):
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    if value is None:
        return "N/A"
    return str(value)


def _md_escape(value):
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _summary_ok(summary):
    return bool(summary.get("rc_success")) and not bool(summary.get("action_required"))


def _mtl_value_summary(mtl_path):
    if not mtl_path or not os.path.exists(mtl_path):
        return []
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        candidates = [root]
    else:
        candidates = [element for element in list(sub_materials) if element.tag == "Material"]
    values = []
    for material in candidates:
        textures = []
        texture_root = material.find("Textures")
        if texture_root is not None:
            for texture in list(texture_root):
                if texture.tag != "Texture":
                    continue
                textures.append(
                    {
                        "map": texture.get("Map", ""),
                        "file": texture.get("File", ""),
                    }
                )
        values.append(
            {
                "name": material.get("Name", ""),
                "shader": material.get("Shader", ""),
                "mtl_flags": material.get("MtlFlags", ""),
                "gen_mask": material.get("GenMask", ""),
                "string_gen_mask": material.get("StringGenMask", ""),
                "textures": textures,
            }
        )
    return values


def _rc_case(case, defaults):
    source_fbx = case["fbx"]
    name = case.get("name") or Path(source_fbx).stem
    work_root = case.get("work_root") or defaults["work_root"]
    work_dir = os.path.join(work_root, _safe_name(name))
    os.makedirs(work_dir, exist_ok=True)
    manifest_path = case.get("manifest") or os.path.join(work_dir, f"{_safe_name(name)}.fbx_material_manifest.json")

    inspect_result = inspect_fbx_materials(
        case.get("blender") or defaults.get("blender", ""),
        source_fbx,
        manifest_path,
    )

    material_specs = material_specs_from_manifest_path(manifest_path)
    external_evidence = (
        load_external_material_texture_evidence(case.get("obj_mtl_evidence", ""))
        if case.get("obj_mtl_evidence")
        else None
    )
    result = run_rc_smoke_test(
        case.get("rc") or defaults.get("rc") or discover_default_rc(),
        source_fbx,
        work_dir,
        asset_name=case.get("asset_name") or _safe_name(name),
        material_specs=material_specs,
        texture_output_dir=case.get("texture_output_dir", ""),
        texture_output_format=case.get("texture_output_format", defaults.get("texture_output_format", "tif")),
        external_material_texture_evidence=external_evidence,
        material_manifest_path=manifest_path,
    )

    material_summary = {}
    texture_gate_ok = None
    mtl_schema_gate_ok = None
    if result.material_report_path and os.path.exists(result.material_report_path):
        material_summary = compact_material_report_summary(load_report(result.material_report_path))
        report = _load_json(result.material_report_path)
        texture_gate_ok = material_summary.get("texture_output_gate_ok")
        mtl_schema_gate_ok = material_summary.get("mtl_schema_gate_ok")

    checks = {
        "manifest_generated": bool(inspect_result.get("success")) and os.path.exists(manifest_path),
        "model_format_ok": result.success and bool(result.expected_output_path) and os.path.exists(result.expected_output_path),
        "material_slots_ok": bool(material_summary.get("slot_alignment_ok")) and bool(material_summary.get("material_slot_evidence_ok")),
        "mtl_format_ok": mtl_schema_gate_ok is True,
        "texture_format_ok": texture_gate_ok is True if case.get("texture_output_dir") else None,
        "material_texture_ok": None,
    }
    if case.get("texture_output_dir"):
        checks["material_texture_ok"] = (
            texture_gate_ok is True
            and bool(material_summary.get("texture_output_gate_ok"))
        )

    ok = (
        checks["manifest_generated"]
        and checks["model_format_ok"]
        and checks["material_slots_ok"]
        and checks["mtl_format_ok"]
        and (checks["texture_format_ok"] is not False)
        and (checks["material_texture_ok"] is not False)
        and _summary_ok(material_summary)
    )

    return {
        "name": name,
        "type": "rc",
        "ok": bool(ok),
        "source_fbx": os.path.abspath(source_fbx),
        "work_dir": work_dir,
        "manifest": manifest_path,
        "material_report": result.material_report_path,
        "mtl_schema_gate": result.mtl_schema_gate_path,
        "mtl": result.mtl_path,
        "json": result.json_path,
        "cgf": result.expected_output_path,
        "checks": checks,
        "mtl_values": _mtl_value_summary(result.mtl_path),
        "summary": material_summary,
        "error": result.error,
    }


def _texture_gate_case(case):
    report = build_texture_output_report_from_paths(
        case.get("paths", []),
        source="asset_flow_validator",
    )
    return {
        "name": case.get("name") or "texture_gate",
        "type": "texture_gate",
        "ok": bool(report["summary"]["ok"]),
        "paths": case.get("paths", []),
        "checks": {
            "texture_format_ok": bool(report["summary"]["ok"]),
        },
        "summary": report["summary"],
        "report": report,
    }


def _texture_process_settings(case):
    settings = {
        "diff_format": "albedo",
        "normal_flip_green": False,
        "generate_missing_spec": True,
        "process_metallic": True,
        "normal_from_height_strength": 10.0,
        "normalize_height": True,
        "texture_types": {
            "diff": True,
            "spec": True,
            "ddna": True,
            "displ": False,
            "emissive": False,
            "sss": False,
        },
    }
    settings.update(case.get("settings", {}))
    if case.get("texture_types"):
        settings["texture_types"] = {**settings["texture_types"], **case["texture_types"]}
    return settings


def _texture_process_case(case):
    name = case.get("name") or "texture_process"
    texture_paths = case.get("textures", [])
    output_dir = case["output_dir"]
    texture_manager = TextureManager()
    added = []
    missing = []
    for texture_path in texture_paths:
        if not os.path.exists(texture_path):
            missing.append(texture_path)
            continue
        texture = texture_manager.add_texture(texture_path)
        if texture:
            added.append(texture)

    processor = BatchProcessor(texture_manager)
    processor.set_output_dir(output_dir)
    processor.set_settings(_texture_process_settings(case))
    progress = []
    processor.set_progress_callback(
        lambda percent, stage, current, status: progress.append(
            {
                "progress": percent,
                "stage": stage,
                "current": current,
                "status": status,
            }
        )
    )
    started = processor.process_all_groups()
    while processor.is_processing():
        time.sleep(0.1)

    report = processor.texture_output_report or build_texture_output_report_from_paths(
        [output_dir],
        source="asset_flow_validator_texture_process",
    )
    summary = report.get("summary", {})
    ok = bool(started) and not missing and bool(summary.get("ok"))
    groups = [
        {
            "base_name": group.base_name,
            "textures": {
                texture_type: texture.get("filename", "")
                for texture_type, texture in group.textures.items()
                if texture_type != "unknown" and texture
            },
            "outputs": group.output,
        }
        for group in texture_manager.get_all_groups()
    ]
    return {
        "name": name,
        "type": "texture_process",
        "ok": ok,
        "textures": texture_paths,
        "output_dir": output_dir,
        "texture_output_report": processor.texture_output_report_path,
        "checks": {
            "raw_textures_found": not missing,
            "texture_processing_started": bool(started),
            "texture_format_ok": bool(summary.get("ok")),
        },
        "summary": summary,
        "groups": groups,
        "missing": missing,
        "progress_tail": progress[-5:],
    }


def format_markdown_report(report):
    summary = report.get("summary", {})
    lines = [
        "# CryEngine Asset Flow Validation",
        "",
        "## Summary",
        "",
        f"- Overall: {_md_bool(summary.get('ok'))}",
        f"- Cases: {summary.get('case_count', 0)}",
        f"- Passed: {summary.get('ok_count', 0)}",
        f"- Failed: {summary.get('failed_count', 0)}",
        "",
        "## Cases",
        "",
        "| Case | Type | Result | Checks | Evidence |",
        "|---|---|---|---|---|",
    ]
    for case in report.get("cases", []):
        checks = ", ".join(
            f"{key}={_md_bool(value)}"
            for key, value in (case.get("checks") or {}).items()
        )
        evidence_values = [
            case.get("texture_output_report"),
            case.get("material_report"),
            case.get("mtl_schema_gate"),
            case.get("mtl"),
            case.get("json"),
            case.get("cgf"),
        ]
        evidence = "<br>".join(_md_escape(value) for value in evidence_values if value)
        lines.append(
            "| {name} | {type} | {result} | {checks} | {evidence} |".format(
                name=_md_escape(case.get("name", "")),
                type=_md_escape(case.get("type", "")),
                result=_md_bool(case.get("ok")),
                checks=_md_escape(checks),
                evidence=evidence,
            )
        )

    rc_cases_with_mtl = [
        case for case in report.get("cases", [])
        if case.get("type") == "rc" and case.get("mtl_values")
    ]
    if rc_cases_with_mtl:
        lines.extend(["", "## MTL Values", ""])
        for case in rc_cases_with_mtl:
            lines.extend([f"### {_md_escape(case.get('name', ''))}", ""])
            lines.append("| Material | Shader | MtlFlags | GenMask | StringGenMask | Textures |")
            lines.append("|---|---|---|---|---|---|")
            for material in case.get("mtl_values", []):
                textures = ", ".join(
                    f"{texture.get('map', '')}:{texture.get('file', '')}"
                    for texture in material.get("textures", [])
                )
                lines.append(
                    "| {name} | {shader} | {mtl_flags} | {gen_mask} | {string_gen_mask} | {textures} |".format(
                        name=_md_escape(material.get("name", "")),
                        shader=_md_escape(material.get("shader", "")),
                        mtl_flags=_md_escape(material.get("mtl_flags", "")),
                        gen_mask=_md_escape(material.get("gen_mask", "")),
                        string_gen_mask=_md_escape(material.get("string_gen_mask", "")),
                        textures=_md_escape(textures),
                    )
                )
            lines.append("")

    failed = [case for case in report.get("cases", []) if not case.get("ok")]
    if failed:
        lines.extend(["", "## Failures", ""])
        for case in failed:
            lines.append(f"- `{_md_escape(case.get('name', ''))}`: {_md_escape(case.get('error', 'failed checks'))}")

    return "\n".join(lines) + "\n"


def run_validation(spec):
    defaults = {
        "work_root": spec.get("work_root", os.path.abspath("asset_flow_validation")),
        "rc": spec.get("rc") or discover_default_rc(),
        "blender": spec.get("blender", ""),
        "texture_output_format": spec.get("texture_output_format", "tif"),
    }
    cases = []
    for case in spec.get("cases", []):
        case_type = case.get("type", "rc")
        try:
            if case_type == "rc":
                cases.append(_rc_case(case, defaults))
            elif case_type == "texture_process":
                cases.append(_texture_process_case(case))
            elif case_type == "texture_gate":
                cases.append(_texture_gate_case(case))
            else:
                cases.append(
                    {
                        "name": case.get("name", "unnamed"),
                        "type": case_type,
                        "ok": False,
                        "error": f"Unknown case type: {case_type}",
                    }
                )
        except Exception as exc:
            cases.append(
                {
                    "name": case.get("name", "unnamed"),
                    "type": case_type,
                    "ok": False,
                    "error": str(exc),
                }
            )

    return {
        "schema": "cryengine_asset_flow_validation.v1",
        "summary": {
            "case_count": len(cases),
            "ok_count": sum(1 for case in cases if case.get("ok")),
            "failed_count": sum(1 for case in cases if not case.get("ok")),
            "ok": all(case.get("ok") for case in cases) if cases else False,
        },
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run practical CryEngine asset-flow validation cases.")
    parser.add_argument("--spec", required=True, help="Validation spec JSON")
    parser.add_argument("--output", required=True, help="Output JSON report")
    parser.add_argument("--markdown-output", default="", help="Optional human-readable Markdown report")
    args = parser.parse_args(argv)

    report = run_validation(_load_json(args.spec))
    _write_json(args.output, report)
    if args.markdown_output:
        _write_text(args.markdown_output, format_markdown_report(report))
    print(args.output)
    if args.markdown_output:
        print(args.markdown_output)
    print(f"ok: {report['summary']['ok']}")
    print(f"case_count: {report['summary']['case_count']}")
    print(f"ok_count: {report['summary']['ok_count']}")
    print(f"failed_count: {report['summary']['failed_count']}")
    for case in report["cases"]:
        print(f"{case.get('name')}: {case.get('ok')}")
        if case.get("error"):
            print(f"  error: {case['error']}")
    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
