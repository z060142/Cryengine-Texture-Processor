import os

from tools.blender_material_fixture import (
    DEFAULT_MATERIALS,
    DEFAULT_POLYGON_SLOTS,
    FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT,
    FIXTURE_KIND_SINGLE_MESH,
    MULTI_MESH_CONFLICT_MATERIALS,
    _blender_script,
    build_blender_command,
    discover_default_blender,
    generate_material_fixture,
    material_names_from_arg,
    polygon_slots_from_arg,
)


def test_material_names_from_arg_uses_defaults():
    assert material_names_from_arg("") == list(DEFAULT_MATERIALS)
    assert material_names_from_arg(" A, B ,, C ") == ["A", "B", "C"]


def test_polygon_slots_from_arg_uses_defaults():
    assert polygon_slots_from_arg("") == list(DEFAULT_POLYGON_SLOTS)
    assert polygon_slots_from_arg(" 0, 2 ,, 1 ") == [0, 2, 1]


def test_discover_default_blender_returns_first_existing_candidate(tmp_path):
    missing = tmp_path / "missing.exe"
    existing = tmp_path / "blender.exe"
    existing.write_text("fake", encoding="utf-8")

    assert discover_default_blender([str(missing), str(existing)]) == str(existing)


def test_build_blender_command_uses_background_factory_startup():
    command = build_blender_command("blender.exe", "script.py")

    assert command == ["blender.exe", "--background", "--factory-startup", "--python", "script.py"]


def test_discover_default_blender_returns_empty_when_missing(tmp_path):
    assert discover_default_blender([str(tmp_path / "missing.exe")]) == ""


def test_multi_mesh_name_conflict_script_uses_local_slot_zero_for_each_object():
    script = _blender_script(
        "out.fbx",
        "manifest.json",
        MULTI_MESH_CONFLICT_MATERIALS,
        DEFAULT_POLYGON_SLOTS,
        FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT,
    )

    assert "CE_MultiMeshSlotProbe_" in script
    assert "'material_slot': 0" in script
    assert "'expect_cgf_material_ids': list(range(len(material_names)))" in script
    assert "Two mesh objects each use local material slot 0" in script


def test_single_mesh_script_keeps_fixture_kind_default_behavior():
    script = _blender_script(
        "out.fbx",
        "manifest.json",
        DEFAULT_MATERIALS,
        DEFAULT_POLYGON_SLOTS,
        FIXTURE_KIND_SINGLE_MESH,
    )

    assert "CE_MaterialSlotProbeMesh" in script
    assert "CE_MultiMeshSlotProbe" not in script


def test_generate_material_fixture_rejects_unknown_fixture_kind(tmp_path):
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")

    try:
        generate_material_fixture(str(blender), tmp_path, fixture_kind="unknown")
    except RuntimeError as exc:
        assert "Unsupported fixture kind" in str(exc)
    else:
        raise AssertionError("unknown fixture kind should fail")
