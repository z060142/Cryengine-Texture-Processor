import os

from model_processing.fbx_exporter import (
    fallback_diffuse_texture_path,
    relative_blender_texture_path,
    resolve_texture_output_dir,
    select_diffuse_texture_path,
)


def test_resolve_texture_output_dir_defaults_to_textures_next_to_fbx(tmp_path):
    fbx_path = tmp_path / "models" / "chair.fbx"

    assert resolve_texture_output_dir(fbx_path) == os.path.abspath(
        tmp_path / "models" / "textures"
    )


def test_resolve_texture_output_dir_anchors_relative_path_to_fbx_dir(tmp_path):
    fbx_path = tmp_path / "models" / "chair.fbx"

    assert resolve_texture_output_dir(fbx_path, "textures") == os.path.abspath(
        tmp_path / "models" / "textures"
    )


def test_resolve_texture_output_dir_preserves_absolute_path(tmp_path):
    fbx_path = tmp_path / "models" / "chair.fbx"
    texture_dir = os.path.abspath(tmp_path / "processed_textures")

    assert resolve_texture_output_dir(fbx_path, texture_dir) == texture_dir


def test_select_diffuse_texture_path_prefers_processed_diff_key():
    texture_data = {
        "Body": {
            "diff": r"C:\out\Body_diff.tif",
            "diffuse": r"C:\old\Body_diffuse.png",
            "albedo": r"C:\old\Body_albedo.png",
        }
    }

    assert select_diffuse_texture_path("Body", texture_data) == r"C:\out\Body_diff.tif"


def test_select_diffuse_texture_path_keeps_legacy_fallback_keys():
    assert select_diffuse_texture_path(
        "Body", {"Body": {"diffuse": r"C:\old\Body_diffuse.png"}}
    ) == r"C:\old\Body_diffuse.png"
    assert select_diffuse_texture_path(
        "Body", {"Body": {"albedo": r"C:\old\Body_albedo.png"}}
    ) == r"C:\old\Body_albedo.png"


def test_select_diffuse_texture_path_returns_none_for_missing_material():
    assert select_diffuse_texture_path("Body", {"Trim": {"diff": "Trim_diff.tif"}}) is None


def test_relative_blender_texture_path_uses_fbx_directory_and_forward_slashes(tmp_path):
    fbx_path = tmp_path / "models" / "chair.fbx"
    texture_path = tmp_path / "models" / "textures" / "Body_diff.tif"

    assert relative_blender_texture_path(fbx_path, texture_path) == "textures/Body_diff.tif"


def test_fallback_diffuse_texture_path_preserves_legacy_name_guess(tmp_path):
    assert fallback_diffuse_texture_path("Body.001", tmp_path) == os.path.join(
        tmp_path, "Body_diff.tif"
    )
