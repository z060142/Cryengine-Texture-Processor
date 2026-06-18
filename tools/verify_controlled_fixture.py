#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify a controlled Blender FBX fixture after RC conversion."""

import argparse
import json


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_fixture_material_ids(manifest_path, report_path):
    manifest = load_json(manifest_path)
    report = load_json(report_path)

    expected = sorted(manifest.get("expect_cgf_material_ids", []))
    actual = sorted(report.get("cgf_material_summary", {}).get("material_ids", []))
    return {
        "ok": expected == actual and not report.get("cgf_read_error"),
        "expected": expected,
        "actual": actual,
        "cgf_read_error": report.get("cgf_read_error", ""),
        "cgf_material_id_alignment": report.get("cgf_material_id_alignment", {}),
        "manifest": manifest_path,
        "report": report_path,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify controlled fixture material ids in an RC material report.")
    parser.add_argument("--manifest", required=True, help="Path to *.fixture_manifest.json")
    parser.add_argument("--report", required=True, help="Path to *.material_report.json")
    args = parser.parse_args(argv)

    result = verify_fixture_material_ids(args.manifest, args.report)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
