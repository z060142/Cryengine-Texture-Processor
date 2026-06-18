import xml.etree.ElementTree as ET

from model_processing.material_index_assigner import (
    assign_material_sub_indices,
    parse_mtl_submaterial_names,
)


def sub_index_by_name(records):
    return {record["clean_name"]: record["sub_index"] for record in records}


def reason_by_name(records):
    return {record["clean_name"]: record["reason"] for record in records}


def test_parse_mtl_submaterial_names_uses_child_order(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark")
    ET.SubElement(sub_materials, "Material", Name="Leaves")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8")

    assert parse_mtl_submaterial_names(str(mtl_path)) == ["Bark", "Leaves"]


def test_existing_mtl_name_match_wins_for_auto_materials():
    records = assign_material_sub_indices(
        [{"name": "Leaves", "id": 1}, {"name": "Bark", "id": 2}],
        existing_submaterial_names=["Bark", "Leaves"],
    )

    assert sub_index_by_name(records) == {"Leaves": 1, "Bark": 0}
    assert reason_by_name(records) == {
        "Leaves": "existing_mtl_name",
        "Bark": "existing_mtl_name",
    }


def test_fbx_material_id_is_preserved_when_slot_is_free():
    records = assign_material_sub_indices(
        [{"name": "Bark", "id": 3}, {"name": "Leaves", "id": 1}],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {"Bark": 2, "Leaves": 0}
    assert reason_by_name(records) == {
        "Bark": "fbx_material_id",
        "Leaves": "fbx_material_id",
    }


def test_remaining_materials_fill_first_free_slot_after_explicit_and_id_slots():
    records = assign_material_sub_indices(
        [
            {"name": "Reserved", "sub_index": 2, "auto_assigned": False},
            {"name": "KeepsId", "id": 1},
            {"name": "FillA", "id": 1},
            {"name": "FillB", "id": 1},
        ],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {
        "Reserved": 2,
        "KeepsId": 0,
        "FillA": 1,
        "FillB": 3,
    }


def test_deleted_material_gets_negative_sub_index():
    records = assign_material_sub_indices(
        [{"name": "Visible", "id": 1}, {"name": "Removed", "deleted": True, "id": 2}],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {"Visible": 0, "Removed": -1}
    assert reason_by_name(records)["Removed"] == "deleted"


def test_duplicate_blender_suffix_is_collapsed():
    records = assign_material_sub_indices(
        [{"name": "Stone", "id": 1}, {"name": "Stone.001", "id": 2}],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {"Stone": 0}
