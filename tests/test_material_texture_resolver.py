import os

from model_processing.material_texture_resolver import (
    build_fbx_texture_data,
    build_mtl_material_data,
    clean_material_name,
    iter_unique_clean_materials,
    strip_known_texture_suffix,
)


class TextureRef:
    def __init__(self, path, material_name):
        self.path = path
        self.material_name = material_name


class TextureManagerStub:
    def classify_texture(self, file_path):
        filename = os.path.splitext(os.path.basename(file_path))[0]
        return "diffuse", filename.removesuffix("_albedo")


def test_clean_material_name_removes_blender_duplicate_suffix():
    assert clean_material_name("Stone.001") == "Stone"
    assert clean_material_name("Stone") == "Stone"


def test_iter_unique_clean_materials_skips_defaults_and_duplicate_suffixes():
    materials = [
        {"name": "Material"},
        {"name": "Stone"},
        {"name": "Stone.001"},
        {"name": "Metal"},
    ]

    result = list(iter_unique_clean_materials(materials))

    assert [item["clean_name"] for item in result] == ["Stone", "Metal"]
    assert [item["sub_index"] for item in result] == [0, 1]


def test_strip_known_texture_suffix_handles_cryengine_outputs():
    assert strip_known_texture_suffix("wall_diff") == "wall"
    assert strip_known_texture_suffix("wall_ddna") == "wall"
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


def test_build_mtl_material_data_keeps_material_without_processed_textures(tmp_path):
    model_data = {"materials": [{"name": "Wall"}]}

    result = build_mtl_material_data(
        model_data,
        [],
        TextureManagerStub(),
        str(tmp_path),
        "tif",
    )

    assert result == [{"name": "Wall", "textures": {}}]
