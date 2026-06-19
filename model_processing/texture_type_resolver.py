#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared texture type normalization used by model/material processing."""

import os

from output_formats.cryengine_mtl_schema import CE_TEXTURE_MAP_TYPES


TEXTURE_TYPE_ALIASES = {
    "basecolor": "diffuse",
    "base_color": "diffuse",
    "color": "diffuse",
    "albedo": "diffuse",
    "diff": "diffuse",
    "diffuse": "diffuse",
    "diffuse_color": "diffuse",
    "n": "normal",
    "norm": "normal",
    "nrm": "normal",
    "normal": "normal",
    "normal_map": "normal",
    "ddn": "normal",
    "ddna": "normal",
    "bumpmap": "normal",
    "spec": "specular",
    "specular": "specular",
    "specular_color": "specular",
    "height": "displacement",
    "heightmap": "displacement",
    "bump": "displacement",
    "disp": "displacement",
    "displ": "displacement",
    "displacement": "displacement",
    "em": "emissive",
    "emission": "emissive",
    "emission_color": "emissive",
    "emissive": "emissive",
    "emittance": "emissive",
    "opacity": "alpha",
    "alpha": "alpha",
    "mask": "alpha",
    "ambient_occlusion": "ao",
    "occlusion": "ao",
    "ao": "ao",
    "rough": "roughness",
    "roughness": "roughness",
    "gloss": "glossiness",
    "glossiness": "glossiness",
    "glossy": "glossiness",
    "glossy_bsdf": "glossiness",
    "metal": "metallic",
    "metallic": "metallic",
    "metalness": "metallic",
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
    ("_col", "diffuse"),
    ("_d", "diffuse"),
    ("_ddna", "normal"),
    ("_ddn", "normal"),
    ("_normal", "normal"),
    ("_norm", "normal"),
    ("_nrm", "normal"),
    ("_nor_dx", "normal"),
    ("_nor_gl", "normal"),
    ("_nor", "normal"),
    ("_n", "normal"),
    ("_specular", "specular"),
    ("_spec", "specular"),
    ("_refl", "specular"),
    ("_s", "specular"),
    ("_displacement", "displacement"),
    ("_displ", "displacement"),
    ("_height", "displacement"),
    ("_disp", "displacement"),
    ("_bump", "displacement"),
    ("_h", "displacement"),
    ("_emissive", "emissive"),
    ("_emission", "emissive"),
    ("_glow", "emissive"),
    ("_em", "emissive"),
    ("_e", "emissive"),
    ("_opacity", "alpha"),
    ("_alpha", "alpha"),
    ("_transparency", "alpha"),
    ("_mask", "alpha"),
    ("_a", "alpha"),
    ("_ao", "ao"),
    ("_ambient", "ao"),
    ("_occlusion", "ao"),
    ("_roughness", "roughness"),
    ("_rough", "roughness"),
    ("_r", "roughness"),
    ("_glossiness", "glossiness"),
    ("_glossy", "glossiness"),
    ("_gloss", "glossiness"),
    ("_g", "glossiness"),
    ("_smoothness", "glossiness"),
    ("_metalness", "metallic"),
    ("_metallic", "metallic"),
    ("_metal", "metallic"),
    ("_m", "metallic"),
    ("_sss", "subsurface"),
    ("_subsurface", "subsurface"),
)

SUBSTRING_HINT_TYPES = (
    ("albedo", "diffuse"),
    ("diffuse", "diffuse"),
    ("color", "diffuse"),
    ("normal", "normal"),
    ("specular", "specular"),
    ("rough", "roughness"),
    ("gloss", "glossiness"),
    ("metal", "metallic"),
    ("emission", "emissive"),
    ("emissive", "emissive"),
    ("alpha", "alpha"),
    ("opacity", "alpha"),
    ("ambient", "ao"),
    ("occlusion", "ao"),
    ("height", "displacement"),
    ("displace", "displacement"),
    ("bump", "displacement"),
)


def _normalize_key(value):
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def normalize_texture_type(texture_type):
    """Return the internal texture type used by converter and extractor code."""
    key = _normalize_key(texture_type)
    if not key:
        return None
    if key in TEXTURE_TYPE_ALIASES:
        return TEXTURE_TYPE_ALIASES[key]

    for internal_type, ce_map_type in CE_TEXTURE_MAP_TYPES.items():
        if ce_map_type and key == _normalize_key(ce_map_type):
            return internal_type
    return None


def infer_texture_type_from_path(texture_path):
    """Infer a texture type from a filename suffix without claiming certainty."""
    stem = os.path.splitext(os.path.basename(str(texture_path or "")))[0].lower()
    for suffix, texture_type in FILENAME_SUFFIX_TYPES:
        if stem.endswith(suffix):
            return texture_type
    return None


def infer_texture_type_from_text(text):
    """Infer a texture type from a socket, node, or label string."""
    normalized = _normalize_key(text)
    if not normalized:
        return None

    direct = normalize_texture_type(normalized)
    if direct:
        return direct

    for hint, texture_type in SUBSTRING_HINT_TYPES:
        if hint in normalized:
            return texture_type
    return None
