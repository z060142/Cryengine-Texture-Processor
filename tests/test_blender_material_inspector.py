from tools.blender_material_inspector import (
    DEFAULT_MANIFEST_SUFFIX,
    _blender_script,
    default_manifest_path,
    inspect_fbx_materials,
)


def test_default_manifest_path_uses_fbx_material_manifest_suffix(tmp_path):
    fbx_path = tmp_path / "asset.fbx"

    assert default_manifest_path(str(fbx_path)).endswith(f"asset{DEFAULT_MANIFEST_SUFFIX}")


def test_blender_script_imports_fbx_and_writes_material_table_manifest():
    script = _blender_script("asset.fbx", "asset.fbx_material_manifest.json")

    assert "bpy.ops.import_scene.fbx" in script
    assert "'manifest_kind': 'blender-fbx-material-inspection'" in script
    assert "'material_table_slot': material_slot" in script
    assert "'expected_cgf_material_id': material_slot" in script


def test_inspect_fbx_materials_rejects_missing_blender(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    fbx_path.write_text("fake", encoding="utf-8")

    try:
        inspect_fbx_materials(str(tmp_path / "missing-blender.exe"), str(fbx_path))
    except RuntimeError as exc:
        assert "Blender executable not found" in str(exc)
    else:
        raise AssertionError("missing Blender should fail")


def test_inspect_fbx_materials_rejects_missing_fbx(tmp_path):
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")

    try:
        inspect_fbx_materials(str(blender), str(tmp_path / "missing.fbx"))
    except RuntimeError as exc:
        assert "FBX file not found" in str(exc)
    else:
        raise AssertionError("missing FBX should fail")
