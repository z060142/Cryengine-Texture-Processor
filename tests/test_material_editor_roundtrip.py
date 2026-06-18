import json
import os
import sys
import xml.etree.ElementTree as ET

from tools.material_editor_roundtrip import (
    compare_roundtrip_manifest,
    prepare_roundtrip_fixtures,
    run_sandbox_roundtrip,
)
from tools.mtl_genmask_probe import MTLMaskVariant


def test_prepare_roundtrip_fixtures_writes_game_materials_and_script(tmp_path):
    game_root = tmp_path / "gamesdk"
    sandbox = tmp_path / "Sandbox.exe"
    cryproject = tmp_path / "gamesdk.cryproject"
    sandbox.write_text("fake sandbox", encoding="utf-8")
    cryproject.write_text("{}", encoding="utf-8")

    manifest = prepare_roundtrip_fixtures(
        str(tmp_path / "work"),
        game_root=str(game_root),
        sandbox_exe=str(sandbox),
        cryproject_path=str(cryproject),
        material_subdir="materials/roundtrip",
        variants=[
            MTLMaskVariant(
                slug="string_only",
                description="test",
                gen_mask=None,
                string_gen_mask="%SUBSURFACE_SCATTERING",
            )
        ],
    )

    case = manifest["cases"][0]
    assert case["material_name"] == "materials/roundtrip/Phase37_string_only.mtl"
    assert os.path.exists(case["input_path"])
    assert os.path.exists(case["staged_path"])
    assert manifest["launch_command"] == [
        str(sandbox),
        "-project",
        str(cryproject),
        "/BatchMode",
        "/runpython",
        manifest["sandbox_script_path"],
    ]
    assert manifest["sandbox_popen"] == {
        "executable": str(sandbox),
        "args": [
            manifest["sandbox_script_path"],
            "-project",
            str(cryproject),
            "/BatchMode",
            "/runpython",
        ],
        "strategy": "script_path_as_argv0",
    }
    script = open(manifest["sandbox_script_path"], encoding="utf-8").read()
    assert "material.set_property" in script
    assert "Material Settings/Surface Type" in script

    material = ET.parse(case["staged_path"]).getroot()
    assert "GenMask" not in material.attrib
    assert material.get("StringGenMask") == "%SUBSURFACE_SCATTERING"


def test_compare_roundtrip_manifest_reports_attribute_changes(tmp_path):
    game_root = tmp_path / "gamesdk"
    manifest = prepare_roundtrip_fixtures(
        str(tmp_path / "work"),
        game_root=str(game_root),
        sandbox_exe=str(tmp_path / "Sandbox.exe"),
        variants=[
            MTLMaskVariant(
                slug="legacy",
                description="test",
                gen_mask="80000000",
                string_gen_mask="%SUBSURFACE_SCATTERING",
            )
        ],
    )
    case = manifest["cases"][0]
    root = ET.parse(case["staged_path"]).getroot()
    root.set("GenMask", "4000000000000")
    root.set("StringGenMask", "%SUBSURFACE_SCATTERING%VERTCOLORS")
    ET.ElementTree(root).write(case["staged_path"], encoding="utf-8", xml_declaration=True)
    with open(manifest["sandbox_result_path"], "w", encoding="utf-8") as f:
        json.dump({"results": [{"slug": "legacy", "success": True}]}, f)

    report = compare_roundtrip_manifest(manifest["manifest_path"])

    assert report["summary"] == {
        "case_count": 1,
        "changed_count": 1,
        "unchanged_count": 0,
        "missing_after_count": 0,
        "sandbox_result_present": True,
    }
    changes = report["cases"][0]["material_changes"][0]["attributes"]
    assert changes["GenMask"] == {"before": "80000000", "after": "4000000000000"}
    assert changes["StringGenMask"]["after"] == "%SUBSURFACE_SCATTERING%VERTCOLORS"


def test_compare_roundtrip_manifest_reports_missing_staged_file(tmp_path):
    game_root = tmp_path / "gamesdk"
    manifest = prepare_roundtrip_fixtures(
        str(tmp_path / "work"),
        game_root=str(game_root),
        variants=[
            MTLMaskVariant(
                slug="missing",
                description="test",
                gen_mask=None,
                string_gen_mask=None,
            )
        ],
    )
    os.remove(manifest["cases"][0]["staged_path"])

    report = compare_roundtrip_manifest(manifest["manifest_path"])

    assert report["summary"]["missing_after_count"] == 1
    assert report["cases"][0]["exists_after"] is False


def test_run_sandbox_roundtrip_detects_result_file(tmp_path):
    game_root = tmp_path / "gamesdk"
    manifest = prepare_roundtrip_fixtures(
        str(tmp_path / "work"),
        game_root=str(game_root),
        variants=[
            MTLMaskVariant(
                slug="result",
                description="test",
                gen_mask=None,
                string_gen_mask=None,
            )
        ],
    )
    result_path = manifest["sandbox_result_path"].replace("\\", "\\\\")
    manifest["launch_command"] = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path(r'{result_path}').write_text('{{\"results\": []}}', encoding='utf-8')",
    ]
    manifest.pop("sandbox_popen", None)
    with open(manifest["manifest_path"], "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    report = run_sandbox_roundtrip(manifest["manifest_path"], timeout_seconds=10)

    assert report["state"] in {"result", "exited"}
    assert report["result_exists"] is True
    assert report["sandbox_result"] == {"results": []}
