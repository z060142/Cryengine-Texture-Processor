from core.material_manager import MaterialManager
from core.model_manager import LEGACY_MODEL_MANAGER_STATUS, ModelManager
from core.texture_manager import TextureGroup, TextureManager


def test_texture_manager_deduplicates_absolute_paths_and_groups_by_base(tmp_path):
    texture_path = tmp_path / "wall_diff.png"
    texture_path.write_text("texture", encoding="utf-8")
    manager = TextureManager()

    first = manager.add_texture(str(texture_path))
    second = manager.add_texture(str(texture_path))

    assert first is not None
    assert second is None
    assert first["type"] == "diffuse"
    assert first["base_name"] == "wall"
    assert [group.base_name for group in manager.get_all_groups()] == ["wall"]


def test_texture_manager_reclassifies_existing_texture_between_slots(tmp_path):
    texture_path = tmp_path / "wall_diff.png"
    texture_path.write_text("texture", encoding="utf-8")
    manager = TextureManager()
    texture = manager.add_texture(str(texture_path))

    assert manager.update_texture_type(texture, "emissive") is True

    group = manager.get_all_groups()[0]
    assert group.textures["diffuse"] is None
    assert group.textures["emissive"] is texture
    assert texture["type"] == "emissive"
    assert texture["is_unknown"] is False


def test_texture_group_generation_methods_are_state_accessors():
    group = TextureGroup("wall")
    group.intermediate["albedo"] = "wall_albedo.tif"
    group.output["diff"] = "wall_diff.tif"

    assert group.generate_intermediate_formats({"process_metallic": True}) == group.intermediate
    assert group.generate_output_formats({"output_format": "tif"}) == group.output


def test_legacy_model_manager_marks_stub_status(tmp_path):
    manager = ModelManager()
    model_path = tmp_path / "asset.fbx"

    model = manager.load_model(str(model_path))

    assert manager.manager_status == LEGACY_MODEL_MANAGER_STATUS
    assert model["manager_status"] == LEGACY_MODEL_MANAGER_STATUS
    assert model["load_status"] == "legacy_stub"
    assert model["filename"] == "asset.fbx"
    assert manager.texture_references == []
    assert manager.match_textures_with_processed({"diffuse": "asset_diff.tif"}) == {}
    assert manager.update_materials() is None
    assert manager.export_model(str(tmp_path / "asset_out.fbx")) == str(tmp_path / "asset_out.fbx")


def test_material_manager_applies_matching_texture_group_to_dict_model():
    manager = MaterialManager()
    group = TextureGroup("Wall")
    group.output.update(
        {
            "diff": "Wall_diff.tif",
            "spec": "Wall_spec.tif",
            "ddna": "Wall_ddna.tif",
            "displ": "Wall_displ.tif",
            "emissive": "Wall_emissive.tif",
            "sss": "Wall_sss.tif",
        }
    )
    model = {"materials": [{"name": "Wall"}]}

    assert manager.apply_to_model(model, [group]) is model
    material = manager.get_material("Wall")
    assert material.textures["diffuse"] == "Wall_diff.tif"
    assert material.textures["specular"] == "Wall_spec.tif"
    assert material.textures["normal"] == "Wall_ddna.tif"
    assert material.textures["displacement"] == "Wall_displ.tif"
    assert material.textures["emissive"] == "Wall_emissive.tif"
    assert material.textures["sss"] == "Wall_sss.tif"
