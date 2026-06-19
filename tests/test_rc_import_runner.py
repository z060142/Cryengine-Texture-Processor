import json
import os
import subprocess

from utils.rc_import_runner import (
    RCImportRunner,
    build_rc_import_command,
    expected_output_path_for_request,
)


def write_request(path, output_ext="cgf"):
    path.write_text(
        json.dumps({"source_filename": "asset.fbx", "output_ext": output_ext}),
        encoding="utf-8",
    )


def test_build_rc_import_command_has_no_embedded_quotes():
    command = build_rc_import_command(
        "rc.exe",
        "asset.json",
        source_fbx_path="asset.fbx",
        output_filename="asset.cgf",
    )

    assert command == [
        "rc.exe",
        "asset.json",
        "/overwriteextension=fbx",
        "/overwritesourcefile=asset.fbx",
        "/overwritefilename=asset.cgf",
    ]


def test_expected_output_path_uses_request_output_ext(tmp_path):
    json_path = tmp_path / "asset.json"
    write_request(json_path, output_ext="skin")

    assert expected_output_path_for_request(str(json_path)) == str(tmp_path / "asset.skin")


def test_expected_output_path_still_accepts_legacy_request_wrapper(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps({"request": {"source_filename": "asset.fbx", "output_ext": "chr"}}),
        encoding="utf-8",
    )

    assert expected_output_path_for_request(str(json_path)) == str(tmp_path / "asset.chr")


def test_runner_reports_missing_rc_path(tmp_path):
    json_path = tmp_path / "asset.json"
    write_request(json_path)

    result = RCImportRunner("").run(str(json_path))

    assert not result.success
    assert result.error == "RC executable path is not configured"


def test_runner_reports_missing_json(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")

    result = RCImportRunner(str(rc_path)).run(str(tmp_path / "missing.json"))

    assert not result.success
    assert "RC request JSON not found" in result.error


def test_runner_succeeds_when_rc_returns_zero_and_output_exists(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")
    json_path = tmp_path / "asset.json"
    write_request(json_path)

    def fake_run(command, check, capture_output, text):
        assert check is False
        assert capture_output is True
        assert text is True
        (tmp_path / "asset.cgf").write_text("fake cgf", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = RCImportRunner(str(rc_path), subprocess_run=fake_run).run(str(json_path))

    assert result.success
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.expected_output_path == os.path.abspath(tmp_path / "asset.cgf")


def test_runner_fails_when_output_is_missing_even_if_rc_returns_zero(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")
    json_path = tmp_path / "asset.json"
    write_request(json_path)

    def fake_run(command, check, capture_output, text):
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = RCImportRunner(str(rc_path), subprocess_run=fake_run).run(str(json_path))

    assert not result.success
    assert "Expected output was not created" in result.error


def test_runner_fails_when_rc_returns_error(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")
    json_path = tmp_path / "asset.json"
    write_request(json_path)

    def fake_run(command, check, capture_output, text):
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="bad")

    result = RCImportRunner(str(rc_path), subprocess_run=fake_run).run(str(json_path))

    assert not result.success
    assert result.returncode == 7
    assert result.stderr == "bad"
    assert result.error == "RC exited with code 7"
