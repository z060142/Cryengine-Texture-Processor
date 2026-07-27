#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert generic material dictionaries into CryEngine-style material data."""

import os
from copy import deepcopy

from model_processing.texture_type_resolver import (
    infer_texture_type_from_path,
    normalize_texture_type,
)
from output_formats.cryengine_mtl_schema import (
    SUB_MATERIAL_DEFAULT_ATTRS,
    exported_material_shader_policy,
    resolve_ce_texture_map,
)


def _coerce_material_name(material):
    if isinstance(material, dict):
        return material.get("name") or material.get("Name") or "Material"
    return getattr(material, "name", "Material")


def _normalize_texture_map(texture_map):
    """
    Normalize texture references to internal texture keys.

    Supported inputs:
    - {"diffuse": "path/to/asset_diff.tif"}
    - {"Diffuse": "path/to/asset_diff.tif"}
    - {"path/to/source_albedo.png": "path/to/asset_diff.tif"}
    """
    normalized = {}
    for raw_key, raw_value in (texture_map or {}).items():
        if not raw_value:
            continue

        texture_type = normalize_texture_type(raw_key)
        if texture_type is None:
            texture_type = infer_texture_type_from_path(raw_value)
        if texture_type is None:
            texture_type = infer_texture_type_from_path(raw_key)
        if texture_type is None:
            continue
        if texture_type == "alpha":
            texture_type = "opacity"

        normalized[texture_type] = raw_value
    return normalized


def _texture_map_to_ce_fields(textures):
    ce_textures = {}
    for texture_type, texture_path in textures.items():
        texture_policy = resolve_ce_texture_map(texture_type, texture_path)
        if texture_policy["exported"]:
            ce_textures[texture_policy["ce_map_type"]] = texture_path
    return ce_textures


def _shader_masks_for_textures(textures):
    policy = exported_material_shader_policy(textures)
    return policy["gen_mask"], policy["string_gen_mask"]


class MaterialConverter:
    """Convert material dictionaries to the conservative CryEngine material shape."""

    def __init__(self):
        shader_policy = exported_material_shader_policy({})
        self.cryengine_template = {
            "Shader": SUB_MATERIAL_DEFAULT_ATTRS["Shader"],
            "GenMask": str(shader_policy["gen_mask"]),
            "StringGenMask": shader_policy["string_gen_mask"],
            "SubMtlCount": "0",
            "Textures": {
                "Diffuse": "",
                "Specular": "",
                "Bumpmap": "",
                "Heightmap": "",
                "Emittance": "",
                "Opacity": "",
                "SubSurface": "",
            },
            "PublicParams": dict(shader_policy["public_params"]),
        }

    def convert(self, material, texture_map):
        """
        Convert a material-like object to CryEngine-style material data.

        This is a conservative data conversion layer. It does not inspect live
        Blender node graphs unless the caller passes texture information in
        `texture_map`.
        """
        cryengine_material = deepcopy(self.cryengine_template)
        cryengine_material["Name"] = _coerce_material_name(material)

        normalized_textures = _normalize_texture_map(texture_map)
        for ce_map_type, texture_path in _texture_map_to_ce_fields(normalized_textures).items():
            cryengine_material["Textures"][ce_map_type] = texture_path

        gen_mask, string_gen_mask = _shader_masks_for_textures(normalized_textures)
        cryengine_material["GenMask"] = str(gen_mask)
        cryengine_material["StringGenMask"] = string_gen_mask
        return cryengine_material

    def _determine_texture_type(self, node, material=None):
        """Infer a texture node type from explicit labels or image filepath."""
        del material
        for attr in ("label", "name"):
            texture_type = normalize_texture_type(getattr(node, attr, None))
            if texture_type:
                return texture_type

        image = getattr(node, "image", None)
        texture_type = infer_texture_type_from_path(getattr(image, "filepath", ""))
        return texture_type or "diffuse"

    def apply_to_material(self, material, cryengine_material):
        """
        Attach converted CryEngine material data to a material-like object.

        Dict materials are updated in place. Other objects receive a
        `cryengine_material` attribute when Python allows it.
        """
        converted = deepcopy(cryengine_material)
        if isinstance(material, dict):
            material["cryengine_material"] = converted
            return material

        try:
            setattr(material, "cryengine_material", converted)
        except Exception:
            pass
        return material

    def _set_texture_node(self, material, texture_type, texture_path):
        """
        Record a texture assignment on dict materials.

        Live Blender material node editing belongs in the FBX exporter path; this
        converter only records normalized data when given plain material dicts.
        """
        normalized_type = normalize_texture_type(texture_type) or str(texture_type)
        if normalized_type == "alpha":
            normalized_type = "opacity"
        if isinstance(material, dict):
            material.setdefault("textures", {})[normalized_type] = texture_path
        else:
            print(f"Setting {normalized_type} texture to {texture_path} for material {material}")
