#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnostics for processed CryEngine texture outputs."""

import json
import os

from output_formats.cryengine_mtl_schema import resolve_ce_texture_map
from output_formats.texture_output_paths import OUTPUT_TEXTURE_TYPE_BY_KEY


OUTPUT_KEY_SUFFIXES = {
    "diff": ("_diff",),
    "spec": ("_spec",),
    "ddna": ("_ddna", "_ddn"),
    "displ": ("_displ",),
    "emissive": ("_em", "_emissive"),
    "sss": ("_sss",),
    "opacity": ("_opacity",),
    "roughness": ("_roughness",),
}


def analyze_texture_output(output_key, texture_path, check_exists=False):
    texture_type = OUTPUT_TEXTURE_TYPE_BY_KEY.get(output_key, "")
    policy = resolve_ce_texture_map(texture_type, texture_path)
    return {
        "output_key": output_key,
        "texture_type": texture_type,
        "texture_path": texture_path,
        "exists": bool(texture_path and os.path.exists(texture_path)) if check_exists else None,
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

        if entry.get("exists") is False:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "missing_texture_output_file",
                    "output_key": output_key,
                    "texture_type": entry.get("texture_type", ""),
                    "ce_map_type": policy.get("ce_map_type", ""),
                    "texture_path": texture_path,
                    "message": "Texture output path does not exist on disk.",
                }
            )

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


def build_texture_output_policy(output_paths, check_exists=False):
    entries = [
        analyze_texture_output(output_key, texture_path, check_exists=check_exists)
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


def build_texture_output_report(texture_groups, source="batch_texture_export", check_exists=False):
    group_reports = []
    diagnostic_count = 0
    output_count = 0

    for group in texture_groups or []:
        outputs = {
            output_key: texture_path
            for output_key, texture_path in getattr(group, "output", {}).items()
            if texture_path
        }
        policy = build_texture_output_policy(outputs, check_exists=check_exists)
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


def infer_output_key_from_filename(filename):
    stem = os.path.splitext(os.path.basename(filename or ""))[0].lower()
    matches = []
    for output_key, suffixes in OUTPUT_KEY_SUFFIXES.items():
        for suffix in suffixes:
            if stem.endswith(suffix):
                matches.append((len(suffix), output_key, suffix))
    if not matches:
        return "", stem
    _, output_key, suffix = sorted(matches, reverse=True)[0]
    return output_key, stem[: -len(suffix)]


def build_texture_groups_from_output_paths(paths):
    from core.texture_manager import TextureGroup

    groups_by_base_name = {}
    for texture_path in sorted(paths or []):
        output_key, base_name = infer_output_key_from_filename(texture_path)
        if not output_key:
            filename = os.path.basename(texture_path)
            base_name = os.path.splitext(filename)[0]
            output_key = f"unknown:{filename}"
        if not base_name:
            base_name = os.path.splitext(os.path.basename(texture_path))[0]
        group = groups_by_base_name.setdefault(base_name, TextureGroup(base_name))
        group.output[output_key] = texture_path
    return [groups_by_base_name[name] for name in sorted(groups_by_base_name)]


def is_texture_output_sidecar(path):
    filename = os.path.basename(str(path or "")).lower()
    return ".thmb." in filename or filename.endswith(".thmb")


def iter_texture_output_files(paths, extensions=("dds", "hdr", "tif", "tiff", "png", "tga", "jpg", "jpeg")):
    allowed_extensions = {str(ext).strip().lstrip(".").lower() for ext in extensions if str(ext).strip()}
    for path in paths or []:
        if os.path.isdir(path):
            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    if is_texture_output_sidecar(filename):
                        continue
                    extension = os.path.splitext(filename)[1].lstrip(".").lower()
                    if extension in allowed_extensions:
                        yield os.path.join(dirpath, filename)
        elif os.path.isfile(path):
            if is_texture_output_sidecar(path):
                continue
            extension = os.path.splitext(path)[1].lstrip(".").lower()
            if extension in allowed_extensions:
                yield path


def build_texture_output_report_from_paths(paths, source="texture_output_gate", check_exists=True):
    groups = build_texture_groups_from_output_paths(iter_texture_output_files(paths))
    return build_texture_output_report(groups, source=source, check_exists=check_exists)
