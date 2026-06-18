#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert generic material dictionaries into CryEngine-style material data."""

import os
from copy import deepcopy

from output_formats.cryengine_mtl_schema import (
    BASE_PUBLIC_PARAMS,
    CE_TEXTURE_MAP_TYPES,
    SUB_MATERIAL_DEFAULT_ATTRS,
    exported_gen_mask,
    exported_string_gen_mask,
)


TEXTURE_TYPE_ALIASES = {
    "basecolor": "diffuse",
    "base_color": "diffuse",
    "color": "diffuse",
    "albedo": "diffuse",
    "diff": "diffuse",
    "diffuse": "diffuse",
    "n": "normal",
    "nrm": "normal",
    "normal": "normal",
    "ddn": "normal",
    "ddna": "normal",
    "bumpmap": "normal",
    "spec": "specular",
    "specular": "specular",
    "height": "displacement",
    "heightmap": "displacement",
    "disp": "displacement",
    "displ": "displacement",
    "displacement": "displacement",
    "em": "emissive",
    "emissive": "emissive",
    "emittance": "emissive",
    "opacity": "opacity",
    "alpha": "opacity",
    "mask": "opacity",
    "sss": "subsurface",
    "sub_surface": "subsurface",
    "subsurface": "subsurface",
}

FILENAME_SUFFIX_TYPES = (
    ("_basecolor", "diffuse"),
    ("_albedo", "diffuse"),
    ("_diffuse", "diffuse"),
    ("_diff", "diffuse"),
    ("_color", "diffuse"),
    ("_ddna", "normal"),
    ("_ddn", "normal"),
    ("_normal", "normal"),
    ("_nrm", "normal"),
    ("_n", "normal"),
    ("_specular", "specular"),
    ("_spec", "specular"),
    ("_displacement", "displacement"),
    ("_displ", "displacement"),
    ("_height", "displacement"),
    ("_disp", "displacement"),
    ("_emissive", "emissive"),
    ("_emission", "emissive"),
    ("_em", "emissive"),
    ("_opacity", "opacity"),
    ("_alpha", "opacity"),
    ("_mask", "opacity"),
    ("_sss", "subsurface"),
)

TEXTURE_MASK_TOKENS = {
    "normal": "%NORMAL_MAP",
    "specular": "%SPECULAR_MAP",
    "displacement": "%DISPLACEMENT_MAPPING",
    "subsurface": "%SUBSURFACE_SCATTERING",
}


def normalize_texture_type(texture_type):
    """Return the internal texture type used by the MTL exporter."""
    if texture_type is None:
        return None
    key = str(texture_type).strip().lower().replace(" ", "_").replace("-", "_")
    if key in TEXTURE_TYPE_ALIASES:
        return TEXTURE_TYPE_ALIASES[key]

    for internal_type, ce_map_type in CE_TEXTURE_MAP_TYPES.items():
        if ce_map_type and key == ce_map_type.lower():
            return internal_type
    return None


def infer_texture_type_from_path(texture_path):
    """Infer a texture type from a filename suffix without claiming certainty."""
    stem = os.path.splitext(os.path.basename(str(texture_path or "")))[0].lower()
    for suffix, texture_type in FILENAME_SUFFIX_TYPES:
        if stem.endswith(suffix):
            return texture_type
    return None


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

        normalized[texture_type] = raw_value
    return normalized


def _texture_map_to_ce_fields(textures):
    ce_textures = {}
    for texture_type, texture_path in textures.items():
        ce_map_type = CE_TEXTURE_MAP_TYPES.get(texture_type)
        if ce_map_type and texture_path:
            ce_textures[ce_map_type] = texture_path
    return ce_textures


def _shader_masks_for_textures(textures):
    tokens = {"%SUBSURFACE_SCATTERING"}
    for texture_type in textures:
        token = TEXTURE_MASK_TOKENS.get(texture_type)
        if token:
            tokens.add(token)
    return exported_gen_mask(tokens), exported_string_gen_mask(tokens)


class MaterialConverter:
    """Convert material dictionaries to the conservative CryEngine material shape."""

    def __init__(self):
        self.cryengine_template = {
            "Shader": SUB_MATERIAL_DEFAULT_ATTRS["Shader"],
            "GenMask": str(exported_gen_mask({"%SUBSURFACE_SCATTERING"})),
            "StringGenMask": exported_string_gen_mask({"%SUBSURFACE_SCATTERING"}),
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
            "PublicParams": dict(BASE_PUBLIC_PARAMS),
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
        if isinstance(material, dict):
            material.setdefault("textures", {})[normalized_type] = texture_path
        else:
            print(f"Setting {normalized_type} texture to {texture_path} for material {material}")
