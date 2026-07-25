pub mod convert;
pub mod diagnostic;
pub mod dump;
pub mod index_assigner;
pub mod manifest;
pub mod model;
pub mod mtl;
pub mod rc_policy;
pub mod report;
pub mod request;
pub mod slot_contract;
pub mod slot_table;
pub mod texture_resolver;

use std::path::Path;

pub fn dump_file(input: &Path, out: &Path) -> Result<(), String> {
    let model = model::ConverterModel::load(input)?;
    dump::write_dump(&model, out)
}

pub fn report_file(input: &Path, manifest: Option<&Path>, out: &Path) -> Result<(), String> {
    let model = model::ConverterModel::load(input)?;
    let manifest = manifest.map(manifest::MaterialManifest::load).transpose()?;
    report::write_report(&model, manifest.as_ref(), out)
}

pub fn convert_file(
    input: &Path,
    manifest: Option<&Path>,
    overrides: Option<&Path>,
    texture_dir: Option<&Path>,
    preserve_mtl_textures: Option<&Path>,
    out_dir: &Path,
) -> Result<convert::ConvertOutputs, String> {
    convert::convert_file(
        input,
        manifest,
        overrides,
        texture_dir,
        preserve_mtl_textures,
        out_dir,
    )
}

pub fn validate_file(input: &Path, out: &Path) -> Result<bool, String> {
    request::validate_file(input, out)
}
