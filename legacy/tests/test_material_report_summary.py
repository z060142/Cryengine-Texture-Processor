import json

from tools.material_report_summary import compact_material_report_summary, main


def test_compact_material_report_summary_extracts_gate_and_slot_counts():
    report = {
        "summary": {
            "rc_success": True,
            "action_required": False,
            "slot_alignment_ok": True,
            "cgf_material_id_alignment_ok": True,
            "cgf_import_settings_alignment_ok": True,
            "material_slot_evidence_ok": True,
            "material_slot_evidence_status_counts": {
                "matched_used_slot": 16,
                "trailing_unassigned_placeholder": 1,
            },
            "unassigned_placeholder_count": 1,
            "used_unassigned_material_count": 0,
        },
        "material_slot_evidence": {"summary": {"row_count": 17}},
        "texture_output_gate": {"summary": {"ok": True}},
        "mtl_schema_gate": {"summary": {"ok": True}},
    }

    assert compact_material_report_summary(report) == {
        "rc_success": True,
        "action_required": False,
        "slot_alignment_ok": True,
        "cgf_material_id_alignment_ok": True,
        "cgf_import_settings_alignment_ok": True,
        "material_slot_evidence_ok": True,
        "material_slot_evidence_status_counts": {
            "matched_used_slot": 16,
            "trailing_unassigned_placeholder": 1,
        },
        "unassigned_placeholder_count": 1,
        "used_unassigned_material_count": 0,
        "texture_output_gate_ok": True,
        "mtl_schema_gate_ok": True,
        "slot_rows": 17,
    }


def test_material_report_summary_cli_returns_nonzero_for_action_required(tmp_path, capsys):
    report_path = tmp_path / "asset.material_report.json"
    report_path.write_text(
        json.dumps({"summary": {"action_required": True, "rc_success": True}}),
        encoding="utf-8",
    )

    assert main([str(report_path)]) == 1
    assert "action_required: True" in capsys.readouterr().out
