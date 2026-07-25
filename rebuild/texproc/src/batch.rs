use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
    sync::atomic::{AtomicBool, Ordering},
    time::Instant,
};

use rayon::prelude::*;

use crate::{
    decode_image, process_stage1, process_stage2, write_stage2_outputs, OutputTextures, Result,
    ScanEntry, ScanGroup, ScanResult, SourceImage, SourceTextures, TexprocError, TextureGroup,
    TextureSettings,
};

#[derive(Clone, Debug)]
pub struct ProcessedGroup {
    pub base_name: String,
    pub written: Vec<PathBuf>,
    pub elapsed_seconds: f64,
}

#[derive(Clone, Debug)]
pub struct BatchProcessReport {
    pub groups: Vec<ProcessedGroup>,
    pub cancelled: bool,
    pub elapsed_seconds: f64,
    pub rayon_threads: usize,
}

pub fn process_scan_parallel(
    scan: &ScanResult,
    settings: &TextureSettings,
    output_root: &Path,
    cancel: &AtomicBool,
    on_group: impl Fn(&ProcessedGroup) + Send + Sync,
) -> Result<BatchProcessReport> {
    let started = Instant::now();
    let results = scan
        .groups
        .par_iter()
        .map(|group| {
            if cancel.load(Ordering::Relaxed) {
                return Ok(None);
            }
            let processed = process_scan_group(group, settings, output_root)?;
            on_group(&processed);
            Ok(Some(processed))
        })
        .collect::<Vec<Result<Option<ProcessedGroup>>>>();

    let mut groups = Vec::new();
    for result in results {
        if let Some(group) = result? {
            groups.push(group);
        }
    }
    Ok(BatchProcessReport {
        groups,
        cancelled: cancel.load(Ordering::Relaxed),
        elapsed_seconds: started.elapsed().as_secs_f64(),
        rayon_threads: rayon::current_num_threads(),
    })
}

pub fn process_scan_group(
    scan_group: &ScanGroup,
    settings: &TextureSettings,
    output_root: &Path,
) -> Result<ProcessedGroup> {
    let started = Instant::now();
    let sources = load_sources(&scan_group.slots, settings)?;
    let mut group = TextureGroup {
        base_name: scan_group.base_name.clone(),
        sources,
        intermediate: Default::default(),
        output: OutputTextures::default(),
    };
    process_stage1(&mut group, &settings.intermediate_settings())?;
    process_stage2(&mut group, settings)?;
    let written = write_stage2_outputs(&group.output, output_root)?;
    Ok(ProcessedGroup {
        base_name: scan_group.base_name.clone(),
        written,
        elapsed_seconds: started.elapsed().as_secs_f64(),
    })
}

fn load_sources(
    slots: &BTreeMap<String, ScanEntry>,
    settings: &TextureSettings,
) -> Result<SourceTextures> {
    let mut sources = SourceTextures::default();
    for (source_type, entry) in slots {
        if !source_is_required(source_type, settings) {
            continue;
        }
        let source = SourceImage::new(&entry.filename, decode_image(&entry.path)?);
        match source_type.as_str() {
            "diffuse" => sources.diffuse = Some(source),
            "normal" => sources.normal = Some(source),
            "specular" => sources.specular = Some(source),
            "glossiness" => sources.glossiness = Some(source),
            "roughness" => sources.roughness = Some(source),
            "displacement" => sources.displacement = Some(source),
            "metallic" => sources.metallic = Some(source),
            "ao" => sources.ao = Some(source),
            "alpha" => sources.alpha = Some(source),
            "emissive" => sources.emissive = Some(source),
            "sss" => sources.sss = Some(source),
            "arm" => sources.arm = Some(source),
            other => {
                return Err(TexprocError::new(format!(
                    "groups JSON contains unsupported source type `{other}`"
                )));
            }
        }
    }
    Ok(sources)
}

fn source_is_required(source_type: &str, settings: &TextureSettings) -> bool {
    let types = settings.texture_types;
    match source_type {
        "diffuse" => {
            types.diff
                || types.spec
                || (types.emissive && settings.generate_missing_emissive)
                || (types.sss
                    && (settings.generate_sss_from_diffuse || settings.generate_missing_sss))
        }
        "normal" | "glossiness" | "roughness" => types.ddna,
        "specular" | "metallic" => types.spec || types.diff,
        "displacement" => types.displ || types.ddna,
        "ao" | "alpha" => types.diff,
        "emissive" => types.emissive,
        "sss" => types.sss,
        "arm" => types.diff || types.spec || types.ddna,
        _ => false,
    }
}
