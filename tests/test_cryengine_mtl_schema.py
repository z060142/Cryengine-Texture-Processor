from output_formats.cryengine_mtl_schema import (
    CE_TEXTURE_MAP_TYPES,
    CE_TEXTURE_SUFFIXES,
    EXPORT_COMPAT_SHADER_MASKS,
    ILLUM_EXT_SHADER_MASKS,
    exported_gen_mask,
    exported_string_gen_mask,
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


def test_exported_gen_mask_preserves_current_export_compat_values():
    tokens = ["%SUBSURFACE_SCATTERING", "%NORMAL_MAP", "%SPECULAR_MAP", "%NORMAL_MAP"]

    assert exported_string_gen_mask(tokens) == "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
    assert exported_gen_mask(tokens) == (
        EXPORT_COMPAT_SHADER_MASKS["%SUBSURFACE_SCATTERING"]
        | EXPORT_COMPAT_SHADER_MASKS["%NORMAL_MAP"]
        | EXPORT_COMPAT_SHADER_MASKS["%SPECULAR_MAP"]
    )
