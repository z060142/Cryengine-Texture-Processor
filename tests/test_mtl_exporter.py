import xml.etree.ElementTree as ET

from output_formats.mtl_exporter import export_mtl


def submaterial_names(mtl_path):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    return [material.get("Name") for material in list(sub_materials)]


def test_export_mtl_preserves_sub_index_slots_and_fills_gaps(tmp_path):
    success, result = export_mtl(
        [
            {"name": "First", "id": 1, "textures": {}},
            {"name": "Third", "id": 3, "textures": {}},
        ],
        str(tmp_path),
        str(tmp_path),
        "asset.mtl",
    )

    assert success
    assert submaterial_names(result) == ["First", "unassigned", "Third"]


def test_export_mtl_preserves_fbx_slots_over_existing_submaterial_name_order(tmp_path):
    existing = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Third")
    ET.SubElement(sub_materials, "Material", Name="First")
    ET.ElementTree(root).write(existing, encoding="utf-8")

    success, result = export_mtl(
        [
            {"name": "First", "id": 1, "textures": {}},
            {"name": "Third", "id": 2, "textures": {}},
        ],
        str(tmp_path),
        str(tmp_path),
        "asset.mtl",
    )

    assert success
    assert submaterial_names(result) == ["First", "Third"]
