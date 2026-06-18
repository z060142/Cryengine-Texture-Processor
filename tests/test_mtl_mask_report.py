import xml.etree.ElementTree as ET

from tools.mtl_mask_report import (
    build_mtl_mask_report,
    mask_from_tokens,
    parse_gen_mask_literal,
    string_gen_mask_tokens,
)


def write_mtl(path, materials):
    root = ET.Element("Material", Name="Root", Shader="Illum", GenMask="0", StringGenMask="")
    sub_materials = ET.SubElement(root, "SubMaterials")
    for material in materials:
        ET.SubElement(sub_materials, "Material", **material)
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_string_gen_mask_tokens_preserve_order():
    assert string_gen_mask_tokens("%NORMAL_MAP%SPECULAR_MAP%NORMAL_MAP") == [
        "%NORMAL_MAP",
        "%SPECULAR_MAP",
        "%NORMAL_MAP",
    ]


def test_mask_from_tokens_reports_unknown_tokens():
    result = mask_from_tokens(["%NORMAL_MAP", "%NOT_REAL"], {"%NORMAL_MAP": 0x1})

    assert result["value"] == 0x1
    assert result["known_tokens"] == ["%NORMAL_MAP"]
    assert result["unknown_tokens"] == ["%NOT_REAL"]


def test_parse_gen_mask_literal_prefers_hex_for_string_masks():
    parsed = parse_gen_mask_literal("80000000", prefer_hex_for_string_mask=True)

    assert parsed["value"] == 0x80000000
    assert parsed["base"] == 16
    assert parsed["ambiguous"] is True
    assert parsed["decimal_value"] == 80000000


def test_parse_gen_mask_literal_keeps_decimal_without_string_mask():
    parsed = parse_gen_mask_literal("268435456", prefer_hex_for_string_mask=False)

    assert parsed["value"] == 268435456
    assert parsed["base"] == 10


def test_build_mtl_mask_report_summarizes_tokenized_mismatches(tmp_path):
    mtl_path = tmp_path / "sample.mtl"
    write_mtl(
        mtl_path,
        [
            {
                "Name": "DefaultStyle",
                "Shader": "Illum",
                "GenMask": "80000000",
                "StringGenMask": "%SUBSURFACE_SCATTERING",
            },
            {
                "Name": "CompatStyle",
                "Shader": "Illum",
                "GenMask": "32",
                "StringGenMask": "%SUBSURFACE_SCATTERING",
            },
        ],
    )

    report = build_mtl_mask_report([str(mtl_path)])

    assert report["summary"]["file_count"] == 1
    assert report["summary"]["material_count"] == 3
    assert report["summary"]["tokenized_material_mismatch_count"] == 1
    assert report["summary"]["unknown_common_global_legacy_fix_token_count"] == 2
    assert report["files"][0]["materials"][1]["gen_mask"]["value"] == 0x80000000
    assert report["files"][0]["materials"][2]["matches_export_compat_mask"] is True


def test_build_mtl_mask_report_matches_common_global_legacy_fix_tokens(tmp_path):
    mtl_path = tmp_path / "sample.mtl"
    write_mtl(
        mtl_path,
        [
            {
                "Name": "VertexColorStyle",
                "Shader": "Illum",
                "GenMask": "2000000000",
                "StringGenMask": "%VERTCOLORS",
            },
        ],
    )

    report = build_mtl_mask_report([str(mtl_path)])
    material = report["files"][0]["materials"][1]

    assert material["matches_common_global_legacy_fix_mask"] is True
    assert material["common_global_legacy_fix_mask"]["value"] == 0x2000000000


def test_build_mtl_mask_report_uses_generated_common_global_table(tmp_path):
    shader_dir = tmp_path / "Shaders"
    shader_dir.mkdir()
    (shader_dir / "Illum.ext").write_text(
        """
        UsesCommonGlobalFlags
        Property { Name = %SUBSURFACE_SCATTERING }
        """,
        encoding="utf-8",
    )
    mtl_path = tmp_path / "sample.mtl"
    write_mtl(
        mtl_path,
        [
            {
                "Name": "GeneratedStyle",
                "Shader": "Illum",
                "GenMask": "1",
                "StringGenMask": "%SUBSURFACE_SCATTERING",
            },
        ],
    )

    report = build_mtl_mask_report([str(mtl_path)], shader_ext_dir=str(shader_dir))
    material = report["files"][0]["materials"][1]

    assert report["common_global_flag_source"]["token_count"] == 1
    assert material["common_global_generated_mask"]["value"] == 1
    assert material["matches_common_global_generated_mask"] is True


def test_build_mtl_mask_report_prefers_saved_globals_file(tmp_path):
    shader_dir = tmp_path / "Shaders"
    shader_dir.mkdir()
    (shader_dir / "Illum.ext").write_text(
        """
        UsesCommonGlobalFlags
        Property { Name = %SUBSURFACE_SCATTERING }
        """,
        encoding="utf-8",
    )
    globals_file = tmp_path / "globals.txt"
    globals_file.write_text(
        """
        FX_CACHE_VER 1.000000
        %ILLUM

        %SUBSURFACE_SCATTERING 80000000
        """,
        encoding="utf-8",
    )
    mtl_path = tmp_path / "sample.mtl"
    write_mtl(
        mtl_path,
        [
            {
                "Name": "SavedGlobalsStyle",
                "Shader": "Illum",
                "GenMask": "80000000",
                "StringGenMask": "%SUBSURFACE_SCATTERING",
            },
        ],
    )

    report = build_mtl_mask_report(
        [str(mtl_path)],
        shader_ext_dir=str(shader_dir),
        globals_file=str(globals_file),
    )
    material = report["files"][0]["materials"][1]

    assert report["common_global_flag_source"]["mode"] == "globals_file"
    assert report["common_global_flag_source"]["token_count"] == 1
    assert material["common_global_generated_mask"]["value"] == 0x80000000
    assert material["matches_common_global_generated_mask"] is True
