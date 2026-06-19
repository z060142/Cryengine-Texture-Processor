#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnostics for processed CryEngine texture outputs."""

import json
import os

from output_formats.cryengine_mtl_schema import resolve_ce_texture_map
from output_formats.texture_output_paths import OUTPUT_TEXTURE_TYPE_BY_KEY


def analyze_texture_output(output_key, texture_path):
    texture_type = OUTPUT_TEXTURE_TYPE_BY_KEY.get(output_key, "")
    policy = resolve_ce_texture_map(texture_type, texture_path)
    return {
        "output_key": output_key,
        "texture_type": texture_type,
        "texture_path": texture_path,
        "policy": policy,
        "source_evidence": policy.get("source_evidence", {}),
    }


def texture_output_diagnostics(entries):
    diagnostics = []
    for entry in entries:
        output_key = entry.get("output_key", "")
        texture_path = entry.get("texture_path", "")
        policy = entry.get("policy", {})
        if not entry.get("texture_type"):
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "unknown_texture_output_key",
                    "output_key": output_key,
                    "texture_path": texture_path,
                    "message": "Texture output key has no CryEngine map policy.",
                }
            )
            continue

        extension_analysis = policy.get("rc_source_extension_analysis", {})
        if extension_analysis and not extension_analysis.get("supported", False):
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "unsupported_rc_texture_output_extension",
                    "output_key": output_key,
                    "texture_type": entry.get("texture_type", ""),
                    "ce_map_type": policy.get("ce_map_type", ""),
                    "texture_path": texture_path,
                    "extension": extension_analysis.get("extension", ""),
                    "supported_extensions": extension_analysis.get("supported_extensions", []),
                    "message": "Processed texture output extension is not listed as a supported RC source format.",
                }
            )

        suffix_analysis = policy.get("suffix_analysis", {})
        if suffix_analysis.get("suffix_status") == "mismatch_expected_suffix":
            diagnostics.append(
                {
                    "severity": "warning",
                    "code": "mismatch_texture_output_suffix",
                    "output_key": output_key,
                    "texture_type": entry.get("texture_type", ""),
                    "ce_map_type": policy.get("ce_map_type", ""),
                    "texture_path": texture_path,
                    "expected_suffix": suffix_analysis.get("expected_suffix", ""),
                    "filename": suffix_analysis.get("filename", ""),
                    "message": "Processed texture output filename does not match the expected CryEngine suffix.",
                }
            )
    return diagnostics


def build_texture_output_policy(output_paths):
    entries = [
        analyze_texture_output(output_key, texture_path)
        for output_key, texture_path in sorted((output_paths or {}).items())
        if texture_path
    ]
    diagnostics = texture_output_diagnostics(entries)
    return {
        "entries": entries,
        "diagnostics": diagnostics,
        "diagnostic_count": len(diagnostics),
        "ok": not diagnostics,
    }


def build_texture_output_report(texture_groups, source="batch_texture_export"):
    group_reports = []
    diagnostic_count = 0
    output_count = 0

    for group in texture_groups or []:
        outputs = {
            output_key: texture_path
            for output_key, texture_path in getattr(group, "output", {}).items()
            if texture_path
        }
        policy = build_texture_output_policy(outputs)
        diagnostics = policy["diagnostics"]
        output_count += len(outputs)
        diagnostic_count += len(diagnostics)
        group_reports.append(
            {
                "base_name": getattr(group, "base_name", ""),
                "outputs": outputs,
                "output_policy": policy,
                "diagnostics": diagnostics,
                "diagnostic_count": len(diagnostics),
                "ok": not diagnostics,
            }
        )

    return {
        "schema": "cryengine_texture_output_diagnostics.v1",
        "source": source,
        "summary": {
            "group_count": len(group_reports),
            "output_count": output_count,
            "diagnostic_count": diagnostic_count,
            "ok": diagnostic_count == 0,
        },
        "groups": group_reports,
    }


def write_texture_output_report(report, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return output_path


def export_texture_output_report(texture_groups, output_dir, output_filename="texture_output_diagnostics.json"):
    output_path = os.path.join(output_dir, output_filename)
    report = build_texture_output_report(texture_groups)
    write_texture_output_report(report, output_path)
    return output_path, report
