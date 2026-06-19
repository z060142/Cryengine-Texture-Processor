from model_processing.model_loader import (
    LOAD_STATUS_DUMMY,
    LOAD_STATUS_IMPORT_ONLY,
    LOAD_STATUS_LOADED,
    ModelLoader,
)
from model_processing.texture_extractor import TextureExtractor, TextureReference


def test_create_dummy_model_records_load_error(tmp_path):
    loader = ModelLoader.__new__(ModelLoader)
    model_path = tmp_path / "missing.fbx"

    model = loader._create_dummy_model(str(model_path), "bpy unavailable")

    assert model["is_dummy"] is True
    assert model["load_status"] == LOAD_STATUS_DUMMY
    assert model["load_error"] == "bpy unavailable"
    assert model["materials"] == []
    assert model["meshes"] == []


def test_import_only_model_records_degraded_status(tmp_path):
    loader = ModelLoader.__new__(ModelLoader)
    model_path = tmp_path / "asset.fbx"

    model = loader._create_model_for_texture_extraction(str(model_path))

    assert model["is_import_only"] is True
    assert model["load_status"] == LOAD_STATUS_IMPORT_ONLY
    assert "filesystem texture scan" in model["load_warning"]
    assert model["materials"][0]["name"] == "asset"


def test_loaded_scene_model_records_loaded_status():
    assert LOAD_STATUS_LOADED == "loaded"


def test_texture_reference_serializes_source_mode():
    ref = TextureReference("wall_diff.tif", "diffuse", "Wall", source_mode="filesystem_no_bpy")

    assert ref.as_dict()["source_mode"] == "filesystem_no_bpy"


def test_texture_extractor_skips_dummy_models():
    extractor = TextureExtractor.__new__(TextureExtractor)
    extractor.bpy = None

    assert extractor.extract({"is_dummy": True, "path": "asset.fbx"}) == []


def test_texture_extractor_filesystem_scan_marks_no_bpy_source_mode(tmp_path):
    model_path = tmp_path / "asset.fbx"
    textures_dir = tmp_path / "textures"
    textures_dir.mkdir()
    texture_path = textures_dir / "asset_diff.png"
    texture_path.write_text("texture", encoding="utf-8")
    extractor = TextureExtractor.__new__(TextureExtractor)
    extractor.bpy = None

    refs = extractor.extract({"path": str(model_path), "materials": [{"name": "asset"}]})

    assert len(refs) == 1
    assert refs[0].path == str(texture_path)
    assert refs[0].texture_type == "diffuse"
    assert refs[0].material_name == "asset"
    assert refs[0].source_mode == "filesystem_no_bpy"


def test_texture_extractor_import_only_scan_marks_import_only_source_mode(tmp_path):
    model_path = tmp_path / "asset.fbx"
    texture_path = tmp_path / "asset_normal.png"
    texture_path.write_text("texture", encoding="utf-8")
    extractor = TextureExtractor.__new__(TextureExtractor)
    extractor.bpy = object()

    refs = extractor.extract(
        {
            "path": str(model_path),
            "is_import_only": True,
            "materials": [{"name": "asset"}],
        }
    )

    assert len(refs) == 1
    assert refs[0].texture_type == "normal"
    assert refs[0].source_mode == "filesystem_import_only"


def test_texture_extractor_filesystem_scan_uses_shared_suffix_resolver(tmp_path):
    model_path = tmp_path / "asset.fbx"
    texture_path = tmp_path / "asset_opacity.png"
    texture_path.write_text("texture", encoding="utf-8")
    extractor = TextureExtractor.__new__(TextureExtractor)
    extractor.bpy = None

    refs = extractor.extract({"path": str(model_path), "materials": [{"name": "asset"}]})

    assert len(refs) == 1
    assert refs[0].texture_type == "alpha"
