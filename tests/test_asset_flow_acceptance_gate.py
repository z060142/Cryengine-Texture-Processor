import json

from tools import asset_flow_acceptance_gate


def report_with_counts(ok=True, **counts):
    return {
        "summary": {
            "ok": ok,
            "check_counts": counts,
        }
    }


def test_evaluate_report_passes_required_coverage():
    gate = asset_flow_acceptance_gate.evaluate_report(
        report_with_counts(
            material_texture_ok={"pass": 3, "fail": 0, "na": 0},
            model_format_ok={"pass": 3, "fail": 0, "na": 0},
        ),
        requirements={"material_texture_ok": 3, "model_format_ok": 3},
    )

    assert gate["ok"] is True
    assert gate["failures"] == []


def test_evaluate_report_fails_when_pass_count_is_too_low():
    gate = asset_flow_acceptance_gate.evaluate_report(
        report_with_counts(material_texture_ok={"pass": 2, "fail": 0, "na": 1}),
        requirements={"material_texture_ok": 3},
    )

    assert gate["ok"] is False
    assert "material_texture_ok pass count 2 < required 3" in gate["failures"]


def test_evaluate_report_fails_when_required_check_has_failures():
    gate = asset_flow_acceptance_gate.evaluate_report(
        report_with_counts(material_texture_ok={"pass": 3, "fail": 1, "na": 0}),
        requirements={"material_texture_ok": 3},
    )

    assert gate["ok"] is False
    assert "material_texture_ok has 1 failed checks" in gate["failures"]


def test_main_writes_gate_report_and_prints_counts(tmp_path, capsys):
    report = tmp_path / "asset_flow.json"
    output = tmp_path / "gate.json"
    report.write_text(
        json.dumps(
            report_with_counts(
                material_texture_ok={"pass": 3, "fail": 0, "na": 0},
            )
        ),
        encoding="utf-8",
    )

    rc = asset_flow_acceptance_gate.main(
        [
            "--report",
            str(report),
            "--output",
            str(output),
            "--no-defaults",
            "--require",
            "material_texture_ok:3",
        ]
    )

    assert rc == 0
    assert json.loads(output.read_text(encoding="utf-8"))["ok"] is True
    text = capsys.readouterr().out
    assert "ok: True" in text
    assert "material_texture_ok: pass=3 fail=0 na=0 required=3 ok=True" in text


def test_main_accepts_texture_backed_baseline_preset(tmp_path):
    report = tmp_path / "asset_flow.json"
    report.write_text(
        json.dumps(
            report_with_counts(
                raw_textures_found={"pass": 3, "fail": 0, "na": 0},
                texture_processing_started={"pass": 3, "fail": 0, "na": 0},
                texture_format_ok={"pass": 6, "fail": 0, "na": 0},
                manifest_generated={"pass": 3, "fail": 0, "na": 0},
                model_format_ok={"pass": 3, "fail": 0, "na": 0},
                material_slots_ok={"pass": 3, "fail": 0, "na": 0},
                mtl_format_ok={"pass": 3, "fail": 0, "na": 0},
                material_texture_ok={"pass": 3, "fail": 0, "na": 0},
            )
        ),
        encoding="utf-8",
    )

    rc = asset_flow_acceptance_gate.main(
        [
            "--report",
            str(report),
            "--preset",
            "texture-backed-baseline",
        ]
    )

    assert rc == 0


def test_build_requirements_keeps_defaults_and_overrides():
    requirements = asset_flow_acceptance_gate.build_requirements(["material_texture_ok:3"])

    assert requirements["raw_textures_found"] == 1
    assert requirements["material_texture_ok"] == 3


def test_build_requirements_can_use_preset_and_override():
    requirements = asset_flow_acceptance_gate.build_requirements(
        ["material_texture_ok:4"],
        preset="texture-backed-baseline",
    )

    assert requirements["raw_textures_found"] == 3
    assert requirements["texture_format_ok"] == 6
    assert requirements["material_texture_ok"] == 4


def test_build_requirements_rejects_unknown_preset():
    try:
        asset_flow_acceptance_gate.build_requirements(preset="missing")
    except ValueError as exc:
        assert "Unknown acceptance preset" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
