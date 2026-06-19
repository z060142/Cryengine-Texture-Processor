import json
import os

from tools.rc_smoke_test import (
    build_smoke_model_data,
    collect_material_slot_diagnostics,
    discover_default_fbx,
    material_names_from_arg,
    material_specs_from_manifest,
    material_specs_from_arg,
    prepare_smoke_bundle,
    run_rc_smoke_test,
    source_material_specs_from_manifest,
)
from utils.rc_import_runner import RCImportResult
import xml.etree.ElementTree as ET


def test_material_names_from_arg_uses_default_when_empty():
    assert material_names_from_arg("") == ["Default"]
    assert material_names_from_arg(" Bark, Leaves ,,") == ["Bark", "Leaves"]


def test_material_specs_from_arg_supports_deleted_and_explicit_slots():
    assert material_specs_from_arg("") == [{"name": "Default", "id": 1, "index": 0}]
    assert material_specs_from_arg(" Bark, Leaves:deleted, Proxy:4 ,,") == [
        {"name": "Bark", "id": 1, "index": 0},
        {"name": "Leaves", "id": 2, "index": 1, "deleted": True, "sub_index": -1},
        {"name": "Proxy", "id": 3, "index": 2, "sub_index": 4, "auto_assigned": False},
    ]


def test_material_specs_from_manifest_uses_rc_material_table(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Stone.001"},
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = material_specs_from_manifest(str(fbx_path))

    assert [(spec["name"], spec["id"], spec["sub_index"], spec["auto_assigned"]) for spec in specs] == [
        ("Stone", 1, 0, False),
        ("Stone.001", 2, 1, False),
    ]


def test_source_material_specs_from_manifest_includes_polygon_only_materials(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Visible"}],
                "polygons": [
                    {"polygon": 0, "material_name": "Visible", "material_table_slot": 0},
                    {"polygon": 1, "material_name": "Missing", "material_table_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = source_material_specs_from_manifest(str(fbx_path))

    assert [(spec["name"], spec["polygon_count"], spec["used_by_polygons"]) for spec in specs] == [
        ("Visible", 1, True),
        ("Missing", 1, True),
    ]


def test_source_material_specs_from_manifest_skips_invalid_slots(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": "bad-slot", "name": "Broken"},
                    {"slot": -1, "name": "DeletedLooking"},
                    {"slot": True, "name": "BooleanSlot"},
                    {"slot": 1.5, "name": "FloatSlot"},
                    {"slot": 1, "name": "Visible"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "Broken", "material_table_slot": "bad-polygon-slot"},
                    {"polygon": 1, "material_name": "DeletedLooking", "material_table_slot": -1},
                    {"polygon": 2, "material_name": "BooleanSlot", "material_table_slot": True},
                    {"polygon": 3, "material_name": "FloatSlot", "material_table_slot": 1.5},
                    {"polygon": 4, "material_name": "Visible", "material_table_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = source_material_specs_from_manifest(str(fbx_path))

    assert [(spec["name"], spec["material_table_slot"], spec["polygon_count"]) for spec in specs] == [
        ("Visible", 1, 1),
    ]


def test_source_material_specs_from_manifest_skips_invalid_rows(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": ["bad-row", {"slot": 1, "name": "Visible"}],
                "polygons": [False, {"polygon": 0, "material_name": "Visible", "material_table_slot": 1}],
            }
        ),
        encoding="utf-8",
    )

    specs = source_material_specs_from_manifest(str(fbx_path))

    assert [(spec["name"], spec["material_table_slot"], spec["polygon_count"]) for spec in specs] == [
        ("Visible", 1, 1),
    ]


def test_source_material_specs_from_manifest_skips_invalid_names(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": ""},
                    {"slot": 1, "name": 123},
                    {"slot": 2, "name": "Visible"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "", "material_table_slot": 0},
                    {"polygon": 1, "material_name": 123, "material_table_slot": 1},
                    {"polygon": 2, "material_name": "Visible", "material_table_slot": 2},
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = source_material_specs_from_manifest(str(fbx_path))

    assert [(spec["name"], spec["material_table_slot"], spec["polygon_count"]) for spec in specs] == [
        ("Visible", 2, 1),
    ]


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


def test_build_smoke_model_data_accepts_manifest_scene_hierarchy():
    hierarchy = [{"name": "Root", "mass": -1.0, "density": -1.0, "children": []}]

    model_data = build_smoke_model_data("asset", ["Bark"], scene_hierarchy=hierarchy)

    assert model_data["scene_hierarchy"] == hierarchy


def test_collect_material_slot_diagnostics_reports_deleted_known_slot():
    diagnostics = collect_material_slot_diagnostics(
        [{"name": "Visible", "id": 1}, {"name": "Removed", "id": 2, "deleted": True}]
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert diagnostics[0]["original_name"] == "Removed"
    assert diagnostics[0]["fbx_slot"] == 1


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
    assert payload["source_filename"] == "asset.fbx"
    assert "request" not in payload
    assert payload["materials"] == [
        {"name": "Bark", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Leaves", "physicalize": "no_collide", "sub_index": 1},
    ]


def test_prepare_smoke_bundle_copies_material_manifest_sidecar(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Stone.001"},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    copied_manifest = work_dir / "asset.fbx_material_manifest.json"
    assert bundle["copied_manifest_path"] == str(copied_manifest)
    assert copied_manifest.exists()
    payload = json.loads((work_dir / "asset.json").read_text(encoding="utf-8"))
    assert payload["materials"] == [
        {"name": "Stone", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Stone.001", "physicalize": "no_collide", "sub_index": 1},
    ]
    root = ET.parse(bundle["mtl_path"]).getroot()
    sub_materials = root.find("SubMaterials")
    assert [material.get("Name") for material in list(sub_materials)] == ["Stone", "Stone.001"]


def test_prepare_smoke_bundle_uses_material_manifest_scene_hierarchy(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Stone", "physicalize": "no"}],
                "scene_hierarchy": [
                    {
                        "name": "Root",
                        "mass": -1.0,
                        "density": -1.0,
                        "children": [{"name": "Mesh", "mass": -1.0, "density": -1.0, "children": []}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    payload = json.loads((work_dir / "asset.json").read_text(encoding="utf-8"))
    assert payload["nodes"] == [
        {
            "name": "Root",
            "path": ["Root"],
            "mass": -1.0,
            "density": -1.0,
            "nodes": [
                {
                    "name": "Mesh",
                    "path": ["Root", "Mesh"],
                    "mass": -1.0,
                    "density": -1.0,
                }
            ],
        }
    ]


def test_prepare_smoke_bundle_reports_manifest_omitted_source_material(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Visible"}],
                "polygons": [
                    {"polygon": 0, "material_name": "Visible", "material_table_slot": 0},
                    {"polygon": 1, "material_name": "Missing", "material_table_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    assert bundle["material_diagnostics"][0]["code"] == "rc_omitted_source_material_faces_deleted"
    assert bundle["material_diagnostics"][0]["material"] == "Missing"


def test_prepare_smoke_bundle_reports_manifest_duplicate_name(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Stone"},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    assert bundle["material_diagnostics"][0]["code"] == "material_manifest_duplicate_name"
    assert bundle["material_diagnostics"][0]["material"] == "Stone"


def test_prepare_smoke_bundle_reports_manifest_polygon_mismatch(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Metal"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "Stone", "material_table_slot": 0},
                    {"polygon": 1, "material_name": "Stone", "material_table_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    assert bundle["material_diagnostics"][0]["code"] == "material_manifest_polygon_slot_name_mismatch"
    assert bundle["material_diagnostics"][0]["polygon_material_name"] == "Stone"
    assert bundle["material_diagnostics"][0]["table_material_name"] == "Metal"


def test_prepare_smoke_bundle_reports_invalid_manifest_slots(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": "bad-slot", "name": "Broken"},
                    {"slot": -1, "name": "DeletedLooking"},
                    {"slot": True, "name": "BooleanSlot"},
                    {"slot": 1.5, "name": "FloatSlot"},
                    {"slot": 1, "name": "Visible"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "Broken", "material_table_slot": "bad-polygon-slot"},
                    {"polygon": 1, "material_name": "DeletedLooking", "material_table_slot": -1},
                    {"polygon": 2, "material_name": "BooleanSlot", "material_table_slot": True},
                    {"polygon": 3, "material_name": "FloatSlot", "material_table_slot": 1.5},
                    {"polygon": 4, "material_name": "Visible", "material_table_slot": 1},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert codes.count("material_manifest_invalid_material_slot") == 4
    assert codes.count("material_manifest_invalid_polygon_slot") == 4


def test_prepare_smoke_bundle_reports_invalid_manifest_polygon_indices(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Stone"}],
                "polygons": [
                    {"material_name": "Stone", "material_table_slot": 0},
                    {"polygon": True, "material_name": "Stone", "material_table_slot": 0},
                    {"polygon": "2", "material_name": "Stone", "material_table_slot": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert codes.count("material_manifest_invalid_polygon_index") == 2


def test_prepare_smoke_bundle_reports_invalid_manifest_shape(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": ["bad-row", {"slot": 0, "name": "Stone"}],
                "polygons": [False, {"polygon": 0, "material_name": "Stone", "material_table_slot": 0}],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert "material_manifest_invalid_material_row" in codes
    assert "material_manifest_invalid_polygon_row" in codes


def test_prepare_smoke_bundle_reports_invalid_manifest_names(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": ""},
                    {"slot": 1, "name": 123},
                    {"slot": 2, "name": "Visible"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "", "material_table_slot": 0},
                    {"polygon": 1, "material_name": 123, "material_table_slot": 1},
                    {"polygon": 2, "material_name": "Visible", "material_table_slot": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert "material_manifest_invalid_material_name" in codes
    assert "material_manifest_invalid_polygon_material_name" in codes


def test_prepare_smoke_bundle_reports_invalid_manifest_root(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=[{"name": "Stone", "id": 1, "index": 0}],
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert "material_manifest_invalid_root" in codes


def test_prepare_smoke_bundle_reports_out_of_range_manifest_slots(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    manifest_path = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 127, "name": "LastValid"},
                    {"slot": 128, "name": "TooHigh"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "LastValid", "material_table_slot": 127},
                    {"polygon": 1, "material_name": "TooHigh", "material_table_slot": 128},
                ],
            }
        ),
        encoding="utf-8",
    )
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=material_specs_from_manifest(str(source_fbx)),
    )

    codes = [diagnostic["code"] for diagnostic in bundle["material_diagnostics"]]
    assert "material_manifest_material_slot_out_of_rc_range" in codes
    assert "material_manifest_polygon_slot_out_of_rc_range" in codes
    assert "rc_sub_index_out_of_range_deleted" in codes


def test_prepare_smoke_bundle_writes_deleted_material_request_and_mtl_gap(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    source_fbx.write_text("fake fbx", encoding="utf-8")
    work_dir = tmp_path / "work"

    bundle = prepare_smoke_bundle(
        str(source_fbx),
        str(work_dir),
        asset_name="asset",
        material_specs=[
            {"name": "Slot_0_Red", "id": 1, "index": 0},
            {"name": "Slot_1_Green", "id": 2, "index": 1, "deleted": True, "sub_index": -1},
            {"name": "Slot_2_Blue", "id": 3, "index": 2},
        ],
    )

    payload = json.loads((work_dir / "asset.json").read_text(encoding="utf-8"))
    assert payload["materials"] == [
        {"name": "Slot_0_Red", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Slot_1_Green", "physicalize": "no_collide", "sub_index": -1},
        {"name": "Slot_2_Blue", "physicalize": "no_collide", "sub_index": 2},
    ]

    root = ET.parse(bundle["mtl_path"]).getroot()
    sub_materials = root.find("SubMaterials")
    assert [material.get("Name") for material in list(sub_materials)] == [
        "Slot_0_Red",
        "unassigned",
        "Slot_2_Blue",
    ]
    assert bundle["material_diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"


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
    assert result.material_report_path.endswith("asset.material_report.json")
    assert os.path.exists(result.material_report_path)


def test_run_rc_smoke_test_writes_preflight_material_diagnostics(tmp_path):
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
        material_specs=[
            {"name": "Visible", "id": 1},
            {"name": "Removed", "id": 2, "deleted": True},
        ],
        runner_factory=FakeRunner,
    )

    assert result.success
    report = json.loads(open(result.material_report_path, encoding="utf-8").read())
    assert report["preflight_material_diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"
