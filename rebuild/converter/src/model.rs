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

        Ok(Self {
            source_fbx: input.display().to_string(),
            materials,
            meshes,
            scene_tree: node_record(&scene.root_node),
            node_count: scene.nodes.count,
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
