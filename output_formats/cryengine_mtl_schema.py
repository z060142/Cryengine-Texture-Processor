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
MTL_FLAG_WIRE = 0x0001
MTL_FLAG_2SIDED = 0x0002
MTL_FLAG_ADDITIVE = 0x0004
MTL_FLAG_DETAIL_DECAL = 0x0008
MTL_FLAG_LIGHTING = 0x0010
MTL_FLAG_NOSHADOW = 0x0020
MTL_FLAG_ALWAYS_USED = 0x0040
MTL_FLAG_PURE_CHILD = 0x0080
MTL_FLAG_MULTI_SUBMTL = 0x0100
MTL_FLAG_NOPHYSICALIZE = 0x0200
MTL_FLAG_NODRAW = 0x0400
MTL_FLAG_NOPREVIEW = 0x0800
MTL_FLAG_NOTINSTANCED = 0x1000
MTL_FLAG_COLLISION_PROXY = 0x2000
MTL_FLAG_SCATTER = 0x4000
MTL_FLAG_REQUIRE_FORWARD_RENDERING = 0x8000
MTL_FLAG_NON_REMOVABLE = 0x10000
MTL_FLAG_HIDEONBREAK = 0x20000
MTL_FLAG_UIMATERIAL = 0x40000
MTL_64BIT_SHADERGENMASK = 0x80000
MTL_FLAG_RAYCAST_PROXY = 0x100000
MTL_FLAG_REQUIRE_NEAREST_CUBEMAP = 0x200000
MTL_FLAG_CONSOLE_MAT = 0x400000
MTL_FLAG_BLEND_TERRAIN = 0x1000000
MTL_FLAG_TRACEABLE_TEXTURE = 0x2000000
MTL_FLAG_REFRACTIVE = 0x4000000

MTL_FLAG_NAMES = {
    MTL_FLAG_WIRE: "MTL_FLAG_WIRE",
    MTL_FLAG_2SIDED: "MTL_FLAG_2SIDED",
    MTL_FLAG_ADDITIVE: "MTL_FLAG_ADDITIVE",
    MTL_FLAG_DETAIL_DECAL: "MTL_FLAG_DETAIL_DECAL",
    MTL_FLAG_LIGHTING: "MTL_FLAG_LIGHTING",
    MTL_FLAG_NOSHADOW: "MTL_FLAG_NOSHADOW",
    MTL_FLAG_ALWAYS_USED: "MTL_FLAG_ALWAYS_USED",
    MTL_FLAG_PURE_CHILD: "MTL_FLAG_PURE_CHILD",
    MTL_FLAG_MULTI_SUBMTL: "MTL_FLAG_MULTI_SUBMTL",
    MTL_FLAG_NOPHYSICALIZE: "MTL_FLAG_NOPHYSICALIZE",
    MTL_FLAG_NODRAW: "MTL_FLAG_NODRAW",
    MTL_FLAG_NOPREVIEW: "MTL_FLAG_NOPREVIEW",
    MTL_FLAG_NOTINSTANCED: "MTL_FLAG_NOTINSTANCED",
    MTL_FLAG_COLLISION_PROXY: "MTL_FLAG_COLLISION_PROXY",
    MTL_FLAG_SCATTER: "MTL_FLAG_SCATTER",
    MTL_FLAG_REQUIRE_FORWARD_RENDERING: "MTL_FLAG_REQUIRE_FORWARD_RENDERING",
    MTL_FLAG_NON_REMOVABLE: "MTL_FLAG_NON_REMOVABLE",
    MTL_FLAG_HIDEONBREAK: "MTL_FLAG_HIDEONBREAK",
    MTL_FLAG_UIMATERIAL: "MTL_FLAG_UIMATERIAL",
    MTL_64BIT_SHADERGENMASK: "MTL_64BIT_SHADERGENMASK",
    MTL_FLAG_RAYCAST_PROXY: "MTL_FLAG_RAYCAST_PROXY",
    MTL_FLAG_REQUIRE_NEAREST_CUBEMAP: "MTL_FLAG_REQUIRE_NEAREST_CUBEMAP",
    MTL_FLAG_CONSOLE_MAT: "MTL_FLAG_CONSOLE_MAT",
    MTL_FLAG_BLEND_TERRAIN: "MTL_FLAG_BLEND_TERRAIN",
    MTL_FLAG_TRACEABLE_TEXTURE: "MTL_FLAG_TRACEABLE_TEXTURE",
    MTL_FLAG_REFRACTIVE: "MTL_FLAG_REFRACTIVE",
}

MTL_KNOWN_FLAG_MASK = sum(MTL_FLAG_NAMES)

MTL_ROOT_DEFAULT_FLAGS = MTL_64BIT_SHADERGENMASK | MTL_FLAG_MULTI_SUBMTL
MTL_SUB_MATERIAL_DEFAULT_FLAGS = MTL_64BIT_SHADERGENMASK | MTL_FLAG_PURE_CHILD

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

EXPORT_SHADER_TOKEN_BY_TEXTURE_TYPE = {
    "normal": ["%NORMAL_MAP"],
    "specular": ["%SPECULAR_MAP"],
    "displacement": ["%DISPLACEMENT_MAPPING", "%PHONG_TESSELLATION"],
}

EXPORT_DEFAULT_SHADER_TOKENS = ["%SUBSURFACE_SCATTERING"]

ALPHA_TEXTURE_TYPES = {"alpha", "transparency", "opacity", "mask"}

SUB_MATERIAL_DEFAULT_ATTRS = {
    "MtlFlags": str(MTL_SUB_MATERIAL_DEFAULT_FLAGS),
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


def compose_mtl_flags(*flags):
    value = 0
    for flag in flags:
        value |= int(flag)
    return value


def mtl_flags_attr(*flags):
    return str(compose_mtl_flags(*flags))


def describe_mtl_flags(value):
    parsed_value = _parse_int_attr(value)
    names = [
        name
        for flag, name in sorted(MTL_FLAG_NAMES.items())
        if parsed_value & flag
    ]
    return {
        "value": parsed_value,
        "names": names,
        "unknown_mask": parsed_value & ~MTL_KNOWN_FLAG_MASK,
        "source": "Code/CryEngine/CryCommon/Cry3DEngine/IMaterial.h",
        "lines": "46-77",
    }


def exported_string_gen_mask(tokens):
    return "".join(sorted(set(tokens)))


def exported_gen_mask(tokens):
    gen_mask = 0
    for token in tokens:
        gen_mask |= EXPORT_COMPAT_SHADER_MASKS[token]
    return gen_mask


def exported_material_shader_policy(textures):
    """
    Return the current exporter shader-mask/PublicParams policy for texture inputs.

    This intentionally preserves the current compatibility GenMask values while
    making the guessed/exporter-owned pieces visible to reports and tests.
    """
    texture_keys = {
        str(texture_type).lower()
        for texture_type, texture_path in (textures or {}).items()
        if texture_path
    }
    tokens = list(EXPORT_DEFAULT_SHADER_TOKENS)
    token_reasons = {
        token: {
            "source": "exporter_default_compatibility",
            "texture_type": "",
        }
        for token in EXPORT_DEFAULT_SHADER_TOKENS
    }
    public_params = dict(BASE_PUBLIC_PARAMS)
    public_param_reasons = {
        name: {
            "source": "exporter_base_compatibility",
        }
        for name in public_params
    }

    for texture_type in sorted(texture_keys):
        for token in EXPORT_SHADER_TOKEN_BY_TEXTURE_TYPE.get(texture_type, []):
            tokens.append(token)
            token_reasons[token] = {
                "source": "texture_presence",
                "texture_type": texture_type,
            }

    if "displacement" in texture_keys:
        public_params.update(DISPLACEMENT_PUBLIC_PARAMS)
        for name in DISPLACEMENT_PUBLIC_PARAMS:
            public_param_reasons[name] = {
                "source": "displacement_texture_compatibility",
                "texture_type": "displacement",
            }

    return {
        "tokens": sorted(set(tokens)),
        "token_reasons": token_reasons,
        "gen_mask": exported_gen_mask(tokens),
        "gen_mask_source": "EXPORT_COMPAT_SHADER_MASKS",
        "gen_mask_policy": "compatibility_preserved_until_roundtrip_evidence",
        "string_gen_mask": exported_string_gen_mask(tokens),
        "string_gen_mask_source": "source_backed_token_names",
        "public_params": public_params,
        "public_param_reasons": public_param_reasons,
        "public_params_policy": "compatibility_preserved_until_roundtrip_evidence",
        "source_evidence": {
            "shader_mask_load_policy": MTL_SHADER_MASK_LOAD_POLICY,
            "public_params_policy": MTL_PUBLIC_PARAMS_POLICY,
        },
    }


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
