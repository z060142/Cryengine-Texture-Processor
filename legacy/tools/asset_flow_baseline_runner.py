#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the practical asset-flow baseline: build spec, validate, gate."""

import argparse
import os

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from tools.asset_flow_acceptance_gate import build_requirements, evaluate_report, write_report as write_gate_report
from tools.asset_flow_spec_builder import _parse_size_mb, build_spec, write_spec
from tools.asset_flow_validator import _write_json, _write_text, format_markdown_report, run_validation


def run_baseline(
    roots,
    obj_mtl_roots,
    output_dir,
    work_root="",
    limit=3,
    max_mb="2",
    max_textures_per_case=2,
    preset="texture-backed-baseline",
):
    output_dir = os.path.abspath(output_dir)
    work_root = os.path.abspath(work_root or os.path.join(output_dir, "work"))
    os.makedirs(output_dir, exist_ok=True)

    spec_path = os.path.join(output_dir, "asset_flow_baseline_spec.json")
    report_path = os.path.join(output_dir, "asset_flow_baseline_report.json")
    markdown_path = os.path.join(output_dir, "asset_flow_baseline_report.md")
    gate_path = os.path.join(output_dir, "asset_flow_baseline_gate.json")

    spec = build_spec(
        roots,
        work_root,
        limit=limit,
        max_bytes=_parse_size_mb(max_mb),
        obj_mtl_roots=obj_mtl_roots or roots,
        include_texture_process=True,
        texture_backed_only=True,
        max_textures_per_case=max_textures_per_case,
    )
    write_spec(spec_path, spec)

    validation_report = run_validation(spec)
    _write_json(report_path, validation_report)
    _write_text(markdown_path, format_markdown_report(validation_report))

    gate_report = evaluate_report(validation_report, requirements=build_requirements(preset=preset))
    write_gate_report(gate_path, gate_report)

    return {
        "schema": "cryengine_asset_flow_baseline_run.v1",
        "ok": bool(validation_report.get("summary", {}).get("ok")) and bool(gate_report.get("ok")),
        "paths": {
            "spec": spec_path,
            "report": report_path,
            "markdown": markdown_path,
            "gate": gate_path,
            "work_root": work_root,
        },
        "validation_summary": validation_report.get("summary", {}),
        "gate": gate_report,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the texture-backed asset-flow acceptance baseline.")
    parser.add_argument("roots", nargs="+", help="FBX files or folders to scan.")
    parser.add_argument("--obj-mtl-root", action="append", default=[], help="OBJ .mtl root. Can be passed more than once.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated spec/report/gate files.")
    parser.add_argument("--work-root", default="", help="ASCII work root for generated conversion files.")
    parser.add_argument("--limit", type=int, default=3, help="Number of texture-backed RC cases to include.")
    parser.add_argument("--max-mb", default="2", help="Maximum FBX size in MB. Use 0 to disable.")
    parser.add_argument("--max-textures-per-case", type=int, default=2, help="Maximum raw textures per texture_process case.")
    parser.add_argument("--preset", default="texture-backed-baseline", help="Acceptance gate preset.")
    args = parser.parse_args(argv)

    result = run_baseline(
        args.roots,
        args.obj_mtl_root,
        args.output_dir,
        work_root=args.work_root,
        limit=args.limit,
        max_mb=args.max_mb,
        max_textures_per_case=args.max_textures_per_case,
        preset=args.preset,
    )

    for key, value in result["paths"].items():
        print(f"{key}: {value}")
    print(f"ok: {result['ok']}")
    summary = result["validation_summary"]
    print(f"case_count: {summary.get('case_count', 0)}")
    print(f"ok_count: {summary.get('ok_count', 0)}")
    print(f"failed_count: {summary.get('failed_count', 0)}")
    print(f"gate_ok: {result['gate'].get('ok')}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
