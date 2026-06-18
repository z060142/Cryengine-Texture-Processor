#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared helpers for resolving model materials to processed CryEngine textures.

The first refactor keeps the existing behavior, but moves the rules into one
place so the next phase can swap them for RC-accurate material/sub-index logic.
"""

import os
import re


IGNORED_MATERIAL_NAMES = {"Material", "Dots Stroke"}

COMMON_TEXTURE_BASE_SUFFIXES = (
    "_diffuse",
    "_diff",
    "_color",
    "_albedo",
    "_basecolor",
    "_n",
    "_normal",
    "_nrm",
    "_ddn",
    "_ddna",
    "_spec",
    "_specular",
    "_h",
    "_height",
    "_disp",
    "_displ",
    "_displacement",
    "_e",
    "_emissive",
    "_emission",
    "_glow",
)

FBX_OUTPUT_TEXTURE_SUFFIXES = {
    "diff": "_diff.{ext}",
    "ddna": "_ddna.{ext}",
}

MTL_OUTPUT_TEXTURE_SUFFIXES = {
    "diffuse": "_diff.{ext}",
    "normal": "_ddna.{ext}",
    "specular": "_spec.{ext}",
    "displacement": "_displ.{ext}",
    "emissive": "_emissive.{ext}",
    "opacity": "_opacity.{ext}",
    "sss": "_sss.{ext}",
}


def clean_material_name(material_name):
    """Remove Blender duplicate suffixes such as .001 while preserving the base name."""
    return re.sub(r"\.[0-9]{3}$", "", material_name or "UnnamedMaterial")


def iter_model_materials(materials, ignored_names=IGNORED_MATERIAL_NAMES):
    """Yield material dicts except known Blender/default placeholders."""
    for index, material in enumerate(materials or []):
        material_name = material.get("name", f"Material_{index}")
        if material_name in ignored_names:
            continue
        yield material_name, material


def iter_unique_clean_materials(materials, ignored_names=IGNORED_MATERIAL_NAMES):
    """
    Yield materials with duplicate Blender suffixes collapsed.

    The yielded index is contiguous and matches the existing JSON exporter
    behavior. This is not yet RC's full material auto-assignment algorithm.
    """
    seen_clean_names = set()
    sub_index = 0

    for material_name, material in iter_model_materials(materials, ignored_names):
        clean_name = clean_material_name(material_name)
        if clean_name in seen_clean_names:
            print(f"Skipping duplicate material after cleaning: {material_name} -> {clean_name}")
            continue

        seen_clean_names.add(clean_name)
        yield {
            "original_name": material_name,
            "clean_name": clean_name,
            "sub_index": sub_index,
            "material": material,
        }
        sub_index += 1


def group_texture_refs_by_material(texture_refs):
    """Return a material-name keyed lookup for extracted texture references."""
    refs_by_material = {}
    for ref in texture_refs or []:
        material_name = getattr(ref, "material_name", None)
        refs_by_material.setdefault(material_name, []).append(ref)
    return refs_by_material


def strip_known_texture_suffix(filename_no_ext, suffixes=COMMON_TEXTURE_BASE_SUFFIXES):
    """Strip one known texture suffix from a filename stem."""
    candidate = filename_no_ext or ""
    candidate_lower = candidate.lower()
    for suffix in suffixes:
        if candidate_lower.endswith(suffix):
            return candidate[: -len(suffix)]
    return candidate


def resolve_base_name(material_refs, texture_manager, suffixes=COMMON_TEXTURE_BASE_SUFFIXES):
    """
    Resolve the processed texture base name for a material.

    Existing behavior is preserved: prefer TextureManager.classify_texture() for
    existing source textures, then fall back to stripping common suffixes from
    the first referenced filename.
    """
    for ref in material_refs or []:
        ref_path = getattr(ref, "path", None)
        if ref_path and os.path.exists(ref_path) and texture_manager:
            try:
                _, potential_base = texture_manager.classify_texture(ref_path)
                if potential_base:
                    return potential_base
            except Exception:
                pass

    for ref in material_refs or []:
        ref_path = getattr(ref, "path", None)
        if ref_path:
            filename_no_ext = os.path.splitext(os.path.basename(ref_path))[0]
            return strip_known_texture_suffix(filename_no_ext, suffixes)

    return None


def find_processed_textures(base_name, texture_output_dir, output_format, suffix_map):
    """Find existing processed output textures for a material base name."""
    processed_textures = {}
    if not base_name or not texture_output_dir:
        return processed_textures

    ext = (output_format or "tif").lstrip(".")
    for texture_key, suffix_template in suffix_map.items():
        expected_filename = f"{base_name}{suffix_template.format(ext=ext)}"
        expected_path = os.path.join(texture_output_dir, expected_filename)
        if os.path.exists(expected_path):
            processed_textures[texture_key] = expected_path

    return processed_textures


def build_material_texture_records(
    model_data,
    texture_refs,
    texture_manager,
    texture_output_dir,
    output_format="tif",
    suffix_map=None,
    include_empty=False,
):
    """
    Build material records with processed texture paths.

    Args:
        model_data: Loaded model dict.
        texture_refs: TextureReference objects extracted from the model.
        texture_manager: TextureManager used for filename classification.
        texture_output_dir: Directory containing processed textures.
        output_format: File extension selected by the UI.
        suffix_map: Mapping from output texture key to filename suffix template.
        include_empty: Keep materials even if no processed textures were found.

    Returns:
        List of records containing material name, base name, and texture paths.
    """
    suffix_map = suffix_map or MTL_OUTPUT_TEXTURE_SUFFIXES
    refs_by_material = group_texture_refs_by_material(texture_refs)
    records = []

    for material_name, material in iter_model_materials(model_data.get("materials", [])):
        material_refs = refs_by_material.get(material_name, [])
        base_name = resolve_base_name(material_refs, texture_manager)
        processed_textures = find_processed_textures(
            base_name,
            texture_output_dir,
            output_format,
            suffix_map,
        )

        if processed_textures or include_empty:
            records.append(
                {
                    "name": material_name,
                    "clean_name": clean_material_name(material_name),
                    "id": material.get("id"),
                    "index": material.get("index"),
                    "sub_index": material.get("sub_index"),
                    "auto_assigned": material.get("auto_assigned", material.get("ui_autoflag", True)),
                    "deleted": material.get("deleted", False),
                    "is_dummy": material.get("is_dummy", False),
                    "base_name": base_name,
                    "textures": processed_textures,
                    "source_texture_count": len(material_refs),
                }
            )
        elif not base_name:
            print(f"Warning: Could not determine base name for material '{material_name}'.")

    return records


def build_fbx_texture_data(*args, **kwargs):
    """Return FbxExporter's expected material-name keyed texture dictionary."""
    kwargs["suffix_map"] = FBX_OUTPUT_TEXTURE_SUFFIXES
    kwargs["include_empty"] = False
    records = build_material_texture_records(*args, **kwargs)
    return {record["name"]: record["textures"] for record in records if record["textures"]}


def build_mtl_material_data(*args, **kwargs):
    """Return export_mtl's expected list of material dictionaries."""
    kwargs["suffix_map"] = MTL_OUTPUT_TEXTURE_SUFFIXES
    kwargs["include_empty"] = True
    records = build_material_texture_records(*args, **kwargs)
    return [
        {
            "name": record["name"],
            "clean_name": record["clean_name"],
            "id": record["id"],
            "index": record["index"],
            "sub_index": record["sub_index"],
            "auto_assigned": record["auto_assigned"],
            "deleted": record["deleted"],
            "is_dummy": record["is_dummy"],
            "textures": record["textures"],
        }
        for record in records
    ]
