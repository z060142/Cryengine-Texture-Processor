#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Processed texture output naming policy."""

import os

from output_formats.cryengine_mtl_schema import resolve_ce_texture_map


OUTPUT_TEXTURE_TYPE_BY_KEY = {
    "diff": "diffuse",
    "spec": "specular",
    "ddna": "normal",
    "displ": "displacement",
    "emissive": "emissive",
    "opacity": "opacity",
    "roughness": "roughness",
    "sss": "subsurface",
}


def texture_output_suffix(output_key, normal_alpha=False):
    if output_key == "ddna" and normal_alpha:
        return "_ddna"

    texture_type = OUTPUT_TEXTURE_TYPE_BY_KEY.get(output_key, "")
    policy = resolve_ce_texture_map(texture_type, "")
    expected_suffix = policy.get("suffix_analysis", {}).get("expected_suffix", "")
    return expected_suffix or f"_{output_key}"


def texture_output_filename(output_key, base_name, normal_alpha=False, extension="tif"):
    extension = str(extension or "tif").lstrip(".")
    return f"{base_name}{texture_output_suffix(output_key, normal_alpha=normal_alpha)}.{extension}"


def texture_output_path(output_key, base_name, output_dir, normal_alpha=False, extension="tif"):
    return os.path.join(
        output_dir,
        texture_output_filename(
            output_key,
            base_name,
            normal_alpha=normal_alpha,
            extension=extension,
        ),
    )
