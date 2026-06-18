#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe how CryEngine RC reacts to .mtl GenMask/StringGenMask variants."""

import argparse
from dataclasses import dataclass
import json
import os
import re
import xml.etree.ElementTree as ET

from tools.rc_smoke_test import (
    DEFAULT_FBX_CANDIDATES,
    DEFAULT_RC_CANDIDATES,
    discover_default_fbx,
    discover_default_rc,
    prepare_smoke_bundle,
)
from utils.rc_import_runner import RCImportRunner


KEEP = "__keep__"
MASK_LOG_PATTERN = re.compile(r"\b(stringgenmask|genmask|shader)\b", re.IGNORECASE)

DEFAULT_MASK_VARIANTS = (
    {
        "slug": "exporter_baseline",
        "description": "Exporter compatibility GenMask and StringGenMask.",
        "gen_mask": KEEP,
        "string_gen_mask": KEEP,
    },
    {
        "slug": "string_only_subsurface",
        "description": "StringGenMask only, with GenMask removed.",
        "gen_mask": None,
        "string_gen_mask": "%SUBSURFACE_SCATTERING",
    },
    {
        "slug": "gen_only_legacy_subsurface",
        "description": "Persisted EngineAssets-style GenMask only, with StringGenMask removed.",
        "gen_mask": "80000000",
        "string_gen_mask": None,
    },
    {
        "slug": "legacy_gen_with_string",
        "description": "Persisted EngineAssets-style GenMask paired with matching StringGenMask.",
        "gen_mask": "80000000",
        "string_gen_mask": "%SUBSURFACE_SCATTERING",
    },
    {
        "slug": "runtime_globals_gen_with_string",
        "description": "Current generated globals GenMask paired with matching StringGenMask.",
        "gen_mask": "4000000000000",
        "string_gen_mask": "%SUBSURFACE_SCATTERING",
    },
    {
        "slug": "no_mask_fields",
        "description": "Both GenMask and StringGenMask removed.",
        "gen_mask": None,
        "string_gen_mask": None,
    },
)


@dataclass
class MTLMaskVariant:
    slug: str
    description: str
    gen_mask: str | None
    string_gen_mask: str | None


def default_mask_variants():
    return [MTLMaskVariant(**variant) for variant in DEFAULT_MASK_VARIANTS]


def _set_or_remove_attribute(element, name, value):
    if value == KEEP:
        return
    if value is None:
        element.attrib.pop(name, None)
    else:
        element.set(name, str(value))


def apply_mask_variant_to_mtl(mtl_path, variant):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    material_elements = []
    if sub_materials is not None:
        material_elements = [child for child in list(sub_materials) if child.tag == "Material"]
    if not material_elements:
        material_elements = [root]

    material_snapshots = []
    for material in material_elements:
        before = {
            "name": material.get("Name", ""),
            "gen_mask": material.get("GenMask", ""),
            "string_gen_mask": material.get("StringGenMask", ""),
        }
        _set_or_remove_attribute(material, "GenMask", variant.gen_mask)
        _set_or_remove_attribute(material, "StringGenMask", variant.string_gen_mask)
        after = {
            "name": material.get("Name", ""),
            "gen_mask": material.get("GenMask", ""),
            "string_gen_mask": material.get("StringGenMask", ""),
        }
        material_snapshots.append({"before": before, "after": after})

    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)
    return material_snapshots


def extract_mask_log_hits(stdout="", stderr=""):
    hits = []
    for stream, text in (("stdout", stdout or ""), ("stderr", stderr or "")):
        for line in text.splitlines():
            if MASK_LOG_PATTERN.search(line):
                hits.append({"stream": stream, "line": line})
    return hits


def run_mtl_genmask_probe(
    rc_exe_path,
    source_fbx_path,
    work_dir,
    asset_name="MTLGenMaskProbe",
    variants=None,
    runner_factory=RCImportRunner,
):
    rc_exe_path = rc_exe_path or ""
    source_fbx_path = os.path.abspath(source_fbx_path) if source_fbx_path else ""
    work_dir = os.path.abspath(work_dir)
    variants = variants or default_mask_variants()

    report = {
        "probe": "mtl_genmask_rc_acceptance",
        "rc_exe_path": rc_exe_path,
        "source_fbx_path": source_fbx_path,
        "work_dir": work_dir,
        "asset_name": asset_name,
        "variants": [],
        "summary": {
            "variant_count": len(variants),
            "success_count": 0,
            "failure_count": 0,
            "mask_related_log_hit_count": 0,
            "rc_accepts_all_variants": False,
        },
    }

    if not rc_exe_path or not os.path.exists(rc_exe_path):
        report["error"] = f"RC executable not found: {rc_exe_path or '<empty>'}"
        return report
    if not source_fbx_path or not os.path.exists(source_fbx_path):
        report["error"] = f"Source FBX not found: {source_fbx_path or '<empty>'}"
        return report

    for variant in variants:
        variant_asset_name = f"{asset_name}_{variant.slug}"
        variant_work_dir = os.path.join(work_dir, variant.slug)
        bundle = prepare_smoke_bundle(
            source_fbx_path,
            variant_work_dir,
            asset_name=variant_asset_name,
            material_names=["Default"],
        )
        material_snapshots = apply_mask_variant_to_mtl(bundle["mtl_path"], variant)

        runner = runner_factory(rc_exe_path)
        rc_result = runner.run(bundle["json_path"], source_fbx_path=bundle["copied_fbx_path"])
        mask_hits = extract_mask_log_hits(rc_result.stdout, rc_result.stderr)
        output_exists = bool(rc_result.expected_output_path and os.path.exists(rc_result.expected_output_path))

        variant_report = {
            "slug": variant.slug,
            "description": variant.description,
            "requested": {
                "gen_mask": variant.gen_mask,
                "string_gen_mask": variant.string_gen_mask,
            },
            "work_dir": variant_work_dir,
            "mtl_path": bundle["mtl_path"],
            "json_path": bundle["json_path"],
            "copied_fbx_path": bundle["copied_fbx_path"],
            "expected_output_path": rc_result.expected_output_path,
            "expected_output_exists": output_exists,
            "material_snapshots": material_snapshots,
            "rc": {
                "success": rc_result.success,
                "returncode": rc_result.returncode,
                "error": rc_result.error,
                "command": rc_result.command,
                "stdout_length": len(rc_result.stdout or ""),
                "stderr_length": len(rc_result.stderr or ""),
                "mask_related_log_hits": mask_hits,
            },
        }
        report["variants"].append(variant_report)

        if rc_result.success:
            report["summary"]["success_count"] += 1
        else:
            report["summary"]["failure_count"] += 1
        report["summary"]["mask_related_log_hit_count"] += len(mask_hits)

    report["summary"]["rc_accepts_all_variants"] = (
        report["summary"]["variant_count"] > 0
        and report["summary"]["success_count"] == report["summary"]["variant_count"]
    )
    return report


def write_probe_report(report, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe RC behavior for .mtl GenMask/StringGenMask variants.")
    parser.add_argument("--rc", default=discover_default_rc(DEFAULT_RC_CANDIDATES), help="Path to rc.exe")
    parser.add_argument("--fbx", default=discover_default_fbx(DEFAULT_FBX_CANDIDATES), help="Path to a source FBX sample")
    parser.add_argument("--work-dir", required=True, help="Directory for generated probe files")
    parser.add_argument("--asset-name", default="MTLGenMaskProbe", help="Output asset base name")
    parser.add_argument("--output", default="", help="Optional JSON report path")
    args = parser.parse_args(argv)

    report = run_mtl_genmask_probe(
        args.rc,
        args.fbx,
        args.work_dir,
        asset_name=args.asset_name,
    )
    output_path = args.output or os.path.join(args.work_dir, "mtl_genmask_probe_report.json")
    write_probe_report(report, output_path)
    print(f"report: {output_path}")
    print(json.dumps(report["summary"], indent=2))
    if report.get("error"):
        print(f"error: {report['error']}")
        return 1
    return 0 if report["summary"]["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
