use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    process::Command,
    sync::{
        atomic::{AtomicBool, AtomicUsize, Ordering},
        mpsc::{self, Receiver},
        Arc,
    },
    thread,
};

use converter::{
    convert::ConvertOutputs,
    diagnostic::Diagnostic as ConverterDiagnostic,
    index_assigner::{assign_sub_indices, inputs_from_model, Assignment},
    model::ConverterModel,
    slot_table::{build_expanded_slot_table, MaterialSlot},
};
use eframe::egui::ColorImage;
use texproc::{
    decode_image, process_scan_parallel, BatchProcessReport, ScanResult, SuffixTable,
    TextureSettings,
};

pub enum ScanEvent {
    Completed {
        scan: ScanResult,
        input_files: Vec<PathBuf>,
    },
    Failed(String),
}

pub fn start_scan(roots: Vec<PathBuf>) -> Receiver<ScanEvent> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let suffixes = match SuffixTable::embedded() {
            Ok(value) => value,
            Err(error) => {
                let _ = sender.send(ScanEvent::Failed(error.to_string()));
                return;
            }
        };
        match texproc::scan_inputs(&roots, &suffixes) {
            Ok(scan) => {
                let input_files = scan_input_files(&scan);
                let _ = sender.send(ScanEvent::Completed { scan, input_files });
            }
            Err(error) => {
                let _ = sender.send(ScanEvent::Failed(error.to_string()));
            }
        }
    });
    receiver
}

fn scan_input_files(scan: &ScanResult) -> Vec<PathBuf> {
    let mut seen = BTreeMap::new();
    for entry in scan
        .groups
        .iter()
        .flat_map(|group| group.slots.values().chain(group.unknown.iter()))
    {
        seen.entry(entry.path.to_lowercase())
            .or_insert_with(|| PathBuf::from(&entry.path));
    }
    seen.into_values().collect()
}

pub struct PreviewImage {
    pub path: PathBuf,
    pub width: u32,
    pub height: u32,
    pub color: ColorImage,
}

pub enum PreviewEvent {
    Completed(PreviewImage),
    Failed { path: PathBuf, error: String },
}

pub fn start_preview(path: PathBuf) -> Receiver<PreviewEvent> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let result = (|| {
            let original = decode_image(&path).map_err(|error| error.to_string())?;
            let width = original.width;
            let height = original.height;
            let maximum = width.max(height);
            let preview = if maximum > 720 {
                texproc::ops::resize(&original, 720).map_err(|error| error.to_string())?
            } else {
                original
            };
            let rgba = planar_rgba(&preview);
            Ok(PreviewImage {
                path: path.clone(),
                width,
                height,
                color: ColorImage::from_rgba_unmultiplied(
                    [preview.width as usize, preview.height as usize],
                    &rgba,
                ),
            })
        })();
        let event = match result {
            Ok(image) => PreviewEvent::Completed(image),
            Err(error) => PreviewEvent::Failed {
                path: path.clone(),
                error,
            },
        };
        let _ = sender.send(event);
    });
    receiver
}

fn planar_rgba(image: &texproc::PlanarImage) -> Vec<u8> {
    let mut rgba = Vec::with_capacity(image.pixel_count() * 4);
    for index in 0..image.pixel_count() {
        let sample = |channel: usize| {
            let source = if image.channels() == 1 {
                0
            } else {
                channel.min(image.channels() - 1)
            };
            (image.planes[source][index].clamp(0.0, 1.0) * 255.0).round() as u8
        };
        rgba.extend_from_slice(&[
            sample(0),
            sample(1),
            sample(2),
            if image.channels() == 2 || image.channels() == 4 {
                sample(image.channels() - 1)
            } else {
                255
            },
        ]);
    }
    rgba
}

pub enum ProcessEvent {
    Progress {
        completed: usize,
        total: usize,
        group: String,
        written: usize,
    },
    DdsProgress {
        completed: usize,
        total: usize,
        name: String,
    },
    Finished(Result<ProcessComplete, String>),
}

pub struct ProcessComplete {
    pub report: BatchProcessReport,
    pub dds: Option<DdsSummary>,
}

/// Outcome of the optional RC → DDS pass that runs after the TIFFs are written.
pub struct DdsSummary {
    pub total: usize,
    pub succeeded: usize,
    /// One `"<file>: <error>"` line per failed conversion (batch is not aborted).
    pub failures: Vec<String>,
}

pub struct ProcessJob {
    pub receiver: Receiver<ProcessEvent>,
    pub cancel: Arc<AtomicBool>,
}

pub fn start_process(
    scan: ScanResult,
    settings: TextureSettings,
    output_root: PathBuf,
    rc_exe: Option<PathBuf>,
) -> ProcessJob {
    let (sender, receiver) = mpsc::channel();
    let cancel = Arc::new(AtomicBool::new(false));
    let worker_cancel = Arc::clone(&cancel);
    thread::spawn(move || {
        let total = scan.groups.len();
        let completed = AtomicUsize::new(0);
        let report =
            process_scan_parallel(&scan, &settings, &output_root, &worker_cancel, |group| {
                let current = completed.fetch_add(1, Ordering::Relaxed) + 1;
                let _ = sender.send(ProcessEvent::Progress {
                    completed: current,
                    total,
                    group: group.base_name.clone(),
                    written: group.written.len(),
                });
            })
            .map_err(|error| error.to_string());
        let complete = report.map(|report| {
            let dds = match &rc_exe {
                Some(rc_exe) if !report.cancelled => {
                    Some(run_dds_pass(rc_exe, &report, &output_root, &sender))
                }
                _ => None,
            };
            ProcessComplete { report, dds }
        });
        let _ = sender.send(ProcessEvent::Finished(complete));
    });
    ProcessJob { receiver, cancel }
}

/// Collect the TIFF outputs from a batch report — one RC → DDS job each.
pub fn dds_jobs(report: &BatchProcessReport) -> Vec<PathBuf> {
    report
        .groups
        .iter()
        .flat_map(|group| group.written.iter())
        .filter(|path| {
            path.extension()
                .and_then(|ext| ext.to_str())
                .is_some_and(|ext| ext.eq_ignore_ascii_case("tif"))
        })
        .cloned()
        .collect()
}

/// Feed each produced TIFF to RC.exe sequentially: `RC.exe <tif> /refresh
/// /userdialog=0`, cwd = output dir. Per-file failures are collected, never
/// aborting the batch. DDS files land next to the TIFFs.
fn run_dds_pass(
    rc_exe: &Path,
    report: &BatchProcessReport,
    output_root: &Path,
    sender: &mpsc::Sender<ProcessEvent>,
) -> DdsSummary {
    let jobs = dds_jobs(report);
    let total = jobs.len();
    let mut succeeded = 0;
    let mut failures = Vec::new();
    for (index, tif) in jobs.iter().enumerate() {
        let name = tif
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or_default()
            .to_owned();
        let _ = sender.send(ProcessEvent::DdsProgress {
            completed: index + 1,
            total,
            name: name.clone(),
        });
        match run_rc_dds(rc_exe, tif, output_root) {
            Ok(()) => succeeded += 1,
            Err(error) => failures.push(format!("{name}: {error}")),
        }
    }
    DdsSummary {
        total,
        succeeded,
        failures,
    }
}

fn run_rc_dds(rc_exe: &Path, tif: &Path, output_root: &Path) -> Result<(), String> {
    let mut command = Command::new(rc_exe);
    command
        .arg(tif)
        .arg("/refresh")
        .arg("/userdialog=0")
        .current_dir(output_root);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    let output = command
        .output()
        .map_err(|error| format!("failed to start {}: {error}", rc_exe.display()))?;
    let dds = tif.with_extension("dds");
    if output.status.success() && dds.is_file() {
        return Ok(());
    }
    let return_code = output.status.code().unwrap_or(-1);
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_owned();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_owned();
    let detail = if !stderr.is_empty() { stderr } else { stdout };
    Err(if detail.is_empty() {
        format!("RC exited with {return_code}, DDS was not produced")
    } else {
        format!("RC exited with {return_code}: {detail}")
    })
}

pub struct ModelReview {
    pub path: PathBuf,
    pub model: ConverterModel,
    pub assignments: Vec<Assignment>,
    pub material_slots: Vec<MaterialSlot>,
    pub diagnostics: Vec<ConverterDiagnostic>,
}

pub enum ModelEvent {
    Completed(Box<ModelReview>),
    Failed(String),
}

pub fn start_model_load(path: PathBuf) -> Receiver<ModelEvent> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || match ConverterModel::load(&path) {
        Ok(model) => {
            let inputs = inputs_from_model(&model);
            let (assignments, diagnostics) = assign_sub_indices(&inputs, &[]);
            let material_slots = build_expanded_slot_table(&assignments, true, true, true);
            let _ = sender.send(ModelEvent::Completed(Box::new(ModelReview {
                path,
                model,
                assignments,
                material_slots,
                diagnostics,
            })));
        }
        Err(error) => {
            let _ = sender.send(ModelEvent::Failed(error));
        }
    });
    receiver
}

pub enum ModelExportEvent {
    Stage(String),
    Completed(ModelExportReport),
    Failed(String),
}

pub struct ModelExportReport {
    pub outputs: ConvertOutputs,
    pub rc: RcExportOutcome,
}

pub enum RcExportOutcome {
    NotConfigured,
    Succeeded {
        cgf: PathBuf,
        return_code: i32,
    },
    Failed {
        error: String,
        return_code: Option<i32>,
    },
}

pub fn start_model_export(
    input: PathBuf,
    manifest: Option<PathBuf>,
    overrides: Option<PathBuf>,
    texture_dir: Option<PathBuf>,
    output_dir: PathBuf,
    physicalize_overrides: BTreeMap<String, String>,
    rc_exe: Option<PathBuf>,
) -> Receiver<ModelExportEvent> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        let _ = sender.send(ModelExportEvent::Stage(
            "Converting materials (.mtl + request)…".to_owned(),
        ));
        let result = converter::convert_file_with_physicalize(
            &input,
            existing_optional(&manifest),
            existing_optional(&overrides),
            texture_dir.as_deref(),
            None,
            &output_dir,
            &physicalize_overrides,
        );
        let event = match result {
            Ok(outputs) => {
                let rc = match rc_exe {
                    Some(rc_exe) => {
                        let _ = sender.send(ModelExportEvent::Stage(
                            "Running Resource Compiler (CGF)…".to_owned(),
                        ));
                        run_resource_compiler(&rc_exe, &input, &outputs, &output_dir)
                    }
                    None => RcExportOutcome::NotConfigured,
                };
                ModelExportEvent::Completed(ModelExportReport { outputs, rc })
            }
            Err(error) => ModelExportEvent::Failed(error),
        };
        let _ = sender.send(event);
    });
    receiver
}

fn run_resource_compiler(
    rc_exe: &Path,
    input: &Path,
    outputs: &ConvertOutputs,
    output_dir: &Path,
) -> RcExportOutcome {
    let request = match fs::read_to_string(&outputs.request)
        .map_err(|error| error.to_string())
        .and_then(|text| {
            serde_json::from_str::<converter::request::ImportRequest>(&text)
                .map_err(|error| error.to_string())
        }) {
        Ok(request) => request,
        Err(error) => {
            return RcExportOutcome::Failed {
                error: format!("failed to read generated request: {error}"),
                return_code: None,
            };
        }
    };
    let cgf = outputs
        .request
        .with_extension(request.output_ext.trim_start_matches('.'));
    if cgf.is_file() {
        if let Err(error) = fs::remove_file(&cgf) {
            return RcExportOutcome::Failed {
                error: format!("failed to replace {}: {error}", cgf.display()),
                return_code: None,
            };
        }
    }
    let Some(cgf_name) = cgf.file_name() else {
        return RcExportOutcome::Failed {
            error: format!("could not derive CGF name from {}", cgf.display()),
            return_code: None,
        };
    };

    let mut command = Command::new(rc_exe);
    command
        .arg(&outputs.request)
        .arg("/overwriteextension=fbx")
        .arg(format!("/overwritesourcefile={}", input.display()))
        .arg(format!("/overwritefilename={}", cgf_name.to_string_lossy()))
        .current_dir(output_dir);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    let output = match command.output() {
        Ok(output) => output,
        Err(error) => {
            return RcExportOutcome::Failed {
                error: format!("failed to start {}: {error}", rc_exe.display()),
                return_code: None,
            };
        }
    };
    let return_code = output.status.code().unwrap_or(-1);
    if output.status.success() && cgf.is_file() {
        RcExportOutcome::Succeeded { cgf, return_code }
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_owned();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_owned();
        let detail = if !stderr.is_empty() { stderr } else { stdout };
        RcExportOutcome::Failed {
            error: if detail.is_empty() {
                format!("RC exited with {return_code}, CGF was not produced")
            } else {
                format!("RC exited with {return_code}: {detail}")
            },
            return_code: Some(return_code),
        }
    }
}

fn existing_optional(path: &Option<PathBuf>) -> Option<&Path> {
    path.as_deref()
        .filter(|path| !path.as_os_str().is_empty() && path.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;
    use texproc::batch::ProcessedGroup;

    fn report(written: Vec<&str>) -> BatchProcessReport {
        BatchProcessReport {
            groups: vec![ProcessedGroup {
                base_name: "Group".to_owned(),
                written: written.into_iter().map(PathBuf::from).collect(),
                elapsed_seconds: 0.0,
            }],
            cancelled: false,
            elapsed_seconds: 0.0,
            rayon_threads: 1,
        }
    }

    #[test]
    fn dds_jobs_selects_only_tiff_outputs() {
        let report = report(vec![
            r"C:\out\Stone_diff.tif",
            r"C:\out\Stone_ddna.TIF",
            r"C:\out\Stone_diff.dds",
            r"C:\out\notes.txt",
        ]);
        let jobs = dds_jobs(&report);
        assert_eq!(jobs.len(), 2);
        assert!(jobs.iter().all(|path| path
            .extension()
            .and_then(|ext| ext.to_str())
            .is_some_and(|ext| ext.eq_ignore_ascii_case("tif"))));
    }

    /// Real end-to-end check of the GUI's DDS pipeline: process the repo texture
    /// fixtures and run each TIFF through a real RC. Ignored by default (needs
    /// RC on disk); run with:
    ///   set CE_RC_EXE=...\rc.exe && cargo test -p texproc-gui -- --ignored dds_pass
    #[test]
    #[ignore = "requires a real RC.exe (CE_RC_EXE or the default S: path)"]
    fn dds_pass_produces_dds_next_to_tiffs() {
        use std::time::{SystemTime, UNIX_EPOCH};

        let rc = std::env::var_os("CE_RC_EXE")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe")
            });
        assert!(rc.is_file(), "RC not found at {}", rc.display());

        let fixtures = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("fixtures")
            .join("textures");
        let suffixes = SuffixTable::embedded().unwrap();
        let scan = texproc::scan_inputs(&[fixtures], &suffixes).unwrap();
        assert!(!scan.groups.is_empty());

        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let out =
            std::env::temp_dir().join(format!("texproc-gui-dds-{}-{nonce}", std::process::id()));
        fs::create_dir_all(&out).unwrap();

        let job = start_process(scan, TextureSettings::default(), out.clone(), Some(rc));
        let mut complete = None;
        let mut dds_progress = 0;
        while let Ok(event) = job.receiver.recv() {
            match event {
                ProcessEvent::DdsProgress { completed, .. } => {
                    dds_progress = dds_progress.max(completed)
                }
                ProcessEvent::Finished(result) => {
                    complete = Some(result.expect("processing succeeded"));
                    break;
                }
                ProcessEvent::Progress { .. } => {}
            }
        }
        let complete = complete.expect("worker finished");
        let dds = complete.dds.expect("DDS pass ran");
        let tifs = dds_jobs(&complete.report);
        assert!(!tifs.is_empty());
        assert_eq!(dds.total, tifs.len());
        assert!(dds_progress >= 1);
        assert_eq!(dds.succeeded, dds.total, "failures: {:?}", dds.failures);
        for tif in &tifs {
            assert!(
                tif.with_extension("dds").is_file(),
                "missing dds for {}",
                tif.display()
            );
        }
        fs::remove_dir_all(&out).ok();
    }
}
