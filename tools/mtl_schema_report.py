#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Summarize CryEngine .mtl XML schema usage from real material files."""

import argparse
from collections import Counter, defaultdict
import json
import os
import xml.etree.ElementTree as ET

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from output_formats.cryengine_mtl_schema import (
    BASE_PUBLIC_PARAMS,
    analyze_ce_texture_map_entry,
    analyze_ce_texture_path_reuse,
    analyze_public_params,
    describe_mtl_flags,
    exported_material_attribute_policy,
    exported_texture_modifier_policy,
)
from tools.mtl_mask_report import parse_gen_mask_literal, string_gen_mask_tokens


MTL_SCHEMA_ERROR_COUNTERS = {
    "texture_map_unknowns": "unknown_ce_texture_map",
    "mtl_flag_unknown_masks": "unknown_mtl_flag_mask",
}

MTL_SCHEMA_ERROR_STATUS_COUNTERS = {
    "texture_suffix_statuses": {
        "mismatch_expected_suffix": "mismatch_ce_texture_suffix",
    },
}

MTL_SCHEMA_WARNING_COUNTERS = {
    "texture_path_reuse_diagnostics": "shared_texture_path_across_ce_maps",
}

MTL_SCHEMA_WARNING_STATUS_COUNTERS = {
    "texture_suffix_statuses": {
        "no_source_backed_suffix": "no_source_backed_texture_suffix",
    },
}

TEXMOD_COMPATIBILITY_STATUSES = {
    "matches_export_minimal_texmod",
    "partial_export_minimal_texmod",
}


def _is_compatibility_policy_status(policy_status):
    return "compatibility" in str(policy_status or "")


def iter_mtl_files(paths):
    for path in paths:
        if os.path.isdir(path):
            for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    if filename.lower().endswith(".mtl"):
                        yield os.path.join(dirpath, filename)
        elif path.lower().endswith(".mtl"):
            yield path


def _material_elements(root):
    yield root, "Material[0]"
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return
    for index, child in enumerate(list(sub_materials)):
        if child.tag in {"Material", "MaterialRef"}:
            yield child, f"SubMaterials/{child.tag}[{index}]"


def _attributes(element):
    return {key: element.get(key, "") for key in sorted(element.attrib)}


def _child_attributes(element, child_name):
    child = element.find(child_name)
    if child is None:
        return {}
    return _attributes(child)


def _analyze_texmod_attrs(texmod_attrs):
    policy = exported_texture_modifier_policy()
    expected_attrs = policy["attributes"]
    if not texmod_attrs:
        status = "missing_texmod"
    elif texmod_attrs == expected_attrs:
        status = "matches_export_minimal_texmod"
    elif all(texmod_attrs.get(name) == value for name, value in expected_attrs.items() if name in texmod_attrs):
        status = "partial_export_minimal_texmod"
    else:
        status = "custom_texmod"

    return {
        "status": status,
        "expected_attrs": expected_attrs,
        "missing_attrs": sorted(set(expected_attrs) - set(texmod_attrs)),
        "extra_attrs": sorted(set(texmod_attrs) - set(expected_attrs)),
        "policy": policy,
    }


def _material_override_state(material_overrides, material_name):
    override = (material_overrides or {}).get(material_name, {})
    if not isinstance(override, dict):
        return {}
    cryengine_material = override.get("cryengine_material")
    if isinstance(cryengine_material, dict):
        return cryengine_material
    return override


def _analyze_material_attributes(attrs, override_attrs=None):
    policy = exported_material_attribute_policy()
    expected_attrs = policy["attributes"]
    override_attrs = override_attrs or {}
    entry_statuses = {}
    for name, expected_value in expected_attrs.items():
        if name not in attrs:
            status = "missing_export_attribute"
        elif attrs.get(name) == expected_value:
            status = "matches_export_attribute"
        else:
            status = "differs_from_export_attribute"
        entry_statuses[name] = {
            "status": status,
            "actual": attrs.get(name, ""),
            "expected": expected_value,
            "policy_status": policy["attribute_status"].get(name, ""),
            "override_backed": name in override_attrs and str(override_attrs.get(name, "")) == attrs.get(name, ""),
        }

    return {
        "entries": entry_statuses,
        "missing_attrs": sorted(name for name, entry in entry_statuses.items() if entry["status"] == "missing_export_attribute"),
        "different_attrs": sorted(name for name, entry in entry_statuses.items() if entry["status"] == "differs_from_export_attribute"),
        "policy": policy,
    }


def _texture_entries(element):
    textures = element.find("Textures")
    if textures is None:
        return []
    entries = []
    for texture in list(textures):
        if texture.tag != "Texture":
            continue
        texmod_attrs = _child_attributes(texture, "TexMod")
        ce_map_type = texture.get("Map", "")
        texture_file = texture.get("File", "")
        entries.append(
            {
                "map": ce_map_type,
                "file": texture_file,
                "attributes": _attributes(texture),
                "texture_map_analysis": analyze_ce_texture_map_entry(ce_map_type, texture_file),
                "texmod": texmod_attrs,
                "texmod_analysis": _analyze_texmod_attrs(texmod_attrs),
            }
        )
    return entries


def _apply_public_param_override_backing(public_param_analysis, public_params, override_public_params=None):
    override_public_params = override_public_params or {}
    for name, analysis in public_param_analysis.items():
        analysis["override_backed"] = (
            name in override_public_params
            and str(override_public_params.get(name, "")) == public_params.get(name, "")
        )
    return public_param_analysis


def analyze_material_element(element, location, material_overrides=None):
    gen_mask = parse_gen_mask_literal(
        element.get("GenMask", ""),
        prefer_hex_for_string_mask=bool(element.get("StringGenMask", "")),
    )
    tokens = string_gen_mask_tokens(element.get("StringGenMask", ""))
    public_params = _child_attributes(element, "PublicParams")
    override_state = _material_override_state(material_overrides, element.get("Name", ""))
    override_public_params = (
        override_state.get("PublicParams", {})
        if isinstance(override_state.get("PublicParams"), dict)
        else {}
    )
    mtl_flags_analysis = describe_mtl_flags(element.get("MtlFlags", ""))
    attributes = _attributes(element)
    textures = _texture_entries(element)
    public_param_analysis = analyze_public_params(public_params)
    return {
        "location": location,
        "tag": element.tag,
        "name": element.get("Name", ""),
        "shader": element.get("Shader", ""),
        "mtl_flags": element.get("MtlFlags", ""),
        "mtl_flags_analysis": mtl_flags_analysis,
        "gen_mask": gen_mask,
        "string_gen_mask": element.get("StringGenMask", ""),
        "tokens": tokens,
        "attributes": attributes,
        "attribute_policy_analysis": _analyze_material_attributes(attributes, override_state),
        "public_params": public_params,
        "public_param_analysis": _apply_public_param_override_backing(
            public_param_analysis,
            public_params,
            override_public_params,
        ),
        "textures": textures,
        "texture_path_reuse_diagnostics": analyze_ce_texture_path_reuse(
            [
                {
                    "ce_map_type": texture["map"],
                    "texture_path": texture["file"],
                    "suffix_analysis": texture["texture_map_analysis"]["suffix_analysis"],
                }
                for texture in textures
            ]
        ),
        "child_tags": [child.tag for child in list(element)],
    }


def analyze_mtl_file(mtl_path, material_overrides=None):
    root = ET.parse(mtl_path).getroot()
    materials = [
        analyze_material_element(element, location, material_overrides=material_overrides)
        for element, location in _material_elements(root)
    ]
    return {
        "path": os.path.abspath(mtl_path),
        "materials": materials,
    }


def _counter_to_sorted_pairs(counter):
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _top_values(mapping, limit):
    return {
        key: _counter_to_sorted_pairs(counter)[:limit]
        for key, counter in sorted(mapping.items())
    }


def _counter_pairs_by_name(schema, key):
    return {
        row.get("name", ""): int(row.get("count", 0))
        for row in schema.get(key, [])
        if row.get("name")
    }


def _append_counter_diagnostics(diagnostics, schema, key, code, severity):
    for name, count in _counter_pairs_by_name(schema, key).items():
        if count <= 0:
            continue
        diagnostics.append(
            {
                "severity": severity,
                "code": code,
                "schema_counter": key,
                "name": name,
                "count": count,
                "message": f"MTL schema counter {key} contains {count} occurrence(s) of {name}.",
            }
        )


def _append_status_diagnostics(diagnostics, schema, key, status_codes, severity):
    counters = _counter_pairs_by_name(schema, key)
    for status, code in status_codes.items():
        count = counters.get(status, 0)
        if count <= 0:
            continue
        diagnostics.append(
            {
                "severity": severity,
                "code": code,
                "schema_counter": key,
                "name": status,
                "count": count,
                "message": f"MTL schema status {status} appears {count} time(s) in {key}.",
            }
        )


def build_mtl_schema_gate(report):
    schema = (report or {}).get("schema", {})
    diagnostics = []
    for key, code in MTL_SCHEMA_ERROR_COUNTERS.items():
        _append_counter_diagnostics(diagnostics, schema, key, code, "error")
    for key, status_codes in MTL_SCHEMA_ERROR_STATUS_COUNTERS.items():
        _append_status_diagnostics(diagnostics, schema, key, status_codes, "error")
    for key, code in MTL_SCHEMA_WARNING_COUNTERS.items():
        _append_counter_diagnostics(diagnostics, schema, key, code, "warning")
    for key, status_codes in MTL_SCHEMA_WARNING_STATUS_COUNTERS.items():
        _append_status_diagnostics(diagnostics, schema, key, status_codes, "warning")

    error_count = sum(1 for diagnostic in diagnostics if diagnostic["severity"] == "error")
    warning_count = sum(1 for diagnostic in diagnostics if diagnostic["severity"] == "warning")
    return {
        "schema": "cryengine_mtl_schema_gate.v1",
        "summary": {
            "ok": error_count == 0,
            "diagnostic_count": len(diagnostics),
            "error_count": error_count,
            "warning_count": warning_count,
        },
        "diagnostics": diagnostics,
    }


def build_mtl_schema_report(paths, limit=None, value_limit=12, include_files=True, material_overrides=None):
    files = []
    file_count = 0
    material_count = 0
    tokenized_material_count = 0
    multi_material_file_count = 0
    shader_counts = Counter()
    tag_counts = Counter()
    child_tag_counts = Counter()
    attribute_counts = Counter()
    public_param_counts = Counter()
    public_param_value_counts = Counter()
    attribute_policy_status_counts = Counter()
    attribute_policy_source_counts = Counter()
    attribute_policy_compatibility_default_counts = Counter()
    attribute_override_backed_counts = Counter()
    attribute_policy_diff_counts = Counter()
    attribute_policy_missing_counts = Counter()
    texture_map_counts = Counter()
    texture_map_reason_counts = Counter()
    texture_map_unknown_counts = Counter()
    texture_suffix_status_counts = Counter()
    texture_expected_suffix_counts = Counter()
    texture_path_reuse_diagnostic_counts = Counter()
    texmod_status_counts = Counter()
    texmod_compatibility_status_counts = Counter()
    texmod_attribute_counts = Counter()
    texmod_extra_attribute_counts = Counter()
    string_gen_mask_counts = Counter()
    gen_mask_literal_counts = Counter()
    token_counts = Counter()
    public_param_component_counts = Counter()
    public_param_compatibility_default_counts = Counter()
    public_param_override_backed_counts = Counter()
    mtl_flag_name_counts = Counter()
    mtl_flag_unknown_mask_counts = Counter()
    attributes_by_shader = defaultdict(Counter)
    public_params_by_shader = defaultdict(Counter)
    public_param_values_by_name = defaultdict(Counter)
    public_param_component_counts_by_name = defaultdict(Counter)
    texture_maps_by_shader = defaultdict(Counter)

    for index, mtl_path in enumerate(sorted(set(iter_mtl_files(paths)))):
        if limit is not None and index >= limit:
            break
        file_count += 1
        file_info = analyze_mtl_file(mtl_path, material_overrides=material_overrides)
        if include_files:
            files.append(file_info)
        if len(file_info["materials"]) > 1:
            multi_material_file_count += 1

        for material in file_info["materials"]:
            material_count += 1
            shader = material["shader"] or "<empty>"
            shader_counts[shader] += 1
            tag_counts[material["tag"]] += 1
            for child_tag in material["child_tags"]:
                child_tag_counts[child_tag] += 1
            for attr_name in material["attributes"]:
                attribute_counts[attr_name] += 1
                attributes_by_shader[shader][attr_name] += 1
            for attr_name, analysis in material["attribute_policy_analysis"]["entries"].items():
                status = analysis["status"]
                policy_status = analysis.get("policy_status", "")
                attribute_policy_status_counts.update([status])
                attribute_policy_source_counts.update([policy_status or "unknown_policy_status"])
                if analysis.get("override_backed"):
                    attribute_override_backed_counts.update([f"{attr_name}={analysis['actual']}"])
                if status == "missing_export_attribute":
                    attribute_policy_missing_counts.update([attr_name])
                elif status == "differs_from_export_attribute":
                    attribute_policy_diff_counts.update([f"{attr_name}={analysis['actual']}"])
                elif (
                    status == "matches_export_attribute"
                    and _is_compatibility_policy_status(policy_status)
                    and not analysis.get("override_backed")
                ):
                    attribute_policy_compatibility_default_counts.update([f"{attr_name}={analysis['actual']}"])
            for param_name in material["public_params"]:
                public_param_counts[param_name] += 1
                public_params_by_shader[shader][param_name] += 1
                param_value = material["public_params"][param_name]
                public_param_value_counts[f"{param_name}={param_value}"] += 1
                public_param_values_by_name[param_name][param_value] += 1
                param_analysis = material["public_param_analysis"].get(param_name, {})
                if param_analysis.get("override_backed"):
                    public_param_override_backed_counts[f"{param_name}={param_value}"] += 1
                elif BASE_PUBLIC_PARAMS.get(param_name) == param_value:
                    public_param_compatibility_default_counts[f"{param_name}={param_value}"] += 1
            for param_info in material["public_param_analysis"].values():
                public_param_component_counts[str(param_info["parsed_component_count"])] += 1
            for param_name, param_info in material["public_param_analysis"].items():
                component_count = str(param_info["parsed_component_count"])
                public_param_component_counts_by_name[param_name][component_count] += 1
            for flag_name in material["mtl_flags_analysis"]["names"]:
                mtl_flag_name_counts[flag_name] += 1
            unknown_mask = material["mtl_flags_analysis"]["unknown_mask"]
            if unknown_mask:
                mtl_flag_unknown_mask_counts[str(unknown_mask)] += 1
            for texture in material["textures"]:
                texture_map = texture["map"] or "<empty>"
                texture_map_counts[texture_map] += 1
                texture_maps_by_shader[shader][texture_map] += 1
                texture_map_analysis = texture["texture_map_analysis"]
                texture_map_reason_counts[texture_map_analysis["reason"]] += 1
                if not texture_map_analysis["known_ce_map"]:
                    texture_map_unknown_counts[texture_map] += 1
                suffix_analysis = texture_map_analysis["suffix_analysis"]
                texture_suffix_status_counts[suffix_analysis["suffix_status"]] += 1
                expected_suffix = suffix_analysis["expected_suffix"]
                if expected_suffix:
                    texture_expected_suffix_counts[expected_suffix] += 1
                texmod_analysis = texture["texmod_analysis"]
                texmod_status_counts[texmod_analysis["status"]] += 1
                if texmod_analysis["status"] in TEXMOD_COMPATIBILITY_STATUSES:
                    texmod_compatibility_status_counts[texmod_analysis["status"]] += 1
                for attr_name in texture["texmod"]:
                    texmod_attribute_counts[attr_name] += 1
                for attr_name in texmod_analysis["extra_attrs"]:
                    texmod_extra_attribute_counts[attr_name] += 1
            for diagnostic in material["texture_path_reuse_diagnostics"]:
                texture_path_reuse_diagnostic_counts[diagnostic["code"]] += 1
            if material["string_gen_mask"]:
                string_gen_mask_counts[material["string_gen_mask"]] += 1
            if material["gen_mask"]["literal"]:
                gen_mask_literal_counts[material["gen_mask"]["literal"]] += 1
            if material["tokens"]:
                tokenized_material_count += 1
            for token in material["tokens"]:
                token_counts[token] += 1

    summary = {
        "file_count": file_count,
        "material_count": material_count,
        "multi_material_file_count": multi_material_file_count,
        "tokenized_material_count": tokenized_material_count,
        "compatibility_preserved_default_count": (
            sum(attribute_policy_compatibility_default_counts.values())
            + sum(public_param_compatibility_default_counts.values())
            + sum(texmod_compatibility_status_counts.values())
        ),
    }
    report = {
        "files": files,
        "summary": summary,
        "schema": {
            "material_tags": _counter_to_sorted_pairs(tag_counts),
            "child_tags": _counter_to_sorted_pairs(child_tag_counts),
            "material_attributes": _counter_to_sorted_pairs(attribute_counts),
            "material_attribute_policy_statuses": _counter_to_sorted_pairs(attribute_policy_status_counts),
            "material_attribute_policy_sources": _counter_to_sorted_pairs(attribute_policy_source_counts),
            "material_attribute_compatibility_defaults": _counter_to_sorted_pairs(
                attribute_policy_compatibility_default_counts
            ),
            "material_attribute_override_backed_values": _counter_to_sorted_pairs(attribute_override_backed_counts),
            "material_attribute_policy_missing": _counter_to_sorted_pairs(attribute_policy_missing_counts),
            "material_attribute_policy_differences": _counter_to_sorted_pairs(attribute_policy_diff_counts),
            "public_params": _counter_to_sorted_pairs(public_param_counts),
            "public_param_values": _counter_to_sorted_pairs(public_param_value_counts)[:value_limit],
            "public_param_compatibility_defaults": _counter_to_sorted_pairs(
                public_param_compatibility_default_counts
            ),
            "public_param_override_backed_values": _counter_to_sorted_pairs(public_param_override_backed_counts),
            "public_param_component_counts": _counter_to_sorted_pairs(public_param_component_counts),
            "public_param_values_by_name": _top_values(public_param_values_by_name, value_limit),
            "public_param_component_counts_by_name": _top_values(public_param_component_counts_by_name, value_limit),
            "mtl_flag_names": _counter_to_sorted_pairs(mtl_flag_name_counts),
            "mtl_flag_unknown_masks": _counter_to_sorted_pairs(mtl_flag_unknown_mask_counts),
            "texture_maps": _counter_to_sorted_pairs(texture_map_counts),
            "texture_map_policy_reasons": _counter_to_sorted_pairs(texture_map_reason_counts),
            "texture_map_unknowns": _counter_to_sorted_pairs(texture_map_unknown_counts),
            "texture_suffix_statuses": _counter_to_sorted_pairs(texture_suffix_status_counts),
            "texture_expected_suffixes": _counter_to_sorted_pairs(texture_expected_suffix_counts),
            "texture_path_reuse_diagnostics": _counter_to_sorted_pairs(texture_path_reuse_diagnostic_counts),
            "texmod_statuses": _counter_to_sorted_pairs(texmod_status_counts),
            "texmod_compatibility_statuses": _counter_to_sorted_pairs(texmod_compatibility_status_counts),
            "texmod_attributes": _counter_to_sorted_pairs(texmod_attribute_counts),
            "texmod_extra_attributes": _counter_to_sorted_pairs(texmod_extra_attribute_counts),
            "shaders": _counter_to_sorted_pairs(shader_counts),
            "string_gen_masks": _counter_to_sorted_pairs(string_gen_mask_counts)[:value_limit],
            "gen_mask_literals": _counter_to_sorted_pairs(gen_mask_literal_counts)[:value_limit],
            "tokens": _counter_to_sorted_pairs(token_counts),
            "attributes_by_shader": _top_values(attributes_by_shader, value_limit),
            "public_params_by_shader": _top_values(public_params_by_shader, value_limit),
            "texture_maps_by_shader": _top_values(texture_maps_by_shader, value_limit),
        },
    }
    report["gate"] = build_mtl_schema_gate(report)
    return report


def write_mtl_schema_report(report, output_path):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return output_path


def load_material_overrides(overrides_path):
    if not overrides_path:
        return {}
    with open(overrides_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict) and isinstance(payload.get("material_overrides"), dict):
        return payload["material_overrides"]
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Material overrides JSON must be an object: {overrides_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize CryEngine .mtl XML schema usage.")
    parser.add_argument("paths", nargs="+", help="MTL files or directories to scan")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of .mtl files to scan")
    parser.add_argument("--value-limit", type=int, default=12, help="Maximum example values per grouped field")
    parser.add_argument("--summary-only", action="store_true", help="Omit per-file material records")
    parser.add_argument("--material-overrides", default="", help="Optional material override JSON for provenance")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args(argv)

    material_overrides = load_material_overrides(args.material_overrides) if args.material_overrides else {}
    report = build_mtl_schema_report(
        args.paths,
        limit=args.limit,
        value_limit=args.value_limit,
        include_files=not args.summary_only,
        material_overrides=material_overrides,
    )
    output = json.dumps(report, indent=2)
    if args.output:
        write_mtl_schema_report(report, args.output)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
