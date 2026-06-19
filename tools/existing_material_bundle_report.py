#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build a material report from an existing RC output bundle."""

import argparse
import json
import os

from tools.material_mapping_report import (
    build_existing_output_material_report,
    write_material_mapping_report,
)


def _default_mtl_path(cgf_path):
    stem, _ = os.path.splitext(cgf_path)
    candidate = f"{stem}.mtl"
    return candidate if os.path.exists(candidate) else ""


def _default_report_path(cgf_path):
    stem, _ = os.path.splitext(cgf_path)
    return f"{stem}.material_report.json"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze an existing .cgf/.mtl bundle, using CGF ImportSettings when request JSON is absent.",
    )
    parser.add_argument("cgf", help="Path to an existing RC-generated .cgf file")
    parser.add_argument("--mtl", default=None, help="Path to the matching .mtl file; defaults to the .cgf stem")
    parser.add_argument("--json", default="", help="Optional original RC request JSON")
    parser.add_argument("--fbx", default="", help="Optional source FBX path for fixture manifest discovery")
    parser.add_argument("--output", default=None, help="Report output path; defaults to <cgf>.material_report.json")
    args = parser.parse_args(argv)

    cgf_path = os.path.abspath(args.cgf)
    mtl_path = os.path.abspath(args.mtl) if args.mtl else _default_mtl_path(cgf_path)
    output_path = os.path.abspath(args.output) if args.output else _default_report_path(cgf_path)
    json_path = os.path.abspath(args.json) if args.json else ""
    fbx_path = os.path.abspath(args.fbx) if args.fbx else ""

    report = build_existing_output_material_report(
        cgf_path,
        mtl_path,
        json_path=json_path,
        source_fbx_path=fbx_path,
    )
    write_material_mapping_report(report, output_path)

    summary = {
        "report": output_path,
        "request_source": report.get("request_source", {}),
        "alignment_ok": report.get("alignment", {}).get("ok"),
        "cgf_import_settings_alignment_ok": report.get("cgf_import_settings_alignment", {}).get("ok"),
        "cgf_material_id_alignment_ok": report.get("cgf_material_id_alignment", {}).get("ok"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if report.get("cgf_import_settings_alignment", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
