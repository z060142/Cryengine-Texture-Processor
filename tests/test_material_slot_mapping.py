from model_processing.material_slot_mapping import (
    build_material_slot_mapping_contract,
    exported_material_slot_mapping_schema,
)


def test_build_material_slot_mapping_contract_classifies_final_slots_and_gaps():
    contract = build_material_slot_mapping_contract(
        [
            {
                "name": "First",
                "original_name": "First",
                "source_order": 0,
                "fbx_material_id": 1,
                "fbx_slot": 0,
                "sub_index": 0,
                "assignment_reason": "fbx_material_id",
                "deleted": False,
            },
            {
                "name": "Third",
                "original_name": "Third",
                "source_order": 1,
                "fbx_material_id": 3,
                "fbx_slot": 2,
                "sub_index": 2,
                "assignment_reason": "fbx_material_id",
                "deleted": False,
            },
            {
                "name": "Removed",
                "original_name": "Removed",
                "source_order": 2,
                "fbx_material_id": 2,
                "fbx_slot": 1,
                "sub_index": -1,
                "assignment_reason": "deleted",
                "deleted": True,
            },
        ]
    )

    assert contract["schema"] == "cryengine_material_slot_mapping.v1"
    assert [rule["id"] for rule in contract["rules"]] == [
        "request_sub_index_is_final_slot",
        "mtl_child_order_matches_final_slots",
        "cgf_subset_material_id_indexes_final_slots",
        "raw_fbx_id_is_one_based",
        "sub_index_limit",
    ]
    assert contract["summary"]["final_slot_count"] == 3
    assert contract["summary"]["gap_slots"] == [1]
    assert contract["summary"]["gap_slot_count"] == 1
    assert contract["summary"]["status_counts"] == {
        "deleted": 1,
        "emitted_final_slot": 2,
    }
    assert contract["mappings"][0]["raw_fbx_slot"] == 0
    assert contract["mappings"][0]["final_sub_index"] == 0
    assert contract["mappings"][0]["mtl_slot"] == 0
    assert contract["mappings"][0]["cgf_material_id"] == 0
    assert contract["mappings"][2]["status"] == "deleted"
    assert contract["mappings"][2]["final_sub_index"] is None


def test_build_material_slot_mapping_contract_counts_out_of_range_and_duplicates():
    contract = build_material_slot_mapping_contract(
        [
            {
                "name": "Wood",
                "sub_index": 0,
                "requested_sub_index": None,
                "assignment_reason": "explicit",
                "duplicate_sub_index_conflict": True,
                "duplicate_sub_index_material_names": ["Wood", "Metal"],
            },
            {
                "name": "Metal",
                "sub_index": 0,
                "requested_sub_index": None,
                "assignment_reason": "explicit",
                "duplicate_sub_index_conflict": True,
                "duplicate_sub_index_material_names": ["Wood", "Metal"],
            },
            {
                "name": "TooHigh",
                "sub_index": -1,
                "requested_sub_index": 128,
                "assignment_reason": "explicit_out_of_range",
            },
        ]
    )

    assert contract["summary"]["duplicate_final_slot_count"] == 2
    assert contract["summary"]["out_of_range_deleted_count"] == 1
    assert contract["summary"]["assignment_reason_counts"] == {
        "explicit": 2,
        "explicit_out_of_range": 1,
    }
    assert contract["mappings"][2]["status"] == "out_of_range_deleted"
    assert contract["mappings"][2]["requested_sub_index"] == 128


def test_exported_material_slot_mapping_schema_documents_external_tool_policy():
    schema = exported_material_slot_mapping_schema()

    assert schema["schema"] == "cryengine_material_slot_mapping.v1"
    policy = schema["assignment_policy"]
    assert policy["rc_request_material_fields"]["name"]["required"] is True
    assert policy["rc_request_material_fields"]["physicalize"]["values"] == [
        "no",
        "default",
        "obstruct",
        "no_collide",
        "proxy_only",
    ]
    assert policy["slot_identity"]["final_sub_index"] == "request.materials[].sub_index for non-deleted materials."
    assert policy["placeholder_policy"]["slot_gaps"]["name"] == "unassigned"
    assert policy["placeholder_policy"]["trailing_unassigned"]["assignment_reason"] == (
        "trailing_unassigned_placeholder"
    )
    hazard_codes = {hazard["code"] for hazard in policy["hazards"]}
    assert "rc_cgf_material_id_missing_slot" in hazard_codes
