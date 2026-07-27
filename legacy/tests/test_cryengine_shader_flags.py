from tools.cryengine_shader_flags import (
    build_common_global_flag_table,
    build_common_global_flag_table_from_dir,
    extract_common_global_tokens_from_ext,
    load_common_global_flag_table,
    parse_common_global_flags_text,
)


def test_extract_common_global_tokens_requires_marker():
    assert extract_common_global_tokens_from_ext("Property { Name = %NORMAL_MAP }") == []
    assert extract_common_global_tokens_from_ext("UsesCommonGlobalFlags\nProperty { Name = %normal_map }") == [
        "%NORMAL_MAP"
    ]


def test_build_common_global_flag_table_sorts_tokens_and_applies_legacy_swap():
    table = build_common_global_flag_table(["%Z_LAST", "%VERTCOLORS", "%A_FIRST"])

    assert table["%A_FIRST"] == 0x1
    assert table["%VERTCOLORS"] == 0x2000000000
    assert table["%Z_LAST"] == 0x4


def test_build_common_global_flag_table_from_dir_reads_ext_files(tmp_path):
    (tmp_path / "Illum.ext").write_text(
        """
        UsesCommonGlobalFlags
        Property { Name = %SUBSURFACE_SCATTERING }
        Property { Name = %VERTCOLORS }
        """,
        encoding="utf-8",
    )
    (tmp_path / "Ignored.ext").write_text("Property { Name = %IGNORED }", encoding="utf-8")

    table = build_common_global_flag_table_from_dir(str(tmp_path))

    assert "%SUBSURFACE_SCATTERING" in table
    assert "%VERTCOLORS" in table
    assert "%IGNORED" not in table


def test_parse_common_global_flags_text_skips_header_and_remap_list():
    table = parse_common_global_flags_text(
        """
        FX_CACHE_VER 1.000000
        %EYE%GLASS%ILLUM

        %normal_map 20
        %SUBSURFACE_SCATTERING 4000000000000
        """
    )

    assert table == {
        "%NORMAL_MAP": 0x20,
        "%SUBSURFACE_SCATTERING": 0x4000000000000,
    }


def test_load_common_global_flag_table_reads_saved_globals_file(tmp_path):
    globals_file = tmp_path / "globals.txt"
    globals_file.write_text(
        "FX_CACHE_VER 1.000000\n%ILLUM\n\n%VERTCOLORS 2000000000\n",
        encoding="utf-8",
    )

    assert load_common_global_flag_table(str(globals_file)) == {"%VERTCOLORS": 0x2000000000}
