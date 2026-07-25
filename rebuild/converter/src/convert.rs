use crate::manifest::MaterialManifest;
use crate::model::ConverterModel;
use crate::mtl::{write_mtl, MaterialOverridePayload};
use crate::request::{build_import_request, write_request};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize)]
pub struct ConvertOutputs {
    pub request: PathBuf,
    pub mtl: PathBuf,
}

pub fn convert_file(
    input: &Path,
    manifest: Option<&Path>,
    overrides: Option<&Path>,
    texture_dir: Option<&Path>,
    out_dir: &Path,
) -> Result<ConvertOutputs, String> {
    let model = ConverterModel::load(input)?;
    let manifest = manifest.map(MaterialManifest::load).transpose()?;
    let overrides = overrides.map(MaterialOverridePayload::load).transpose()?;
    let request = build_import_request(&model, manifest.as_ref());
    let base_name = Path::new(&request.source_filename)
        .file_stem()
        .and_then(|name| name.to_str())
        .ok_or_else(|| {
            format!(
                "could not derive output basename from {:?}",
                request.source_filename
            )
        })?;
    fs::create_dir_all(out_dir)
        .map_err(|error| format!("failed to create {}: {error}", out_dir.display()))?;
    let request_path = out_dir.join(format!("{base_name}.json"));
    let mtl_path = out_dir.join(format!("{base_name}.mtl"));
    let texture_dir = texture_dir.unwrap_or(out_dir);
    write_request(&request, &request_path)?;
    write_mtl(&model, &request, overrides.as_ref(), texture_dir, &mtl_path)?;
    Ok(ConvertOutputs {
        request: request_path,
        mtl: mtl_path,
    })
}
