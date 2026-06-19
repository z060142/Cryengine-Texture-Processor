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

# Source evidence:
# CRYENGINE_Source-release/Code/CryEngine/CryCommon/Cry3DEngine/IMaterial.h
MTL_FLAG_MULTI_SUBMTL = 0x0100
MTL_64BIT_SHADERGENMASK = 0x80000

MTL_SHADER_MASK_LOAD_POLICY = {
    "runtime_source": "Code/CryEngine/Cry3DEngine/MatMan.cpp",
    "runtime_lines": "451-475",
    "editor_load_source": "Code/Sandbox/EditorQt/Material/Material.cpp",
    "editor_load_lines": "887-915",
    "editor_save_source": "Code/Sandbox/EditorQt/Material/Material.cpp",
    "editor_save_lines": "1132-1137",
    "public_params_source": "Code/CryEngine/Cry3DEngine/MatMan.cpp",
    "public_params_lines": "813-830",
    "rule": (
        "GenMask is read first, but a present StringGenMask is converted through "
        "EF_GetShaderGlobalMaskGenFromString and becomes the effective shader mask. "
        "If StringGenMask is absent, GenMask is remapped through EF_GetRemapedShaderMaskGen. "
        "The Material Editor saves both GenMask and StringGenMask."
    ),
}

MTL_PUBLIC_PARAMS_POLICY = {
    "runtime_source": "Code/CryEngine/Cry3DEngine/MatMan.cpp",
    "runtime_lines": "800-830",
    "editor_save_source": "Code/CryEngine/Cry3DEngine/MaterialHelpers.cpp",
    "editor_save_lines": "774-803",
    "editor_cache_source": "Code/Sandbox/EditorQt/Material/Material.cpp",
    "editor_cache_lines": "523-533",
    "rule": (
        "PublicParams XML attributes are parsed into SShaderParam color/vector storage "
        "with sscanf(\"%f,%f,%f,%f\"). Missing components keep the zero value assigned "
        "before parsing. MaterialHelpers saves byte/short/int/float params as scalar "
        "attributes and color/vector params as Vec3 attributes."
    ),
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


def _parse_int_attr(value):
    value = str(value or "").strip()
    if not value:
        return 0
    return int(value, 16 if value.lower().startswith("0x") else 10)


def shader_mask_load_policy(material_attrs):
    """
    Return the source-backed shader-mask load policy for one .mtl Material node.

    This does not calculate renderer-specific masks. It records which XML field
    CryEngine runtime/editor load logic treats as authoritative.
    """
    attrs = dict(material_attrs or {})
    mtl_flags = _parse_int_attr(attrs.get("MtlFlags", ""))
    is_multi_submaterial = bool(mtl_flags & MTL_FLAG_MULTI_SUBMTL)
    has_string_gen_mask = "StringGenMask" in attrs
    has_gen_mask = "GenMask" in attrs
    has_64bit_flag = bool(mtl_flags & MTL_64BIT_SHADERGENMASK)

    if is_multi_submaterial:
        effective_source = "sub_materials"
        operation = "skip_multi_submaterial_container_shader_mask"
    elif has_string_gen_mask:
        effective_source = "StringGenMask"
        operation = "EF_GetShaderGlobalMaskGenFromString"
    elif has_gen_mask:
        effective_source = "GenMask"
        operation = "EF_GetRemapedShaderMaskGen"
    else:
        effective_source = "shader_default"
        operation = "load_shader_defaults"

    return {
        "effective_source": effective_source,
        "operation": operation,
        "has_gen_mask": has_gen_mask,
        "has_string_gen_mask": has_string_gen_mask,
        "has_64bit_shadergenmask_flag": has_64bit_flag,
        "is_multi_submaterial_container": is_multi_submaterial,
        "source_evidence": MTL_SHADER_MASK_LOAD_POLICY,
    }


def parse_public_param_value(value):
    """
    Parse a PublicParams XML attribute the way MatMan accepts it.

    CryEngine initializes all four components to zero, then parses up to four
    comma-separated floats. Scalar attrs therefore become [value, 0, 0, 0].
    """
    components = [0.0, 0.0, 0.0, 0.0]
    parsed_count = 0
    raw_parts = str(value or "").split(",")

    for index, raw_part in enumerate(raw_parts[:4]):
        raw_part = raw_part.strip()
        if not raw_part:
            break
        try:
            components[index] = float(raw_part)
        except ValueError:
            break
        parsed_count += 1

    return {
        "raw": str(value or ""),
        "components": components,
        "parsed_component_count": parsed_count,
        "source_evidence": MTL_PUBLIC_PARAMS_POLICY,
    }


def analyze_public_params(public_params):
    return {
        name: parse_public_param_value(value)
        for name, value in sorted((public_params or {}).items())
    }
