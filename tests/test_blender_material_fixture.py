import os

from tools.blender_material_fixture import (
    DEFAULT_MATERIALS,
    DEFAULT_POLYGON_SLOTS,
    build_blender_command,
    discover_default_blender,
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
