import xml.etree.ElementTree as ET

from output_formats.mtl_exporter import build_mtl_document, build_mtl_material_slots, export_mtl


def submaterial_names(mtl_path):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    return [material.get("Name") for material in list(sub_materials)]


def submaterial_names_from_root(root):
    sub_materials = root.find("SubMaterials")
    return [material.get("Name") for material in list(sub_materials)]


def test_build_mtl_material_slots_returns_expanded_slot_table():
    slots = build_mtl_material_slots(
        [
            {"name": "First", "id": 1, "textures": {}},
            {"name": "Third", "id": 3, "textures": {}},
        ]
    )

    assert [slot["name"] for slot in slots] == ["First", "unassigned", "Third"]
    assert slots[1]["is_dummy"] is True
    assert slots[2]["sub_index"] == 2


def test_build_mtl_document_maps_textures_and_shader_params(tmp_path):
    texture_paths = {
        "Diffuse": tmp_path / "asset_diff.dds",
        "Normal": tmp_path / "asset_ddna.dds",
        "Specular": tmp_path / "asset_spec.dds",
        "Displacement": tmp_path / "asset_displ.dds",
        "Emissive": tmp_path / "asset_emissive.dds",
        "Opacity": tmp_path / "asset_opacity.dds",
    }
    for texture_path in texture_paths.values():
        texture_path.write_text("dds", encoding="utf-8")

    root, slots = build_mtl_document(
        [
            {
                "name": "Stone",
                "textures": {texture_type: str(texture_path) for texture_type, texture_path in texture_paths.items()},
            }
        ],
        str(tmp_path),
    )

    assert [slot["name"] for slot in slots] == ["Stone"]
    material = root.find("SubMaterials").find("Material")
    assert material.get("Name") == "Stone"
    assert material.get("AlphaTest") == "0.5"
    assert material.get("Emittance") == "1,1,1,10"
    assert "%NORMAL_MAP" in material.get("StringGenMask")
    assert "%SPECULAR_MAP" in material.get("StringGenMask")
    assert "%DISPLACEMENT_MAPPING" in material.get("StringGenMask")
    assert "%PHONG_TESSELLATION" in material.get("StringGenMask")

    texture_maps = {
        texture.get("Map"): texture.get("File")
        for texture in list(material.find("Textures"))
        if texture.tag == "Texture"
    }
    assert texture_maps == {
        "Diffuse": "./asset_diff.dds",
        "Bumpmap": "./asset_ddna.dds",
        "Specular": "./asset_spec.dds",
        "Heightmap": "./asset_displ.dds",
        "Emittance": "./asset_emissive.dds",
        "Opacity": "./asset_opacity.dds",
    }
    public_params = material.find("PublicParams")
    assert public_params.get("TessellationFactorMax") == "32"


def test_build_mtl_document_uses_default_material_for_empty_input(tmp_path):
    root, slots = build_mtl_document([], str(tmp_path))

    assert [slot["name"] for slot in slots] == ["Default"]
    assert submaterial_names_from_root(root) == ["Default"]


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


def test_export_mtl_preserves_manifest_pinned_suffix_materials(tmp_path):
    success, result = export_mtl(
        [
            {"name": "Stone", "sub_index": 0, "auto_assigned": False, "textures": {}},
            {"name": "Stone.001", "sub_index": 1, "auto_assigned": False, "textures": {}},
        ],
        str(tmp_path),
        str(tmp_path),
        "asset.mtl",
    )

    assert success
    assert submaterial_names(result) == ["Stone", "Stone.001"]


def test_export_mtl_cryasset_counts_default_material(tmp_path):
    success, result = export_mtl([], str(tmp_path), str(tmp_path), "asset.mtl")

    assert success
    cryasset_root = ET.parse(result + ".cryasset").getroot()
    details = {
        detail.get("name"): detail.text
        for detail in list(cryasset_root.find("Details"))
        if detail.tag == "Detail"
    }
    assert details["subMaterialCount"] == "1"
