import json

from ui_pyside.model_import import (
    collect_model_material_diagnostics,
    generate_model_material_manifest,
    load_model_material_manifest,
    material_manifest_summary_text,
    model_display_name,
)


def test_collect_model_material_diagnostics_reports_deleted_known_slot():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {"name": "Visible", "id": 1},
                {
                    "name": "Removed",
                    "id": 2,
                    "deleted": True,
                    "polygon_count": 2,
                    "used_by_polygons": True,
                    "mesh_names": ["ProbeMesh"],
                },
            ]
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert diagnostics[0]["material"] == "Removed"
    assert diagnostics[0]["fbx_slot"] == 1
    assert diagnostics[0]["polygon_count"] == 2
    assert diagnostics[0]["used_by_polygons"] is True
    assert diagnostics[0]["mesh_names"] == ["ProbeMesh"]


def test_collect_model_material_diagnostics_is_empty_for_normal_slots():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {"name": "Bark", "id": 1},
                {"name": "Leaves", "id": 2},
            ]
        }
    )

    assert diagnostics == []


def test_collect_model_material_diagnostics_reports_slot_name_conflict_warning():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {
                    "name": "Wood",
                    "id": 1,
                    "material_names": ["Metal", "Wood"],
                    "slot_name_conflict": True,
                },
            ]
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["code"] == "material_slot_name_conflict"
    assert diagnostics[0]["material_names"] == ["Metal", "Wood"]


def test_model_display_name_marks_hazards():
    assert model_display_name({"filename": "tree.fbx", "material_diagnostics": []}) == "tree.fbx"
    assert (
        model_display_name(
            {
                "filename": "tree.fbx",
                "material_diagnostics": [{"severity": "warning"}],
            }
        )
        == "tree.fbx [diagnostics]"
    )
    assert (
        model_display_name(
            {
                "filename": "tree.fbx",
                "material_diagnostics": [{"severity": "hazard"}],
            }
        )
        == "tree.fbx [hazard]"
    )


def test_load_model_material_manifest_reads_fbx_material_sidecar(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Stone", "first_object": "Mesh", "first_local_slot": 0}],
                "polygons": [{"polygon": 0}],
            }
        ),
        encoding="utf-8",
    )

    info = load_model_material_manifest(str(fbx_path))

    assert info["path"] == str(manifest_path)
    assert info["summary"]["material_count"] == 1
    assert info["materials"] == [{"slot": 0, "name": "Stone", "source": "Mesh", "local_slot": 0}]
    assert material_manifest_summary_text(info) == "1 slots / 1 polygons (blender-fbx-material-inspection)"


def test_material_manifest_summary_text_handles_missing_manifest():
    assert material_manifest_summary_text({}) == "not found"


def test_generate_model_material_manifest_runs_inspector_and_reloads_sidecar(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fbx", encoding="utf-8")

    def fake_inspector(blender_path, model_path):
        assert blender_path == ""
        assert model_path == str(fbx_path)
        manifest_path.write_text(
            json.dumps(
                {
                    "manifest_kind": "blender-fbx-material-inspection",
                    "materials": [
                        {"slot": 0, "name": "Stone", "first_object": "MeshA", "first_local_slot": 0},
                        {"slot": 1, "name": "Stone.001", "first_object": "MeshB", "first_local_slot": 0},
                    ],
                    "polygons": [{"polygon": 0}, {"polygon": 1}],
                }
            ),
            encoding="utf-8",
        )
        return {"success": True, "manifest": str(manifest_path)}

    info = generate_model_material_manifest(str(fbx_path), inspector_func=fake_inspector)

    assert info["path"] == str(manifest_path)
    assert info["summary"]["material_count"] == 2
    assert info["materials"][1]["name"] == "Stone.001"
