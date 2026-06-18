#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Summarize CryEngine .mtl XML schema usage from real material files."""

import argparse
from collections import Counter, defaultdict
import json
import os
import xml.etree.ElementTree as ET

from tools.mtl_mask_report import parse_gen_mask_literal, string_gen_mask_tokens


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


def _texture_entries(element):
    textures = element.find("Textures")
    if textures is None:
        return []
    entries = []
    for texture in list(textures):
        if texture.tag != "Texture":
            continue
        entries.append(
            {
                "map": texture.get("Map", ""),
                "file": texture.get("File", ""),
                "attributes": _attributes(texture),
                "texmod": _child_attributes(texture, "TexMod"),
            }
        )
    return entries


def analyze_material_element(element, location):
    gen_mask = parse_gen_mask_literal(
        element.get("GenMask", ""),
        prefer_hex_for_string_mask=bool(element.get("StringGenMask", "")),
    )
    tokens = string_gen_mask_tokens(element.get("StringGenMask", ""))
    return {
        "location": location,
        "tag": element.tag,
        "name": element.get("Name", ""),
        "shader": element.get("Shader", ""),
        "mtl_flags": element.get("MtlFlags", ""),
        "gen_mask": gen_mask,
        "string_gen_mask": element.get("StringGenMask", ""),
        "tokens": tokens,
        "attributes": _attributes(element),
        "public_params": _child_attributes(element, "PublicParams"),
        "textures": _texture_entries(element),
        "child_tags": [child.tag for child in list(element)],
    }


def analyze_mtl_file(mtl_path):
    root = ET.parse(mtl_path).getroot()
    materials = [
        analyze_material_element(element, location)
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


def build_mtl_schema_report(paths, limit=None, value_limit=12, include_files=True):
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
    texture_map_counts = Counter()
    string_gen_mask_counts = Counter()
    gen_mask_literal_counts = Counter()
    token_counts = Counter()
    attributes_by_shader = defaultdict(Counter)
    public_params_by_shader = defaultdict(Counter)
    texture_maps_by_shader = defaultdict(Counter)

    for index, mtl_path in enumerate(sorted(set(iter_mtl_files(paths)))):
        if limit is not None and index >= limit:
            break
        file_count += 1
        file_info = analyze_mtl_file(mtl_path)
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
            for param_name in material["public_params"]:
                public_param_counts[param_name] += 1
                public_params_by_shader[shader][param_name] += 1
            for texture in material["textures"]:
                texture_map = texture["map"] or "<empty>"
                texture_map_counts[texture_map] += 1
                texture_maps_by_shader[shader][texture_map] += 1
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
    }
    return {
        "files": files,
        "summary": summary,
        "schema": {
            "material_tags": _counter_to_sorted_pairs(tag_counts),
            "child_tags": _counter_to_sorted_pairs(child_tag_counts),
            "material_attributes": _counter_to_sorted_pairs(attribute_counts),
            "public_params": _counter_to_sorted_pairs(public_param_counts),
            "texture_maps": _counter_to_sorted_pairs(texture_map_counts),
            "shaders": _counter_to_sorted_pairs(shader_counts),
            "string_gen_masks": _counter_to_sorted_pairs(string_gen_mask_counts)[:value_limit],
            "gen_mask_literals": _counter_to_sorted_pairs(gen_mask_literal_counts)[:value_limit],
            "tokens": _counter_to_sorted_pairs(token_counts),
            "attributes_by_shader": _top_values(attributes_by_shader, value_limit),
            "public_params_by_shader": _top_values(public_params_by_shader, value_limit),
            "texture_maps_by_shader": _top_values(texture_maps_by_shader, value_limit),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Summarize CryEngine .mtl XML schema usage.")
    parser.add_argument("paths", nargs="+", help="MTL files or directories to scan")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of .mtl files to scan")
    parser.add_argument("--value-limit", type=int, default=12, help="Maximum example values per grouped field")
    parser.add_argument("--summary-only", action="store_true", help="Omit per-file material records")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args(argv)

    report = build_mtl_schema_report(
        args.paths,
        limit=args.limit,
        value_limit=args.value_limit,
        include_files=not args.summary_only,
    )
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
