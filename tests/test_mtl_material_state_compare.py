import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from tools.mtl_material_state_compare import build_material_state_compare_report


def write_state_mtl(path, *, glass_mask="%SPECULAR_MAP%TINT_MAP", tint_cloudiness="0.050000001"):
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(
        sub_materials,
        "Material",
        Name="Paint",
        Shader="Multilayeredmaterials",
        MtlFlags="526464",
        GenMask="0",
        StringGenMask="",
    )
    glass = ET.SubElement(
        sub_materials,
        "Material",
        Name="Glass",
        Shader="Glass",
        MtlFlags="526466",
        GenMask="2080000000000",
        StringGenMask=glass_mask,
    )
    ET.SubElement(
        glass,
        "PublicParams",
        TintCloudiness=tint_cloudiness,
        TintColor="0.16078432,0.16078432,0.16078432",
    )
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_build_material_state_compare_report_passes_matching_material_state(tmp_path):
    reference = tmp_path / "reference.mtl"
    candidate = tmp_path / "candidate.mtl"
    write_state_mtl(reference)
    write_state_mtl(candidate)

    report = build_material_state_compare_report(reference, candidate)

    assert report["comparison"]["ok"] is True
    assert report["reference_summary"] == report["candidate_summary"]
    assert report["reference_summary"]["shader_counts"] == {
        "Glass": 1,
        "Multilayeredmaterials": 1,
    }


def test_build_material_state_compare_report_flags_material_state_mismatch(tmp_path):
    reference = tmp_path / "reference.mtl"
    candidate = tmp_path / "candidate.mtl"
    write_state_mtl(reference)
    write_state_mtl(candidate, glass_mask="%SPECULAR_MAP", tint_cloudiness="0.1")

    report = build_material_state_compare_report(reference, candidate)

    assert report["comparison"]["ok"] is False
    assert report["comparison"]["summary_mismatches"][0]["path"] == "summary.string_gen_mask_counts"
    glass = report["comparison"]["material_mismatches"][0]
    assert glass["name"] == "Glass"
    assert {
        diff["path"]
        for diff in glass["differences"]
    } == {
        "attrs.StringGenMask",
        "public_params.TintCloudiness",
    }


def test_mtl_material_state_compare_script_exits_nonzero_on_mismatch(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    reference = tmp_path / "reference.mtl"
    candidate = tmp_path / "candidate.mtl"
    output = tmp_path / "compare.json"
    write_state_mtl(reference)
    write_state_mtl(candidate, glass_mask="%SPECULAR_MAP")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.mtl_material_state_compare",
            "--reference",
            str(reference),
            "--candidate",
            str(candidate),
            "--output",
            str(output),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "ok: False" in result.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["comparison"]["ok"] is False
