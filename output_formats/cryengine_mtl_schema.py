#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CryEngine material XML schema evidence used by the MTL exporter."""

# Source evidence:
# CRYENGINE_Source-release/Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp
CE_TEXTURE_MAP_TYPES = {
    "diffuse": "Diffuse",
    "normal": "Bumpmap",
    "specular": "Specular",
    "environment": "Environment",
    "detail": "Detail",
    "smoothness": "Smoothness",
    "height": "Heightmap",
    "displacement": "Heightmap",
    "decal": "Decal",
    "subsurface": "SubSurface",
    "custom": "Custom",
    "opacity": "Opacity",
    "alpha": "Opacity",
    "transparency": "Opacity",
    "mask": "Opacity",
    "translucency": "Translucency",
    "emissive": "Emittance",
    "emittance": "Emittance",
    "ao": None,
    "glossiness": None,
}

CE_TEXTURE_SUFFIXES = {
    "Diffuse": "_diff",
    "Bumpmap": "_ddn",
    "Specular": "_spec",
    "Environment": "_cm",
    "Detail": "_detail",
    "Smoothness": "_ddna",
    "Heightmap": "_displ",
    "SubSurface": "_sss",
    "Translucency": "_trans",
    "Emittance": "_em",
}

# Source evidence:
# CRYENGINE_Source-release/Engine/Shaders/Illum.ext
ILLUM_EXT_SHADER_MASKS = {
    "%NORMAL_MAP": 0x1,
    "%SPECULAR_MAP": 0x10,
    "%DETAIL_MAPPING": 0x4000,
    "%OFFSET_BUMP_MAPPING": 0x20000,
    "%VERTCOLORS": 0x400000,
    "%BILLBOARD": 0x2000,
    "%DECAL": 0x2000000,
    "%PARALLAX_OCCLUSION_MAPPING": 0x8000000,
    "%DISPLACEMENT_MAPPING": 0x10000000,
    "%PHONG_TESSELLATION": 0x20000000,
    "%PN_TESSELLATION": 0x40000000,
    "%DIRTLAYER": 0x200000,
    "%BLENDLAYER": 0x100,
    "%ALPHAMASK_DETAILMAP": 0x800000,
    "%SILHOUETTE_PARALLAX_OCCLUSION_MAPPING": 0x10000,
    "%SUBSURFACE_SCATTERING": 0x80000,
}

# Current exporter compatibility values. These predate the source-backed schema
# layer and must be replaced only after a real RC/Material Editor comparison.
EXPORT_COMPAT_SHADER_MASKS = {
    "%NORMAL_MAP": 0x4000000000000,
    "%SPECULAR_MAP": 0x80000,
    "%DISPLACEMENT_MAPPING": 0x200000000000,
    "%PHONG_TESSELLATION": 0x10000000000000,
    "%SUBSURFACE_SCATTERING": 0x20,
}

ALPHA_TEXTURE_TYPES = {"alpha", "transparency", "opacity", "mask"}

SUB_MATERIAL_DEFAULT_ATTRS = {
    "MtlFlags": "524416",
    "Shader": "Illum",
    "SurfaceType": "",
    "MatTemplate": "",
    "Diffuse": "1,1,1",
    "Specular": "1,1,1",
    "Emittance": "0,0,0,0",
    "Opacity": "1",
    "Shininess": "255",
}

BASE_PUBLIC_PARAMS = {
    "EmittanceMapGamma": "1",
    "SSSIndex": "0",
}

DISPLACEMENT_PUBLIC_PARAMS = {
    "TessellationDispBias": "0.5",
    "TessellationFactor": "1",
    "TessellationFactorMax": "32",
    "TessellationFactorMin": "1",
    "TessellationHeightScale": "1",
}


def exported_string_gen_mask(tokens):
    return "".join(sorted(set(tokens)))


def exported_gen_mask(tokens):
    gen_mask = 0
    for token in tokens:
        gen_mask |= EXPORT_COMPAT_SHADER_MASKS[token]
    return gen_mask
