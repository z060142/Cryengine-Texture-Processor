use crate::diagnostic::Diagnostic;
use crate::dump::write_pretty_json;
use crate::index_assigner::{assign_sub_indices, inputs_from_model, Assignment};
use crate::model::ConverterModel;
use crate::rc_policy::{physicalize_diagnostics, resolve_physicalize, PhysicalizeResolution};
use crate::slot_contract::build_slot_mapping_contract;
use crate::slot_table::{build_expanded_slot_table, MaterialSlot};
use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Serialize)]
struct PolicyReport<'a> {
    schema: &'static str,
    generated_by: &'static str,
    source_fbx: &'a str,
    summary: PolicySummary,
    materials: Vec<PolicyMaterial>,
    diagnostics: Vec<Diagnostic>,
    material_slots: Vec<MaterialSlot>,
    material_slot_mapping: Value,
    material_slot_evidence: SlotEvidence,
    golden_policy_projection: GoldenPolicyProjection,
    limitations: [&'static str; 2],
}

#[derive(Serialize)]
struct PolicySummary {
    material_count: usize,
    emitted_material_count: usize,
    slot_count: usize,
    diagnostic_count: usize,
    action_required: bool,
}

#[derive(Serialize)]
struct PolicyMaterial {
    order: usize,
    name: String,
    element_id: u32,
    typed_id: u32,
    fbx_material_id: u32,
    raw_fbx_slot: u32,
    sub_index: i32,
    assignment_reason: String,
    polygon_count: usize,
    physicalize: String,
    physicalize_source: String,
}

#[derive(Serialize)]
struct SlotEvidence {
    schema: &'static str,
    evidence_basis: &'static str,
    summary: SlotEvidenceSummary,
    rows: Vec<SlotEvidenceRow>,
}

#[derive(Serialize)]
struct SlotEvidenceSummary {
    ok: bool,
    row_count: usize,
    used_source_material_slot_count: usize,
    max_used_material_id: Option<i32>,
    status_counts: BTreeMap<String, usize>,
    action_required: bool,
}

#[derive(Serialize)]
struct SlotEvidenceRow {
    ok: bool,
    status: String,
    slot: i32,
    name: String,
    source_order: Option<usize>,
    fbx_material_id: Option<u32>,
    physicalize: String,
    source_face_count: usize,
    used_by_source: bool,
    is_unassigned_placeholder: bool,
}

#[derive(Serialize)]
struct GoldenPolicyProjection {
    request_materials: Vec<ProjectedRequestMaterial>,
}

#[derive(Serialize)]
struct ProjectedRequestMaterial {
    order: usize,
    name: String,
    sub_index: i32,
    physicalize: String,
}

pub fn write_report(model: &ConverterModel, out: &Path) -> Result<(), String> {
    let inputs = inputs_from_model(model);
    let (assignments, mut diagnostics) = assign_sub_indices(&inputs, &[]);
    let physicalize: Vec<_> = assignments
        .iter()
        .map(|assignment| resolve_physicalize(None, &assignment.name))
        .collect();
    for (assignment, resolution) in assignments.iter().zip(&physicalize) {
        diagnostics.extend(physicalize_diagnostics(&assignment.name, resolution));
    }

    let slots = build_expanded_slot_table(&assignments, true, true, true);
    let materials = policy_materials(model, &assignments, &physicalize);
    let slot_evidence = build_slot_evidence(&assignments, &physicalize, &slots);
    let request_materials = projected_request_materials(&assignments, &physicalize, &slots);
    let report = PolicyReport {
        schema: "cryengine_converter_policy_report.v1",
        generated_by: "converter report (C1+C2 policy projection)",
        source_fbx: &model.source_fbx,
        summary: PolicySummary {
            material_count: assignments.len(),
            emitted_material_count: assignments
                .iter()
                .filter(|assignment| assignment.sub_index >= 0 && !assignment.deleted)
                .count(),
            slot_count: slots.len(),
            diagnostic_count: diagnostics.len(),
            action_required: diagnostics
                .iter()
                .any(|item| matches!(item.severity.as_str(), "hazard" | "error")),
        },
        materials,
        diagnostics,
        material_slots: slots,
        material_slot_mapping: build_slot_mapping_contract(&assignments),
        material_slot_evidence: slot_evidence,
        golden_policy_projection: GoldenPolicyProjection { request_materials },
        limitations: [
            "No manifest/request input is accepted by this temporary C2 command, so physicalize values without explicit metadata use the name heuristic.",
            "No RC, CGF, or MTL readback is performed; material_slot_evidence is a source-FBX policy projection, not engine-output evidence.",
        ],
    };
    write_pretty_json(out, &report)
}

fn projected_request_materials(
    assignments: &[Assignment],
    physicalize: &[PhysicalizeResolution],
    slots: &[MaterialSlot],
) -> Vec<ProjectedRequestMaterial> {
    let resolutions: BTreeMap<_, _> = assignments
        .iter()
        .zip(physicalize)
        .map(|(assignment, resolution)| (assignment.sub_index, resolution.value.as_str()))
        .collect();
    slots
        .iter()
        .enumerate()
        .map(|(order, slot)| ProjectedRequestMaterial {
            order,
            name: slot.name.clone(),
            sub_index: slot.sub_index,
            physicalize: resolutions
                .get(&slot.sub_index)
                .copied()
                .unwrap_or("no")
                .to_owned(),
        })
        .collect()
}

fn policy_materials(
    model: &ConverterModel,
    assignments: &[Assignment],
    physicalize: &[PhysicalizeResolution],
) -> Vec<PolicyMaterial> {
    assignments
        .iter()
        .zip(physicalize)
        .map(|(assignment, resolution)| {
            let material = &model.materials[assignment.source_order];
            PolicyMaterial {
                order: assignment.source_order,
                name: assignment.name.clone(),
                element_id: material.element_id,
                typed_id: material.typed_id,
                fbx_material_id: assignment.fbx_material_id.unwrap_or(0),
                raw_fbx_slot: assignment.fbx_slot.unwrap_or(0),
                sub_index: assignment.sub_index,
                assignment_reason: assignment.assignment_reason.clone(),
                polygon_count: assignment.polygon_count.unwrap_or(0),
                physicalize: resolution.value.as_str().to_owned(),
                physicalize_source: resolution.source.clone(),
            }
        })
        .collect()
}

fn build_slot_evidence(
    assignments: &[Assignment],
    physicalize: &[PhysicalizeResolution],
    slots: &[MaterialSlot],
) -> SlotEvidence {
    let resolutions: BTreeMap<_, _> = assignments
        .iter()
        .zip(physicalize)
        .map(|(assignment, resolution)| (assignment.sub_index, resolution.value.as_str()))
        .collect();
    let assignments_by_slot: BTreeMap<_, _> = assignments
        .iter()
        .filter(|assignment| assignment.sub_index >= 0 && !assignment.deleted)
        .map(|assignment| (assignment.sub_index, assignment))
        .collect();
    let mut status_counts = BTreeMap::new();
    let rows = slots
        .iter()
        .map(|slot| {
            let assignment = assignments_by_slot.get(&slot.sub_index).copied();
            let is_placeholder = slot.is_unassigned_placeholder == Some(true);
            let status = if is_placeholder {
                "trailing_unassigned_placeholder"
            } else if assignment.is_some() {
                "source_slot_projected"
            } else {
                "slot_gap"
            };
            *status_counts.entry(status.to_owned()).or_default() += 1;
            let face_count = assignment.and_then(|item| item.polygon_count).unwrap_or(0);
            SlotEvidenceRow {
                ok: true,
                status: status.to_owned(),
                slot: slot.sub_index,
                name: slot.name.clone(),
                source_order: assignment.map(|item| item.source_order),
                fbx_material_id: assignment.and_then(|item| item.fbx_material_id),
                physicalize: if is_placeholder {
                    "no"
                } else {
                    resolutions.get(&slot.sub_index).copied().unwrap_or("no")
                }
                .to_owned(),
                source_face_count: face_count,
                used_by_source: face_count > 0,
                is_unassigned_placeholder: is_placeholder,
            }
        })
        .collect::<Vec<_>>();
    let used_slots: Vec<_> = rows.iter().filter(|row| row.used_by_source).collect();

    SlotEvidence {
        schema: "cryengine_material_slot_policy_evidence.v1",
        evidence_basis: "source_fbx_policy_projection_not_cgf_readback",
        summary: SlotEvidenceSummary {
            ok: true,
            row_count: rows.len(),
            used_source_material_slot_count: used_slots.len(),
            max_used_material_id: used_slots.iter().map(|row| row.slot).max(),
            status_counts,
            action_required: false,
        },
        rows,
    }
}
