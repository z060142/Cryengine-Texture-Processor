import json
from types import SimpleNamespace

from tools import asset_flow_validator


def test_texture_gate_case_reports_processed_outputs(tmp_path):
    (tmp_path / "wall_diff.tif").write_text("fake")
    report = asset_flow_validator.run_validation(
        {
            "cases": [
                {
                    "name": "textures",
                    "type": "texture_gate",
                    "paths": [str(tmp_path)],
                }
            ]
        }
    )

    assert report["summary"]["ok"] is True
    assert report["cases"][0]["checks"]["texture_format_ok"] is True


def test_rc_case_collects_acceptance_checks(monkeypatch, tmp_path):
    fbx = tmp_path / "asset.fbx"
    fbx.write_text("fake")
    manifest = tmp_path / "asset.fbx_material_manifest.json"
    cgf = tmp_path / "work" / "asset.cgf"
    cgf.parent.mkdir()
    cgf.write_text("fake")
    material_report = tmp_path / "work" / "asset.material_report.json"
    material_report.write_text(
        json.dumps(
            {
                    "summary": {
                        "rc_success": True,
                        "action_required": False,
                        "slot_alignment_ok": True,
                        "material_slot_evidence_ok": True,
                        "mtl_schema_gate_ok": True,
                    },
                    "mtl_schema_gate": {"gate": {"ok": True}},
            }
        ),
        encoding="utf-8",
    )

    def fake_inspect(blender, source_fbx, manifest_path):
        manifest.write_text("{}", encoding="utf-8")
        return {"success": True, "manifest": str(manifest)}

    monkeypatch.setattr(asset_flow_validator, "inspect_fbx_materials", fake_inspect)
    monkeypatch.setattr(
        asset_flow_validator,
        "material_specs_from_manifest",
        lambda source_fbx: [{"name": "Mat", "sub_index": 0}],
    )
    monkeypatch.setattr(
        asset_flow_validator,
        "run_rc_smoke_test",
        lambda *args, **kwargs: SimpleNamespace(
            success=True,
            expected_output_path=str(cgf),
            material_report_path=str(material_report),
            mtl_path=str(tmp_path / "work" / "asset.mtl"),
            json_path=str(tmp_path / "work" / "asset.json"),
            error="",
        ),
    )

    report = asset_flow_validator.run_validation(
        {
            "work_root": str(tmp_path / "work"),
            "cases": [
                {
                    "name": "asset",
                    "type": "rc",
                    "fbx": str(fbx),
                    "manifest": str(manifest),
                }
            ],
        }
    )

    assert report["summary"]["ok"] is True
    assert report["cases"][0]["checks"]["model_format_ok"] is True
    assert report["cases"][0]["checks"]["material_slots_ok"] is True
    assert report["cases"][0]["checks"]["mtl_format_ok"] is True
