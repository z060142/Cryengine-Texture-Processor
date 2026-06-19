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


def test_build_requirements_keeps_defaults_and_overrides():
    requirements = asset_flow_acceptance_gate.build_requirements(["material_texture_ok:3"])

    assert requirements["raw_textures_found"] == 1
    assert requirements["material_texture_ok"] == 3
