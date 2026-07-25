use crate::index_assigner::{assign_sub_indices, inputs_from_model};
use crate::manifest::MaterialManifest;
use crate::model::{ConverterModel, NodeRecord};
use crate::rc_policy::{resolve_physicalize, Physicalize, RC_MAX_SUB_MATERIALS};
use crate::slot_table::build_expanded_slot_table;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

const OUTPUT_EXTENSIONS: &[&str] = &["caf", "cgf", "chr", "i_caf", "skin"];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ImportRequest {
    pub source_filename: String,
    pub output_ext: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub material_filename: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub forward_up_axes: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unit_size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scale: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub physics_primitive: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub merge_all_nodes: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub scene_origin: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ignore_custom_normals: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ignore_uv: Option<bool>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub materials: Vec<RequestMaterial>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub nodes: Vec<RequestNode>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub autolodsettings: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub animation: Option<RequestAnimation>,
    #[serde(rename = "jointPhysicsData", default)]
    pub joint_physics_data: Vec<JointPhysics>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequestMaterial {
    pub name: String,
    pub physicalize: String,
    pub sub_index: i32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequestNode {
    pub name: String,
    pub path: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mass: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub density: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub no_hit_refinement: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dynamic: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub entity: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pieces: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub primitive: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub no_explosion_occlusion: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stiffness: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hardness: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_stretch: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_impulse: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub skin_dist: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub thickness: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explosion_scale: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gameplay_critical: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub player_can_break: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub constraint_limit: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub constraint_minang: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub constraint_maxang: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub constraint_damping: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub constraint_collides: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub udp: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub nodes: Vec<RequestNode>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequestAnimation {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(rename = "motionNodePath", skip_serializing_if = "Option::is_none")]
    pub motion_node_path: Option<Vec<String>>,
    #[serde(rename = "startFrame", skip_serializing_if = "Option::is_none")]
    pub start_frame: Option<i64>,
    #[serde(rename = "endFrame", skip_serializing_if = "Option::is_none")]
    pub end_frame: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct JointPhysics {
    #[serde(rename = "jointNodePath")]
    pub joint_node_path: Vec<String>,
    #[serde(rename = "proxyNodePath")]
    pub proxy_node_path: Vec<String>,
    #[serde(rename = "snapToJoint")]
    pub snap_to_joint: bool,
    #[serde(rename = "jointLimits", skip_serializing_if = "Option::is_none")]
    pub joint_limits: Option<JointLimits>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct JointLimits {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_x: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_y: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_z: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_x: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_y: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_z: Option<f64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct RequestDiagnostic {
    pub severity: String,
    pub code: String,
    pub location: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GateSummary {
    pub ok: bool,
    pub diagnostic_count: usize,
    pub error_count: usize,
    pub warning_count: usize,
}

#[derive(Debug, Serialize)]
pub struct RequestGate {
    pub schema: &'static str,
    pub source: String,
    pub summary: RequestGateFileSummary,
    pub gate: Gate,
}

#[derive(Debug, Serialize)]
pub struct RequestGateFileSummary {
    pub request_count: usize,
}

#[derive(Debug, Serialize)]
pub struct Gate {
    pub schema: &'static str,
    pub summary: GateSummary,
    pub diagnostics: Vec<RequestDiagnostic>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct NodeType {
    pub is_lod: bool,
    pub is_proxy: bool,
    pub is_helper: bool,
    pub lod_level: Option<u32>,
}

pub fn detect_node_type(name: &str) -> NodeType {
    let lower = name.to_ascii_lowercase();
    let lod_level = lod_level(&lower);
    let is_proxy = lower.starts_with("$proxy")
        || lower.starts_with("$physics")
        || lower.starts_with("proxy_")
        || lower.starts_with("physics_")
        || ["_proxy", "_physics", "_phys"]
            .iter()
            .any(|suffix| lower.ends_with(suffix));
    let is_helper = ["_helper", "_control", "_pivot", "_locator", "_target"]
        .iter()
        .any(|part| lower.contains(part));
    NodeType {
        is_lod: lod_level.is_some(),
        is_proxy,
        is_helper,
        lod_level,
    }
}

fn lod_level(name: &str) -> Option<u32> {
    for prefix in ["$lod", "lod"] {
        if let Some(rest) = name.strip_prefix(prefix) {
            let digits: String = rest.chars().take_while(char::is_ascii_digit).collect();
            if !digits.is_empty()
                && rest
                    .chars()
                    .nth(digits.len())
                    .is_none_or(|next| next == '_')
            {
                return digits.parse().ok();
            }
        }
    }
    let (_, suffix) = name.rsplit_once("_lod")?;
    (!suffix.is_empty() && suffix.chars().all(|ch| ch.is_ascii_digit()))
        .then(|| suffix.parse().ok())
        .flatten()
}

pub fn build_import_request(
    model: &ConverterModel,
    manifest: Option<&MaterialManifest>,
) -> ImportRequest {
    let source_filename = manifest
        .and_then(MaterialManifest::source_filename)
        .map(str::to_owned)
        .or_else(|| {
            Path::new(&model.source_fbx)
                .file_name()
                .and_then(|name| name.to_str())
                .map(str::to_owned)
        })
        .unwrap_or_else(|| model.source_fbx.clone());
    let material_filename = Path::new(&source_filename)
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or(&source_filename)
        .to_owned();

    let inputs = manifest.map_or_else(
        || inputs_from_model(model),
        |manifest| manifest.apply_to_model(model),
    );
    let (assignments, _) = assign_sub_indices(&inputs, &[]);
    let slots = build_expanded_slot_table(&assignments, false, true, true);
    let materials = slots
        .into_iter()
        .map(|slot| {
            let physicalize = resolve_physicalize(
                slot.physicalize
                    .as_deref()
                    .map(|value| ("physicalize", value)),
                &slot.name,
            );
            RequestMaterial {
                name: slot.name,
                physicalize: physicalize.value.as_str().to_owned(),
                sub_index: slot.sub_index,
            }
        })
        .collect();

    let mut nodes: Vec<_> = model
        .scene_tree
        .children
        .iter()
        .map(|node| request_node(node, &[]))
        .collect();
    sort_nodes(&mut nodes);
    let mut joint_physics_data = Vec::new();
    collect_joint_physics(&nodes, &mut joint_physics_data);

    ImportRequest {
        source_filename,
        output_ext: "cgf".to_owned(),
        material_filename: Some(material_filename),
        forward_up_axes: Some("-Y+Z".to_owned()),
        unit_size: Some("cm".to_owned()),
        scale: Some(1.0),
        physics_primitive: None,
        merge_all_nodes: Some(false),
        scene_origin: Some(false),
        ignore_custom_normals: Some(false),
        ignore_uv: Some(false),
        materials,
        nodes,
        autolodsettings: Some(json!({"GenerateAutomaticLODs": false})),
        animation: None,
        joint_physics_data,
    }
}

fn request_node(node: &NodeRecord, parent_path: &[String]) -> RequestNode {
    let mut path = parent_path.to_vec();
    path.push(node.name.clone());
    let mut children: Vec<_> = node
        .children
        .iter()
        .map(|child| request_node(child, &path))
        .collect();
    sort_nodes(&mut children);
    RequestNode {
        name: node.name.clone(),
        path,
        mass: Some(-1.0),
        density: Some(-1.0),
        no_hit_refinement: None,
        dynamic: None,
        entity: None,
        pieces: None,
        primitive: None,
        no_explosion_occlusion: None,
        stiffness: None,
        hardness: None,
        max_stretch: None,
        max_impulse: None,
        skin_dist: None,
        thickness: None,
        explosion_scale: None,
        gameplay_critical: None,
        player_can_break: None,
        constraint_limit: None,
        constraint_minang: None,
        constraint_maxang: None,
        constraint_damping: None,
        constraint_collides: None,
        udp: None,
        nodes: children,
    }
}

fn sort_nodes(nodes: &mut [RequestNode]) {
    nodes.sort_by(|left, right| left.name.cmp(&right.name));
    for node in nodes {
        sort_nodes(&mut node.nodes);
    }
}

fn collect_joint_physics(nodes: &[RequestNode], output: &mut Vec<JointPhysics>) {
    for node in nodes {
        if detect_node_type(&node.name).is_proxy && node.path.len() > 1 {
            output.push(JointPhysics {
                joint_node_path: node.path[..node.path.len() - 1].to_vec(),
                proxy_node_path: node.path.clone(),
                snap_to_joint: true,
                joint_limits: None,
            });
        }
        collect_joint_physics(&node.nodes, output);
    }
}

pub fn validate_request(request: &ImportRequest) -> Vec<RequestDiagnostic> {
    let mut diagnostics = Vec::new();
    if request.source_filename.trim().is_empty() {
        diagnostics.push(error(
            "rc_request_invalid_source_filename",
            "source_filename",
            "RC import request source_filename must be a non-empty string.",
        ));
    }
    if !OUTPUT_EXTENSIONS.contains(&request.output_ext.as_str()) {
        diagnostics.push(error(
            "rc_request_invalid_output_ext",
            "output_ext",
            "RC import request output_ext is not a supported FBX converter output extension.",
        ));
    }
    for (index, material) in request.materials.iter().enumerate() {
        if material.name.trim().is_empty() {
            diagnostics.push(error(
                "rc_request_invalid_material_name",
                &format!("materials[{index}].name"),
                "RC import request material name must be a non-empty string.",
            ));
        }
        if Physicalize::parse(&material.physicalize).is_none() {
            diagnostics.push(error(
                "rc_request_invalid_material_physicalize",
                &format!("materials[{index}].physicalize"),
                "RC import request material physicalize must match the source-backed enum.",
            ));
        }
        if material.sub_index < -1 || material.sub_index >= RC_MAX_SUB_MATERIALS {
            diagnostics.push(error(
                "rc_request_invalid_material_sub_index",
                &format!("materials[{index}].sub_index"),
                "RC-facing material sub_index must be from -1 through 127.",
            ));
        }
    }
    validate_nodes(&request.nodes, "nodes", &mut diagnostics);
    if let Some(animation) = &request.animation {
        for (field, value) in [
            ("startFrame", animation.start_frame),
            ("endFrame", animation.end_frame),
        ] {
            if value.is_some_and(|frame| frame < -1) {
                diagnostics.push(error(
                    "rc_request_invalid_animation_frame",
                    &format!("animation.{field}"),
                    "Animation frame bounds must be integer frame numbers or -1.",
                ));
            }
        }
    }
    diagnostics
}

fn validate_nodes(
    nodes: &[RequestNode],
    path_prefix: &str,
    diagnostics: &mut Vec<RequestDiagnostic>,
) {
    for (index, node) in nodes.iter().enumerate() {
        let location = format!("{path_prefix}[{index}]");
        if node.name.trim().is_empty() {
            diagnostics.push(error(
                "rc_request_invalid_node_name",
                &format!("{location}.name"),
                "RC import request node name must be a non-empty string.",
            ));
        }
        validate_nodes(&node.nodes, &format!("{location}.nodes"), diagnostics);
    }
}

fn error(code: &str, location: &str, message: &str) -> RequestDiagnostic {
    RequestDiagnostic {
        severity: "error".to_owned(),
        code: code.to_owned(),
        location: location.to_owned(),
        message: message.to_owned(),
    }
}

pub fn write_request(request: &ImportRequest, path: &Path) -> Result<(), String> {
    let mut json = serde_json::to_string_pretty(request)
        .map_err(|error| format!("failed to serialize request: {error}"))?;
    json.push('\n');
    fs::write(path, json).map_err(|error| format!("failed to write {}: {error}", path.display()))
}

pub fn validate_file(input: &Path, out: &Path) -> Result<bool, String> {
    let source = input.display().to_string();
    let parsed = fs::read_to_string(input)
        .map_err(|error| format!("failed to read request {}: {error}", input.display()))
        .and_then(|json| {
            serde_json::from_str::<ImportRequest>(&json)
                .map_err(|error| format!("request schema/type error: {error}"))
        });
    let diagnostics = match parsed {
        Ok(request) => validate_request(&request),
        Err(message) => vec![error(
            "rc_request_schema_or_type_error",
            "request",
            &message,
        )],
    };
    let error_count = diagnostics
        .iter()
        .filter(|diagnostic| diagnostic.severity == "error")
        .count();
    let warning_count = diagnostics
        .iter()
        .filter(|diagnostic| diagnostic.severity == "warning")
        .count();
    let ok = error_count == 0;
    let gate = RequestGate {
        schema: "cryengine_rc_import_request_schema_gate.v1",
        source,
        summary: RequestGateFileSummary { request_count: 1 },
        gate: Gate {
            schema: "cryengine_rc_import_request_schema_gate.v1",
            summary: GateSummary {
                ok,
                diagnostic_count: diagnostics.len(),
                error_count,
                warning_count,
            },
            diagnostics,
        },
    };
    let mut json = serde_json::to_string_pretty(&gate)
        .map_err(|error| format!("failed to serialize request gate: {error}"))?;
    json.push('\n');
    fs::write(out, json).map_err(|error| format!("failed to write {}: {error}", out.display()))?;
    Ok(ok)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_request() -> ImportRequest {
        ImportRequest {
            source_filename: "chair.fbx".to_owned(),
            output_ext: "cgf".to_owned(),
            material_filename: Some("chair".to_owned()),
            forward_up_axes: Some("-Y+Z".to_owned()),
            unit_size: Some("cm".to_owned()),
            scale: Some(1.0),
            physics_primitive: None,
            merge_all_nodes: Some(false),
            scene_origin: Some(false),
            ignore_custom_normals: Some(false),
            ignore_uv: Some(false),
            materials: vec![RequestMaterial {
                name: "Chair".to_owned(),
                physicalize: "no_collide".to_owned(),
                sub_index: 0,
            }],
            nodes: Vec::new(),
            autolodsettings: Some(json!({"GenerateAutomaticLODs": false})),
            animation: None,
            joint_physics_data: Vec::new(),
        }
    }

    #[test]
    fn serde_schema_rejects_unknown_fields() {
        let json = r#"{"source_filename":"a.fbx","output_ext":"cgf","debug":true}"#;
        let error = serde_json::from_str::<ImportRequest>(json).unwrap_err();
        assert!(error.to_string().contains("unknown field `debug`"));
    }

    #[test]
    fn serde_schema_rejects_unknown_nested_fields() {
        let json = r#"{
            "source_filename":"a.fbx",
            "output_ext":"cgf",
            "materials":[{"name":"Stone","physicalize":"no","sub_index":0,"debug":true}]
        }"#;
        let error = serde_json::from_str::<ImportRequest>(json).unwrap_err();
        assert!(error.to_string().contains("unknown field `debug`"));
    }

    #[test]
    fn semantic_validation_covers_rc_value_domains() {
        let mut request = minimal_request();
        request.output_ext = "abc".to_owned();
        request.materials[0].name.clear();
        request.materials[0].physicalize = "render_only".to_owned();
        request.materials[0].sub_index = 128;
        let diagnostics = validate_request(&request);
        assert_eq!(
            diagnostics
                .iter()
                .map(|diagnostic| diagnostic.code.as_str())
                .collect::<Vec<_>>(),
            [
                "rc_request_invalid_output_ext",
                "rc_request_invalid_material_name",
                "rc_request_invalid_material_physicalize",
                "rc_request_invalid_material_sub_index",
            ]
        );
    }

    #[test]
    fn animation_and_joint_physics_fields_round_trip() {
        let mut request = minimal_request();
        request.output_ext = "caf".to_owned();
        request.animation = Some(RequestAnimation {
            name: Some("Walk".to_owned()),
            motion_node_path: Some(vec!["Root".to_owned(), "Hips".to_owned()]),
            start_frame: Some(-1),
            end_frame: Some(30),
        });
        request.joint_physics_data.push(JointPhysics {
            joint_node_path: vec!["Root".to_owned()],
            proxy_node_path: vec!["Root".to_owned(), "Chair_proxy".to_owned()],
            snap_to_joint: true,
            joint_limits: Some(JointLimits {
                min_x: Some(-1.0),
                min_y: None,
                min_z: None,
                max_x: Some(1.0),
                max_y: None,
                max_z: None,
            }),
        });
        let json = serde_json::to_string(&request).unwrap();
        let round_trip: ImportRequest = serde_json::from_str(&json).unwrap();
        assert_eq!(request, round_trip);
        assert!(validate_request(&request).is_empty());
    }

    #[test]
    fn node_type_detection_matches_python_policy() {
        assert_eq!(detect_node_type("$lod2_body").lod_level, Some(2));
        assert_eq!(detect_node_type("body_lod3").lod_level, Some(3));
        assert!(detect_node_type("Chair_proxy").is_proxy);
        assert!(detect_node_type("wheel_pivot").is_helper);
        assert!(!detect_node_type("ChairMesh").is_proxy);
    }

    #[test]
    fn evidence_numbers_keep_integer_and_float_types() {
        let request: ImportRequest = serde_json::from_str(
            r#"{
                "source_filename":"a.fbx",
                "output_ext":"cgf",
                "scale":1.0,
                "materials":[{"name":"Stone","physicalize":"no","sub_index":0}]
            }"#,
        )
        .unwrap();
        assert_eq!(request.scale, Some(1.0));
        assert_eq!(request.materials[0].sub_index, 0);
    }
}
