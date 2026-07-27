use crate::model::{ConverterModel, MaterialRecord, MeshRecord, NodeRecord, TextureRef};
use serde::Serialize;
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;

#[derive(Serialize)]
struct DumpReport<'a> {
    schema: &'static str,
    generated_by: &'static str,
    source_fbx: &'a str,
    counts: SceneCounts,
    materials: Vec<DumpMaterial<'a>>,
    meshes: &'a [MeshRecord],
    scene_tree: &'a NodeRecord,
}

#[derive(Serialize)]
struct SceneCounts {
    materials: usize,
    meshes: usize,
    nodes: usize,
}

#[derive(Serialize)]
struct DumpMaterial<'a> {
    file_index: usize,
    name: &'a str,
    element_id: u32,
    typed_id: u32,
    textures: &'a [TextureRef],
}

pub fn write_dump(model: &ConverterModel, out: &Path) -> Result<(), String> {
    let report = DumpReport {
        schema: "cryengine_ufbx_dump.v1",
        generated_by: "converter dump (ufbx 0.11.2)",
        source_fbx: &model.source_fbx,
        counts: SceneCounts {
            materials: model.materials.len(),
            meshes: model.meshes.len(),
            nodes: model.node_count,
        },
        materials: model
            .materials
            .iter()
            .enumerate()
            .map(dump_material)
            .collect(),
        meshes: &model.meshes,
        scene_tree: &model.scene_tree,
    };
    write_pretty_json(out, &report)
}

fn dump_material((file_index, material): (usize, &MaterialRecord)) -> DumpMaterial<'_> {
    DumpMaterial {
        file_index,
        name: &material.name,
        element_id: material.element_id,
        typed_id: material.typed_id,
        textures: &material.textures,
    }
}

pub(crate) fn write_pretty_json<T: Serialize>(out: &Path, value: &T) -> Result<(), String> {
    let file = File::create(out)
        .map_err(|error| format!("failed to create {}: {error}", out.display()))?;
    let mut writer = BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, value)
        .map_err(|error| format!("failed to write {}: {error}", out.display()))?;
    writer
        .write_all(b"\n")
        .map_err(|error| format!("failed to finish {}: {error}", out.display()))?;
    writer
        .flush()
        .map_err(|error| format!("failed to finish {}: {error}", out.display()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;
    use std::fs;
    use std::path::PathBuf;

    #[test]
    fn car_dump_has_no_t003_regression_when_fixture_is_available() {
        let crate_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let input = crate_dir.join("../fixtures/car/car.fbx");
        let baseline = crate_dir.join("../legacy/docs/ufbx_alignment_report.json");
        if !input.exists() || !baseline.exists() {
            return;
        }

        let model = ConverterModel::load(&input).unwrap();
        let output = std::env::temp_dir().join(format!(
            "converter-t004-dump-regression-{}-{}.json",
            std::process::id(),
            line!()
        ));
        write_dump(&model, &output).unwrap();

        let mut expected: Value =
            serde_json::from_str(&fs::read_to_string(baseline).unwrap()).unwrap();
        expected["source_fbx"] = Value::String(model.source_fbx.clone());
        let actual: Value = serde_json::from_str(&fs::read_to_string(&output).unwrap()).unwrap();
        let actual_texture_filenames: Vec<Vec<Value>> = actual["materials"]
            .as_array()
            .unwrap()
            .iter()
            .map(|material| {
                material["textures"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|texture| texture["filename"].clone())
                    .collect()
            })
            .collect();
        for (material, filenames) in expected["materials"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .zip(actual_texture_filenames)
        {
            for (texture, filename) in material["textures"]
                .as_array_mut()
                .unwrap()
                .iter_mut()
                .zip(filenames)
            {
                texture["filename"] = filename;
            }
        }
        fs::remove_file(output).unwrap();
        assert_eq!(actual, expected);
    }
}
