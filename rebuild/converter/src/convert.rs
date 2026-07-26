use crate::manifest::MaterialManifest;
use crate::model::ConverterModel;
use crate::mtl::{write_mtl, MaterialOverridePayload, MaterialTextureDiagnostic};
use crate::request::{build_import_request_with_physicalize_overrides, write_request};
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize)]
pub struct ConvertOutputs {
    pub request: PathBuf,
    pub mtl: PathBuf,
    pub material_diagnostics: Vec<MaterialTextureDiagnostic>,
}

pub fn convert_file(
    input: &Path,
    manifest: Option<&Path>,
    overrides: Option<&Path>,
    texture_dir: Option<&Path>,
    preserve_mtl_textures: Option<&Path>,
    out_dir: &Path,
) -> Result<ConvertOutputs, String> {
    convert_file_with_physicalize(
        input,
        manifest,
        overrides,
        texture_dir,
        preserve_mtl_textures,
        out_dir,
        &BTreeMap::new(),
    )
}

pub fn convert_file_with_physicalize(
    input: &Path,
    manifest: Option<&Path>,
    overrides: Option<&Path>,
    texture_dir: Option<&Path>,
    preserve_mtl_textures: Option<&Path>,
    out_dir: &Path,
    physicalize_overrides: &BTreeMap<String, String>,
) -> Result<ConvertOutputs, String> {
    let model = ConverterModel::load(input)?;
    let manifest = manifest.map(MaterialManifest::load).transpose()?;
    let overrides = overrides.map(MaterialOverridePayload::load).transpose()?;
    let request = build_import_request_with_physicalize_overrides(
        &model,
        manifest.as_ref(),
        physicalize_overrides,
    );
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
    let material_diagnostics = write_mtl(
        &model,
        &request,
        overrides.as_ref(),
        texture_dir,
        preserve_mtl_textures,
        &mtl_path,
    )?;
    Ok(ConvertOutputs {
        request: request_path,
        mtl: mtl_path,
        material_diagnostics,
    })
}
