#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export a machine-readable schema for external CryEngine converter tools."""

import argparse
import json
import os

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from model_processing.material_slot_mapping import SLOT_MAPPING_RULES
from output_formats.cryengine_mtl_schema import (
    CE_TEXTURE_MAP_TYPES,
    RC_TEXTURE_SOURCE_EXTENSIONS,
    analyze_rc_texture_source_extension,
    exported_material_attribute_policy,
    exported_material_shader_policy,
    exported_mtl_flags_policy,
    exported_texture_map_policy,
    exported_texture_modifier_policy,
    resolve_ce_texture_map,
)
from output_formats.texture_output_diagnostics import OUTPUT_TEXTURE_TYPE_BY_KEY


def _sample_texture_path(texture_type, ce_map_type):
    suffix = resolve_ce_texture_map(texture_type, "").get("suffix_analysis", {}).get("expected_suffix", "")
    return f"asset{suffix or '_' + texture_type}.tif"


def _texture_output_schema():
    outputs = []
    for output_key, texture_type in sorted(OUTPUT_TEXTURE_TYPE_BY_KEY.items()):
        sample_policy = resolve_ce_texture_map(texture_type, _sample_texture_path(texture_type, texture_type))
        outputs.append(
            {
                "output_key": output_key,
                "texture_type": texture_type,
                "ce_map_type": sample_policy.get("ce_map_type", ""),
                "expected_suffix": sample_policy.get("suffix_analysis", {}).get("expected_suffix", ""),
                "accepted_suffixes": sample_policy.get("suffix_analysis", {}).get("accepted_suffixes", []),
                "supported_source_extensions": sample_policy.get("rc_source_extension_analysis", {}).get(
                    "supported_extensions",
                    [],
                ),
                "source_evidence": sample_policy.get("source_evidence", {}),
            }
        )

    return {
        "schema": "cryengine_texture_output_schema.v1",
        "outputs": outputs,
        "supported_source_extensions": sorted(RC_TEXTURE_SOURCE_EXTENSIONS),
        "source_evidence": analyze_rc_texture_source_extension("asset_diff.tif").get("source_evidence", {}),
    }


def _mtl_texture_map_schema():
    entries = []
    for texture_type, ce_map_type in sorted(CE_TEXTURE_MAP_TYPES.items()):
        sample_path = _sample_texture_path(texture_type, ce_map_type)
        policy = resolve_ce_texture_map(texture_type, sample_path)
        entries.append(
            {
                "texture_type": texture_type,
                "ce_map_type": ce_map_type or "",
                "exported": policy.get("exported", False),
                "reason": policy.get("reason", ""),
                "expected_suffix": policy.get("suffix_analysis", {}).get("expected_suffix", ""),
                "accepted_suffixes": policy.get("suffix_analysis", {}).get("accepted_suffixes", []),
            }
        )

    policy = exported_texture_map_policy({})
    return {
        "schema": "cryengine_mtl_texture_map_schema.v1",
        "entries": entries,
        "source_evidence": policy.get("source_evidence", {}),
    }


def build_converter_schema():
    return {
        "schema": "cryengine_converter_schema.v1",
        "material_slot_mapping": {
            "schema": "cryengine_material_slot_mapping.v1",
            "rules": SLOT_MAPPING_RULES,
        },
        "texture_outputs": _texture_output_schema(),
        "mtl": {
            "texture_maps": _mtl_texture_map_schema(),
            "texture_modifier": exported_texture_modifier_policy(),
            "material_attributes": exported_material_attribute_policy(),
            "mtl_flags": exported_mtl_flags_policy(),
            "shader_policy": {
                "empty_material": exported_material_shader_policy({}),
                "normal_specular_displacement": exported_material_shader_policy(
                    {
                        "normal": "asset_ddn.tif",
                        "specular": "asset_spec.tif",
                        "displacement": "asset_displ.tif",
                    }
                ),
            },
        },
    }


def write_converter_schema(schema, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return output_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export the CryEngine converter schema used by external tools.")
    parser.add_argument("--output", default="", help="Optional output JSON path. Prints to stdout when omitted.")
    args = parser.parse_args(argv)

    schema = build_converter_schema()
    if args.output:
        output_path = os.path.abspath(args.output)
        write_converter_schema(schema, output_path)
        print(output_path)
    else:
        print(json.dumps(schema, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
