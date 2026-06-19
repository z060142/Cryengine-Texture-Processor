import json

from output_formats.material_diagnostics_exporter import (
    build_material_diagnostics_report,
    export_material_diagnostics,
)


def test_build_material_diagnostics_report_summarizes_hazards():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1},
            {
                "name": "Removed",
                "id": 2,
                "deleted": True,
                "polygon_count": 3,
                "used_by_polygons": True,
                "mesh_names": ["ProbeMesh"],
                "material_names": ["Removed"],
                "slot_name_conflict": False,
            },
        ],
        source_model="probe.fbx",
        artifact_kind="fbx",
    )

    assert report["source_model"] == "probe.fbx"
    assert report["artifact_kind"] == "fbx"
    assert report["summary"] == {
        "material_count": 2,
        "diagnostic_count": 1,
        "hazard_count": 1,
    }
    assert report["materials"][1]["name"] == "Removed"
    assert report["materials"][1]["fbx_slot"] == 1
    assert report["materials"][1]["polygon_count"] == 3
    assert report["materials"][1]["used_by_polygons"] is True
    assert report["materials"][1]["mesh_names"] == ["ProbeMesh"]
    assert report["materials"][1]["material_names"] == ["Removed"]
    assert report["materials"][1]["slot_name_conflict"] is False
    assert report["diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert report["diagnostics"][0]["polygon_count"] == 3
    assert report["diagnostics"][0]["used_by_polygons"] is True
    assert report["diagnostics"][0]["mesh_names"] == ["ProbeMesh"]


def test_build_material_diagnostics_report_includes_slot_name_conflict_warning():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wood",
                "id": 1,
                "polygon_count": 2,
                "used_by_polygons": True,
                "mesh_names": ["MeshA", "MeshB"],
                "material_names": ["Metal", "Wood"],
                "slot_name_conflict": True,
            }
        ],
        source_model="conflict.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["slot_name_conflict"] is True
    assert report["materials"][0]["material_names"] == ["Metal", "Wood"]
    assert report["diagnostics"][0]["severity"] == "warning"
    assert report["diagnostics"][0]["code"] == "material_slot_name_conflict"
    assert report["diagnostics"][0]["material_names"] == ["Metal", "Wood"]


def test_build_material_diagnostics_report_includes_case_insensitive_name_collision():
    report = build_material_diagnostics_report(
        [
            {"name": "Wood", "id": 1},
            {"name": "wood", "id": 2},
        ],
        source_model="case.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 2
    assert report["summary"]["hazard_count"] == 2
    assert report["materials"][0]["case_insensitive_name_conflict"] is True
    assert report["materials"][0]["case_insensitive_material_names"] == ["Wood", "wood"]
    assert report["diagnostics"][0]["code"] == "rc_case_insensitive_material_name_collision"
    assert report["diagnostics"][0]["case_insensitive_material_names"] == ["Wood", "wood"]


def test_build_material_diagnostics_report_includes_texture_ref_evidence_warning():
    evidence = [
        {
            "path": "textures/wall_diff.png",
            "filename": "wall_diff.png",
            "texture_type": "diffuse",
            "source_mode": "filesystem_no_bpy",
        }
    ]
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wall",
                "id": 1,
                "texture_ref_evidence": evidence,
            }
        ],
        source_model="wall.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["texture_ref_evidence"] == evidence
    assert report["materials"][0]["diagnostics"][0]["code"] == "degraded_texture_reference_source"
    assert report["diagnostics"][0]["source_modes"] == ["filesystem_no_bpy"]
    assert report["diagnostics"][0]["texture_ref_evidence"] == evidence


def test_build_material_diagnostics_report_does_not_warn_for_blender_texture_evidence():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wall",
                "id": 1,
                "texture_ref_evidence": [
                    {
                        "path": "textures/wall_diff.png",
                        "filename": "wall_diff.png",
                        "texture_type": "diffuse",
                        "source_mode": "blender",
                    }
                ],
            }
        ]
    )

    assert report["summary"]["diagnostic_count"] == 0
    assert report["diagnostics"] == []


def test_build_material_diagnostics_report_allows_deleted_known_unused_slot():
    report = build_material_diagnostics_report(
        [
            {"name": "Removed", "id": 2, "deleted": True, "polygon_count": 0},
        ],
        source_model="probe.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 0
    assert report["summary"]["hazard_count"] == 0


def test_build_material_diagnostics_report_flags_deleted_known_used_slot():
    report = build_material_diagnostics_report(
        [
            {"name": "Removed", "id": 2, "deleted": True, "polygon_count": 4},
        ],
        source_model="probe.fbx",
    )

    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["fbx_slot"] == 1


def test_build_material_diagnostics_report_keeps_clean_material_records_without_hazards():
    report = build_material_diagnostics_report(
        [
            {"name": "Bark", "id": 1},
            {"name": "Leaves", "id": 2},
        ],
        source_model="tree.fbx",
    )

    assert report["summary"]["hazard_count"] == 0
    assert report["diagnostics"] == []
    assert [item["sub_index"] for item in report["materials"]] == [0, 1]


def test_build_material_diagnostics_report_flags_used_ignored_source_material():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1},
            {"name": "Material", "id": 2, "polygon_count": 4, "used_by_polygons": True},
        ],
        source_model="default_material.fbx",
    )

    assert report["summary"]["material_count"] == 1
    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["code"] == "rc_omitted_source_material_faces_deleted"
    assert report["diagnostics"][0]["material"] == "Material"
    assert report["diagnostics"][0]["polygon_count"] == 4


def test_build_material_diagnostics_report_does_not_warn_when_only_ignored_materials_are_present():
    report = build_material_diagnostics_report(
        [{"name": "Material", "id": 1, "polygon_count": 4, "used_by_polygons": True}],
        source_model="default_only.fbx",
    )

    assert report["summary"]["material_count"] == 0
    assert report["summary"]["diagnostic_count"] == 0
    assert report["diagnostics"] == []


def test_build_material_diagnostics_report_uses_existing_mtl_fallback_when_provided():
    report = build_material_diagnostics_report(
        [
            {"name": "Reserved", "sub_index": 0, "auto_assigned": False},
            {"name": "Moved", "id": 1},
        ],
        existing_submaterial_names=["Reserved", "Moved"],
    )

    assert report["materials"][1]["name"] == "Moved"
    assert report["materials"][1]["sub_index"] == 1
    assert report["diagnostics"][0]["code"] == "sub_index_differs_from_fbx_slot_usage_unknown"


def test_build_material_diagnostics_report_flags_duplicate_sub_index():
    report = build_material_diagnostics_report(
        [
            {"name": "Wood", "id": 1, "sub_index": 0, "auto_assigned": False},
            {"name": "Metal", "id": 2, "sub_index": 0, "auto_assigned": False},
        ],
        source_model="duplicate.fbx",
    )

    assert report["summary"]["hazard_count"] == 3
    assert report["materials"][0]["duplicate_sub_index_conflict"] is True
    assert report["materials"][0]["duplicate_sub_index_material_names"] == ["Wood", "Metal"]
    assert report["diagnostics"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"
    assert report["diagnostics"][0]["duplicate_sub_index_material_names"] == ["Wood", "Metal"]


def test_build_material_diagnostics_report_flags_rc_sub_index_limit():
    report = build_material_diagnostics_report(
        [{"name": "TooHigh", "sub_index": 128, "auto_assigned": False}],
        source_model="too_high.fbx",
    )

    assert report["summary"]["hazard_count"] == 1
    assert report["materials"][0]["sub_index"] == -1
    assert report["materials"][0]["requested_sub_index"] == 128
    assert report["diagnostics"][0]["code"] == "rc_sub_index_out_of_range_deleted"


def test_build_material_diagnostics_report_flags_unknown_physicalize():
    report = build_material_diagnostics_report(
        [{"name": "Odd", "physicalize": "render_only"}],
        source_model="odd.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["physicalize"] == "no"
    assert report["materials"][0]["requested_physicalize"] == "render_only"
    assert report["diagnostics"][0]["code"] == "rc_unknown_physicalize_defaults_to_no"


def test_export_material_diagnostics_writes_json(tmp_path):
    output_path = export_material_diagnostics(
        [{"name": "Removed", "id": 1, "deleted": True}],
        str(tmp_path),
        "asset.material_diagnostics.json",
        source_model="asset.fbx",
    )

    payload = json.loads((tmp_path / "asset.material_diagnostics.json").read_text(encoding="utf-8"))

    assert output_path.endswith("asset.material_diagnostics.json")
    assert payload["source_model"] == "asset.fbx"
    assert payload["summary"]["hazard_count"] == 1
