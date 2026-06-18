import json
import os

from tools.rc_smoke_test import (
    build_smoke_model_data,
    discover_default_fbx,
    material_names_from_arg,
    prepare_smoke_bundle,
    run_rc_smoke_test,
)
from utils.rc_import_runner import RCImportResult


def test_material_names_from_arg_uses_default_when_empty():
    assert material_names_from_arg("") == ["Default"]
    assert material_names_from_arg(" Bark, Leaves ,,") == ["Bark", "Leaves"]


def test_discover_default_fbx_returns_first_existing_candidate(tmp_path):
    missing = tmp_path / "missing.fbx"
    existing = tmp_path / "sample.fbx"
    existing.write_text("fake fbx", encoding="utf-8")

    assert discover_default_fbx([str(missing), str(existing)]) == str(existing)


def test_build_smoke_model_data_uses_empty_node_list():
    model_data = build_smoke_model_data("asset", ["Bark", "Leaves"])

    assert model_data["path"] == "asset.fbx"
    assert model_data["scene_hierarchy"] == []
    assert model_data["materials"] == [
        {"name": "Bark", "id": 1, "index": 0},
        {"name": "Leaves", "id": 2, "index": 1},
    ]


def test_prepare_smoke_bundle_copies_fbx_and_writes_mtl_and_request(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_names=["Bark", "Leaves"],
    )

    assert (work_dir / "asset.fbx").read_text(encoding="utf-8") == "fake fbx"
    assert os.path.exists(bundle["mtl_path"])
    payload = json.loads((work_dir / "asset.json").read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"request"}
    assert payload["request"]["source_filename"] == "asset.fbx"
    assert payload["request"]["materials"] == [
        {"name": "Bark", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Leaves", "physicalize": "no_collide", "sub_index": 1},
    ]


def test_run_rc_smoke_test_reports_missing_rc(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    source_fbx.write_text("fake fbx", encoding="utf-8")

    result = run_rc_smoke_test("", str(source_fbx), str(tmp_path / "work"))

    assert not result.success
    assert result.error == "RC executable path is required"


def test_run_rc_smoke_test_reports_missing_fbx(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")

    result = run_rc_smoke_test(str(rc_path), str(tmp_path / "missing.fbx"), str(tmp_path / "work"))

    assert not result.success
    assert "Source FBX not found" in result.error


def test_run_rc_smoke_test_uses_runner_factory(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")
    source_fbx = tmp_path / "source.fbx"
    source_fbx.write_text("fake fbx", encoding="utf-8")

    class FakeRunner:
        def __init__(self, rc_exe_path):
            self.rc_exe_path = rc_exe_path

        def run(self, json_path, source_fbx_path=None):
            return RCImportResult(
                success=True,
                command=[self.rc_exe_path, json_path],
                json_path=json_path,
                expected_output_path=os.path.splitext(json_path)[0] + ".cgf",
                returncode=0,
                stdout="ok",
            )

    result = run_rc_smoke_test(
        str(rc_path),
        str(source_fbx),
        str(tmp_path / "work"),
        asset_name="asset",
        runner_factory=FakeRunner,
    )

    assert result.success
    assert result.rc_result.stdout == "ok"
    assert result.json_path.endswith("asset.json")
    assert result.copied_fbx_path.endswith("asset.fbx")
