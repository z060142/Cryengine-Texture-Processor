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
    )
    textures = ET.SubElement(root, "Textures")
    texture = ET.SubElement(textures, "Texture", Map="Diffuse", File="./asset_diff.dds")
    ET.SubElement(texture, "TexMod", TexMod_RotateType="0")
    ET.SubElement(root, "PublicParams", SSSIndex="0", IndirectColor="0.25,0.25,0.25")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(
        sub_materials,
        "Material",
        Name="Slot_0",
        MtlFlags="524416",
        Shader="Illum",
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
    assert {"name": "SSSIndex", "count": 1} in schema["public_params"]
    assert {"name": "1", "count": 1} in schema["public_param_component_counts"]
    assert {"name": "3", "count": 1} in schema["public_param_component_counts"]
    assert {"name": "MTL_64BIT_SHADERGENMASK", "count": 2} in schema["mtl_flag_names"]
    assert {"name": "MTL_FLAG_MULTI_SUBMTL", "count": 1} in schema["mtl_flag_names"]
    assert {"name": "MTL_FLAG_PURE_CHILD", "count": 1} in schema["mtl_flag_names"]
    assert schema["mtl_flag_unknown_masks"] == []
    assert {"name": "Diffuse", "count": 1} in schema["texture_maps"]
    assert {"name": "%SUBSURFACE_SCATTERING", "count": 2} in schema["tokens"]
    assert report["files"][0]["materials"][0]["mtl_flags_analysis"]["names"] == [
        "MTL_FLAG_MULTI_SUBMTL",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert report["files"][0]["materials"][1]["mtl_flags_analysis"]["names"] == [
        "MTL_FLAG_PURE_CHILD",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert report["files"][0]["materials"][0]["textures"][0]["texmod"]["TexMod_RotateType"] == "0"
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


def test_build_mtl_schema_report_can_omit_per_file_records(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    write_schema_mtl(mtl_path)

    report = build_mtl_schema_report([str(mtl_path)], include_files=False)

    assert report["files"] == []
    assert report["summary"]["file_count"] == 1
    assert report["summary"]["material_count"] == 2
