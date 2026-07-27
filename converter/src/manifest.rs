use crate::index_assigner::{inputs_from_model, AssignmentInput};
use crate::model::ConverterModel;
use serde::Deserialize;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct MaterialManifest {
    #[serde(default)]
    fbx: Option<String>,
    #[serde(default)]
    materials: Vec<ManifestMaterial>,
    #[serde(default)]
    polygons: Vec<ManifestPolygon>,
}

#[derive(Debug, Deserialize)]
struct ManifestMaterial {
    slot: Option<i32>,
    name: Option<String>,
    physicalize: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ManifestPolygon {
    expected_cgf_material_id: Option<i32>,
    material_table_slot: Option<i32>,
    material_slot: Option<i32>,
    object: Option<String>,
}

impl MaterialManifest {
    pub fn load(path: &Path) -> Result<Self, String> {
        let json = fs::read_to_string(path)
            .map_err(|error| format!("failed to read manifest {}: {error}", path.display()))?;
        Self::from_json_str(&json)
            .map_err(|error| format!("failed to parse manifest {}: {error}", path.display()))
    }

    pub fn from_json_str(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }

    pub fn source_filename(&self) -> Option<&str> {
        self.fbx
            .as_deref()
            .and_then(|path| path.rsplit(['\\', '/']).next())
            .filter(|name| !name.is_empty())
    }

    pub fn apply_to_model(&self, model: &ConverterModel) -> Vec<AssignmentInput> {
        self.apply_to_inputs(inputs_from_model(model))
    }

    pub fn apply_to_inputs(
        &self,
        source_inputs: impl IntoIterator<Item = AssignmentInput>,
    ) -> Vec<AssignmentInput> {
        let source_inputs: Vec<_> = source_inputs.into_iter().collect();
        if self.materials.is_empty() {
            return source_inputs;
        }

        let mut source_by_name: BTreeMap<_, _> = source_inputs
            .into_iter()
            .map(|input| (input.name.clone(), input))
            .collect();
        let (polygon_counts, mesh_names) = self.polygon_metadata();
        let mut materials: Vec<_> = self
            .materials
            .iter()
            .enumerate()
            .filter_map(|(manifest_order, material)| {
                let slot = material.slot.filter(|slot| *slot >= 0)?;
                let name = material
                    .name
                    .as_deref()
                    .filter(|name| !name.trim().is_empty())?;
                Some((slot, manifest_order, name, material))
            })
            .collect();
        materials.sort_by_key(|(slot, manifest_order, _, _)| (*slot, *manifest_order));

        materials
            .into_iter()
            .enumerate()
            .map(|(source_order, (slot, _, name, material))| {
                let mut merged = source_by_name
                    .remove(name)
                    .unwrap_or_else(|| AssignmentInput::new(name, source_order));
                merged.name = name.to_owned();
                merged.original_name = name.to_owned();
                merged.source_order = source_order;
                merged.fbx_material_id = u32::try_from(slot)
                    .ok()
                    .and_then(|slot| slot.checked_add(1));
                merged.explicit_sub_index = Some(slot);
                merged.auto_assigned = false;
                if merged.polygon_count.is_none() {
                    merged.polygon_count = Some(*polygon_counts.get(&slot).unwrap_or(&0));
                }
                if merged.used_by_polygons.is_none() {
                    merged.used_by_polygons =
                        Some(polygon_counts.get(&slot).is_some_and(|count| *count > 0));
                }
                if merged.mesh_names.is_empty() {
                    merged.mesh_names = mesh_names
                        .get(&slot)
                        .map(|names| names.iter().cloned().collect())
                        .unwrap_or_default();
                }
                if merged.material_names.is_empty() {
                    merged.material_names.push(name.to_owned());
                }
                if merged.physicalize.is_none() {
                    merged.physicalize = material.physicalize.clone();
                }
                merged
            })
            .collect()
    }

    fn polygon_metadata(&self) -> (BTreeMap<i32, usize>, BTreeMap<i32, BTreeSet<String>>) {
        let mut counts = BTreeMap::new();
        let mut mesh_names: BTreeMap<i32, BTreeSet<String>> = BTreeMap::new();
        for polygon in &self.polygons {
            let slot = polygon
                .expected_cgf_material_id
                .or(polygon.material_table_slot)
                .or(polygon.material_slot)
                .filter(|slot| *slot >= 0);
            let Some(slot) = slot else {
                continue;
            };
            *counts.entry(slot).or_default() += 1;
            if let Some(name) = polygon.object.as_deref().filter(|name| !name.is_empty()) {
                mesh_names.entry(slot).or_default().insert(name.to_owned());
            }
        }
        (counts, mesh_names)
    }
}

pub fn apply_physicalize_overrides(
    inputs: &mut [AssignmentInput],
    overrides: &BTreeMap<String, String>,
) {
    for input in inputs {
        if let Some(value) = overrides.get(&input.name) {
            input.physicalize = Some(value.clone());
        }
    }
}
