pub mod diagnostic;
pub mod dump;
pub mod index_assigner;
pub mod manifest;
pub mod model;
pub mod rc_policy;
pub mod report;
pub mod slot_contract;
pub mod slot_table;

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
