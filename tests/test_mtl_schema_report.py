import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from tools.mtl_schema_report import build_mtl_schema_report


def write_schema_mtl(path):
    root = ET.Element(
        "Material",
        MtlFlags="524544",
        Shader="Illum",
        GenMask="80000000",
        StringGenMask="%SUBSURFACE_SCATTERING",
        SurfaceType="mat_concrete",
        Diffuse="1,1,1",
        Opacity="1",
    )
    textures = ET.SubElement(root, "Textures")
    texture = ET.SubElement(textures, "Texture", Map="Diffuse", File="./asset_diff.dds")
    ET.SubElement(texture, "TexMod", TexMod_RotateType="0")
    ET.SubElement(textures, "Texture", Map="Specular", File="./asset_s.dds")
    custom_texture = ET.SubElement(textures, "Texture", Map="Bumpmap", File="./asset_ddn.dds")
    ET.SubElement(
        custom_texture,
        "TexMod",
        TexMod_RotateType="1",
        TexMod_TexGenType="0",
        TexMod_bTexGenProjected="0",
        TileU="2",
    )
    ET.SubElement(textures, "Texture", Map="PackedORM", File="./asset_orm.dds")
    ET.SubElement(
        root,
        "PublicParams",
        SSSIndex="0",
        IndirectColor="0.25,0.25,0.25",
        EmittanceMapGamma="1",
    )
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(
        sub_materials,
        "Material",
        Name="Slot_0",
        MtlFlags="524416",
        Shader="Illum",
        Shininess="10",
        GenMask="2020000000",
        StringGenMask="%SUBSURFACE_SCATTERING%VERTCOLORS",
    )
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_build_mtl_schema_report_summarizes_attrs_params_textures_and_tokens(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    write_schema_mtl(mtl_path)

    report = build_mtl_schema_report([str(mtl_path)])

    assert report["summary"] == {
        "file_count": 1,
        "material_count": 2,
        "multi_material_file_count": 1,
        "tokenized_material_count": 2,
    }
    schema = report["schema"]
    assert {"name": "Shader", "count": 2} in schema["material_attributes"]
    assert {"name": "matches_export_attribute", "count": 5} in schema["material_attribute_policy_statuses"]
    assert {"name": "missing_export_attribute", "count": 10} in schema["material_attribute_policy_statuses"]
    assert {"name": "differs_from_export_attribute", "count": 3} in schema["material_attribute_policy_statuses"]
    assert {"name": "MtlFlags=524544", "count": 1} in schema["material_attribute_policy_differences"]
    assert {"name": "SurfaceType=mat_concrete", "count": 1} in schema["material_attribute_policy_differences"]
    assert {"name": "Shininess=10", "count": 1} in schema["material_attribute_policy_differences"]
    assert {"name": "Specular", "count": 2} in schema["material_attribute_policy_missing"]
    assert {"name": "SSSIndex", "count": 1} in schema["public_params"]
    assert {"name": "IndirectColor=0.25,0.25,0.25", "count": 1} in schema["public_param_values"]
    assert {"name": "EmittanceMapGamma=1", "count": 1} in schema["public_param_values"]
    assert schema["public_param_values_by_name"]["SSSIndex"] == [{"name": "0", "count": 1}]
    assert schema["public_param_values_by_name"]["IndirectColor"] == [
        {"name": "0.25,0.25,0.25", "count": 1}
    ]
    assert schema["public_param_component_counts_by_name"]["SSSIndex"] == [{"name": "1", "count": 1}]
    assert schema["public_param_component_counts_by_name"]["IndirectColor"] == [{"name": "3", "count": 1}]
    assert {"name": "1", "count": 2} in schema["public_param_component_counts"]
    assert {"name": "3", "count": 1} in schema["public_param_component_counts"]
    assert {"name": "MTL_64BIT_SHADERGENMASK", "count": 2} in schema["mtl_flag_names"]
    assert {"name": "MTL_FLAG_MULTI_SUBMTL", "count": 1} in schema["mtl_flag_names"]
    assert {"name": "MTL_FLAG_PURE_CHILD", "count": 1} in schema["mtl_flag_names"]
    assert schema["mtl_flag_unknown_masks"] == []
    assert {"name": "Diffuse", "count": 1} in schema["texture_maps"]
    assert {"name": "Specular", "count": 1} in schema["texture_maps"]
    assert {"name": "Bumpmap", "count": 1} in schema["texture_maps"]
    assert {"name": "PackedORM", "count": 1} in schema["texture_maps"]
    assert {"name": "source_backed_ce_map", "count": 3} in schema["texture_map_policy_reasons"]
    assert {"name": "unknown_ce_map_type", "count": 1} in schema["texture_map_policy_reasons"]
    assert {"name": "PackedORM", "count": 1} in schema["texture_map_unknowns"]
    assert {"name": "matches_expected_suffix", "count": 2} in schema["texture_suffix_statuses"]
    assert {"name": "mismatch_expected_suffix", "count": 1} in schema["texture_suffix_statuses"]
    assert {"name": "no_source_backed_suffix", "count": 1} in schema["texture_suffix_statuses"]
    assert {"name": "_diff", "count": 1} in schema["texture_expected_suffixes"]
    assert {"name": "_ddn", "count": 1} in schema["texture_expected_suffixes"]
    assert {"name": "_spec", "count": 1} in schema["texture_expected_suffixes"]
    assert {"name": "partial_export_minimal_texmod", "count": 1} in schema["texmod_statuses"]
    assert {"name": "missing_texmod", "count": 2} in schema["texmod_statuses"]
    assert {"name": "custom_texmod", "count": 1} in schema["texmod_statuses"]
    assert {"name": "TexMod_RotateType", "count": 2} in schema["texmod_attributes"]
    assert {"name": "TileU", "count": 1} in schema["texmod_extra_attributes"]
    assert {"name": "%SUBSURFACE_SCATTERING", "count": 2} in schema["tokens"]
    assert report["files"][0]["materials"][0]["mtl_flags_analysis"]["names"] == [
        "MTL_FLAG_MULTI_SUBMTL",
        "MTL_64BIT_SHADERGENMASK",
    ]
    root_attribute_policy = report["files"][0]["materials"][0]["attribute_policy_analysis"]
    assert root_attribute_policy["entries"]["Shader"]["status"] == "matches_export_attribute"
    assert root_attribute_policy["entries"]["SurfaceType"]["status"] == "differs_from_export_attribute"
    assert root_attribute_policy["entries"]["Specular"]["status"] == "missing_export_attribute"
    assert root_attribute_policy["different_attrs"] == ["MtlFlags", "SurfaceType"]
    assert report["files"][0]["materials"][1]["mtl_flags_analysis"]["names"] == [
        "MTL_FLAG_PURE_CHILD",
        "MTL_64BIT_SHADERGENMASK",
    ]
    sub_attribute_policy = report["files"][0]["materials"][1]["attribute_policy_analysis"]
    assert sub_attribute_policy["entries"]["Shininess"]["status"] == "differs_from_export_attribute"
    assert sub_attribute_policy["entries"]["Shininess"]["actual"] == "10"
    assert report["files"][0]["materials"][0]["textures"][0]["texmod"]["TexMod_RotateType"] == "0"
    assert report["files"][0]["materials"][0]["textures"][0]["texture_map_analysis"]["reason"] == (
        "source_backed_ce_map"
    )
    assert report["files"][0]["materials"][0]["textures"][1]["texture_map_analysis"]["suffix_analysis"][
        "suffix_status"
    ] == "mismatch_expected_suffix"
    assert report["files"][0]["materials"][0]["textures"][3]["texture_map_analysis"]["reason"] == (
        "unknown_ce_map_type"
    )
    assert report["files"][0]["materials"][0]["textures"][0]["texmod_analysis"]["status"] == (
        "partial_export_minimal_texmod"
    )
    assert report["files"][0]["materials"][0]["textures"][1]["texmod_analysis"]["status"] == "missing_texmod"
    assert report["files"][0]["materials"][0]["textures"][2]["texmod_analysis"]["status"] == "custom_texmod"
    assert report["files"][0]["materials"][0]["textures"][2]["texmod_analysis"]["extra_attrs"] == ["TileU"]
    assert report["files"][0]["materials"][0]["public_param_analysis"]["SSSIndex"]["components"] == [
        0.0,
        0.0,
        0.0,
        0.0,
    ]
    assert report["files"][0]["materials"][0]["public_param_analysis"]["SSSIndex"]["parsed_component_count"] == 1
    assert report["files"][0]["materials"][0]["public_param_analysis"]["IndirectColor"]["components"] == [
        0.25,
        0.25,
        0.25,
        0.0,
    ]


def test_build_mtl_schema_report_accepts_ddna_bumpmap_alias(tmp_path):
    mtl_path = tmp_path / "normal_alpha.mtl"
    root = ET.Element("Material", Name="NormalAlpha", Shader="Illum")
    textures = ET.SubElement(root, "Textures")
    ET.SubElement(textures, "Texture", Map="Bumpmap", File="./normal_alpha_ddna.tif")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8")

    report = build_mtl_schema_report([str(mtl_path)])

    assert {"name": "matches_accepted_alias_suffix", "count": 1} in report["schema"]["texture_suffix_statuses"]
    suffix_analysis = report["files"][0]["materials"][0]["textures"][0]["texture_map_analysis"]["suffix_analysis"]
    assert suffix_analysis["expected_suffix"] == "_ddn"
    assert suffix_analysis["accepted_suffixes"] == ["_ddn", "_ddna"]
    assert suffix_analysis["matched_suffix"] == "_ddna"


def test_build_mtl_schema_report_flags_shared_texture_path_across_ce_maps(tmp_path):
    mtl_path = tmp_path / "shared_texture_maps.mtl"
    root = ET.Element("Material", Name="SharedMaps", Shader="Illum")
    textures = ET.SubElement(root, "Textures")
    ET.SubElement(textures, "Texture", Map="Diffuse", File="./rock_face_01_diff.dds")
    ET.SubElement(textures, "Texture", Map="Specular", File="./rock_face_01_diff.dds")
    ET.SubElement(textures, "Texture", Map="Heightmap", File="./rock_face_01_diff.dds")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8")

    report = build_mtl_schema_report([str(mtl_path)])

    assert {"name": "shared_texture_path_across_ce_maps", "count": 1} in report["schema"][
        "texture_path_reuse_diagnostics"
    ]
    diagnostics = report["files"][0]["materials"][0]["texture_path_reuse_diagnostics"]
    assert len(diagnostics) == 1
    assert diagnostics[0]["ce_map_types"] == ["Diffuse", "Heightmap", "Specular"]
    assert diagnostics[0]["expected_suffixes"] == ["_diff", "_displ", "_spec"]


def test_build_mtl_schema_report_can_omit_per_file_records(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    write_schema_mtl(mtl_path)

    report = build_mtl_schema_report([str(mtl_path)], include_files=False)

    assert report["files"] == []
    assert report["summary"]["file_count"] == 1
    assert report["summary"]["material_count"] == 2


def test_mtl_schema_report_script_runs_from_tools_path(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    mtl_path = tmp_path / "asset.mtl"
    output_path = tmp_path / "report.json"
    write_schema_mtl(mtl_path)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "tools" / "mtl_schema_report.py"),
            str(mtl_path),
            "--output",
            str(output_path),
            "--summary-only",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["file_count"] == 1
    assert payload["files"] == []
