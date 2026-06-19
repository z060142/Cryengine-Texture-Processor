from model_processing.material_slot_table import (
    build_expanded_material_slot_table,
    build_material_slot_records,
)


def test_build_material_slot_records_resolves_manifest_before_assignment():
    manifest_info = {
        "manifest": {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [
                {"slot": 0, "name": "Stone"},
                {"slot": 1, "name": "Stone.001"},
            ],
        }
    }

    records = build_material_slot_records(
        [{"name": "Stone.001"}, {"name": "Stone"}],
        material_manifest_info=manifest_info,
    )

    assert [(record["clean_name"], record["sub_index"], record["reason"]) for record in records] == [
        ("Stone", 0, "explicit"),
        ("Stone.001", 1, "explicit"),
    ]


def test_expanded_material_slot_table_fills_gaps_and_keeps_metadata():
    slots = build_expanded_material_slot_table(
        [
            {"name": "First", "id": 1, "textures": {"diffuse": "first.dds"}},
            {"name": "Third", "id": 3, "textures": {"diffuse": "third.dds"}},
        ]
    )

    assert [slot["name"] for slot in slots] == ["First", "unassigned", "Third"]
    assert slots[0]["assignment_reason"] == "fbx_material_id"
    assert slots[1]["assignment_reason"] == "slot_gap"
    assert slots[1]["is_dummy"] is True
    assert slots[2]["sub_index"] == 2
    assert slots[2]["textures"] == {"diffuse": "third.dds"}


def test_expanded_material_slot_table_can_append_trailing_unassigned_placeholder():
    slots = build_expanded_material_slot_table(
        [{"name": "Stone", "id": 1}],
        include_trailing_unassigned=True,
    )

    assert [slot["name"] for slot in slots] == ["Stone", "<unassigned>"]
    assert slots[1]["sub_index"] == 1
    assert slots[1]["assignment_reason"] == "trailing_unassigned_placeholder"


def test_expanded_material_slot_table_does_not_append_out_of_range_trailing_placeholder():
    slots = build_expanded_material_slot_table(
        [{"name": "LastValid", "sub_index": 127, "auto_assigned": False}],
        fill_gaps=False,
        include_trailing_unassigned=True,
    )

    assert [slot["name"] for slot in slots] == ["LastValid"]


def test_expanded_material_slot_table_omits_deleted_materials_but_keeps_default_for_empty_input():
    assert build_expanded_material_slot_table([]) == [
        {"name": "Default", "textures": {}, "is_default": True, "sub_index": 0}
    ]

    slots = build_expanded_material_slot_table(
        [{"name": "Visible", "id": 1}, {"name": "Removed", "id": 2, "deleted": True}]
    )

    assert [slot["name"] for slot in slots] == ["Visible"]


def test_expanded_material_slot_table_can_drop_gap_placeholders():
    slots = build_expanded_material_slot_table(
        [{"name": "First", "id": 1}, {"name": "Third", "id": 3}],
        fill_gaps=False,
    )

    assert [slot["name"] for slot in slots] == ["First", "Third"]


def test_expanded_material_slot_table_omits_rc_out_of_range_slots():
    slots = build_expanded_material_slot_table(
        [{"name": "Visible", "id": 1}, {"name": "TooHigh", "id": 129}]
    )

    assert [slot["name"] for slot in slots] == ["Visible"]
