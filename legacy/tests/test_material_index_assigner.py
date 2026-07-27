import xml.etree.ElementTree as ET

from model_processing.material_index_assigner import (
    assign_material_sub_indices,
    parse_mtl_submaterial_names,
)


def sub_index_by_name(records):
    return {record["clean_name"]: record["sub_index"] for record in records}


def reason_by_name(records):
    return {record["clean_name"]: record["reason"] for record in records}


def diagnostics_by_name(records):
    return {record["clean_name"]: record["diagnostics"] for record in records}


def test_parse_mtl_submaterial_names_uses_child_order(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark")
    ET.SubElement(sub_materials, "Material", Name="Leaves")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8")

    assert parse_mtl_submaterial_names(str(mtl_path)) == ["Bark", "Leaves"]


def test_fbx_material_id_wins_over_existing_mtl_name_for_auto_materials():
    records = assign_material_sub_indices(
        [{"name": "Leaves", "id": 1}, {"name": "Bark", "id": 2}],
        existing_submaterial_names=["Bark", "Leaves"],
    )

    assert sub_index_by_name(records) == {"Leaves": 0, "Bark": 1}
    assert reason_by_name(records) == {
        "Leaves": "fbx_material_id",
        "Bark": "fbx_material_id",
    }


def test_existing_mtl_name_match_is_fallback_when_fbx_slot_is_occupied():
    records = assign_material_sub_indices(
        [
            {"name": "Reserved", "sub_index": 0, "auto_assigned": False},
            {"name": "Leaves", "id": 1},
        ],
        existing_submaterial_names=["Reserved", "Leaves"],
    )

    assert sub_index_by_name(records) == {"Reserved": 0, "Leaves": 1}
    assert reason_by_name(records) == {
        "Reserved": "explicit",
        "Leaves": "existing_mtl_name",
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


def test_deleted_known_fbx_slot_reports_hazard_when_usage_unknown():
    records = assign_material_sub_indices(
        [{"name": "Visible", "id": 1}, {"name": "Removed", "deleted": True, "id": 2}],
        existing_submaterial_names=[],
    )

    diagnostics = diagnostics_by_name(records)

    assert diagnostics["Visible"] == []
    assert diagnostics["Removed"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert diagnostics["Removed"][0]["fbx_slot"] == 1
    assert diagnostics["Removed"][0]["sub_index"] == -1


def test_deleted_known_fbx_slot_has_no_hazard_when_usage_is_known_unused():
    records = assign_material_sub_indices(
        [{"name": "Removed", "deleted": True, "id": 2, "polygon_count": 0}],
        existing_submaterial_names=[],
    )

    assert diagnostics_by_name(records)["Removed"] == []


def test_explicit_sub_index_can_remap_from_fbx_slot_without_warning():
    records = assign_material_sub_indices(
        [
            {"name": "Reserved", "sub_index": 0, "auto_assigned": False},
            {"name": "Moved", "id": 1},
        ],
        existing_submaterial_names=["Reserved", "Moved"],
    )

    diagnostics = diagnostics_by_name(records)

    assert sub_index_by_name(records)["Moved"] == 1
    assert diagnostics["Moved"] == []


def test_duplicate_explicit_sub_index_reports_overwrite_hazard():
    records = assign_material_sub_indices(
        [
            {"name": "Wood", "id": 1, "sub_index": 0, "auto_assigned": False},
            {"name": "Metal", "id": 2, "sub_index": 0, "auto_assigned": False},
        ],
        existing_submaterial_names=[],
    )

    diagnostics = diagnostics_by_name(records)

    assert sub_index_by_name(records) == {"Wood": 0, "Metal": 0}
    assert diagnostics["Wood"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"
    assert diagnostics["Wood"][0]["conflicting_material_names"] == ["Wood", "Metal"]
    assert diagnostics["Metal"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"
    assert diagnostics["Metal"][0]["conflicting_material_names"] == ["Wood", "Metal"]


def test_malformed_explicit_sub_index_falls_back_to_fbx_material_id():
    records = assign_material_sub_indices(
        [
            {"name": "BoolExplicit", "id": 3, "sub_index": True, "auto_assigned": False},
            {"name": "FloatExplicit", "id": 4, "sub_index": 1.5, "auto_assigned": False},
        ],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {"BoolExplicit": 2, "FloatExplicit": 3}
    assert reason_by_name(records) == {
        "BoolExplicit": "fbx_material_id",
        "FloatExplicit": "fbx_material_id",
    }
    assert records[0]["requested_sub_index"] is None
    assert records[1]["requested_sub_index"] is None


def test_slot_name_conflict_reports_warning():
    records = assign_material_sub_indices(
        [
            {
                "name": "Wood",
                "id": 1,
                "material_names": ["Metal", "Wood"],
                "slot_name_conflict": True,
                "mesh_names": ["MeshA", "MeshB"],
            }
        ],
        existing_submaterial_names=[],
    )

    diagnostic = diagnostics_by_name(records)["Wood"][0]

    assert diagnostic["severity"] == "warning"
    assert diagnostic["code"] == "material_slot_name_conflict"
    assert diagnostic["fbx_slot"] == 0
    assert diagnostic["material_names"] == ["Metal", "Wood"]
    assert diagnostic["mesh_names"] == ["MeshA", "MeshB"]


def test_case_insensitive_material_name_collision_reports_hazard():
    records = assign_material_sub_indices(
        [{"name": "Wood", "id": 1}, {"name": "wood", "id": 2}],
        existing_submaterial_names=[],
    )

    diagnostics = diagnostics_by_name(records)

    assert sub_index_by_name(records) == {"Wood": 0, "wood": 1}
    assert diagnostics["Wood"][0]["code"] == "rc_case_insensitive_material_name_collision"
    assert diagnostics["Wood"][0]["conflicting_material_names"] == ["Wood", "wood"]
    assert diagnostics["wood"][0]["code"] == "rc_case_insensitive_material_name_collision"
    assert diagnostics["wood"][0]["conflicting_material_names"] == ["Wood", "wood"]


def test_blender_duplicate_suffix_is_preserved_as_distinct_material():
    records = assign_material_sub_indices(
        [{"name": "Stone", "id": 1}, {"name": "Stone.001", "id": 2}],
        existing_submaterial_names=[],
    )

    assert sub_index_by_name(records) == {"Stone": 0, "Stone.001": 1}


def test_explicit_sub_index_at_rc_limit_is_normalized_to_delete():
    records = assign_material_sub_indices(
        [{"name": "TooHigh", "sub_index": 128, "auto_assigned": False}],
        existing_submaterial_names=[],
    )

    record = records[0]
    diagnostic = record["diagnostics"][0]

    assert record["sub_index"] == -1
    assert record["requested_sub_index"] == 128
    assert record["reason"] == "explicit_out_of_range"
    assert diagnostic["code"] == "rc_sub_index_out_of_range_deleted"
    assert diagnostic["requested_sub_index"] == 128
    assert diagnostic["max_sub_materials"] == 128


def test_fbx_material_id_beyond_rc_limit_is_normalized_to_delete():
    records = assign_material_sub_indices(
        [{"name": "Slot128", "id": 129}],
        existing_submaterial_names=[],
    )

    assert records[0]["sub_index"] == -1
    assert records[0]["requested_sub_index"] == 128
    assert records[0]["reason"] == "fbx_material_id_out_of_range"
    assert records[0]["diagnostics"][0]["fbx_slot"] == 128
