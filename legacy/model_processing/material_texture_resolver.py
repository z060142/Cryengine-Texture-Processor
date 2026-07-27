#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Shared helpers for resolving model materials to processed CryEngine textures.

The first refactor keeps the existing behavior, but moves the rules into one
place so the next phase can swap them for RC-accurate material/sub-index logic.
"""

import os
import re

from model_processing.material_manifest import material_manifest_materials
from model_processing.texture_type_resolver import FILENAME_SUFFIX_TYPES, infer_texture_type_from_path
from output_formats.cryengine_mtl_schema import RC_TEXTURE_SOURCE_EXTENSIONS
from output_formats.texture_output_paths import texture_output_suffix

IGNORED_MATERIAL_NAMES = {"Material", "Dots Stroke"}
DEFAULT_TEXTURE_OUTPUT_EXTENSION = "tif"
AUTO_TEXTURE_OUTPUT_EXTENSIONS = ("dds", "hdr", "tif")
CE_TEXTURE_OUTPUT_EQUIVALENT_EXTENSIONS = {
    "dds": ("tif",),
    "tif": ("dds",),
}

COMMON_TEXTURE_BASE_SUFFIXES = tuple(suffix for suffix, _ in FILENAME_SUFFIX_TYPES)
MTL_MATERIAL_OVERRIDE_KEYS = (
    "cryengine_material",
    "ce_material",
    "mtl_overrides",
    "material_attrs",
    "mtl_attrs",
    "public_params",
    "PublicParams",
    "shader",
    "Shader",
    "GenMask",
    "StringGenMask",
    "gen_mask",
    "string_gen_mask",
)


def _suffix_template(output_key, normal_alpha=False):
    return f"{texture_output_suffix(output_key, normal_alpha=normal_alpha)}.{{ext}}"


FBX_OUTPUT_TEXTURE_SUFFIXES = {
    "diff": (_suffix_template("diff"),),
    "ddna": (_suffix_template("ddna", normal_alpha=True), _suffix_template("ddna")),
}

MTL_OUTPUT_TEXTURE_SUFFIXES = {
    "diffuse": (_suffix_template("diff"),),
    "normal": (_suffix_template("ddna", normal_alpha=True), _suffix_template("ddna")),
    "specular": (_suffix_template("spec"),),
    "displacement": (_suffix_template("displ"),),
    "emissive": (_suffix_template("emissive"),),
    "opacity": ("_opacity.{ext}",),
    "roughness": ("_roughness.{ext}",),
    "sss": (_suffix_template("sss"),),
}


def clean_material_name(material_name):
    """Return the material name that should be emitted to RC-visible files."""
    return material_name or "UnnamedMaterial"


def iter_model_materials(materials, ignored_names=IGNORED_MATERIAL_NAMES):
    """Yield material dicts except known Blender/default placeholders."""
    for index, material in enumerate(materials or []):
        material_name = material.get("name", f"Material_{index}")
        if material_name in ignored_names:
            continue
        yield material_name, material


def iter_unique_clean_materials(materials, ignored_names=IGNORED_MATERIAL_NAMES):
    """
    Yield materials with exact duplicate names collapsed.

    The yielded index is contiguous and matches the existing JSON exporter
    behavior. Blender suffixes such as `.001` are preserved because RC can use
    them as distinct FBX material table names.
    """
    seen_clean_names = set()
    sub_index = 0

    for material_name, material in iter_model_materials(materials, ignored_names):
        clean_name = clean_material_name(material_name)
        if clean_name in seen_clean_names:
            print(f"Skipping exact duplicate material name: {material_name}")
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


def texture_ref_type(ref):
    """Return a normalized texture type for a texture reference when known."""
    texture_type = getattr(ref, "texture_type", None)
    if texture_type:
        return texture_type
    return infer_texture_type_from_path(getattr(ref, "path", ""))


def strip_known_texture_suffix(filename_no_ext, suffixes=COMMON_TEXTURE_BASE_SUFFIXES):
    """Strip one known texture suffix from a filename stem."""
    candidate = filename_no_ext or ""
    candidate_lower = candidate.lower()
    for suffix in suffixes:
        if candidate_lower.endswith(suffix):
            return candidate[: -len(suffix)]
    return candidate


def texture_ref_evidence(material_refs):
    """Summarize texture reference evidence used to resolve processed outputs."""
    evidence = []
    for ref in material_refs or []:
        ref_path = getattr(ref, "path", "")
        evidence.append(
            {
                "path": ref_path,
                "filename": os.path.basename(ref_path) if ref_path else getattr(ref, "filename", ""),
                "texture_type": texture_ref_type(ref),
                "source_mode": getattr(ref, "source_mode", ""),
            }
        )
    return evidence


def _external_material_texture_table(model_data):
    raw = (
        model_data.get("external_material_texture_evidence")
        or model_data.get("obj_mtl_report")
        or {}
    )
    if not raw:
        return {}

    materials = raw.get("materials", raw) if isinstance(raw, dict) else raw
    table = {}
    if isinstance(materials, dict):
        iterable = materials.items()
    else:
        iterable = []
        if isinstance(materials, list):
            iterable = ((item.get("name"), item) for item in materials if isinstance(item, dict))

    for material_name, material in iterable:
        if not material_name or not isinstance(material, dict):
            continue
        textures = material.get("textures", [])
        if isinstance(textures, dict):
            textures = [
                {
                    "texture_type": texture_type,
                    "file": texture_path,
                    "filename": os.path.basename(str(texture_path)),
                }
                for texture_type, texture_path in textures.items()
                if texture_path
            ]
        texture_rows = [texture for texture in textures if isinstance(texture, dict)]
        material_name = str(material_name)
        table[material_name] = texture_rows
        normalized_name = _loose_material_key(material_name)
        if normalized_name and normalized_name not in table:
            table[normalized_name] = texture_rows
    return table


def _loose_material_key(material_name):
    key = str(material_name or "").lower()
    key = re.sub(r"(?:_?mat|_?sg)$", "", key)
    key = re.sub(r"[^a-z0-9]+", "", key)
    return key


def _external_refs_for_material(external_refs_by_material, material_name):
    return (
        external_refs_by_material.get(material_name)
        or external_refs_by_material.get(_loose_material_key(material_name))
        or []
    )


def external_texture_evidence(material_name, model_data):
    """Return optional OBJ-MTL/native evidence rows for a material name."""
    rows = _external_refs_for_material(_external_material_texture_table(model_data), material_name)
    evidence = []
    for row in rows:
        ref_path = row.get("file") or row.get("path") or row.get("filename") or ""
        evidence.append(
            {
                "path": ref_path,
                "filename": os.path.basename(ref_path) if ref_path else row.get("filename", ""),
                "texture_type": row.get("texture_type") or row.get("type", ""),
                "source_mode": row.get("source_mode", "external_obj_mtl"),
            }
        )
    return evidence


def material_mtl_overrides(material):
    return {
        key: material[key]
        for key in MTL_MATERIAL_OVERRIDE_KEYS
        if key in material
    }


def _material_override_table(model_data):
    raw_overrides = (
        model_data.get("mtl_material_overrides")
        or model_data.get("material_overrides")
        or {}
    )
    if isinstance(raw_overrides, dict):
        return {
            str(name): override
            for name, override in raw_overrides.items()
            if name and isinstance(override, dict)
        }
    if isinstance(raw_overrides, list):
        overrides = {}
        for item in raw_overrides:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("Name")
            if name:
                overrides[str(name)] = item
        return overrides
    return {}


def resolve_base_name(material_refs, texture_manager, suffixes=COMMON_TEXTURE_BASE_SUFFIXES, external_refs=None):
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

    for ref in external_refs or []:
        ref_path = ref.get("file") or ref.get("path") or ref.get("filename") or ""
        if not ref_path:
            continue
        texture_type = ref.get("texture_type") or ref.get("type", "")
        if texture_type in {"normal", "bump"} and not any(
            preferred.get("texture_type") in {"diffuse", "ambient", "specular", "reflection"}
            for preferred in external_refs or []
            if isinstance(preferred, dict)
        ):
            continue
        filename_no_ext = os.path.splitext(os.path.basename(ref_path))[0]
        base_name = strip_known_texture_suffix(filename_no_ext, suffixes)
        if base_name:
            return base_name

    return None


def find_processed_textures(base_name, texture_output_dir, output_format, suffix_map):
    """Find existing processed output textures for a material base name."""
    processed_textures = {}
    if not base_name or not texture_output_dir:
        return processed_textures

    extensions = texture_output_extensions(output_format)
    for texture_key, suffix_templates in suffix_map.items():
        if isinstance(suffix_templates, str):
            suffix_templates = (suffix_templates,)
        for ext in extensions:
            for suffix_template in suffix_templates:
                expected_filename = f"{base_name}{suffix_template.format(ext=ext)}"
                expected_path = os.path.join(texture_output_dir, expected_filename)
                if os.path.exists(expected_path):
                    processed_textures[texture_key] = expected_path
                    break
            if texture_key in processed_textures:
                break

    return processed_textures


def texture_output_extensions(output_format):
    """Return the processed texture extensions to probe, in priority order."""
    if isinstance(output_format, (list, tuple)):
        raw_extensions = output_format
    else:
        raw_value = str(output_format or DEFAULT_TEXTURE_OUTPUT_EXTENSION)
        if raw_value.strip().lower() == "auto":
            raw_extensions = AUTO_TEXTURE_OUTPUT_EXTENSIONS
        else:
            raw_extensions = raw_value.replace(";", ",").split(",")

    requested_extensions = []
    seen = set()
    supported_extensions = set(RC_TEXTURE_SOURCE_EXTENSIONS)
    for ext in raw_extensions:
        normalized = str(ext or "").strip().lstrip(".").lower()
        if not normalized or normalized in seen or normalized not in supported_extensions:
            continue
        seen.add(normalized)
        requested_extensions.append(normalized)

    if not requested_extensions:
        requested_extensions = [DEFAULT_TEXTURE_OUTPUT_EXTENSION]

    extensions = []
    requested_set = set(requested_extensions)
    seen.clear()
    for ext in requested_extensions:
        if ext not in seen:
            extensions.append(ext)
            seen.add(ext)
        for equivalent_ext in CE_TEXTURE_OUTPUT_EQUIVALENT_EXTENSIONS.get(ext, ()):
            if equivalent_ext in requested_set or equivalent_ext in seen:
                continue
            extensions.append(equivalent_ext)
            seen.add(equivalent_ext)
    return extensions


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
    external_refs_by_material = _external_material_texture_table(model_data)
    records = []

    source_materials = material_manifest_materials(
        model_data.get("materials", []),
        model_data.get("material_manifest"),
    )
    overrides_by_name = _material_override_table(model_data)
    for material_name, material in iter_model_materials(source_materials):
        material = {
            **material,
            **overrides_by_name.get(material_name, {}),
        }
        material_refs = refs_by_material.get(material_name, [])
        external_refs = _external_refs_for_material(external_refs_by_material, material_name)
        base_name = resolve_base_name(material_refs, texture_manager, external_refs=external_refs)
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
                    "polygon_count": material.get("polygon_count"),
                    "face_count": material.get("face_count"),
                    "used_polygon_count": material.get("used_polygon_count"),
                    "used_by_polygons": material.get("used_by_polygons"),
                    "mesh_names": material.get("mesh_names", []),
                    "material_names": material.get("material_names", []),
                    "slot_name_conflict": material.get("slot_name_conflict", False),
                    "base_name": base_name,
                    "textures": processed_textures,
                    "texture_ref_evidence": texture_ref_evidence(material_refs)
                    + external_texture_evidence(material_name, model_data),
                    "source_texture_count": len(material_refs),
                    "external_texture_count": len(external_refs),
                    "mtl_overrides": material_mtl_overrides(material),
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
    materials = [
        {
            "name": record["name"],
            "clean_name": record["clean_name"],
            "id": record["id"],
            "index": record["index"],
            "sub_index": record["sub_index"],
            "auto_assigned": record["auto_assigned"],
            "deleted": record["deleted"],
            "is_dummy": record["is_dummy"],
            "polygon_count": record["polygon_count"],
            "face_count": record["face_count"],
            "used_polygon_count": record["used_polygon_count"],
            "used_by_polygons": record["used_by_polygons"],
            "mesh_names": record["mesh_names"],
            "material_names": record["material_names"],
            "slot_name_conflict": record["slot_name_conflict"],
            "textures": record["textures"],
            "texture_ref_evidence": record["texture_ref_evidence"],
            **record.get("mtl_overrides", {}),
        }
        for record in records
    ]
    model_data = args[0] if args else kwargs.get("model_data", {})
    return material_manifest_materials(materials, model_data.get("material_manifest"))
