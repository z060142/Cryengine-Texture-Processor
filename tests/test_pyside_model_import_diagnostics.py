from ui_pyside.model_import import collect_model_material_diagnostics, model_display_name


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
