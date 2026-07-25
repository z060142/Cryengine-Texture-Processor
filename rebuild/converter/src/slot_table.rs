use crate::index_assigner::Assignment;
use crate::rc_policy::RC_MAX_SUB_MATERIALS;
use serde::Serialize;
use std::collections::BTreeMap;

pub const TRAILING_UNASSIGNED_MATERIAL_NAME: &str = "<unassigned>";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MaterialSlot {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub original_name: Option<String>,
    pub sub_index: i32,
    pub textures: BTreeMap<String, String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub physicalize: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_default: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_dummy: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_unassigned_placeholder: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub assignment_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_order: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fbx_material_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub requested_sub_index: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deleted: Option<bool>,
}

pub fn build_expanded_slot_table(
    assignments: &[Assignment],
    include_default: bool,
    fill_gaps: bool,
    include_trailing_unassigned: bool,
) -> Vec<MaterialSlot> {
    if assignments.is_empty() && include_default {
        return vec![default_slot()];
    }

    let used: Vec<_> = assignments
        .iter()
        .filter(|record| record.sub_index >= 0)
        .collect();
    let Some(max_slot) = used.iter().map(|record| record.sub_index).max() else {
        return Vec::new();
    };

    let mut slots = vec![None; max_slot as usize + 1];
    for record in used {
        slots[record.sub_index as usize] = Some(slot_from_assignment(record));
    }

    let mut slots = if fill_gaps {
        slots
            .into_iter()
            .enumerate()
            .map(|(index, slot)| slot.unwrap_or_else(|| gap_slot(index as i32)))
            .collect()
    } else {
        slots.into_iter().flatten().collect()
    };

    if include_trailing_unassigned {
        append_trailing_unassigned(&mut slots);
    }
    slots
}

pub fn append_trailing_unassigned(slots: &mut Vec<MaterialSlot>) {
    let Some(last) = slots.last() else {
        return;
    };
    if is_unassigned_name(&last.name) {
        return;
    }
    let Some(max_slot) = slots.iter().map(|slot| slot.sub_index).max() else {
        return;
    };
    if max_slot + 1 >= RC_MAX_SUB_MATERIALS {
        return;
    }
    slots.push(trailing_unassigned_slot(max_slot + 1));
}

pub fn trailing_unassigned_slot(sub_index: i32) -> MaterialSlot {
    MaterialSlot {
        name: TRAILING_UNASSIGNED_MATERIAL_NAME.to_owned(),
        original_name: Some(TRAILING_UNASSIGNED_MATERIAL_NAME.to_owned()),
        sub_index,
        textures: BTreeMap::new(),
        physicalize: Some("no".to_owned()),
        is_default: None,
        is_dummy: Some(true),
        is_unassigned_placeholder: Some(true),
        assignment_reason: Some("trailing_unassigned_placeholder".to_owned()),
        source_order: None,
        fbx_material_id: None,
        requested_sub_index: None,
        deleted: None,
    }
}

fn default_slot() -> MaterialSlot {
    MaterialSlot {
        name: "Default".to_owned(),
        original_name: None,
        sub_index: 0,
        textures: BTreeMap::new(),
        physicalize: None,
        is_default: Some(true),
        is_dummy: None,
        is_unassigned_placeholder: None,
        assignment_reason: None,
        source_order: None,
        fbx_material_id: None,
        requested_sub_index: None,
        deleted: None,
    }
}

fn gap_slot(sub_index: i32) -> MaterialSlot {
    MaterialSlot {
        name: "unassigned".to_owned(),
        original_name: Some("unassigned".to_owned()),
        sub_index,
        textures: BTreeMap::new(),
        physicalize: None,
        is_default: None,
        is_dummy: Some(true),
        is_unassigned_placeholder: None,
        assignment_reason: Some("slot_gap".to_owned()),
        source_order: None,
        fbx_material_id: None,
        requested_sub_index: None,
        deleted: None,
    }
}

fn slot_from_assignment(record: &Assignment) -> MaterialSlot {
    MaterialSlot {
        name: record.name.clone(),
        original_name: Some(record.original_name.clone()),
        sub_index: record.sub_index,
        textures: record.textures.clone(),
        physicalize: record.physicalize.clone(),
        is_default: None,
        is_dummy: Some(record.is_dummy),
        is_unassigned_placeholder: None,
        assignment_reason: Some(record.assignment_reason.clone()),
        source_order: Some(record.source_order),
        fbx_material_id: record.fbx_material_id,
        requested_sub_index: record.requested_sub_index,
        deleted: Some(record.deleted),
    }
}

fn is_unassigned_name(name: &str) -> bool {
    matches!(
        name.trim().to_ascii_lowercase().as_str(),
        "unassigned" | "<unassigned>"
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::index_assigner::{assign_sub_indices, AssignmentInput};
    use crate::manifest::MaterialManifest;

    #[test]
    fn manifest_is_applied_before_assignment_and_pins_slot_order() {
        let manifest = MaterialManifest::from_json_str(
            r#"{
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone", "physicalize": "no"},
                    {"slot": 1, "name": "Stone.001", "physicalize": "no"}
                ]
            }"#,
        )
        .unwrap();
        let source = [
            AssignmentInput::new("Stone.001", 0),
            AssignmentInput::new("Stone", 1),
        ];
        let inputs = manifest.apply_to_inputs(source);
        let (records, diagnostics) = assign_sub_indices(&inputs, &[]);

        assert!(diagnostics.is_empty());
        assert_eq!(records[0].physicalize.as_deref(), Some("no"));
        assert_eq!(records[1].physicalize.as_deref(), Some("no"));
        let slots = build_expanded_slot_table(&records, false, true, false);
        assert_eq!(slots[0].physicalize.as_deref(), Some("no"));
        assert_eq!(slots[1].physicalize.as_deref(), Some("no"));
        assert_eq!(
            records
                .iter()
                .map(|record| (
                    record.name.as_str(),
                    record.sub_index,
                    record.assignment_reason.as_str()
                ))
                .collect::<Vec<_>>(),
            [("Stone", 0, "explicit"), ("Stone.001", 1, "explicit")]
        );
    }

    #[test]
    fn gaps_are_filled_and_metadata_is_preserved() {
        let mut first = AssignmentInput::new("First", 0);
        first
            .textures
            .insert("diffuse".to_owned(), "first.dds".to_owned());
        let mut third = AssignmentInput::new("Third", 2);
        third
            .textures
            .insert("diffuse".to_owned(), "third.dds".to_owned());
        let (records, _) = assign_sub_indices(&[first, third], &[]);
        let slots = build_expanded_slot_table(&records, true, true, false);
        assert_eq!(
            slots
                .iter()
                .map(|slot| slot.name.as_str())
                .collect::<Vec<_>>(),
            ["First", "unassigned", "Third"]
        );
        assert_eq!(slots[1].assignment_reason.as_deref(), Some("slot_gap"));
        assert_eq!(slots[1].is_dummy, Some(true));
        assert_eq!(slots[2].textures["diffuse"], "third.dds");
    }

    #[test]
    fn trailing_placeholder_obeys_all_three_rules() {
        let (records, _) = assign_sub_indices(&[AssignmentInput::new("Stone", 0)], &[]);
        let slots = build_expanded_slot_table(&records, true, true, true);
        assert_eq!(slots[1].name, "<unassigned>");
        assert_eq!(slots[1].sub_index, 1);
        assert_eq!(
            slots[1].assignment_reason.as_deref(),
            Some("trailing_unassigned_placeholder")
        );

        let mut existing = slots.clone();
        append_trailing_unassigned(&mut existing);
        assert_eq!(existing.len(), 2);

        let mut last = AssignmentInput::new("LastValid", 0);
        last.explicit_sub_index = Some(127);
        last.auto_assigned = false;
        let (last, _) = assign_sub_indices(&[last], &[]);
        assert_eq!(
            build_expanded_slot_table(&last, true, false, true)
                .iter()
                .map(|slot| slot.name.as_str())
                .collect::<Vec<_>>(),
            ["LastValid"]
        );
    }

    #[test]
    fn empty_deleted_gap_and_out_of_range_cases_match_python() {
        assert_eq!(
            build_expanded_slot_table(&[], true, true, false)[0].name,
            "Default"
        );

        let visible = AssignmentInput::new("Visible", 0);
        let mut removed = AssignmentInput::new("Removed", 1);
        removed.deleted = true;
        let mut too_high = AssignmentInput::new("TooHigh", 128);
        too_high.fbx_material_id = Some(129);
        let (records, _) = assign_sub_indices(&[visible, removed, too_high], &[]);
        assert_eq!(
            build_expanded_slot_table(&records, true, true, false)
                .iter()
                .map(|slot| slot.name.as_str())
                .collect::<Vec<_>>(),
            ["Visible"]
        );

        let (gapped, _) = assign_sub_indices(
            &[
                AssignmentInput::new("First", 0),
                AssignmentInput::new("Third", 2),
            ],
            &[],
        );
        assert_eq!(
            build_expanded_slot_table(&gapped, true, false, false)
                .iter()
                .map(|slot| slot.name.as_str())
                .collect::<Vec<_>>(),
            ["First", "Third"]
        );
    }
}
