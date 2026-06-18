import json
import xml.etree.ElementTree as ET

from tools.material_mapping_report import (
    build_material_mapping_report,
    evaluate_material_slot_alignment,
    load_cryasset_details,
    load_mtl_slots,
    load_request_materials,
    write_material_mapping_report,
)


def test_load_request_materials_reads_rc_request(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps(
            {
                "request": {
                    "materials": [
                        {"name": "Bark", "physicalize": "no_collide", "sub_index": 0},
                        {"name": "proxy", "physicalize": "proxy_only", "sub_index": 2},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_request_materials(str(json_path)) == [
        {"order": 0, "name": "Bark", "sub_index": 0, "physicalize": "no_collide"},
        {"order": 1, "name": "proxy", "sub_index": 2, "physicalize": "proxy_only"},
    ]


def test_load_mtl_slots_reads_submaterial_order(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark", Shader="Illum", SurfaceType="")
    ET.SubElement(sub_materials, "Material", Name="Leaves", Shader="Illum", SurfaceType="mat_leaves")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    assert load_mtl_slots(str(mtl_path)) == [
        {"slot": 0, "name": "Bark", "shader": "Illum", "surface_type": ""},
        {"slot": 1, "name": "Leaves", "shader": "Illum", "surface_type": "mat_leaves"},
    ]


def test_load_cryasset_details_reads_detail_values(tmp_path):
    cryasset_path = tmp_path / "asset.mtl.cryasset"
    root = ET.Element("AssetMetadata")
    details = ET.SubElement(root, "Details")
    ET.SubElement(details, "Detail", name="subMaterialCount").text = "2"
    ET.SubElement(details, "Detail", name="textureCount").text = "0"
    ET.ElementTree(root).write(cryasset_path, encoding="utf-8", xml_declaration=True)

    assert load_cryasset_details(str(cryasset_path)) == {
        "subMaterialCount": "2",
        "textureCount": "0",
    }


def test_evaluate_material_slot_alignment_reports_mismatch():
    result = evaluate_material_slot_alignment(
        [{"name": "Bark", "sub_index": 1}],
        [{"slot": 1, "name": "Leaves"}],
    )

    assert not result["ok"]
    assert result["checks"][0]["type"] == "slot_name_mismatch"


def test_build_and_write_material_mapping_report(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps({"request": {"materials": [{"name": "Bark", "sub_index": 0, "physicalize": "no_collide"}]}}),
        encoding="utf-8",
    )

    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark", Shader="Illum", SurfaceType="")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    cryasset_path = tmp_path / "asset.mtl.cryasset"
    cryasset_root = ET.Element("AssetMetadata")
    details = ET.SubElement(cryasset_root, "Details")
    ET.SubElement(details, "Detail", name="subMaterialCount").text = "1"
    ET.ElementTree(cryasset_root).write(cryasset_path, encoding="utf-8", xml_declaration=True)

    cgf_path = tmp_path / "asset.cgf"
    cgf_path.write_bytes(b"cgf")

    report = build_material_mapping_report(
        str(json_path),
        str(mtl_path),
        expected_output_path=str(cgf_path),
        rc_exe_path="rc.exe",
        source_fbx_path="source.fbx",
        copied_fbx_path="asset.fbx",
        rc_returncode=0,
    )

    assert report["alignment"]["ok"]
    assert report["rc"]["output_exists"]
    assert report["rc"]["output_size"] == 3
    assert report["mtl_cryasset_details"]["subMaterialCount"] == "1"

    report_path = tmp_path / "asset.material_report.json"
    write_material_mapping_report(report, str(report_path))
    assert json.loads(report_path.read_text(encoding="utf-8"))["alignment"]["ok"]
