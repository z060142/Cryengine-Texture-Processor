#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Report CryEngine .mtl GenMask/StringGenMask evidence."""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET

from output_formats.cryengine_mtl_schema import (
    COMMON_GLOBAL_LEGACY_FIX_MASKS,
    EXPORT_COMPAT_SHADER_MASKS,
    ILLUM_EXT_SHADER_MASKS,
)
from tools.cryengine_shader_flags import build_common_global_flag_table_from_dir


TOKEN_PATTERN = re.compile(r"%[A-Za-z0-9_]+")


def string_gen_mask_tokens(value):
    return TOKEN_PATTERN.findall(value or "")


def mask_from_tokens(tokens, mapping):
    known = []
    unknown = []
    value = 0
    for token in tokens:
        if token in mapping:
            known.append(token)
            value |= mapping[token]
        else:
            unknown.append(token)
    return {
        "value": value,
        "known_tokens": sorted(set(known)),
        "unknown_tokens": sorted(set(unknown)),
    }


def parse_gen_mask_literal(value, prefer_hex_for_string_mask=True):
    value = (value or "").strip()
    if not value:
        return {
            "literal": "",
            "value": 0,
            "base": None,
            "ambiguous": False,
        }

    lower_value = value.lower()
    if lower_value.startswith("0x"):
        return {
            "literal": value,
            "value": int(value, 16),
            "base": 16,
            "ambiguous": False,
        }

    contains_hex_letters = any(char in "abcdefABCDEF" for char in value)
    decimal_value = int(value, 10) if value.isdigit() else None
    hex_value = int(value, 16)
    ambiguous = value.isdigit() and decimal_value != hex_value

    if contains_hex_letters or (prefer_hex_for_string_mask and value.isdigit() and len(value) >= 8):
        return {
            "literal": value,
            "value": hex_value,
            "base": 16,
            "ambiguous": ambiguous,
            "decimal_value": decimal_value,
            "hex_value": hex_value,
        }

    return {
        "literal": value,
        "value": decimal_value if decimal_value is not None else hex_value,
        "base": 10 if decimal_value is not None else 16,
        "ambiguous": ambiguous,
        "decimal_value": decimal_value,
        "hex_value": hex_value,
    }


def _material_elements(root):
    yield root, "Material[0]"
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return
    for index, child in enumerate(list(sub_materials)):
        if child.tag == "Material":
            yield child, f"SubMaterials/Material[{index}]"


def analyze_material_element(element, location, common_global_flags=None):
    string_gen_mask = element.get("StringGenMask", "")
    tokens = string_gen_mask_tokens(string_gen_mask)
    gen_mask = parse_gen_mask_literal(
        element.get("GenMask", ""),
        prefer_hex_for_string_mask=bool(tokens),
    )
    illum_ext = mask_from_tokens(tokens, ILLUM_EXT_SHADER_MASKS)
    common_legacy_fix = mask_from_tokens(tokens, COMMON_GLOBAL_LEGACY_FIX_MASKS)
    common_generated = mask_from_tokens(tokens, common_global_flags or {})
    export_compat = mask_from_tokens(tokens, EXPORT_COMPAT_SHADER_MASKS)

    return {
        "location": location,
        "name": element.get("Name", ""),
        "shader": element.get("Shader", ""),
        "mtl_flags": element.get("MtlFlags", ""),
        "gen_mask": gen_mask,
        "string_gen_mask": string_gen_mask,
        "tokens": tokens,
        "illum_ext_mask": illum_ext,
        "common_global_legacy_fix_mask": common_legacy_fix,
        "common_global_generated_mask": common_generated,
        "export_compat_mask": export_compat,
        "matches_illum_ext_mask": bool(tokens) and gen_mask["value"] == illum_ext["value"],
        "matches_common_global_legacy_fix_mask": bool(tokens) and gen_mask["value"] == common_legacy_fix["value"],
        "matches_common_global_generated_mask": bool(tokens) and gen_mask["value"] == common_generated["value"],
        "matches_export_compat_mask": bool(tokens) and gen_mask["value"] == export_compat["value"],
    }


def analyze_mtl_file(mtl_path, common_global_flags=None):
    root = ET.parse(mtl_path).getroot()
    materials = [
        analyze_material_element(element, location, common_global_flags)
        for element, location in _material_elements(root)
    ]
    return {
        "path": os.path.abspath(mtl_path),
        "materials": materials,
    }


def iter_mtl_files(paths):
    for path in paths:
        if os.path.isdir(path):
            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.lower().endswith(".mtl"):
                        yield os.path.join(dirpath, filename)
        elif path.lower().endswith(".mtl"):
            yield path


def build_mtl_mask_report(paths, limit=None, shader_ext_dir=None):
    common_global_flags = (
        build_common_global_flag_table_from_dir(shader_ext_dir)
        if shader_ext_dir
        else {}
    )
    files = []
    for index, mtl_path in enumerate(sorted(set(iter_mtl_files(paths)))):
        if limit is not None and index >= limit:
            break
        files.append(analyze_mtl_file(mtl_path, common_global_flags))

    material_count = sum(len(file_info["materials"]) for file_info in files)
    mismatch_count = 0
    unknown_token_count = 0
    unknown_common_legacy_token_count = 0
    unknown_common_generated_token_count = 0
    generated_match_count = 0
    for file_info in files:
        for material in file_info["materials"]:
            if material["tokens"] and not (
                material["matches_illum_ext_mask"] or material["matches_export_compat_mask"]
                or material["matches_common_global_legacy_fix_mask"]
                or material["matches_common_global_generated_mask"]
            ):
                mismatch_count += 1
            unknown_token_count += len(material["illum_ext_mask"]["unknown_tokens"])
            unknown_common_legacy_token_count += len(
                material["common_global_legacy_fix_mask"]["unknown_tokens"]
            )
            unknown_common_generated_token_count += len(
                material["common_global_generated_mask"]["unknown_tokens"]
            )
            if material["matches_common_global_generated_mask"]:
                generated_match_count += 1

    return {
        "files": files,
        "common_global_flag_source": {
            "shader_ext_dir": os.path.abspath(shader_ext_dir) if shader_ext_dir else "",
            "token_count": len(common_global_flags),
        },
        "summary": {
            "file_count": len(files),
            "material_count": material_count,
            "tokenized_material_mismatch_count": mismatch_count,
            "unknown_illum_token_count": unknown_token_count,
            "unknown_common_global_legacy_fix_token_count": unknown_common_legacy_token_count,
            "unknown_common_global_generated_token_count": unknown_common_generated_token_count,
            "common_global_generated_match_count": generated_match_count,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report CryEngine .mtl GenMask/StringGenMask evidence.")
    parser.add_argument("paths", nargs="+", help="MTL files or directories to scan")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of .mtl files to scan")
    parser.add_argument("--shader-ext-dir", default="", help="Optional CryEngine Engine/Shaders folder")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args(argv)

    report = build_mtl_mask_report(args.paths, limit=args.limit, shader_ext_dir=args.shader_ext_dir or None)
    output = json.dumps(report, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
