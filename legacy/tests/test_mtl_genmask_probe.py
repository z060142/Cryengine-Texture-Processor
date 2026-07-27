import os
import xml.etree.ElementTree as ET

from tools.mtl_genmask_probe import (
    MTLMaskVariant,
    apply_mask_variant_to_mtl,
    extract_mask_log_hits,
    run_mtl_genmask_probe,
)
from utils.rc_import_runner import RCImportResult


def write_probe_mtl(path):
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(
        sub_materials,
        "Material",
        Name="Default",
        Shader="Illum",
        GenMask="32",
        StringGenMask="%SUBSURFACE_SCATTERING",
    )
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_apply_mask_variant_to_mtl_sets_and_removes_material_attrs(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    write_probe_mtl(mtl_path)
    variant = MTLMaskVariant(
        slug="string_only",
        description="test",
        gen_mask=None,
        string_gen_mask="%NORMAL_MAP",
    )

    snapshots = apply_mask_variant_to_mtl(str(mtl_path), variant)
    material = ET.parse(mtl_path).getroot().find("SubMaterials").find("Material")

    assert snapshots[0]["before"]["gen_mask"] == "32"
    assert snapshots[0]["after"]["gen_mask"] == ""
    assert "GenMask" not in material.attrib
    assert material.get("StringGenMask") == "%NORMAL_MAP"


def test_extract_mask_log_hits_filters_shader_mask_lines():
    hits = extract_mask_log_hits(
        stdout="loading\nShader cache ok\n",
        stderr="warning: GenMask mismatch\nplain warning\n",
    )

    assert hits == [
        {"stream": "stdout", "line": "Shader cache ok"},
        {"stream": "stderr", "line": "warning: GenMask mismatch"},
    ]


def test_run_mtl_genmask_probe_records_variant_rc_results(tmp_path):
    rc_path = tmp_path / "rc.exe"
    rc_path.write_text("fake rc", encoding="utf-8")
    fbx_path = tmp_path / "asset.fbx"
    fbx_path.write_text("fake fbx", encoding="utf-8")

    class FakeRunner:
        def __init__(self, rc_exe_path):
            self.rc_exe_path = rc_exe_path

        def run(self, json_path, source_fbx_path=None):
            expected_output_path = os.path.splitext(json_path)[0] + ".cgf"
            with open(expected_output_path, "w", encoding="utf-8") as f:
                f.write("fake cgf")
            return RCImportResult(
                success=True,
                command=[self.rc_exe_path, json_path],
                json_path=json_path,
                expected_output_path=expected_output_path,
                returncode=0,
                stdout="Shader compile ok",
            )

    report = run_mtl_genmask_probe(
        str(rc_path),
        str(fbx_path),
        str(tmp_path / "work"),
        asset_name="Probe",
        variants=[
            MTLMaskVariant(
                slug="no_masks",
                description="test",
                gen_mask=None,
                string_gen_mask=None,
            )
        ],
        runner_factory=FakeRunner,
    )

    assert report["summary"]["variant_count"] == 1
    assert report["summary"]["success_count"] == 1
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["rc_accepts_all_variants"] is True
    assert report["variants"][0]["expected_output_exists"] is True
    assert report["variants"][0]["material_snapshots"][0]["after"]["gen_mask"] == ""
    assert report["variants"][0]["rc"]["mask_related_log_hits"][0]["line"] == "Shader compile ok"


def test_run_mtl_genmask_probe_reports_missing_rc(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    fbx_path.write_text("fake fbx", encoding="utf-8")

    report = run_mtl_genmask_probe("", str(fbx_path), str(tmp_path / "work"))

    assert "RC executable not found" in report["error"]
    assert report["summary"]["variant_count"] > 0
