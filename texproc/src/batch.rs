use std::{
    collections::BTreeMap,
    panic::{catch_unwind, AssertUnwindSafe},
    path::{Path, PathBuf},
    sync::atomic::{AtomicBool, Ordering},
    time::Instant,
};

use rayon::prelude::*;

use crate::{
    decode_image, process_and_write_stage2, process_stage1, OutputTextures, Result, ScanEntry,
    ScanGroup, ScanResult, SourceImage, SourceTextures, TexprocError, TextureGroup,
    TextureSettings,
};

#[derive(Clone, Debug)]
pub struct ProcessedGroup {
    pub base_name: String,
    pub written: Vec<PathBuf>,
    pub elapsed_seconds: f64,
}

/// A group that could not be processed (a Stage 1/2 error or a caught panic).
/// The batch records it and carries on instead of aborting the whole run.
#[derive(Clone, Debug)]
pub struct FailedGroup {
    pub base_name: String,
    pub message: String,
}

#[derive(Clone, Debug)]
pub struct BatchProcessReport {
    pub groups: Vec<ProcessedGroup>,
    pub failed: Vec<FailedGroup>,
    pub cancelled: bool,
    pub elapsed_seconds: f64,
    pub rayon_threads: usize,
    /// Memory admission budget in bytes (50% of physical RAM, or the
    /// `TEXPROC_MEM_BUDGET_MB` override).
    pub memory_budget_bytes: u64,
    /// Number of admission waves the groups were split into.
    pub waves: usize,
}

/// Conservative per-file working-set model for a source image that cannot be
/// probed: a 4096×4096 four-channel float buffer.
const DEFAULT_PIXELS: u64 = 4096 * 4096;
const DEFAULT_CHANNELS: u64 = 4;
const FLOAT_BYTES: u64 = 4;
/// Sources are decoded to planar f32, then intermediates and outputs are
/// derived from them; ×3 covers that live working set beyond the sources alone.
const WORKING_SET_FACTOR: u64 = 3;
/// Non-Windows fallback budget when physical RAM cannot be queried.
const FALLBACK_BUDGET_BYTES: u64 = 8 * 1024 * 1024 * 1024;

pub fn process_scan_parallel(
    scan: &ScanResult,
    settings: &TextureSettings,
    output_root: &Path,
    cancel: &AtomicBool,
    on_group: impl Fn(&ProcessedGroup) + Send + Sync,
) -> Result<BatchProcessReport> {
    let started = Instant::now();
    let budget = memory_budget_bytes();
    let waves = plan_waves(&scan.groups, settings, budget);

    let mut groups = Vec::new();
    let mut failed = Vec::new();
    let mut wave_count = 0;
    for wave in &waves {
        if cancel.load(Ordering::Relaxed) {
            break;
        }
        wave_count += 1;
        // Every group in a wave sums to <= budget, and rayon runs at most
        // `current_num_threads` at once, so the live working set stays bounded.
        let outcomes = wave
            .par_iter()
            .map(|&index| {
                let group = &scan.groups[index];
                if cancel.load(Ordering::Relaxed) {
                    return GroupOutcome::Skipped;
                }
                match catch_unwind(AssertUnwindSafe(|| {
                    process_scan_group(group, settings, output_root)
                })) {
                    Ok(Ok(processed)) => {
                        on_group(&processed);
                        GroupOutcome::Done(processed)
                    }
                    Ok(Err(error)) => {
                        GroupOutcome::Failed(group.base_name.clone(), error.to_string())
                    }
                    Err(panic) => {
                        GroupOutcome::Failed(group.base_name.clone(), panic_message(panic))
                    }
                }
            })
            .collect::<Vec<_>>();
        for outcome in outcomes {
            match outcome {
                GroupOutcome::Done(group) => groups.push(group),
                GroupOutcome::Failed(base_name, message) => {
                    failed.push(FailedGroup { base_name, message })
                }
                GroupOutcome::Skipped => {}
            }
        }
    }

    Ok(BatchProcessReport {
        groups,
        failed,
        cancelled: cancel.load(Ordering::Relaxed),
        elapsed_seconds: started.elapsed().as_secs_f64(),
        rayon_threads: rayon::current_num_threads(),
        memory_budget_bytes: budget,
        waves: wave_count,
    })
}

enum GroupOutcome {
    Done(ProcessedGroup),
    Failed(String, String),
    Skipped,
}

fn panic_message(panic: Box<dyn std::any::Any + Send>) -> String {
    if let Some(message) = panic.downcast_ref::<&str>() {
        (*message).to_owned()
    } else if let Some(message) = panic.downcast_ref::<String>() {
        message.clone()
    } else {
        "panicked".to_owned()
    }
}

pub fn process_scan_group(
    scan_group: &ScanGroup,
    settings: &TextureSettings,
    output_root: &Path,
) -> Result<ProcessedGroup> {
    #[cfg(test)]
    if scan_group.base_name == "__panic_for_test__" {
        panic!("injected test panic");
    }
    let started = Instant::now();
    let sources = load_sources(&scan_group.slots, settings)?;
    let mut group = TextureGroup {
        base_name: scan_group.base_name.clone(),
        sources,
        intermediate: Default::default(),
        output: OutputTextures::default(),
    };
    process_stage1(&mut group, &settings.intermediate_settings())?;
    // Stream each Stage 2 output to disk and drop it, instead of accumulating
    // all six in `group.output` before writing.
    let written = process_and_write_stage2(&group, settings, output_root)?;
    Ok(ProcessedGroup {
        base_name: scan_group.base_name.clone(),
        written,
        elapsed_seconds: started.elapsed().as_secs_f64(),
    })
}

/// Split the groups into admission waves whose per-group memory estimates each
/// sum to at most `budget`. A group larger than the whole budget lands in a
/// wave of its own (it always runs alone). Input order is preserved.
fn plan_waves(groups: &[ScanGroup], settings: &TextureSettings, budget: u64) -> Vec<Vec<usize>> {
    let mut waves = Vec::new();
    let mut current: Vec<usize> = Vec::new();
    let mut current_bytes = 0_u64;
    for (index, group) in groups.iter().enumerate() {
        let estimate = estimate_group_bytes(group, settings);
        if !current.is_empty() && current_bytes.saturating_add(estimate) > budget {
            waves.push(std::mem::take(&mut current));
            current_bytes = 0;
        }
        current.push(index);
        current_bytes = current_bytes.saturating_add(estimate);
    }
    if !current.is_empty() {
        waves.push(current);
    }
    waves
}

/// Estimate the live working set of a group: the sum over its required source
/// files of `width × height × channels × 4 bytes`, scaled by
/// [`WORKING_SET_FACTOR`] to cover intermediates and outputs.
fn estimate_group_bytes(group: &ScanGroup, settings: &TextureSettings) -> u64 {
    let mut bytes = 0_u64;
    for (source_type, entry) in &group.slots {
        if !source_is_required(source_type, settings) {
            continue;
        }
        bytes = bytes.saturating_add(source_file_bytes(entry));
    }
    bytes.saturating_mul(WORKING_SET_FACTOR)
}

/// Decoded planar-f32 size of one source file, from its scan-time header (or a
/// fresh header probe), falling back to a conservative 4K RGBA estimate when the
/// file cannot be probed. No pixel decode happens here.
fn source_file_bytes(entry: &ScanEntry) -> u64 {
    let dimensions = entry
        .header
        .as_ref()
        .map(|header| {
            (
                u64::from(header.width),
                u64::from(header.height),
                u64::from(header.channels),
            )
        })
        .or_else(|| {
            crate::probe_header(&entry.path).ok().map(|header| {
                (
                    u64::from(header.width),
                    u64::from(header.height),
                    u64::from(header.channels),
                )
            })
        });
    match dimensions {
        Some((width, height, channels)) => width
            .saturating_mul(height)
            .saturating_mul(channels.max(1))
            .saturating_mul(FLOAT_BYTES),
        None => DEFAULT_PIXELS
            .saturating_mul(DEFAULT_CHANNELS)
            .saturating_mul(FLOAT_BYTES),
    }
}

fn memory_budget_bytes() -> u64 {
    if let Some(bytes) =
        budget_override_bytes(std::env::var("TEXPROC_MEM_BUDGET_MB").ok().as_deref())
    {
        return bytes;
    }
    physical_memory_bytes()
        .map(|total| total / 2)
        .unwrap_or(FALLBACK_BUDGET_BYTES)
}

/// Parse the `TEXPROC_MEM_BUDGET_MB` override into a byte budget. A missing,
/// empty, non-numeric, or zero value yields `None` (fall back to RAM query).
fn budget_override_bytes(raw: Option<&str>) -> Option<u64> {
    raw.map(str::trim)
        .filter(|value| !value.is_empty())
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|&megabytes| megabytes > 0)
        .map(|megabytes| megabytes.saturating_mul(1024 * 1024))
}

#[cfg(windows)]
fn physical_memory_bytes() -> Option<u64> {
    #[repr(C)]
    struct MemoryStatusEx {
        length: u32,
        memory_load: u32,
        total_phys: u64,
        avail_phys: u64,
        total_page_file: u64,
        avail_page_file: u64,
        total_virtual: u64,
        avail_virtual: u64,
        avail_extended_virtual: u64,
    }
    extern "system" {
        fn GlobalMemoryStatusEx(buffer: *mut MemoryStatusEx) -> i32;
    }
    let mut status: MemoryStatusEx = unsafe { std::mem::zeroed() };
    status.length = std::mem::size_of::<MemoryStatusEx>() as u32;
    // SAFETY: `status` is a correctly sized, zeroed MEMORYSTATUSEX with its
    // length field set, exactly as GlobalMemoryStatusEx requires.
    let ok = unsafe { GlobalMemoryStatusEx(&mut status) };
    (ok != 0 && status.total_phys > 0).then_some(status.total_phys)
}

#[cfg(not(windows))]
fn physical_memory_bytes() -> Option<u64> {
    None
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grouping::HeaderRecord;

    fn entry(source_type: &str, width: u32, height: u32, channels: u8) -> ScanEntry {
        ScanEntry {
            path: format!("{source_type}.png"),
            filename: format!("sample_{source_type}.png"),
            source_type: source_type.to_owned(),
            base_name: "sample".to_owned(),
            header: Some(HeaderRecord {
                channels,
                bit_depth: 8,
                width,
                height,
            }),
            arm_order: None,
        }
    }

    fn group(base: &str, slots: Vec<(&str, ScanEntry)>) -> ScanGroup {
        ScanGroup {
            key: base.to_owned(),
            base_name: base.to_owned(),
            slots: slots
                .into_iter()
                .map(|(name, entry)| (name.to_owned(), entry))
                .collect(),
            unknown: Vec::new(),
            diagnostics: Vec::new(),
        }
    }

    #[test]
    fn estimate_sums_required_sources_times_working_factor() {
        // diffuse 4096×4096×4ch + normal 2048×2048×3ch, ×3.
        let group = group(
            "sample",
            vec![
                ("diffuse", entry("diffuse", 4096, 4096, 4)),
                ("normal", entry("normal", 2048, 2048, 3)),
            ],
        );
        let diffuse = 4096u64 * 4096 * 4 * FLOAT_BYTES;
        let normal = 2048u64 * 2048 * 3 * FLOAT_BYTES;
        let expected = (diffuse + normal) * WORKING_SET_FACTOR;
        assert_eq!(
            estimate_group_bytes(&group, &TextureSettings::default()),
            expected
        );
    }

    #[test]
    fn estimate_falls_back_to_4k_rgba_when_header_missing_and_probe_fails() {
        let mut only = entry("diffuse", 1, 1, 1);
        only.header = None; // path "diffuse.png" does not exist -> probe fails
        let group = group("sample", vec![("diffuse", only)]);
        let expected = DEFAULT_PIXELS * DEFAULT_CHANNELS * FLOAT_BYTES * WORKING_SET_FACTOR;
        assert_eq!(
            estimate_group_bytes(&group, &TextureSettings::default()),
            expected
        );
    }

    #[test]
    fn waves_pack_up_to_budget_and_oversize_group_runs_alone() {
        let settings = TextureSettings::default();
        // Each group: one 1024×1024×4 source -> 1024*1024*4*4*3 bytes.
        let per_group = 1024u64 * 1024 * 4 * FLOAT_BYTES * WORKING_SET_FACTOR;
        let groups: Vec<ScanGroup> = (0..5)
            .map(|i| {
                group(
                    &format!("g{i}"),
                    vec![("diffuse", entry("diffuse", 1024, 1024, 4))],
                )
            })
            .collect();
        // Budget for exactly two groups per wave.
        let waves = plan_waves(&groups, &settings, per_group * 2);
        assert_eq!(waves, vec![vec![0, 1], vec![2, 3], vec![4]]);

        // A single group larger than the whole budget still runs, alone.
        let waves = plan_waves(&groups, &settings, per_group / 2);
        assert_eq!(waves, vec![vec![0], vec![1], vec![2], vec![3], vec![4]]);
    }

    #[test]
    fn budget_override_parsing_rejects_junk_and_zero() {
        assert_eq!(budget_override_bytes(None), None);
        assert_eq!(budget_override_bytes(Some("")), None);
        assert_eq!(budget_override_bytes(Some("  ")), None);
        assert_eq!(budget_override_bytes(Some("nope")), None);
        assert_eq!(budget_override_bytes(Some("0")), None);
        assert_eq!(
            budget_override_bytes(Some(" 2048 ")),
            Some(2048 * 1024 * 1024)
        );
    }

    #[test]
    fn a_panicking_group_is_recorded_as_failed_and_the_batch_continues() {
        // Two groups: the first decodes a nonexistent file (Err), the second is
        // empty (produces only a fallback spec). Neither aborts the batch, and
        // both outcomes are reported.
        let output = std::env::temp_dir().join(format!(
            "texproc-batch-fail-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let bad = group(
            "broken",
            vec![("diffuse", entry("does-not-exist", 8, 8, 3))],
        );
        let mut panicking = group("__panic_for_test__", Vec::new());
        panicking.key = "boom".to_owned();
        let ok = ScanGroup {
            key: "empty".to_owned(),
            base_name: "empty".to_owned(),
            slots: BTreeMap::new(),
            unknown: Vec::new(),
            diagnostics: Vec::new(),
        };
        let scan = ScanResult {
            version: 1,
            groups: vec![bad, panicking, ok],
            diagnostics: Vec::new(),
        };
        let cancel = AtomicBool::new(false);
        let report =
            process_scan_parallel(&scan, &TextureSettings::default(), &output, &cancel, |_| {})
                .expect("batch itself does not error");
        // Both the erroring group and the panicking group are recorded; the
        // clean group still completes.
        assert_eq!(report.failed.len(), 2);
        assert!(report.failed.iter().any(|f| f.base_name == "broken"));
        let panicked = report
            .failed
            .iter()
            .find(|f| f.base_name == "__panic_for_test__")
            .expect("panicking group recorded");
        assert!(panicked.message.contains("injected test panic"));
        assert_eq!(report.groups.len(), 1);
        assert_eq!(report.groups[0].base_name, "empty");
        let _ = std::fs::remove_dir_all(&output);
    }
}
