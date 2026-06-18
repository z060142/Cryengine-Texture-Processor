import json

from output_formats.material_diagnostics_exporter import (
    build_material_diagnostics_report,
    export_material_diagnostics,
)


def test_build_material_diagnostics_report_summarizes_hazards():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1},
            {"name": "Removed", "id": 2, "deleted": True},
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
    assert report["diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"


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
