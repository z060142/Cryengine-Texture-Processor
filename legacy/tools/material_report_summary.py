#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Print a compact summary for RC material reports."""

import argparse
import json


def load_report(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compact_material_report_summary(report):
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    slot_evidence = report.get("material_slot_evidence", {}) if isinstance(report, dict) else {}
    texture_gate = report.get("texture_output_gate", {}) if isinstance(report, dict) else {}
    mtl_gate = report.get("mtl_schema_gate", {}) if isinstance(report, dict) else {}
    return {
        "rc_success": summary.get("rc_success"),
        "action_required": summary.get("action_required"),
        "slot_alignment_ok": summary.get("slot_alignment_ok"),
        "cgf_material_id_alignment_ok": summary.get("cgf_material_id_alignment_ok"),
        "cgf_import_settings_alignment_ok": summary.get("cgf_import_settings_alignment_ok"),
        "material_slot_evidence_ok": summary.get("material_slot_evidence_ok"),
        "material_slot_evidence_status_counts": summary.get("material_slot_evidence_status_counts", {}),
        "unassigned_placeholder_count": summary.get("unassigned_placeholder_count", 0),
        "used_unassigned_material_count": summary.get("used_unassigned_material_count", 0),
        "texture_output_gate_ok": (texture_gate.get("summary") or {}).get("ok"),
        "mtl_schema_gate_ok": (mtl_gate.get("gate") or mtl_gate.get("summary") or {}).get("ok"),
        "slot_rows": (slot_evidence.get("summary") or {}).get("row_count", 0),
    }


def format_summary(summary):
    lines = [
        f"rc_success: {summary.get('rc_success')}",
        f"action_required: {summary.get('action_required')}",
        f"slot_alignment_ok: {summary.get('slot_alignment_ok')}",
        f"cgf_material_id_alignment_ok: {summary.get('cgf_material_id_alignment_ok')}",
        f"cgf_import_settings_alignment_ok: {summary.get('cgf_import_settings_alignment_ok')}",
        f"material_slot_evidence_ok: {summary.get('material_slot_evidence_ok')}",
        f"slot_rows: {summary.get('slot_rows')}",
        f"slot_status_counts: {summary.get('material_slot_evidence_status_counts')}",
        f"unassigned_placeholders: {summary.get('unassigned_placeholder_count')}",
        f"used_unassigned: {summary.get('used_unassigned_material_count')}",
        f"texture_output_gate_ok: {summary.get('texture_output_gate_ok')}",
        f"mtl_schema_gate_ok: {summary.get('mtl_schema_gate_ok')}",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print a compact RC material report summary.")
    parser.add_argument("report", help="Path to *.material_report.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    summary = compact_material_report_summary(load_report(args.report))
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(format_summary(summary))
    return 1 if summary.get("action_required") else 0


if __name__ == "__main__":
    raise SystemExit(main())
