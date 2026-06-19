import json
import os
import xml.etree.ElementTree as ET

from tools.rc_export_gate import run_rc_import_with_gates
from utils.rc_import_runner import RCImportResult


class FakeRunner:
    def __init__(self, expected_output_path):
        self.expected_output_path = expected_output_path

    def run(self, json_path, source_fbx_path=None):
        return RCImportResult(
            success=True,
            command=["rc.exe", json_path],
            json_path=json_path,
            expected_output_path=self.expected_output_path,
            returncode=0,
            stdout="ok",
        )


def write_request(path, materials=None):
    path.write_text(
        json.dumps(
            {
                "request": {
                    "source_filename": "asset.fbx",
                    "output_filename": "asset.cgf",
                    "materials": materials or [{"name": "Stone", "physicalize": "no", "sub_index": 0}],
                }
            }
        ),
        encoding="utf-8",
    )


def write_mtl(path, texture_file="./Stone_diff.tif"):
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    material = ET.SubElement(
        sub_materials,
        "Material",
        Name="Stone",
        Shader="Illum",
        MtlFlags="524416",
        GenMask="0",
        StringGenMask="",
    )
    textures = ET.SubElement(material, "Textures")
    texture = ET.SubElement(textures, "Texture", Map="Diffuse", File=texture_file)
    ET.SubElement(texture, "TexMod", TexMod_RotateType="0", TexMod_TexGenType="0", TexMod_bTexGenProjected="0")
    ET.SubElement(material, "PublicParams")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_cryasset(path):
    root = ET.Element("AssetMetadata")
    details = ET.SubElement(root, "Details")
    ET.SubElement(details, "Detail", name="subMaterialCount").text = "1"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_run_rc_import_with_gates_writes_reports_for_clean_export(tmp_path):
    json_path = tmp_path / "asset.json"
    mtl_path = tmp_path / "asset.mtl"
    cgf_path = tmp_path / "asset.cgf"
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    (texture_dir / "Stone_diff.tif").write_text("fake texture", encoding="utf-8")
    cgf_path.write_bytes(b"cgf")
    write_request(json_path)
    write_mtl(mtl_path, "./textures/Stone_diff.tif")
    write_cryasset(tmp_path / "asset.mtl.cryasset")

    result = run_rc_import_with_gates(
        FakeRunner(str(cgf_path)),
        str(json_path),
        str(tmp_path / "asset.fbx"),
        str(mtl_path),
        rc_exe_path="rc.exe",
        texture_output_dir=str(texture_dir),
    )

    assert result["rc_result"].success is True
    assert result["material_report"]["summary"]["action_required"] is False
    assert result["mtl_schema_gate"]["summary"]["ok"] is True
    assert result["texture_output_gate"]["summary"]["ok"] is True
    assert os.path.exists(result["material_report_path"])
    assert os.path.exists(result["mtl_schema_gate_path"])
    assert os.path.exists(result["texture_output_gate_path"])


def test_run_rc_import_with_gates_fails_on_material_mapping_action_required(monkeypatch, tmp_path):
    json_path = tmp_path / "asset.json"
    mtl_path = tmp_path / "asset.mtl"
    cgf_path = tmp_path / "asset.cgf"
    cgf_path.write_bytes(b"cgf")
    write_request(json_path)
    write_mtl(mtl_path)

    def fake_report(*args, **kwargs):
        del args, kwargs
        return {"summary": {"action_required": True}}

    monkeypatch.setattr("tools.rc_export_gate.build_material_mapping_report", fake_report)

    result = run_rc_import_with_gates(
        FakeRunner(str(cgf_path)),
        str(json_path),
        str(tmp_path / "asset.fbx"),
        str(mtl_path),
    )

    assert result["rc_result"].success is False
    assert "Material mapping report requires action" in result["rc_result"].error


def test_run_rc_import_with_gates_fails_on_mtl_schema_gate(tmp_path):
    json_path = tmp_path / "asset.json"
    mtl_path = tmp_path / "asset.mtl"
    cgf_path = tmp_path / "asset.cgf"
    cgf_path.write_bytes(b"cgf")
    write_request(json_path)
    write_mtl(mtl_path, "./Stone_basecolor.png")

    result = run_rc_import_with_gates(
        FakeRunner(str(cgf_path)),
        str(json_path),
        str(tmp_path / "asset.fbx"),
        str(mtl_path),
    )

    assert result["rc_result"].success is False
    assert "MTL schema gate failed" in result["rc_result"].error
    assert result["mtl_schema_gate"]["summary"]["ok"] is False


def test_run_rc_import_with_gates_fails_on_texture_output_gate(tmp_path):
    json_path = tmp_path / "asset.json"
    mtl_path = tmp_path / "asset.mtl"
    cgf_path = tmp_path / "asset.cgf"
    texture_dir = tmp_path / "textures"
    texture_dir.mkdir()
    (texture_dir / "Stone_diff.png").write_text("bad texture", encoding="utf-8")
    cgf_path.write_bytes(b"cgf")
    write_request(json_path)
    write_mtl(mtl_path)

    result = run_rc_import_with_gates(
        FakeRunner(str(cgf_path)),
        str(json_path),
        str(tmp_path / "asset.fbx"),
        str(mtl_path),
        texture_output_dir=str(texture_dir),
    )

    assert result["rc_result"].success is False
    assert "Texture output gate failed" in result["rc_result"].error
    assert result["texture_output_gate"]["summary"]["ok"] is False
