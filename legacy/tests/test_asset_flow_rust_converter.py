import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
REBUILD_ROOT = REPO_ROOT.parent
FIXTURE_ROOT = REBUILD_ROOT / "fixtures" / "car"
DEFAULT_CONVERTER_EXE = REBUILD_ROOT / "target" / "release" / "converter.exe"
EXPECTED_DUMP_SHA256 = "332F2A2ADB5DB0210797321C6F8F7ADB92AD9E94E1BC8C8543CD717049BB8FC0"
CAR_FBX = r"fixtures\car\car.fbx"
CAR_MANIFEST = r"fixtures\car\car.fbx_material_manifest.json"


def _converter_exe():
    return Path(os.environ.get("CE_CONVERTER_EXE", DEFAULT_CONVERTER_EXE))


def _run_converter(*args, expected_exit=0):
    executable = _converter_exe()
    assert executable.is_file(), (
        f"Rust converter not found at {executable}; build release or set CE_CONVERTER_EXE"
    )
    result = subprocess.run(
        [str(executable), *map(str, args)],
        cwd=REBUILD_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected_exit, (
        f"converter exit {result.returncode}, expected {expected_exit}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def _normalize_json(value):
    if isinstance(value, dict):
        return {key: _normalize_json(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize_json(child) for child in value]
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value


def _xml_tree(element):
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        (element.text or "").strip(),
        tuple(_xml_tree(child) for child in element),
    )


def _request_materials(report):
    return report["golden_policy_projection"]["request_materials"]


def test_rust_converter_asset_flow(tmp_path):
    dump = tmp_path / "car-dump.json"
    report_path = tmp_path / "car-report.json"
    texture_dir = tmp_path / "example" / "car"
    out_dir = tmp_path / "phase" / "rc_work"
    texture_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    generated_mtl_reference = FIXTURE_ROOT / "car-generated-reference.mtl"
    for texture in ET.parse(generated_mtl_reference).findall(".//Texture"):
        filename = Path(texture.attrib["File"].replace("\\", "/")).name
        (texture_dir / filename).touch()

    _run_converter(
        "dump",
        CAR_FBX,
        "--out",
        dump,
    )
    assert hashlib.sha256(dump.read_bytes()).hexdigest().upper() == EXPECTED_DUMP_SHA256

    _run_converter(
        "report",
        CAR_FBX,
        "--manifest",
        CAR_MANIFEST,
        "--out",
        report_path,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for reference_name in (
        "car_direct_rc_export_material_report.json",
        "phase104_car_trailing_unassigned_material_report.json",
    ):
        reference = json.loads((REPO_ROOT / "docs" / reference_name).read_text(encoding="utf-8"))
        assert _request_materials(report) == reference["request_materials"]

    _run_converter(
        "convert",
        CAR_FBX,
        "--manifest",
        CAR_MANIFEST,
        "--overrides",
        "legacy/docs/car_native_material_overrides.json",
        "--texture-dir",
        texture_dir,
        "--out-dir",
        out_dir,
    )
    actual_mtl = out_dir / "kb3d_citycarsessentialssedan-native.mtl"
    actual_request = out_dir / "kb3d_citycarsessentialssedan-native.json"
    assert _xml_tree(ET.parse(actual_mtl).getroot()) == _xml_tree(
        ET.parse(generated_mtl_reference).getroot()
    )
    expected_request = json.loads(
        (FIXTURE_ROOT / "car-reference.request.json").read_text(encoding="utf-8")
    )
    actual_request_json = json.loads(actual_request.read_text(encoding="utf-8"))
    # Whitelist forward_up_axes: the golden records the legacy Python defect
    # "-Y+Z" (up=+Z), but correctness is anchored to the native car CGF chunk
    # (+Z+Y, up=+Y) and the Sandbox Y-up import default "-Z+Y". See T-B03 R9.
    for request in (expected_request, actual_request_json):
        request.pop("forward_up_axes", None)
    assert _normalize_json(actual_request_json) == _normalize_json(expected_request)

    _run_converter("validate", actual_request)
    gate_path = actual_request.with_suffix(".schema_gate.json")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate_reference = json.loads(
        (REPO_ROOT / "docs" / "car_direct_rc_export_mtl_schema_gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert gate["gate"]["summary"] == gate_reference["gate"]["summary"]
