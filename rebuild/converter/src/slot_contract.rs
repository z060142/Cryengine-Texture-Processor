use crate::index_assigner::Assignment;
use crate::rc_policy::RC_MAX_SUB_MATERIALS;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};

pub fn exported_material_slot_mapping_schema() -> Value {
    json!({
        "schema": "cryengine_material_slot_mapping.v1",
        "rules": slot_mapping_rules(),
        "assignment_policy": assignment_policy(),
    })
}

pub fn build_slot_mapping_contract(assignments: &[Assignment]) -> Value {
    let mut mappings = Vec::new();
    let mut final_slots = BTreeSet::new();
    let mut reason_counts = BTreeMap::<String, usize>::new();
    let mut status_counts = BTreeMap::<String, usize>::new();
    let mut duplicate_final_slot_count = 0;

    for item in assignments {
        let final_slot = (item.sub_index >= 0).then_some(item.sub_index);
        let status = if final_slot.is_some() && !item.deleted {
            "emitted_final_slot"
        } else if item.requested_sub_index.is_some() {
            "out_of_range_deleted"
        } else if item.deleted {
            "deleted"
        } else {
            "not_emitted"
        };
        let reason = if item.assignment_reason.is_empty() {
            "unknown"
        } else {
            &item.assignment_reason
        };
        *reason_counts.entry(reason.to_owned()).or_default() += 1;
        *status_counts.entry(status.to_owned()).or_default() += 1;
        if let Some(slot) = final_slot {
            final_slots.insert(slot);
        }
        if item.duplicate_sub_index_conflict {
            duplicate_final_slot_count += 1;
        }

        mappings.push(json!({
            "name": item.name,
            "original_name": item.original_name,
            "source_order": item.source_order,
            "fbx_material_id": item.fbx_material_id,
            "raw_fbx_slot": item.fbx_slot,
            "final_sub_index": final_slot,
            "mtl_slot": final_slot,
            "cgf_material_id": final_slot,
            "requested_sub_index": item.requested_sub_index,
            "assignment_reason": item.assignment_reason,
            "status": status,
            "deleted": item.deleted,
            "duplicate_final_slot": item.duplicate_sub_index_conflict,
            "duplicate_final_slot_material_names": item.duplicate_sub_index_material_names,
        }));
    }

    let final_slot_count = final_slots
        .iter()
        .next_back()
        .map_or(0, |slot| *slot as usize + 1);
    let gap_slots: Vec<_> = (0..final_slot_count as i32)
        .filter(|slot| !final_slots.contains(slot))
        .collect();

    json!({
        "schema": "cryengine_material_slot_mapping.v1",
        "rules": slot_mapping_rules(),
        "summary": {
            "material_count": mappings.len(),
            "emitted_material_count": status_counts.get("emitted_final_slot").copied().unwrap_or(0),
            "deleted_material_count": status_counts.get("deleted").copied().unwrap_or(0),
            "out_of_range_deleted_count": status_counts.get("out_of_range_deleted").copied().unwrap_or(0),
            "duplicate_final_slot_count": duplicate_final_slot_count,
            "final_slot_count": final_slot_count,
            "gap_slot_count": gap_slots.len(),
            "gap_slots": gap_slots,
            "assignment_reason_counts": object_from_counts(reason_counts),
            "status_counts": object_from_counts(status_counts),
        },
        "mappings": mappings,
    })
}

fn object_from_counts(counts: BTreeMap<String, usize>) -> Value {
    Value::Object(
        counts
            .into_iter()
            .map(|(key, count)| (key, Value::from(count)))
            .collect::<Map<_, _>>(),
    )
}

fn slot_mapping_rules() -> Value {
    json!([
        {
            "id": "request_sub_index_is_final_slot",
            "summary": "materials[].sub_index is the final CryEngine sub-material id written by RC.",
            "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
        },
        {
            "id": "mtl_child_order_matches_final_slots",
            "summary": "MTL SubMaterials child order follows the final sub_index table; gaps are placeholders.",
            "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
        },
        {
            "id": "cgf_subset_material_id_indexes_final_slots",
            "summary": "CGF MeshSubset material_id indexes the final CGF material table, not subset order.",
            "evidence": "docs/refactor_phase9_controlled_blender_material_fixture.md",
        },
        {
            "id": "raw_fbx_id_is_one_based",
            "summary": "Known FBX material ids are one-based; raw FBX slot is fbx_material_id - 1.",
            "evidence": "model_processing/material_index_assigner.py",
        },
        {
            "id": "sub_index_limit",
            "summary": format!(
                "sub_index values 0..{} are supported; higher values normalize to -1.",
                RC_MAX_SUB_MATERIALS - 1
            ),
            "evidence": "docs/refactor_phase55_rc_sub_index_limit_policy.md",
        }
    ])
}

fn assignment_policy() -> Value {
    json!({
        "schema": "cryengine_material_slot_assignment.v1",
        "rc_request_material_fields": {
            "name": {
                "required": true,
                "type": "string",
                "meaning": "Source FBX scene material name. RC matches this name to the imported FBX material table.",
                "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
            },
            "physicalize": {
                "required": true,
                "type": "enum",
                "values": ["no", "default", "obstruct", "no_collide", "proxy_only"],
                "meaning": "CryEngine physicalization policy stored with the final material slot.",
                "evidence": "docs/refactor_phase99_cgf_import_settings_request_schema.md",
            },
            "sub_index": {
                "required": true,
                "type": "integer",
                "valid_values": {"min": -1, "max": RC_MAX_SUB_MATERIALS - 1},
                "meaning": "Final CryEngine sub-material id. Non-negative values become MTL slots and CGF material ids.",
                "evidence": "docs/refactor_phase55_rc_sub_index_limit_policy.md",
            },
        },
        "slot_identity": {
            "raw_fbx_slot": "fbx_material_id - 1 when a one-based FBX material id is known.",
            "final_sub_index": "request.materials[].sub_index for non-deleted materials.",
            "mtl_slot": "SubMaterials child order after expanding the final_sub_index table and filling gaps.",
            "cgf_material_id": "MeshSubset material_id after RC remaps FBX material names through final_sub_index.",
        },
        "assignment_priority": [
            {
                "id": "explicit_sub_index",
                "condition": "material has sub_index >= 0 and auto_assigned/ui_autoflag is false",
                "result": "reserve that exact final slot unless it is outside the RC range",
            },
            {
                "id": "fbx_material_id",
                "condition": "material has a known FBX id and its zero-based slot is free",
                "result": "use fbx_material_id - 1 as final_sub_index",
            },
            {
                "id": "existing_mtl_name",
                "condition": "material name exists in an existing MTL and that child-order slot is free",
                "result": "reuse the existing MTL slot",
            },
            {
                "id": "first_free",
                "condition": "no explicit, FBX, or existing-MTL slot was available",
                "result": "fill the first free final slot after sorting dummy materials first, then by name",
            },
        ],
        "placeholder_policy": {
            "slot_gaps": {
                "name": "unassigned",
                "assignment_reason": "slot_gap",
                "meaning": "Generated MTL placeholder for missing intermediate final slots.",
            },
            "trailing_unassigned": {
                "name": "<unassigned>",
                "assignment_reason": "trailing_unassigned_placeholder",
                "meaning": "Optional trailing request/MTL placeholder expected in CE-authored assets. It may be absent from the CGF MtlName table when no mesh subset uses it.",
            },
        },
        "hazards": [
            {
                "code": "rc_duplicate_sub_index_overwrites_material",
                "meaning": "Multiple request materials target the same final slot; the later RC material can overwrite slot state.",
            },
            {
                "code": "rc_sub_index_out_of_range_deleted",
                "meaning": format!(
                    "sub_index >= {} normalizes to -1, so matching source faces can be deleted.",
                    RC_MAX_SUB_MATERIALS
                ),
            },
            {
                "code": "rc_case_insensitive_material_name_collision",
                "meaning": "RC name matching is case-insensitive, so names that differ only by case cannot be targeted safely.",
            },
            {
                "code": "deleted_known_fbx_slot_usage_unknown",
                "meaning": "Deleting a known FBX slot is unsafe unless polygon usage proves it is unused.",
            },
            {
                "code": "rc_omitted_source_material_faces_deleted",
                "meaning": "When request materials are present, source materials omitted from the request can lose their faces.",
            },
            {
                "code": "rc_cgf_material_id_missing_slot",
                "meaning": "After an RC smoke run, every CGF material id used by mesh subsets must exist in both the request material table and generated MTL slot table.",
            },
        ],
        "minimal_request_example": {
            "request": {
                "source_filename": "asset.fbx",
                "output_ext": "cgf",
                "material_filename": "asset",
                "materials": [
                    {"name": "Body", "physicalize": "no", "sub_index": 0},
                    {"name": "Glass", "physicalize": "no", "sub_index": 1},
                    {"name": "<unassigned>", "physicalize": "no", "sub_index": 2},
                ],
            },
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::index_assigner::{assign_sub_indices, AssignmentInput};

    #[test]
    fn contract_classifies_final_slots_gaps_and_deleted_records() {
        let first = AssignmentInput::new("First", 0);
        let third = AssignmentInput::new("Third", 2);
        let mut removed = AssignmentInput::new("Removed", 1);
        removed.deleted = true;
        removed.polygon_count = Some(0);
        let (records, _) = assign_sub_indices(&[first, third, removed], &[]);
        let contract = build_slot_mapping_contract(&records);
        assert_eq!(contract["schema"], "cryengine_material_slot_mapping.v1");
        assert_eq!(contract["summary"]["final_slot_count"], 3);
        assert_eq!(contract["summary"]["gap_slots"], json!([1]));
        assert_eq!(
            contract["summary"]["status_counts"],
            json!({"deleted": 1, "emitted_final_slot": 2})
        );
        assert_eq!(contract["mappings"][0]["raw_fbx_slot"], 0);
        assert_eq!(contract["mappings"][2]["status"], "deleted");
        assert!(contract["mappings"][2]["final_sub_index"].is_null());
    }

    #[test]
    fn contract_counts_duplicates_and_out_of_range_records() {
        let mut wood = AssignmentInput::new("Wood", 0);
        wood.explicit_sub_index = Some(0);
        wood.auto_assigned = false;
        let mut metal = AssignmentInput::new("Metal", 1);
        metal.explicit_sub_index = Some(0);
        metal.auto_assigned = false;
        let mut too_high = AssignmentInput::new("TooHigh", 2);
        too_high.explicit_sub_index = Some(128);
        too_high.auto_assigned = false;
        let (records, _) = assign_sub_indices(&[wood, metal, too_high], &[]);
        let contract = build_slot_mapping_contract(&records);
        assert_eq!(contract["summary"]["duplicate_final_slot_count"], 2);
        assert_eq!(contract["summary"]["out_of_range_deleted_count"], 1);
        assert_eq!(
            contract["summary"]["assignment_reason_counts"],
            json!({"explicit": 2, "explicit_out_of_range": 1})
        );
        assert_eq!(contract["mappings"][2]["status"], "out_of_range_deleted");
    }

    #[test]
    fn exported_schema_documents_external_policy() {
        let schema = exported_material_slot_mapping_schema();
        assert_eq!(schema["schema"], "cryengine_material_slot_mapping.v1");
        assert_eq!(
            schema["assignment_policy"]["rc_request_material_fields"]["physicalize"]["values"],
            json!(["no", "default", "obstruct", "no_collide", "proxy_only"])
        );
        assert_eq!(
            schema["assignment_policy"]["placeholder_policy"]["slot_gaps"]["name"],
            "unassigned"
        );
        assert!(schema["assignment_policy"]["hazards"]
            .as_array()
            .unwrap()
            .iter()
            .any(|hazard| hazard["code"] == "rc_cgf_material_id_missing_slot"));
    }

    #[test]
    fn exported_schema_is_exactly_the_frozen_python_policy() {
        let frozen: Value =
            serde_json::from_str(include_str!("../../ce-schema/data/converter_schema.json"))
                .unwrap();
        assert_eq!(
            exported_material_slot_mapping_schema(),
            frozen["material_slot_mapping"]
        );
    }
}
