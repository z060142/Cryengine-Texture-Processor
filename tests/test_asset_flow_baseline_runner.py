import json

from tools import asset_flow_baseline_runner


def test_run_baseline_writes_spec_report_markdown_and_gate(monkeypatch, tmp_path):
    seen = {}

    def fake_build_spec(*args, **kwargs):
        seen["build_args"] = args
        seen["build_kwargs"] = kwargs
        return {"work_root": args[1], "cases": [{"name": "asset", "type": "rc"}]}

    def fake_run_validation(spec):
        seen["spec"] = spec
        return {
            "summary": {
                "ok": True,
                "case_count": 1,
                "ok_count": 1,
                "failed_count": 0,
                "check_counts": {"material_texture_ok": {"pass": 3, "fail": 0, "na": 0}},
            },
            "cases": [],
        }

    def fake_evaluate_report(report, requirements=None):
        seen["requirements"] = requirements
        return {"ok": True, "requirements": [], "failures": []}

    monkeypatch.setattr(asset_flow_baseline_runner, "build_spec", fake_build_spec)
    monkeypatch.setattr(asset_flow_baseline_runner, "run_validation", fake_run_validation)
    monkeypatch.setattr(asset_flow_baseline_runner, "evaluate_report", fake_evaluate_report)
    monkeypatch.setattr(asset_flow_baseline_runner, "build_requirements", lambda preset: {"material_texture_ok": 3})

    result = asset_flow_baseline_runner.run_baseline(
        ["assets"],
        ["obj"],
        str(tmp_path / "baseline"),
        work_root=str(tmp_path / "work"),
    )

    assert result["ok"] is True
    assert seen["build_kwargs"]["include_texture_process"] is True
    assert seen["build_kwargs"]["texture_backed_only"] is True
    assert seen["requirements"] == {"material_texture_ok": 3}
    for path in result["paths"].values():
        if path.endswith(".json") or path.endswith(".md"):
            assert path
    assert json.loads((tmp_path / "baseline" / "asset_flow_baseline_spec.json").read_text(encoding="utf-8"))["cases"]
    assert json.loads((tmp_path / "baseline" / "asset_flow_baseline_gate.json").read_text(encoding="utf-8"))["ok"] is True


def test_main_prints_baseline_paths(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        asset_flow_baseline_runner,
        "run_baseline",
        lambda *args, **kwargs: {
            "ok": True,
            "paths": {
                "spec": "spec.json",
                "report": "report.json",
                "markdown": "report.md",
                "gate": "gate.json",
                "work_root": "work",
            },
            "validation_summary": {"case_count": 1, "ok_count": 1, "failed_count": 0},
            "gate": {"ok": True},
        },
    )

    rc = asset_flow_baseline_runner.main(["assets", "--output-dir", str(tmp_path)])

    text = capsys.readouterr().out
    assert rc == 0
    assert "spec: spec.json" in text
    assert "gate_ok: True" in text
