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

# Source evidence:
# CRYENGINE_Source-release/Code/CryEngine/RenderDll/Common/Shaders/ShaderCore.cpp
COMMON_GLOBAL_LEGACY_FIX_MASKS = {
    "%ALPHAGLOW": 0x2,
    "%ALPHAMASK_DETAILMAP": 0x4,
    "%ANISO_SPECULAR": 0x8,
    "%BILINEAR_FP16": 0x10,
    "%BUMP_DIFFUSE": 0x20,
    "%CHARACTER_DECAL": 0x40,
    "%CUSTOM_SPECULAR": 0x400,
    "%DECAL": 0x800,
    "%DETAIL_BENDING": 0x1000,
    "%DETAIL_BUMP_MAPPING": 0x2000,
    "%DISABLE_RAIN_PASS": 0x4000,
    "%ENVIRONMENT_MAP": 0x10000,
    "%EYE_OVERLAY": 0x20000,
    "%GLOSS_DIFFUSEALPHA": 0x40000,
    "%GLOSS_MAP": 0x80000,
    "%GRADIENT_COLORING": 0x100000,
    "%GRASS": 0x200000,
    "%IRIS": 0x400000,
    "%LEAVES": 0x800000,
    "%NANOSUIT_EFFECTS": 0x1000000,
    "%OFFSET_BUMP_MAPPING": 0x2000000,
    "%BLENDTERRAIN": 0x4000000,
    "%PARALLAX_OCCLUSION_MAPPING": 0x8000000,
    "%REALTIME_MIRROR_REFLECTION": 0x10000000,
    "%REFRACTION_MAP": 0x20000000,
    "%RIM_LIGHTING": 0x40000000,
    "%SPECULARPOW_GLOSSALPHA": 0x80000000,
    "%BILLBOARD": 0x100000000,
    "%TEMP_TERRAIN": 0x200000000,
    "%TEMP_VEGETATION": 0x400000000,
    "%TERRAINHEIGHTADAPTION": 0x800000000,
    "%TWO_SIDED_SORTING": 0x1000000000,
    "%VERTCOLORS": 0x2000000000,
    "%WIND_BENDING": 0x4000000000,
    "%WRINKLE_BLENDING": 0x8000000000,
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
