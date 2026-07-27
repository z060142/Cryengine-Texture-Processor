use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Debug, Clone)]
pub struct ConverterModel {
    pub source_fbx: String,
    pub materials: Vec<MaterialRecord>,
    pub meshes: Vec<MeshRecord>,
    pub scene_tree: NodeRecord,
    pub node_count: usize,
    pub axes: AxisDetection,
}

/// RC `forward_up_axes` derived from the source FBX's ufbx coordinate axes.
#[derive(Debug, Clone)]
pub struct AxisDetection {
    /// Value written into the RC import request.
    pub forward_up_axes: String,
    /// `true` when derived from declared axes, `false` when the default fallback
    /// was used (undeclared / unknown axes).
    pub declared: bool,
    /// Display token of the source up axis (e.g. `+Y`), if declared.
    pub up_token: Option<&'static str>,
    /// Display token of the source front axis (e.g. `+Z`), if declared.
    pub front_token: Option<&'static str>,
}

/// RC default source axes used when a file does not declare its coordinate axes.
/// Standard FBX is Y-up, so an undeclared file is almost certainly Y-up: the
/// Sandbox default for a Y-up import is Forward=-Z / Up=+Y, i.e. `-Z+Y`. (The
/// old hardcoded `-Y+Z` was a legacy defect — up=+Z is wrong for a Y-up file.)
pub const FALLBACK_FORWARD_UP_AXES: &str = "-Z+Y";

impl AxisDetection {
    /// Fallback for undeclared axes (and the value used by hand-built test models).
    pub fn fallback() -> Self {
        Self {
            forward_up_axes: FALLBACK_FORWARD_UP_AXES.to_owned(),
            declared: false,
            up_token: None,
            front_token: None,
        }
    }

    fn from_axes(front: ufbx::CoordinateAxis, up: ufbx::CoordinateAxis) -> Self {
        match derive_forward_up_axes(front, up) {
            Some(forward_up_axes) => Self {
                forward_up_axes,
                declared: true,
                up_token: axis_token(up),
                front_token: axis_token(front),
            },
            None => Self::fallback(),
        }
    }

    /// One-line detection summary for the GUI model panel.
    pub fn summary(&self) -> String {
        match (self.front_token, self.up_token) {
            (Some(front), Some(up)) => format!(
                "Axes: up {up}, front {front} → forward_up_axes {}",
                self.forward_up_axes
            ),
            _ => format!(
                "Axes: undeclared → forward_up_axes {} (default)",
                self.forward_up_axes
            ),
        }
    }
}

fn axis_token(axis: ufbx::CoordinateAxis) -> Option<&'static str> {
    use ufbx::CoordinateAxis::*;
    Some(match axis {
        PositiveX => "+X",
        NegativeX => "-X",
        PositiveY => "+Y",
        NegativeY => "-Y",
        PositiveZ => "+Z",
        NegativeZ => "-Z",
        Unknown => return None,
    })
}

fn negated_axis_token(axis: ufbx::CoordinateAxis) -> Option<&'static str> {
    use ufbx::CoordinateAxis::*;
    Some(match axis {
        PositiveX => "-X",
        NegativeX => "+X",
        PositiveY => "-Y",
        NegativeY => "+Y",
        PositiveZ => "-Z",
        NegativeZ => "+Z",
        Unknown => return None,
    })
}

/// Map the source FBX's ufbx coordinate axes to the RC `forward_up_axes` string
/// (`<forward><up>`).
///
/// ufbx defines `front` as the _opposite_ of forward (ufbx.h: "front is the
/// _opposite_ from forward"), so the source's forward direction = negate(front).
/// The RC up token is the source up axis unchanged. Anchored to the Sandbox
/// import default for a standard Y-up file (ufbx up=+Y, front=+Z) which Sandbox
/// imports as Forward=-Z / Up=+Y → `-Z+Y`; this also matches the native car CGF
/// chunk's up=+Y (phase99 evidence `+Z+Y`). The rule is:
///   forward token = negate(front), up token = up
///
/// Returns `None` when either axis is `Unknown` (undeclared) so the caller can
/// fall back to [`FALLBACK_FORWARD_UP_AXES`].
pub fn derive_forward_up_axes(
    front: ufbx::CoordinateAxis,
    up: ufbx::CoordinateAxis,
) -> Option<String> {
    Some(format!("{}{}", negated_axis_token(front)?, axis_token(up)?))
}

#[derive(Debug, Clone)]
pub struct MaterialRecord {
    pub name: String,
    pub typed_id: u32,
    pub element_id: u32,
    pub textures: Vec<TextureRef>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TextureRef {
    pub material_prop: String,
    pub shader_prop: String,
    pub filename: String,
    pub absolute_filename: String,
    pub relative_filename: String,
    pub embedded: bool,
    pub content_size: usize,
    #[serde(skip)]
    pub content: Vec<u8>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MeshRecord {
    pub name: String,
    pub element_id: u32,
    pub typed_id: u32,
    pub instances: Vec<String>,
    pub material_slots: Vec<MeshMaterialSlot>,
    pub face_count: usize,
    pub face_material_counts: Vec<FaceMaterialCount>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MeshMaterialSlot {
    pub slot: usize,
    pub name: String,
    pub element_id: u32,
    pub typed_id: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct FaceMaterialCount {
    pub slot: u32,
    pub face_count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct NodeRecord {
    pub name: String,
    pub element_id: u32,
    pub typed_id: u32,
    pub children: Vec<NodeRecord>,
}

impl ConverterModel {
    pub fn load(input: &Path) -> Result<Self, String> {
        let input_utf8 = input
            .to_str()
            .ok_or_else(|| format!("input path is not valid UTF-8: {}", input.display()))?;
        let scene = ufbx::load_file(input_utf8, ufbx::LoadOpts::default())
            .map_err(|error| format!("failed to read {}: {error:?}", input.display()))?;

        let materials = scene
            .materials
            .iter()
            .map(|material| MaterialRecord {
                name: material.element.name.to_string(),
                element_id: material.element.element_id,
                typed_id: material.element.typed_id,
                textures: material
                    .textures
                    .iter()
                    .map(|material_texture| {
                        let texture = &material_texture.texture;
                        TextureRef {
                            material_prop: material_texture.material_prop.to_string(),
                            shader_prop: material_texture.shader_prop.to_string(),
                            filename: texture.filename.to_string(),
                            absolute_filename: texture.absolute_filename.to_string(),
                            relative_filename: texture.relative_filename.to_string(),
                            embedded: !texture.content.is_empty(),
                            content_size: texture.content.len(),
                            content: texture.content.to_vec(),
                        }
                    })
                    .collect(),
            })
            .collect();

        let meshes = scene
            .meshes
            .iter()
            .map(|mesh| {
                let mut counts = BTreeMap::<u32, usize>::new();
                for &slot in mesh.face_material.iter() {
                    *counts.entry(slot).or_default() += 1;
                }

                MeshRecord {
                    name: mesh.element.name.to_string(),
                    element_id: mesh.element.element_id,
                    typed_id: mesh.element.typed_id,
                    instances: mesh
                        .element
                        .instances
                        .iter()
                        .map(|node| node.element.name.to_string())
                        .collect(),
                    material_slots: mesh
                        .materials
                        .iter()
                        .enumerate()
                        .map(|(slot, material)| MeshMaterialSlot {
                            slot,
                            name: material.element.name.to_string(),
                            element_id: material.element.element_id,
                            typed_id: material.element.typed_id,
                        })
                        .collect(),
                    face_count: mesh.num_faces,
                    face_material_counts: counts
                        .into_iter()
                        .map(|(slot, face_count)| FaceMaterialCount { slot, face_count })
                        .collect(),
                }
            })
            .collect();

        let axes = AxisDetection::from_axes(scene.settings.axes.front, scene.settings.axes.up);

        Ok(Self {
            source_fbx: input.display().to_string(),
            materials,
            meshes,
            scene_tree: node_record(&scene.root_node),
            node_count: scene.nodes.count,
            axes,
        })
    }

    pub fn material_face_counts(&self) -> BTreeMap<u32, usize> {
        let mut counts = BTreeMap::new();
        for mesh in &self.meshes {
            for face_count in &mesh.face_material_counts {
                let Some(material) = mesh.material_slots.get(face_count.slot as usize) else {
                    continue;
                };
                *counts.entry(material.typed_id).or_default() += face_count.face_count;
            }
        }
        counts
    }
}

fn node_record(node: &ufbx::Node) -> NodeRecord {
    NodeRecord {
        name: node.element.name.to_string(),
        element_id: node.element.element_id,
        typed_id: node.element.typed_id,
        children: node
            .children
            .iter()
            .map(|child| node_record(child))
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ufbx::CoordinateAxis::*;

    #[test]
    fn sandbox_anchor_derives_y_up_forward_up_axes() {
        // Standard FBX Y-up (ufbx up=+Y, front=+Z, as car.fbx and every KB3D
        // fixture probe) must derive the Sandbox import default `-Z+Y`
        // (Forward=-Z / Up=+Y). This is up=+Y, matching the native car CGF
        // import-settings chunk (phase99 `+Z+Y`, up=+Y); the old `-Y+Z` was a
        // legacy Python defect (up=+Z) that flipped Y-up models over.
        assert_eq!(
            derive_forward_up_axes(PositiveZ, PositiveY).as_deref(),
            Some("-Z+Y")
        );
    }

    #[test]
    fn unknown_axes_fall_back() {
        assert_eq!(derive_forward_up_axes(Unknown, PositiveY), None);
        assert_eq!(derive_forward_up_axes(PositiveZ, Unknown), None);
        let detection = AxisDetection::from_axes(Unknown, PositiveY);
        assert!(!detection.declared);
        assert_eq!(detection.forward_up_axes, FALLBACK_FORWARD_UP_AXES);
    }

    #[test]
    fn full_enum_sweep_maps_forward_negate_up_and_up_from_front() {
        let axes = [
            PositiveX, NegativeX, PositiveY, NegativeY, PositiveZ, NegativeZ,
        ];
        for &front in &axes {
            for &up in &axes {
                let derived = derive_forward_up_axes(front, up).unwrap();
                // forward token = negate(front), up token = up.
                let expected = format!(
                    "{}{}",
                    negated_axis_token(front).unwrap(),
                    axis_token(up).unwrap()
                );
                assert_eq!(derived, expected, "front={front:?} up={up:?}");
                // Structure: 2 signed axis tokens (forward then up).
                assert_eq!(derived.len(), 4);
            }
        }
        // Spot-check a genuinely Z-up source (up=+Z, front=-Y → forward=+Y).
        assert_eq!(
            derive_forward_up_axes(NegativeY, PositiveZ).as_deref(),
            Some("+Y+Z")
        );
    }
}
