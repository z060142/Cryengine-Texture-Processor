from output_formats.cryengine_mtl_schema import (
    CE_TEXTURE_ACCEPTED_SUFFIXES,
    CE_TEXTURE_MAP_TYPES,
    CE_TEXTURE_MAP_NAMES,
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
    analyze_ce_texture_map_entry,
    analyze_ce_texture_path_reuse,
    analyze_ce_texture_suffix,
    analyze_rc_texture_source_extension,
    analyze_public_params,
    compose_mtl_flags,
    describe_mtl_flags,
    exported_gen_mask,
    exported_material_attribute_policy,
    exported_material_state_contract,
    exported_material_shader_policy,
    exported_mtl_flags_policy,
    exported_texture_map_policy,
    exported_texture_modifier_policy,
    exported_string_gen_mask,
    mtl_flags_attr,
    parse_public_param_value,
    resolve_ce_texture_map,
    shader_mask_load_policy,
)


def test_ce_texture_map_types_follow_material_helpers_names():
    assert CE_TEXTURE_MAP_TYPES["diffuse"] == "Diffuse"
    assert CE_TEXTURE_MAP_TYPES["normal"] == "Bumpmap"
    assert CE_TEXTURE_MAP_TYPES["bumpmap"] == "Bumpmap"
    assert CE_TEXTURE_MAP_TYPES["specular"] == "Specular"
    assert CE_TEXTURE_MAP_TYPES["displacement"] == "Heightmap"
    assert CE_TEXTURE_MAP_TYPES["heightmap"] == "Heightmap"
    assert CE_TEXTURE_MAP_TYPES["opacity"] == "Opacity"
    assert CE_TEXTURE_MAP_TYPES["emissive"] == "Emittance"
    assert CE_TEXTURE_MAP_TYPES["ao"] is None
    assert "Diffuse" in CE_TEXTURE_MAP_NAMES
    assert "Bumpmap" in CE_TEXTURE_MAP_NAMES


def test_ce_texture_suffixes_follow_material_helpers_suffixes():
    assert CE_TEXTURE_SUFFIXES["Diffuse"] == "_diff"
    assert CE_TEXTURE_SUFFIXES["Bumpmap"] == "_ddn"
    assert CE_TEXTURE_SUFFIXES["Smoothness"] == "_ddna"
    assert CE_TEXTURE_SUFFIXES["Heightmap"] == "_displ"
    assert CE_TEXTURE_SUFFIXES["Emittance"] == "_em"
    assert CE_TEXTURE_ACCEPTED_SUFFIXES["Bumpmap"] == ("_ddn", "_ddna")
    assert CE_TEXTURE_ACCEPTED_SUFFIXES["Emittance"] == ("_em", "_emissive")


def test_analyze_ce_texture_suffix_reports_match_and_mismatch():
    match = analyze_ce_texture_suffix("Diffuse", r"textures\wall_diff.dds")
    assert match["expected_suffix"] == "_diff"
    assert match["accepted_suffixes"] == ["_diff"]
    assert match["matched_suffix"] == "_diff"
    assert match["suffix_status"] == "matches_expected_suffix"
    assert match["source_evidence"]["source"].endswith("MaterialHelpers.cpp")

    alias = analyze_ce_texture_suffix("Bumpmap", "textures/wall_ddna.dds")
    assert alias["expected_suffix"] == "_ddn"
    assert alias["accepted_suffixes"] == ["_ddn", "_ddna"]
    assert alias["matched_suffix"] == "_ddna"
    assert alias["suffix_status"] == "matches_accepted_alias_suffix"
    assert alias["source_evidence"]["alias_source"].endswith("TextureCompiler.cpp")

    emissive_alias = analyze_ce_texture_suffix("Emittance", "textures/wall_emissive.dds")
    assert emissive_alias["expected_suffix"] == "_em"
    assert emissive_alias["accepted_suffixes"] == ["_em", "_emissive"]
    assert emissive_alias["matched_suffix"] == "_emissive"
    assert emissive_alias["suffix_status"] == "matches_accepted_alias_suffix"

    mismatch = analyze_ce_texture_suffix("Bumpmap", "textures/wall_normal.dds")
    assert mismatch["expected_suffix"] == "_ddn"
    assert mismatch["suffix_status"] == "mismatch_expected_suffix"

    missing = analyze_ce_texture_suffix("", "")
    assert missing["suffix_status"] == "not_applicable"


def test_analyze_ce_texture_suffix_accepts_observed_roughness_opacity_suffix():
    roughness = analyze_ce_texture_suffix("Opacity", "./carpaint_roughness.dds")

    assert roughness["expected_suffix"] == ""
    assert roughness["observed_suffixes"] == ["_roughness"]
    assert roughness["matched_suffix"] == "_roughness"
    assert roughness["suffix_status"] == "matches_observed_sample_suffix"


def test_analyze_ce_texture_map_entry_reports_known_unknown_and_suffix_status():
    known = analyze_ce_texture_map_entry("Diffuse", "./wall_diff.dds")
    assert known["known_ce_map"] is True
    assert known["reason"] == "source_backed_ce_map"
    assert known["suffix_analysis"]["suffix_status"] == "matches_expected_suffix"

    mismatch = analyze_ce_texture_map_entry("Specular", "./wall_s.dds")
    assert mismatch["known_ce_map"] is True
    assert mismatch["reason"] == "source_backed_ce_map"
    assert mismatch["suffix_analysis"]["suffix_status"] == "mismatch_expected_suffix"

    unknown = analyze_ce_texture_map_entry("PackedORM", "./wall_orm.dds")
    assert unknown["known_ce_map"] is False
    assert unknown["reason"] == "unknown_ce_map_type"
    assert unknown["suffix_analysis"]["suffix_status"] == "no_source_backed_suffix"


def test_analyze_rc_texture_source_extension_follows_texture_compiler_supported_formats():
    tif = analyze_rc_texture_source_extension("textures/wall_diff.tif")
    assert tif["supported"] is True
    assert tif["status"] == "supported_rc_texture_source_extension"
    assert tif["supported_extensions"] == ["dds", "hdr", "tif"]
    assert tif["source_evidence"]["source"].endswith("TextureCompiler.h")

    dds = analyze_rc_texture_source_extension("textures/wall_diff.dds")
    assert dds["supported"] is True

    png = analyze_rc_texture_source_extension("textures/wall_diff.png")
    assert png["supported"] is False
    assert png["status"] == "unsupported_rc_texture_source_extension"


def test_analyze_ce_texture_path_reuse_flags_conflicting_expected_suffixes():
    diagnostics = analyze_ce_texture_path_reuse(
        [
            {"ce_map_type": "Diffuse", "texture_path": "./rock_diff.dds"},
            {"ce_map_type": "Specular", "texture_path": "rock_diff.dds"},
            {"ce_map_type": "Opacity", "texture_path": "rock_diff.dds"},
        ]
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic["code"] == "shared_texture_path_across_ce_maps"
    assert diagnostic["ce_map_types"] == ["Diffuse", "Opacity", "Specular"]
    assert diagnostic["expected_suffixes"] == ["_diff", "_spec"]
    assert diagnostic["normalized_texture_path"] == "rock_diff.dds"


def test_analyze_ce_texture_path_reuse_allows_diffuse_opacity_alpha_sharing():
    diagnostics = analyze_ce_texture_path_reuse(
        [
            {"ce_map_type": "Diffuse", "texture_path": "./leaf_diff.dds"},
            {"ce_map_type": "Opacity", "texture_path": "leaf_diff.dds"},
        ]
    )

    assert diagnostics == []


def test_resolve_ce_texture_map_exposes_export_and_skip_reasons():
    diffuse = resolve_ce_texture_map("Diffuse", "wall_diff.dds")
    assert diffuse["texture_type"] == "diffuse"
    assert diffuse["ce_map_type"] == "Diffuse"
    assert diffuse["exported"] is True
    assert diffuse["reason"] == "source_backed_texture_map"
    assert diffuse["suffix_analysis"]["expected_suffix"] == "_diff"
    assert diffuse["suffix_analysis"]["suffix_status"] == "matches_expected_suffix"
    assert diffuse["rc_source_extension_analysis"]["supported"] is True
    assert diffuse["source_evidence"]["source"].endswith("MaterialHelpers.cpp")

    ao = resolve_ce_texture_map("ao", "wall_ao.dds")
    assert ao["ce_map_type"] == ""
    assert ao["exported"] is False
    assert ao["reason"] == "known_internal_non_mtl_channel"

    missing = resolve_ce_texture_map("normal", "")
    assert missing["exported"] is False
    assert missing["reason"] == "missing_texture_path"

    unknown = resolve_ce_texture_map("packed_orm", "wall_orm.dds")
    assert unknown["exported"] is False
    assert unknown["reason"] == "unknown_texture_type"
    assert unknown["suffix_analysis"]["suffix_status"] == "not_applicable"


def test_resolve_ce_texture_map_exports_roughness_as_observed_opacity_alias():
    roughness = resolve_ce_texture_map("roughness", "carpaint_roughness.dds")

    assert roughness["ce_map_type"] == "Opacity"
    assert roughness["exported"] is True
    assert roughness["reason"] == "observed_ce_sample_texture_map_alias"
    assert roughness["suffix_analysis"]["suffix_status"] == "matches_observed_sample_suffix"
    assert roughness["observed_alias_evidence"]["source"] == "docs/phase98_car_example_material_alignment.json"


def test_exported_texture_map_policy_splits_exported_and_skipped_entries():
    policy = exported_texture_map_policy(
        {
            "diffuse": "wall_diff.dds",
            "normal": "wall_ddn.dds",
            "ao": "wall_ao.dds",
            "glossiness": "wall_gloss.dds",
        }
    )

    assert [entry["ce_map_type"] for entry in policy["exported"]] == ["Diffuse", "Bumpmap"]
    assert [entry["suffix_analysis"]["suffix_status"] for entry in policy["exported"]] == [
        "matches_expected_suffix",
        "matches_expected_suffix",
    ]
    assert [entry["reason"] for entry in policy["skipped"]] == [
        "known_internal_non_mtl_channel",
        "known_internal_non_mtl_channel",
    ]


def test_exported_texture_modifier_policy_preserves_minimal_texmod_attrs():
    policy = exported_texture_modifier_policy()

    assert policy["attributes"] == {
        "TexMod_RotateType": "0",
        "TexMod_TexGenType": "0",
        "TexMod_bTexGenProjected": "0",
    }
    assert policy["emission_policy"] == "compatibility_preserved_emits_minimal_texmod"
    assert set(policy["attribute_status"].values()) == {"compatibility_preserved_default_texmod"}
    assert policy["source_evidence"]["save_source"].endswith("MaterialHelpers.cpp")

    texture_policy = resolve_ce_texture_map("diffuse", "wall_diff.dds")
    assert texture_policy["texmod_policy"]["attributes"]["TexMod_RotateType"] == "0"


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
        "%NORMAL_MAP",
        "%SPECULAR_MAP",
        "%SUBSURFACE_SCATTERING",
    ]
    assert policy["string_gen_mask"] == "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
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
    assert "%DISPLACEMENT_MAPPING" not in policy["token_reasons"]
    assert "%PHONG_TESSELLATION" not in policy["token_reasons"]
    assert "TessellationFactorMax" not in policy["public_params"]
    assert "TessellationFactorMax" not in policy["public_param_reasons"]


def test_exported_material_shader_policy_accepts_ce_map_names_as_texture_keys():
    policy = exported_material_shader_policy(
        {
            "Bumpmap": "asset_ddn.dds",
            "Specular": "asset_spec.dds",
            "Heightmap": "asset_displ.dds",
        }
    )

    assert policy["tokens"] == [
        "%NORMAL_MAP",
        "%SPECULAR_MAP",
        "%SUBSURFACE_SCATTERING",
    ]
    assert policy["token_reasons"]["%NORMAL_MAP"] == {
        "source": "texture_presence",
        "texture_type": "bumpmap",
    }
    assert "%DISPLACEMENT_MAPPING" not in policy["token_reasons"]
    assert "%PHONG_TESSELLATION" not in policy["token_reasons"]
    assert "TessellationFactorMax" not in policy["public_params"]
    assert "TessellationFactorMax" not in policy["public_param_reasons"]


def test_exported_material_attribute_policy_marks_source_backed_and_compat_defaults():
    policy = exported_material_attribute_policy()

    assert policy["attributes"]["Shader"] == "Illum"
    assert policy["attributes"]["Diffuse"] == "1,1,1"
    assert policy["attributes"]["Opacity"] == "1"
    assert policy["attributes"]["Shininess"] == "255"
    assert policy["attribute_status"]["Shader"] == "source_backed_editor_default"
    assert policy["attribute_status"]["Diffuse"] == "source_backed_editor_default"
    assert policy["attribute_status"]["Opacity"] == "source_backed_editor_default"
    assert policy["attribute_status"]["Shininess"] == "compatibility_preserved_editor_default_differs"
    assert policy["source_evidence"]["lighting_load_source"].endswith("MaterialHelpers.cpp")
    assert policy["source_evidence"]["editor_default_source"].endswith("Material.cpp")


def test_exported_material_state_contract_separates_reference_overrides_from_fallbacks():
    contract = exported_material_state_contract()

    assert contract["schema"] == "cryengine_mtl_material_state_contract.v1"
    assert contract["authoritative_sources"][0]["tool"] == "tools.mtl_override_extractor"
    assert contract["authoritative_sources"][0]["payload_schema"] == "cryengine_material_overrides.v1"
    assert contract["state_fields"]["shader_masks"]["load_precedence"]["runtime_source"].endswith("MatMan.cpp")
    assert contract["state_fields"]["shader_masks"]["export_default_policy"]["gen_mask_policy"] == (
        "compatibility_preserved_until_roundtrip_evidence"
    )
    assert contract["state_fields"]["public_params"]["override_aliases"] == ["PublicParams", "public_params"]
    assert contract["comparison_gate"]["tool"] == "tools.mtl_material_state_compare"
    assert contract["comparison_gate"]["compared_attrs"] == [
        "Shader",
        "MtlFlags",
        "GenMask",
        "StringGenMask",
        "PublicParams",
    ]
    assert contract["fallback_policy"]["status"] == "degraded_without_reference_mtl"


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


def test_exported_mtl_flags_policy_exposes_root_and_submaterial_defaults():
    policy = exported_mtl_flags_policy()

    assert policy["root_material"]["mtl_flags"] == "524544"
    assert policy["root_material"]["analysis"]["names"] == [
        "MTL_FLAG_MULTI_SUBMTL",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert policy["sub_material"]["mtl_flags"] == "524416"
    assert policy["sub_material"]["analysis"]["names"] == [
        "MTL_FLAG_PURE_CHILD",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert policy["source_evidence"]["source"].endswith("IMaterial.h")


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
