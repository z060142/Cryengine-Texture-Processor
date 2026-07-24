use clap::{Parser, Subcommand};
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

#[derive(Parser)]
#[command(version, about = "CryEngine FBX converter")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Dump raw ufbx scene evidence without applying conversion policy.
    Dump {
        /// Source FBX file.
        input: PathBuf,
        /// Destination JSON report.
        #[arg(long)]
        out: PathBuf,
    },
    Convert,
    Validate,
}

#[derive(Serialize)]
struct DumpReport {
    schema: &'static str,
    generated_by: &'static str,
    source_fbx: String,
    counts: SceneCounts,
    materials: Vec<MaterialReport>,
    meshes: Vec<MeshReport>,
    scene_tree: NodeReport,
}

#[derive(Serialize)]
struct SceneCounts {
    materials: usize,
    meshes: usize,
    nodes: usize,
}

#[derive(Serialize)]
struct MaterialReport {
    file_index: usize,
    name: String,
    element_id: u32,
    typed_id: u32,
    textures: Vec<TextureReport>,
}

#[derive(Serialize)]
struct TextureReport {
    material_prop: String,
    shader_prop: String,
    filename: String,
    absolute_filename: String,
    relative_filename: String,
    embedded: bool,
    content_size: usize,
}

#[derive(Serialize)]
struct MeshReport {
    name: String,
    element_id: u32,
    typed_id: u32,
    instances: Vec<String>,
    material_slots: Vec<MeshMaterialSlot>,
    face_count: usize,
    face_material_counts: Vec<FaceMaterialCount>,
}

#[derive(Serialize)]
struct MeshMaterialSlot {
    slot: usize,
    name: String,
    element_id: u32,
    typed_id: u32,
}

#[derive(Serialize)]
struct FaceMaterialCount {
    slot: u32,
    face_count: usize,
}

#[derive(Serialize)]
struct NodeReport {
    name: String,
    element_id: u32,
    typed_id: u32,
    children: Vec<NodeReport>,
}

fn main() -> ExitCode {
    match run(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run(cli: Cli) -> Result<(), String> {
    match cli.command {
        Command::Dump { input, out } => dump(&input, &out),
        Command::Convert | Command::Validate => Err("not implemented".to_owned()),
    }
}

fn dump(input: &Path, out: &Path) -> Result<(), String> {
    let input_utf8 = input
        .to_str()
        .ok_or_else(|| format!("input path is not valid UTF-8: {}", input.display()))?;
    let scene = ufbx::load_file(input_utf8, ufbx::LoadOpts::default())
        .map_err(|error| format!("failed to read {}: {error:?}", input.display()))?;

    let report = DumpReport {
        schema: "cryengine_ufbx_dump.v1",
        generated_by: "converter dump (ufbx 0.11.2)",
        source_fbx: input.display().to_string(),
        counts: SceneCounts {
            materials: scene.materials.count,
            meshes: scene.meshes.count,
            nodes: scene.nodes.count,
        },
        materials: scene
            .materials
            .iter()
            .enumerate()
            .map(|(file_index, material)| MaterialReport {
                file_index,
                name: material.element.name.to_string(),
                element_id: material.element.element_id,
                typed_id: material.element.typed_id,
                textures: material
                    .textures
                    .iter()
                    .map(|material_texture| {
                        let texture = &material_texture.texture;
                        TextureReport {
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
            .collect(),
        meshes: scene
            .meshes
            .iter()
            .map(|mesh| {
                let mut face_material_counts = BTreeMap::<u32, usize>::new();
                for &slot in mesh.face_material.iter() {
                    *face_material_counts.entry(slot).or_default() += 1;
                }

                MeshReport {
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
                    face_material_counts: face_material_counts
                        .into_iter()
                        .map(|(slot, face_count)| FaceMaterialCount { slot, face_count })
                        .collect(),
                }
            })
            .collect(),
        scene_tree: node_report(&scene.root_node),
    };

    let file = File::create(out)
        .map_err(|error| format!("failed to create {}: {error}", out.display()))?;
    let mut writer = BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, &report)
        .map_err(|error| format!("failed to write {}: {error}", out.display()))?;
    writer
        .write_all(b"\n")
        .map_err(|error| format!("failed to finish {}: {error}", out.display()))?;
    writer
        .flush()
        .map_err(|error| format!("failed to finish {}: {error}", out.display()))
}

fn node_report(node: &ufbx::Node) -> NodeReport {
    NodeReport {
        name: node.element.name.to_string(),
        element_id: node.element.element_id,
        typed_id: node.element.typed_id,
        children: node
            .children
            .iter()
            .map(|child| node_report(child))
            .collect(),
    }
}
