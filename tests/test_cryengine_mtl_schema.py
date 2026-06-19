from output_formats.cryengine_mtl_schema import (
    CE_TEXTURE_MAP_TYPES,
    CE_TEXTURE_SUFFIXES,
    COMMON_GLOBAL_LEGACY_FIX_MASKS,
    EXPORT_COMPAT_SHADER_MASKS,
    ILLUM_EXT_SHADER_MASKS,
    MTL_64BIT_SHADERGENMASK,
    MTL_FLAG_MULTI_SUBMTL,
    MTL_FLAG_NODRAW,
    MTL_FLAG_PURE_CHILD,
    MTL_FLAG_REFRACTIVE,
    MTL_ROOT_DEFAULT_FLAGS,
    MTL_PUBLIC_PARAMS_POLICY,
    MTL_SHADER_MASK_LOAD_POLICY,
    MTL_SUB_MATERIAL_DEFAULT_FLAGS,
    SUB_MATERIAL_DEFAULT_ATTRS,
    analyze_public_params,
    compose_mtl_flags,
    describe_mtl_flags,
    exported_gen_mask,
    exported_material_shader_policy,
    exported_string_gen_mask,
    mtl_flags_attr,
    parse_public_param_value,
    shader_mask_load_policy,
)


def test_ce_texture_map_types_follow_material_helpers_names():
    assert CE_TEXTURE_MAP_TYPES["diffuse"] == "Diffuse"
    assert CE_TEXTURE_MAP_TYPES["normal"] == "Bumpmap"
    assert CE_TEXTURE_MAP_TYPES["specular"] == "Specular"
    assert CE_TEXTURE_MAP_TYPES["displacement"] == "Heightmap"
    assert CE_TEXTURE_MAP_TYPES["opacity"] == "Opacity"
    assert CE_TEXTURE_MAP_TYPES["emissive"] == "Emittance"
    assert CE_TEXTURE_MAP_TYPES["ao"] is None


def test_ce_texture_suffixes_follow_material_helpers_suffixes():
    assert CE_TEXTURE_SUFFIXES["Diffuse"] == "_diff"
    assert CE_TEXTURE_SUFFIXES["Bumpmap"] == "_ddn"
    assert CE_TEXTURE_SUFFIXES["Smoothness"] == "_ddna"
    assert CE_TEXTURE_SUFFIXES["Heightmap"] == "_displ"
    assert CE_TEXTURE_SUFFIXES["Emittance"] == "_em"


def test_illum_ext_shader_masks_are_source_evidence_not_export_compat_values():
    assert ILLUM_EXT_SHADER_MASKS["%NORMAL_MAP"] == 0x1
    assert ILLUM_EXT_SHADER_MASKS["%SPECULAR_MAP"] == 0x10
    assert ILLUM_EXT_SHADER_MASKS["%DISPLACEMENT_MAPPING"] == 0x10000000
    assert ILLUM_EXT_SHADER_MASKS["%PHONG_TESSELLATION"] == 0x20000000
    assert ILLUM_EXT_SHADER_MASKS["%SUBSURFACE_SCATTERING"] == 0x80000

    assert EXPORT_COMPAT_SHADER_MASKS["%NORMAL_MAP"] != ILLUM_EXT_SHADER_MASKS["%NORMAL_MAP"]


def test_common_global_legacy_fix_masks_follow_shadercore_evidence():
    assert COMMON_GLOBAL_LEGACY_FIX_MASKS["%OFFSET_BUMP_MAPPING"] == 0x2000000
    assert COMMON_GLOBAL_LEGACY_FIX_MASKS["%BILLBOARD"] == 0x100000000
    assert COMMON_GLOBAL_LEGACY_FIX_MASKS["%VERTCOLORS"] == 0x2000000000


def test_exported_gen_mask_preserves_current_export_compat_values():
    tokens = ["%SUBSURFACE_SCATTERING", "%NORMAL_MAP", "%SPECULAR_MAP", "%NORMAL_MAP"]

    assert exported_string_gen_mask(tokens) == "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
    assert exported_gen_mask(tokens) == (
        EXPORT_COMPAT_SHADER_MASKS["%SUBSURFACE_SCATTERING"]
        | EXPORT_COMPAT_SHADER_MASKS["%NORMAL_MAP"]
        | EXPORT_COMPAT_SHADER_MASKS["%SPECULAR_MAP"]
    )


def test_exported_material_shader_policy_exposes_current_compatibility_rules():
    policy = exported_material_shader_policy(
        {
            "normal": "asset_ddn.dds",
            "specular": "asset_spec.dds",
            "displacement": "asset_displ.dds",
            "diffuse": "asset_diff.dds",
        }
    )

    assert policy["tokens"] == [
        "%DISPLACEMENT_MAPPING",
        "%NORMAL_MAP",
        "%PHONG_TESSELLATION",
        "%SPECULAR_MAP",
        "%SUBSURFACE_SCATTERING",
    ]
    assert policy["string_gen_mask"] == (
        "%DISPLACEMENT_MAPPING%NORMAL_MAP%PHONG_TESSELLATION%SPECULAR_MAP%SUBSURFACE_SCATTERING"
    )
    assert policy["gen_mask"] == exported_gen_mask(policy["tokens"])
    assert policy["gen_mask_policy"] == "compatibility_preserved_until_roundtrip_evidence"
    assert policy["string_gen_mask_source"] == "source_backed_token_names"
    assert policy["token_reasons"]["%NORMAL_MAP"] == {
        "source": "texture_presence",
        "texture_type": "normal",
    }
    assert policy["token_reasons"]["%SUBSURFACE_SCATTERING"] == {
        "source": "exporter_default_compatibility",
        "texture_type": "",
    }
    assert policy["public_params"]["TessellationFactorMax"] == "32"
    assert policy["public_param_reasons"]["TessellationFactorMax"] == {
        "source": "displacement_texture_compatibility",
        "texture_type": "displacement",
    }


def test_shader_mask_load_policy_follows_runtime_and_editor_source_precedence():
    assert MTL_FLAG_MULTI_SUBMTL == 0x0100
    assert MTL_FLAG_PURE_CHILD == 0x0080
    assert MTL_64BIT_SHADERGENMASK == 0x80000
    assert MTL_SHADER_MASK_LOAD_POLICY["runtime_source"].endswith("MatMan.cpp")

    policy = shader_mask_load_policy(
        {
            "MtlFlags": str(MTL_64BIT_SHADERGENMASK),
            "GenMask": "32",
            "StringGenMask": "%SUBSURFACE_SCATTERING",
        }
    )
    assert policy["effective_source"] == "StringGenMask"
    assert policy["operation"] == "EF_GetShaderGlobalMaskGenFromString"
    assert policy["has_64bit_shadergenmask_flag"] is True

    policy = shader_mask_load_policy({"MtlFlags": "0", "GenMask": "32"})
    assert policy["effective_source"] == "GenMask"
    assert policy["operation"] == "EF_GetRemapedShaderMaskGen"

    policy = shader_mask_load_policy({"MtlFlags": str(MTL_FLAG_MULTI_SUBMTL)})
    assert policy["effective_source"] == "sub_materials"
    assert policy["operation"] == "skip_multi_submaterial_container_shader_mask"


def test_default_mtl_flags_are_named_source_backed_compositions():
    assert MTL_ROOT_DEFAULT_FLAGS == compose_mtl_flags(MTL_64BIT_SHADERGENMASK, MTL_FLAG_MULTI_SUBMTL)
    assert MTL_SUB_MATERIAL_DEFAULT_FLAGS == compose_mtl_flags(MTL_64BIT_SHADERGENMASK, MTL_FLAG_PURE_CHILD)
    assert mtl_flags_attr(MTL_64BIT_SHADERGENMASK, MTL_FLAG_MULTI_SUBMTL) == "524544"
    assert SUB_MATERIAL_DEFAULT_ATTRS["MtlFlags"] == "524416"

    root_flags = describe_mtl_flags(MTL_ROOT_DEFAULT_FLAGS)
    assert root_flags["names"] == ["MTL_FLAG_MULTI_SUBMTL", "MTL_64BIT_SHADERGENMASK"]
    assert root_flags["source"].endswith("IMaterial.h")

    submaterial_flags = describe_mtl_flags(SUB_MATERIAL_DEFAULT_ATTRS["MtlFlags"])
    assert submaterial_flags["names"] == ["MTL_FLAG_PURE_CHILD", "MTL_64BIT_SHADERGENMASK"]


def test_describe_mtl_flags_decodes_known_names_and_unknown_bits():
    unknown_bit = 0x8000000
    flags = describe_mtl_flags(MTL_FLAG_NODRAW | MTL_FLAG_REFRACTIVE | unknown_bit)

    assert flags["names"] == ["MTL_FLAG_NODRAW", "MTL_FLAG_REFRACTIVE"]
    assert flags["unknown_mask"] == unknown_bit
    assert flags["lines"] == "46-77"


def test_public_param_parser_follows_matman_vector4_parsing():
    assert MTL_PUBLIC_PARAMS_POLICY["runtime_source"].endswith("MatMan.cpp")

    scalar = parse_public_param_value("1")
    assert scalar["components"] == [1.0, 0.0, 0.0, 0.0]
    assert scalar["parsed_component_count"] == 1

    vec3 = parse_public_param_value("0.25,0.5,0.75")
    assert vec3["components"] == [0.25, 0.5, 0.75, 0.0]
    assert vec3["parsed_component_count"] == 3

    invalid = parse_public_param_value("not-a-number")
    assert invalid["components"] == [0.0, 0.0, 0.0, 0.0]
    assert invalid["parsed_component_count"] == 0


def test_analyze_public_params_preserves_raw_values_and_sorted_names():
    analysis = analyze_public_params({"ZParam": "2", "AParam": "1,2,3,4"})

    assert list(analysis) == ["AParam", "ZParam"]
    assert analysis["AParam"]["raw"] == "1,2,3,4"
    assert analysis["AParam"]["parsed_component_count"] == 4
    assert analysis["ZParam"]["components"] == [2.0, 0.0, 0.0, 0.0]
