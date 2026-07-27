use crate::diagnostic::Diagnostic;
use crate::model::ConverterModel;
use crate::rc_policy::{normalize_sub_index, RC_MAX_SUB_MATERIALS};
use serde::Serialize;
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

const IGNORED_MATERIAL_NAMES: &[&str] = &["Material", "Dots Stroke"];

pub fn parse_mtl_submaterial_names(path: &Path) -> Result<Vec<String>, String> {
    use quick_xml::events::Event;

    let mut reader = quick_xml::Reader::from_file(path)
        .map_err(|error| format!("failed to read {}: {error}", path.display()))?;
    reader.config_mut().trim_text(true);
    let mut buffer = Vec::new();
    let mut in_submaterials = false;
    let mut names = Vec::new();
    loop {
        match reader.read_event_into(&mut buffer) {
            Ok(Event::Start(event)) if event.name().as_ref() == b"SubMaterials" => {
                in_submaterials = true;
            }
            Ok(Event::End(event)) if event.name().as_ref() == b"SubMaterials" => {
                in_submaterials = false;
            }
            Ok(Event::Start(event) | Event::Empty(event))
                if in_submaterials && event.name().as_ref() == b"Material" =>
            {
                let name = event
                    .attributes()
                    .filter_map(Result::ok)
                    .find(|attribute| attribute.key.as_ref() == b"Name")
                    .and_then(|attribute| {
                        attribute
                            .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                            .ok()
                    })
                    .map_or_else(String::new, |value| value.into_owned());
                names.push(name);
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(error) => {
                return Err(format!("failed to parse {}: {error}", path.display()));
            }
        }
        buffer.clear();
    }
    Ok(names)
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AssignmentInput {
    pub name: String,
    pub original_name: String,
    pub source_order: usize,
    pub fbx_material_id: Option<u32>,
    pub explicit_sub_index: Option<i32>,
    pub auto_assigned: bool,
    pub deleted: bool,
    pub is_dummy: bool,
    pub polygon_count: Option<usize>,
    pub used_by_polygons: Option<bool>,
    pub slot_name_conflict: bool,
    pub material_names: Vec<String>,
    pub mesh_names: Vec<String>,
    pub textures: BTreeMap<String, String>,
    pub physicalize: Option<String>,
}

impl AssignmentInput {
    pub fn new(name: impl Into<String>, source_order: usize) -> Self {
        let name = name.into();
        Self {
            original_name: name.clone(),
            name,
            source_order,
            fbx_material_id: Some(source_order as u32 + 1),
            explicit_sub_index: None,
            auto_assigned: true,
            deleted: false,
            is_dummy: false,
            polygon_count: None,
            used_by_polygons: None,
            slot_name_conflict: false,
            material_names: Vec::new(),
            mesh_names: Vec::new(),
            textures: BTreeMap::new(),
            physicalize: None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Assignment {
    pub name: String,
    pub original_name: String,
    pub source_order: usize,
    pub fbx_material_id: Option<u32>,
    pub fbx_slot: Option<u32>,
    pub sub_index: i32,
    pub requested_sub_index: Option<i32>,
    pub assignment_reason: String,
    pub deleted: bool,
    pub is_dummy: bool,
    pub polygon_count: Option<usize>,
    pub used_by_polygons: Option<bool>,
    pub duplicate_sub_index_conflict: bool,
    pub duplicate_sub_index_material_names: Vec<String>,
    pub case_insensitive_name_conflict: bool,
    pub case_insensitive_material_names: Vec<String>,
    pub slot_name_conflict: bool,
    pub material_names: Vec<String>,
    pub mesh_names: Vec<String>,
    pub textures: BTreeMap<String, String>,
    pub physicalize: Option<String>,
    #[serde(skip)]
    explicit_sub_index: Option<i32>,
    #[serde(skip)]
    auto_assigned: bool,
}

impl Assignment {
    fn from_input(input: AssignmentInput) -> Self {
        let deleted = input.deleted || input.explicit_sub_index.is_some_and(|value| value < 0);
        Self {
            name: if input.name.is_empty() {
                "UnnamedMaterial".to_owned()
            } else {
                input.name
            },
            original_name: input.original_name,
            source_order: input.source_order,
            fbx_material_id: input.fbx_material_id,
            fbx_slot: input.fbx_material_id.and_then(|id| id.checked_sub(1)),
            sub_index: i32::MIN,
            requested_sub_index: None,
            assignment_reason: String::new(),
            deleted,
            is_dummy: input.is_dummy,
            polygon_count: input.polygon_count,
            used_by_polygons: input.used_by_polygons,
            duplicate_sub_index_conflict: false,
            duplicate_sub_index_material_names: Vec::new(),
            case_insensitive_name_conflict: false,
            case_insensitive_material_names: Vec::new(),
            slot_name_conflict: input.slot_name_conflict,
            material_names: input.material_names,
            mesh_names: input.mesh_names,
            textures: input.textures,
            physicalize: input.physicalize,
            explicit_sub_index: input.explicit_sub_index,
            auto_assigned: input.auto_assigned,
        }
    }
}

pub fn inputs_from_model(model: &ConverterModel) -> Vec<AssignmentInput> {
    let face_counts = model.material_face_counts();
    model
        .materials
        .iter()
        .enumerate()
        .map(|(source_order, material)| AssignmentInput {
            name: material.name.clone(),
            original_name: material.name.clone(),
            source_order,
            fbx_material_id: Some(material.typed_id + 1),
            explicit_sub_index: None,
            auto_assigned: true,
            deleted: false,
            is_dummy: false,
            polygon_count: Some(*face_counts.get(&material.typed_id).unwrap_or(&0)),
            used_by_polygons: Some(
                face_counts
                    .get(&material.typed_id)
                    .is_some_and(|count| *count > 0),
            ),
            slot_name_conflict: false,
            material_names: Vec::new(),
            mesh_names: Vec::new(),
            textures: BTreeMap::new(),
            physicalize: None,
        })
        .collect()
}

pub fn assign_sub_indices(
    inputs: &[AssignmentInput],
    existing_submaterial_names: &[String],
) -> (Vec<Assignment>, Vec<Diagnostic>) {
    let mut seen_exact = BTreeSet::new();
    let mut records: Vec<_> = inputs
        .iter()
        .filter(|input| !IGNORED_MATERIAL_NAMES.contains(&input.name.as_str()))
        .filter(|input| seen_exact.insert(input.name.clone()))
        .cloned()
        .map(Assignment::from_input)
        .collect();

    mark_case_collisions(&mut records);

    let existing_lookup: BTreeMap<_, _> = existing_submaterial_names
        .iter()
        .enumerate()
        .map(|(index, name)| (name.clone(), index as i32))
        .collect();
    let mut occupied = BTreeSet::new();

    for record in &mut records {
        if record.deleted {
            record.sub_index = -1;
            record.assignment_reason = "deleted".to_owned();
        } else if let Some(slot) = record
            .explicit_sub_index
            .filter(|slot| *slot >= 0 && !record.auto_assigned)
        {
            assign(record, slot, "explicit");
            if record.sub_index >= 0 {
                occupied.insert(record.sub_index);
            }
        }
    }

    for record in &mut records {
        if record.sub_index != i32::MIN {
            continue;
        }
        let preferred = record.fbx_slot.map(|slot| slot as i32);
        if let Some(slot) = preferred.filter(|slot| !occupied.contains(slot)) {
            assign(record, slot, "fbx_material_id");
            if record.sub_index >= 0 {
                occupied.insert(record.sub_index);
            }
        }
    }

    for record in &mut records {
        if record.sub_index != i32::MIN {
            continue;
        }
        if let Some(slot) = existing_lookup
            .get(&record.name)
            .copied()
            .filter(|slot| !occupied.contains(slot))
        {
            assign(record, slot, "existing_mtl_name");
            if record.sub_index >= 0 {
                occupied.insert(record.sub_index);
            }
        }
    }

    let mut remaining: Vec<_> = records
        .iter()
        .enumerate()
        .filter_map(|(index, record)| (record.sub_index == i32::MIN).then_some(index))
        .collect();
    remaining.sort_by_key(|index| {
        let record = &records[*index];
        (!record.is_dummy, record.name.to_lowercase())
    });
    for index in remaining {
        let mut slot = 0;
        while occupied.contains(&slot) {
            slot += 1;
        }
        assign(&mut records[index], slot, "first_free");
        if records[index].sub_index >= 0 {
            occupied.insert(records[index].sub_index);
        }
    }

    mark_duplicate_slots(&mut records);
    let diagnostics = records.iter().flat_map(diagnose).collect();
    (records, diagnostics)
}

fn assign(record: &mut Assignment, requested: i32, reason: &str) {
    record.sub_index = normalize_sub_index(Some(requested));
    if record.sub_index == requested {
        record.assignment_reason = reason.to_owned();
    } else {
        record.requested_sub_index = Some(requested);
        record.assignment_reason = format!("{reason}_out_of_range");
    }
}

fn mark_case_collisions(records: &mut [Assignment]) {
    let mut groups = BTreeMap::<String, Vec<usize>>::new();
    for (index, record) in records.iter().enumerate() {
        groups
            .entry(record.name.to_lowercase())
            .or_default()
            .push(index);
    }
    for indices in groups.values().filter(|indices| indices.len() > 1) {
        let names: Vec<_> = indices
            .iter()
            .map(|index| records[*index].name.clone())
            .collect();
        for &index in indices {
            records[index].case_insensitive_name_conflict = true;
            records[index].case_insensitive_material_names = names.clone();
        }
    }
}

fn mark_duplicate_slots(records: &mut [Assignment]) {
    let mut groups = BTreeMap::<i32, Vec<usize>>::new();
    for (index, record) in records.iter().enumerate() {
        if record.sub_index >= 0 {
            groups.entry(record.sub_index).or_default().push(index);
        }
    }
    for indices in groups.values().filter(|indices| indices.len() > 1) {
        let names: Vec<_> = indices
            .iter()
            .map(|index| records[*index].name.clone())
            .collect();
        for &index in indices {
            records[index].duplicate_sub_index_conflict = true;
            records[index].duplicate_sub_index_material_names = names.clone();
        }
    }
}

fn diagnose(record: &Assignment) -> Vec<Diagnostic> {
    let mut diagnostics = Vec::new();
    if record.case_insensitive_name_conflict {
        diagnostics.push(
            Diagnostic::new(
                "hazard",
                "rc_case_insensitive_material_name_collision",
                &record.name,
                "RC matches request materials to FBX scene materials case-insensitively. Materials whose names differ only by case cannot be targeted independently; the first request material with a case-insensitive match will win.",
            )
            .detail("fbx_slot", json!(record.fbx_slot))
            .detail("sub_index", record.sub_index)
            .detail(
                "conflicting_material_names",
                json!(record.case_insensitive_material_names),
            ),
        );
    }
    if record.duplicate_sub_index_conflict {
        diagnostics.push(
            Diagnostic::new(
                "hazard",
                "rc_duplicate_sub_index_overwrites_material",
                &record.name,
                "Multiple request materials map to the same non-negative sub_index. The later RC material can overwrite slot state.",
            )
            .detail("fbx_slot", json!(record.fbx_slot))
            .detail("sub_index", record.sub_index)
            .detail(
                "conflicting_material_names",
                json!(record.duplicate_sub_index_material_names),
            ),
        );
    }
    if let Some(requested) = record.requested_sub_index {
        diagnostics.push(
            Diagnostic::new(
                "hazard",
                "rc_sub_index_out_of_range_deleted",
                &record.name,
                "sub_index values at or above the RC material limit normalize to -1 and can delete matching faces.",
            )
            .detail("fbx_slot", json!(record.fbx_slot))
            .detail("sub_index", record.sub_index)
            .detail("requested_sub_index", requested)
            .detail("max_sub_materials", RC_MAX_SUB_MATERIALS)
            .detail("assignment_reason", record.assignment_reason.clone()),
        );
    }
    if record.slot_name_conflict {
        diagnostics.push(
            Diagnostic::new(
                "warning",
                "material_slot_name_conflict",
                &record.name,
                "Multiple material names were found for the same FBX material slot across meshes.",
            )
            .detail("fbx_slot", json!(record.fbx_slot))
            .detail("sub_index", record.sub_index)
            .detail("material_names", json!(record.material_names))
            .detail("mesh_names", json!(record.mesh_names)),
        );
    }
    let usage_known_unused = match record.polygon_count {
        Some(count) => count == 0,
        None => record.used_by_polygons == Some(false),
    };
    if record.deleted && record.fbx_slot.is_some() && !usage_known_unused {
        diagnostics.push(
            Diagnostic::new(
                "hazard",
                "deleted_known_fbx_slot_usage_unknown",
                &record.name,
                "Deleting a known FBX slot is unsafe unless polygon usage proves it is unused.",
            )
            .detail("fbx_slot", json!(record.fbx_slot))
            .detail("sub_index", record.sub_index),
        );
    }
    diagnostics
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn indices(records: &[Assignment]) -> BTreeMap<&str, i32> {
        records
            .iter()
            .map(|record| (record.name.as_str(), record.sub_index))
            .collect()
    }

    fn reasons(records: &[Assignment]) -> BTreeMap<&str, &str> {
        records
            .iter()
            .map(|record| (record.name.as_str(), record.assignment_reason.as_str()))
            .collect()
    }

    #[test]
    fn mtl_submaterial_names_use_child_order() {
        let path = std::env::temp_dir().join(format!(
            "converter-index-assigner-{}-{}.mtl",
            std::process::id(),
            line!()
        ));
        fs::write(
            &path,
            r#"<Material><SubMaterials><Material Name="Bark"/><Material Name="Leaves"/></SubMaterials></Material>"#,
        )
        .unwrap();
        let names = parse_mtl_submaterial_names(&path).unwrap();
        fs::remove_file(path).unwrap();
        assert_eq!(names, ["Bark", "Leaves"]);
    }

    #[test]
    fn fbx_id_wins_over_existing_mtl_order() {
        let inputs = vec![
            AssignmentInput::new("Leaves", 0),
            AssignmentInput::new("Bark", 1),
        ];
        let existing = vec!["Bark".to_owned(), "Leaves".to_owned()];
        let (records, _) = assign_sub_indices(&inputs, &existing);
        assert_eq!(
            indices(&records),
            BTreeMap::from([("Bark", 1), ("Leaves", 0)])
        );
        assert_eq!(
            reasons(&records),
            BTreeMap::from([("Bark", "fbx_material_id"), ("Leaves", "fbx_material_id")])
        );
    }

    #[test]
    fn nonsequential_fbx_id_is_preserved_when_free() {
        let mut bark = AssignmentInput::new("Bark", 0);
        bark.fbx_material_id = Some(3);
        let leaves = AssignmentInput::new("Leaves", 0);
        let (records, _) = assign_sub_indices(&[bark, leaves], &[]);
        assert_eq!(
            indices(&records),
            BTreeMap::from([("Bark", 2), ("Leaves", 0)])
        );
    }

    #[test]
    fn existing_mtl_is_fallback_when_fbx_slot_is_occupied() {
        let mut reserved = AssignmentInput::new("Reserved", 0);
        reserved.explicit_sub_index = Some(0);
        reserved.auto_assigned = false;
        let leaves = AssignmentInput::new("Leaves", 0);
        let existing = vec!["Reserved".to_owned(), "Leaves".to_owned()];
        let (records, _) = assign_sub_indices(&[reserved, leaves], &existing);
        assert_eq!(
            indices(&records),
            BTreeMap::from([("Leaves", 1), ("Reserved", 0)])
        );
        assert_eq!(
            reasons(&records),
            BTreeMap::from([("Leaves", "existing_mtl_name"), ("Reserved", "explicit")])
        );
    }

    #[test]
    fn explicit_fbx_and_first_free_priority_is_preserved() {
        let mut reserved = AssignmentInput::new("Reserved", 0);
        reserved.explicit_sub_index = Some(2);
        reserved.auto_assigned = false;
        let keeps = AssignmentInput::new("KeepsId", 0);
        let fill_a = AssignmentInput::new("FillA", 0);
        let fill_b = AssignmentInput::new("FillB", 0);
        let (records, _) = assign_sub_indices(&[reserved, keeps, fill_a, fill_b], &[]);
        assert_eq!(
            indices(&records),
            BTreeMap::from([("FillA", 1), ("FillB", 3), ("KeepsId", 0), ("Reserved", 2)])
        );
    }

    #[test]
    fn deleted_material_and_usage_hazard_match_python() {
        let visible = AssignmentInput::new("Visible", 0);
        let mut removed = AssignmentInput::new("Removed", 1);
        removed.deleted = true;
        let (records, diagnostics) = assign_sub_indices(&[visible, removed], &[]);
        assert_eq!(
            indices(&records),
            BTreeMap::from([("Removed", -1), ("Visible", 0)])
        );
        assert_eq!(diagnostics[0].code, "deleted_known_fbx_slot_usage_unknown");

        let mut unused = AssignmentInput::new("Removed", 1);
        unused.deleted = true;
        unused.polygon_count = Some(0);
        assert!(assign_sub_indices(&[unused], &[]).1.is_empty());
    }

    #[test]
    fn explicit_remap_from_fbx_slot_does_not_warn() {
        let mut reserved = AssignmentInput::new("Reserved", 0);
        reserved.explicit_sub_index = Some(0);
        reserved.auto_assigned = false;
        let moved = AssignmentInput::new("Moved", 0);
        let existing = vec!["Reserved".to_owned(), "Moved".to_owned()];
        let (records, diagnostics) = assign_sub_indices(&[reserved, moved], &existing);
        assert_eq!(indices(&records)["Moved"], 1);
        assert!(diagnostics.is_empty());
    }

    #[test]
    fn duplicate_explicit_slot_and_case_collision_are_diagnosed() {
        let mut wood = AssignmentInput::new("Wood", 0);
        wood.explicit_sub_index = Some(0);
        wood.auto_assigned = false;
        let mut lower = AssignmentInput::new("wood", 1);
        lower.explicit_sub_index = Some(0);
        lower.auto_assigned = false;
        let (_, diagnostics) = assign_sub_indices(&[wood, lower], &[]);
        assert_eq!(
            diagnostics
                .iter()
                .filter(|item| item.code == "rc_case_insensitive_material_name_collision")
                .count(),
            2
        );
        assert_eq!(
            diagnostics
                .iter()
                .filter(|item| item.code == "rc_duplicate_sub_index_overwrites_material")
                .count(),
            2
        );
    }

    #[test]
    fn slot_name_conflict_and_out_of_range_are_diagnosed() {
        let mut conflict = AssignmentInput::new("Wood", 0);
        conflict.slot_name_conflict = true;
        conflict.material_names = vec!["Metal".to_owned(), "Wood".to_owned()];
        conflict.mesh_names = vec!["MeshA".to_owned(), "MeshB".to_owned()];
        let mut too_high = AssignmentInput::new("TooHigh", 1);
        too_high.explicit_sub_index = Some(128);
        too_high.auto_assigned = false;
        let (records, diagnostics) = assign_sub_indices(&[conflict, too_high], &[]);
        assert_eq!(records[1].sub_index, -1);
        assert_eq!(records[1].requested_sub_index, Some(128));
        assert_eq!(records[1].assignment_reason, "explicit_out_of_range");
        assert!(diagnostics
            .iter()
            .any(|item| item.code == "material_slot_name_conflict"));
        assert!(diagnostics
            .iter()
            .any(|item| item.code == "rc_sub_index_out_of_range_deleted"));
    }

    #[test]
    fn fbx_id_beyond_limit_is_normalized_to_delete() {
        let mut input = AssignmentInput::new("Slot128", 0);
        input.fbx_material_id = Some(129);
        let (records, diagnostics) = assign_sub_indices(&[input], &[]);
        assert_eq!(records[0].sub_index, -1);
        assert_eq!(records[0].requested_sub_index, Some(128));
        assert_eq!(records[0].assignment_reason, "fbx_material_id_out_of_range");
        assert_eq!(diagnostics[0].details["fbx_slot"], json!(128));
    }

    #[test]
    fn blender_numeric_suffix_remains_distinct() {
        let (records, _) = assign_sub_indices(
            &[
                AssignmentInput::new("Stone", 0),
                AssignmentInput::new("Stone.001", 1),
            ],
            &[],
        );
        assert_eq!(
            indices(&records),
            BTreeMap::from([("Stone", 0), ("Stone.001", 1)])
        );
    }
}
