import json

from tools.verify_controlled_fixture import verify_fixture_material_ids


def test_verify_fixture_material_ids_passes_when_expected_matches_actual(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [1, 0]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "", "cgf_material_summary": {"material_ids": [0, 1]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert result["ok"]
    assert result["expected"] == [0, 1]
    assert result["actual"] == [0, 1]


def test_verify_fixture_material_ids_fails_when_ids_differ(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [0, 2]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "", "cgf_material_summary": {"material_ids": [0, 1]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert not result["ok"]
    assert result["expected"] == [0, 2]
    assert result["actual"] == [0, 1]


def test_verify_fixture_material_ids_fails_on_cgf_read_error(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [0]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "bad cgf", "cgf_material_summary": {"material_ids": [0]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert not result["ok"]
    assert result["cgf_read_error"] == "bad cgf"
