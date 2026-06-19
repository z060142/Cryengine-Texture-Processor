import os

from model_processing.material_texture_resolver import (
    build_material_texture_records,
    build_fbx_texture_data,
    build_mtl_material_data,
    clean_material_name,
    iter_unique_clean_materials,
    strip_known_texture_suffix,
    texture_output_extensions,
)


class TextureRef:
    def __init__(self, path, material_name, texture_type=None, source_mode="blender"):
        self.path = path
        self.material_name = material_name
        self.texture_type = texture_type
        self.source_mode = source_mode
        self.filename = os.path.basename(path) if path else ""


class TextureManagerStub:
    def classify_texture(self, file_path):
        filename = os.path.splitext(os.path.basename(file_path))[0]
        return "diffuse", filename.removesuffix("_albedo")


def test_clean_material_name_preserves_blender_duplicate_suffix():
    assert clean_material_name("Stone.001") == "Stone.001"
    assert clean_material_name("Stone") == "Stone"


def test_iter_unique_clean_materials_skips_defaults_and_preserves_suffixes():
    materials = [
        {"name": "Material"},
        {"name": "Stone"},
        {"name": "Stone.001"},
        {"name": "Metal"},
    ]

    result = list(iter_unique_clean_materials(materials))

    assert [item["clean_name"] for item in result] == ["Stone", "Stone.001", "Metal"]
    assert [item["sub_index"] for item in result] == [0, 1, 2]


def test_strip_known_texture_suffix_handles_cryengine_outputs():
    assert strip_known_texture_suffix("wall_diff") == "wall"
    assert strip_known_texture_suffix("wall_ddna") == "wall"
    assert strip_known_texture_suffix("wall_em") == "wall"
    assert strip_known_texture_suffix("wall_basecolor") == "wall"
    assert strip_known_texture_suffix("wall_opacity") == "wall"
    assert strip_known_texture_suffix("wall") == "wall"


def test_build_fbx_texture_data_finds_existing_diff_and_ddna(tmp_path):
    source = tmp_path / "wall_albedo.png"
    source.write_text("fake source")
    (tmp_path / "wall_diff.tif").write_text("fake diff")
    (tmp_path / "wall_ddna.tif").write_text("fake ddna")
    model_data = {"materials": [{"name": "Wall"}]}
    refs = [TextureRef(str(source), "Wall")]

    result = build_fbx_texture_data(
        model_data,
        refs,
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert set(result["Wall"].keys()) == {"diff", "ddna"}


def test_build_fbx_texture_data_accepts_ddn_when_no_normal_alpha_output_exists(tmp_path):
    source = tmp_path / "wall_normal.png"
    source.write_text("fake source")
    (tmp_path / "wall_diff.tif").write_text("fake diff")
    (tmp_path / "wall_ddn.tif").write_text("fake ddn")
    model_data = {"materials": [{"name": "Wall"}]}
    refs = [TextureRef(str(source), "Wall", texture_type="normal")]

    result = build_fbx_texture_data(
        model_data,
        refs,
        texture_manager=None,
        texture_output_dir=str(tmp_path),
        output_format="tif",
    )

    assert result["Wall"]["ddna"] == str(tmp_path / "wall_ddn.tif")


def test_build_mtl_material_data_prefers_ddna_but_accepts_ddn(tmp_path):
    source = tmp_path / "wall_normal.png"
    source.write_text("fake source")
    (tmp_path / "wall_ddn.tif").write_text("fake ddn")
    model_data = {"materials": [{"name": "Wall"}]}
    refs = [TextureRef(str(source), "Wall", texture_type="normal")]

    ddn_result = build_mtl_material_data(model_data, refs, None, str(tmp_path), "tif")
    assert ddn_result[0]["textures"]["normal"] == str(tmp_path / "wall_ddn.tif")

    (tmp_path / "wall_ddna.tif").write_text("fake ddna")
    ddna_result = build_mtl_material_data(model_data, refs, None, str(tmp_path), "tif")
    assert ddna_result[0]["textures"]["normal"] == str(tmp_path / "wall_ddna.tif")


def test_material_texture_records_capture_texture_ref_evidence(tmp_path):
    source = tmp_path / "wall_opacity.png"
    source.write_text("fake source")
    (tmp_path / "wall_opacity.tif").write_text("fake opacity")
    model_data = {"materials": [{"name": "Wall"}]}
    refs = [TextureRef(str(source), "Wall", texture_type="alpha", source_mode="filesystem_no_bpy")]

    records = build_material_texture_records(
        model_data,
        refs,
        texture_manager=None,
        texture_output_dir=str(tmp_path),
        output_format="tif",
    )

    assert records[0]["textures"]["opacity"] == str(tmp_path / "wall_opacity.tif")
    assert records[0]["texture_ref_evidence"] == [
        {
            "path": str(source),
            "filename": "wall_opacity.png",
            "texture_type": "alpha",
            "source_mode": "filesystem_no_bpy",
        }
    ]


def test_build_mtl_material_data_preserves_roughness_semantics_for_mtl_export(tmp_path):
    source = tmp_path / "carpaint_roughness.png"
    source.write_text("fake source")
    (tmp_path / "carpaint_roughness.tif").write_text("fake roughness")
    model_data = {"materials": [{"name": "CarPaint"}]}
    refs = [TextureRef(str(source), "CarPaint", texture_type="roughness")]

    result = build_mtl_material_data(
        model_data,
        refs,
        texture_manager=None,
        texture_output_dir=str(tmp_path),
        output_format="tif",
    )

    assert result[0]["textures"]["roughness"] == str(tmp_path / "carpaint_roughness.tif")


def test_build_mtl_material_data_probes_multiple_output_extensions(tmp_path):
    source = tmp_path / "carpaint_roughness.png"
    source.write_text("fake source")
    (tmp_path / "carpaint_diff.dds").write_text("fake diff")
    (tmp_path / "carpaint_roughness.tif").write_text("fake roughness")
    model_data = {"materials": [{"name": "CarPaint"}]}
    refs = [TextureRef(str(source), "CarPaint", texture_type="roughness")]

    result = build_mtl_material_data(
        model_data,
        refs,
        texture_manager=None,
        texture_output_dir=str(tmp_path),
        output_format="dds,tif",
    )

    assert result[0]["textures"]["diffuse"] == str(tmp_path / "carpaint_diff.dds")
    assert result[0]["textures"]["roughness"] == str(tmp_path / "carpaint_roughness.tif")


def test_texture_output_extensions_normalizes_lists_auto_and_csv():
    assert texture_output_extensions("dds,tif;png") == ["dds", "tif"]
    assert texture_output_extensions([".dds", "dds", "TIF"]) == ["dds", "tif"]
    assert texture_output_extensions("auto") == ["dds", "hdr", "tif"]
    assert texture_output_extensions("png") == ["tif"]


def test_build_mtl_material_data_finds_ce_emissive_output_suffix(tmp_path):
    source = tmp_path / "wall_emissive.png"
    source.write_text("fake source")
    (tmp_path / "wall_em.tif").write_text("fake emissive")
    model_data = {"materials": [{"name": "Wall"}]}
    refs = [TextureRef(str(source), "Wall", texture_type="emissive")]

    result = build_mtl_material_data(
        model_data,
        refs,
        None,
        str(tmp_path),
        "tif",
    )

    assert result[0]["textures"]["emissive"] == str(tmp_path / "wall_em.tif")


def test_build_mtl_material_data_keeps_material_without_processed_textures(tmp_path):
    model_data = {
        "materials": [
            {
                "name": "Wall",
                "polygon_count": 3,
                "used_by_polygons": True,
                "mesh_names": ["WallMesh"],
                "material_names": ["Wall", "WallAlt"],
                "slot_name_conflict": True,
            }
        ]
    }

    result = build_mtl_material_data(
        model_data,
        [],
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert len(result) == 1
    assert result[0]["name"] == "Wall"
    assert result[0]["textures"] == {}
    assert result[0]["polygon_count"] == 3
    assert result[0]["used_by_polygons"] is True
    assert result[0]["mesh_names"] == ["WallMesh"]
    assert result[0]["material_names"] == ["Wall", "WallAlt"]
    assert result[0]["slot_name_conflict"] is True
    assert result[0]["texture_ref_evidence"] == []


def test_build_mtl_material_data_preserves_explicit_mtl_overrides(tmp_path):
    model_data = {
        "materials": [
            {
                "name": "Glass",
                "cryengine_material": {
                    "Shader": "Glass",
                    "StringGenMask": "%SPECULAR_MAP%TINT_MAP",
                    "PublicParams": {"TintCloudiness": "0.050000001"},
                },
            },
            {
                "name": "Paint",
                "mtl_overrides": {
                    "shader": "Multilayeredmaterials",
                    "string_gen_mask": "",
                    "public_params": {"Layer0ReflectivityScale": "1.5"},
                },
            },
        ]
    }

    result = build_mtl_material_data(
        model_data,
        [],
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert result[0]["cryengine_material"]["Shader"] == "Glass"
    assert result[0]["cryengine_material"]["PublicParams"]["TintCloudiness"] == "0.050000001"
    assert result[1]["mtl_overrides"]["shader"] == "Multilayeredmaterials"
    assert result[1]["mtl_overrides"]["string_gen_mask"] == ""
    assert result[1]["mtl_overrides"]["public_params"]["Layer0ReflectivityScale"] == "1.5"


def test_build_mtl_material_data_applies_bulk_material_overrides_by_name(tmp_path):
    model_data = {
        "materials": [
            {"name": "Paint"},
            {"name": "Glass"},
        ],
        "material_overrides": {
            "Paint": {
                "mtl_overrides": {
                    "shader": "Multilayeredmaterials",
                    "string_gen_mask": "",
                    "public_params": {"Layer0ReflectivityScale": "1.5"},
                },
            },
            "Glass": {
                "cryengine_material": {
                    "Shader": "Glass",
                    "StringGenMask": "%SPECULAR_MAP%TINT_MAP",
                    "PublicParams": {"TintCloudiness": "0.050000001"},
                },
            },
        },
    }

    result = build_mtl_material_data(
        model_data,
        [],
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert result[0]["mtl_overrides"]["shader"] == "Multilayeredmaterials"
    assert result[0]["mtl_overrides"]["string_gen_mask"] == ""
    assert result[1]["cryengine_material"]["Shader"] == "Glass"
    assert result[1]["cryengine_material"]["PublicParams"]["TintCloudiness"] == "0.050000001"


def test_build_mtl_material_data_follows_material_manifest_order(tmp_path):
    model_data = {
        "materials": [{"name": "Stone.001"}, {"name": "Stone"}],
        "material_manifest": {
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Stone.001"},
                ],
            }
        },
    }

    result = build_mtl_material_data(
        model_data,
        [],
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert [item["name"] for item in result] == ["Stone", "Stone.001"]
    assert [item["sub_index"] for item in result] == [0, 1]
    assert [item["auto_assigned"] for item in result] == [False, False]


def test_build_mtl_material_data_resolves_manifest_only_material_textures(tmp_path):
    source = tmp_path / "Glass_basecolor.png"
    source.write_text("fake source")
    (tmp_path / "Glass_diff.tif").write_text("fake diff")
    model_data = {
        "materials": [{"name": "Stone"}],
        "material_manifest": {
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Glass"},
                ],
            }
        },
    }
    refs = [TextureRef(str(source), "Glass", texture_type="diffuse")]

    result = build_mtl_material_data(
        model_data,
        refs,
        texture_manager=None,
        texture_output_dir=str(tmp_path),
        output_format="tif",
    )

    assert [item["name"] for item in result] == ["Stone", "Glass"]
    assert result[1]["textures"]["diffuse"] == str(tmp_path / "Glass_diff.tif")
