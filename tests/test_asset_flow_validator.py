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


def test_texture_process_case_reports_raw_to_processed_flow(monkeypatch, tmp_path):
    source = tmp_path / "wall_a.tga"
    source.write_text("fake")
    output_dir = tmp_path / "out"

    class FakeProcessor:
        def __init__(self, texture_manager):
            self.texture_manager = texture_manager
            self.texture_output_report_path = str(output_dir / "texture_output_diagnostics.json")
            self.texture_output_report = {
                "summary": {
                    "group_count": 1,
                    "output_count": 1,
                    "diagnostic_count": 0,
                    "ok": True,
                }
            }

        def set_output_dir(self, value):
            output_dir.mkdir(exist_ok=True)

        def set_settings(self, value):
            self.settings = value

        def set_progress_callback(self, callback):
            self.callback = callback

        def process_all_groups(self):
            group = self.texture_manager.get_all_groups()[0]
            group.output["diff"] = str(output_dir / "wall_diff.tif")
            return True

        def is_processing(self):
            return False

    monkeypatch.setattr(asset_flow_validator, "BatchProcessor", FakeProcessor)

    report = asset_flow_validator.run_validation(
        {
            "cases": [
                {
                    "name": "raw_textures",
                    "type": "texture_process",
                    "textures": [str(source)],
                    "output_dir": str(output_dir),
                }
            ]
        }
    )

    assert report["summary"]["ok"] is True
    case = report["cases"][0]
    assert case["checks"]["raw_textures_found"] is True
    assert case["checks"]["texture_format_ok"] is True
    assert case["groups"][0]["outputs"]["diff"].endswith("wall_diff.tif")


def test_format_markdown_report_summarizes_cases():
    markdown = asset_flow_validator.format_markdown_report(
        {
            "summary": {
                "ok": True,
                "case_count": 1,
                "ok_count": 1,
                "failed_count": 0,
            },
            "cases": [
                {
                    "name": "asset",
                    "type": "rc",
                    "ok": True,
                    "checks": {
                        "model_format_ok": True,
                        "texture_format_ok": None,
                    },
                    "cgf": "S:/out/asset.cgf",
                }
            ],
        }
    )

    assert "# CryEngine Asset Flow Validation" in markdown
    assert "asset" in markdown
    assert "model_format_ok=PASS" in markdown
    assert "texture_format_ok=N/A" in markdown
    assert "S:/out/asset.cgf" in markdown


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
