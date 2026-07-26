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
    delete_tif: bool,
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
                    let tifs = dds_jobs(&report);
                    Some(run_dds_pass(
                        rc_exe,
                        &tifs,
                        &output_root,
                        delete_tif,
                        Some(&sender),
                    ))
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
/// aborting the batch. DDS files land next to the TIFFs. When `delete_tif` is
/// set, each source TIFF is removed only after its DDS is produced; a failed
/// conversion keeps its TIFF (and its diagnostic). `sender` is optional so the
/// model-export flow (no per-file progress bar) can reuse the same pass.
fn run_dds_pass(
    rc_exe: &Path,
    jobs: &[PathBuf],
    output_root: &Path,
    delete_tif: bool,
    sender: Option<&mpsc::Sender<ProcessEvent>>,
) -> DdsSummary {
    let total = jobs.len();
    let mut succeeded = 0;
    let mut failures = Vec::new();
    for (index, tif) in jobs.iter().enumerate() {
        let name = tif
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or_default()
            .to_owned();
        if let Some(sender) = sender {
            let _ = sender.send(ProcessEvent::DdsProgress {
                completed: index + 1,
                total,
                name: name.clone(),
            });
        }
        match run_rc_dds(rc_exe, tif, output_root) {
            Ok(()) => {
                succeeded += 1;
                if delete_tif {
                    let _ = fs::remove_file(tif);
                }
            }
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
    /// Present only when "Export associated textures with model" ran.
    pub textures: Option<AssociatedTexturesReport>,
}

/// Stage (a)+(d) of the "Export associated textures with model" flow: the
/// FBX-ingested texture groups processed into the texture output directory, and
/// the optional DDS pass over the resulting TIFFs.
pub struct AssociatedTextures {
    pub scan: ScanResult,
    pub settings: TextureSettings,
    pub output_dir: PathBuf,
    pub generate_dds: bool,
    pub delete_tif: bool,
}

pub struct AssociatedTexturesReport {
    pub groups: usize,
    pub written: usize,
    pub dds: Option<DdsSummary>,
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

// ponytail: export request has many independently-sourced fields; a params
// struct would be churn for one worker entry point.
#[allow(clippy::too_many_arguments)]
pub fn start_model_export(
    input: PathBuf,
    manifest: Option<PathBuf>,
    overrides: Option<PathBuf>,
    texture_dir: Option<PathBuf>,
    output_dir: PathBuf,
    physicalize_overrides: BTreeMap<String, String>,
    rc_exe: Option<PathBuf>,
    associated: Option<AssociatedTextures>,
) -> Receiver<ModelExportEvent> {
    let (sender, receiver) = mpsc::channel();
    thread::spawn(move || {
        // Stage (a): process the FBX-ingested texture groups into the texture
        // output directory so the MTL below resolves against fresh outputs.
        let textures = match associated.as_ref() {
            Some(assoc) => {
                let _ = sender.send(ModelExportEvent::Stage(format!(
                    "Processing {} associated texture groups…",
                    assoc.scan.groups.len()
                )));
                let cancel = AtomicBool::new(false);
                match process_scan_parallel(
                    &assoc.scan,
                    &assoc.settings,
                    &assoc.output_dir,
                    &cancel,
                    |_| {},
                ) {
                    Ok(report) => Some(report),
                    Err(error) => {
                        let _ = sender.send(ModelExportEvent::Failed(format!(
                            "associated texture processing failed: {error}"
                        )));
                        return;
                    }
                }
            }
            None => None,
        };

        // Stage (b): convert (.mtl + request), pointing texture resolution at
        // the texture output directory when associated textures were processed.
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
        let outputs = match result {
            Ok(outputs) => outputs,
            Err(error) => {
                let _ = sender.send(ModelExportEvent::Failed(error));
                return;
            }
        };

        // Stage (c): RC → CGF.
        let rc = match &rc_exe {
            Some(rc_exe) => {
                let _ = sender.send(ModelExportEvent::Stage(
                    "Running Resource Compiler (CGF)…".to_owned(),
                ));
                run_resource_compiler(rc_exe, &input, &outputs, &output_dir)
            }
            None => RcExportOutcome::NotConfigured,
        };

        // Stage (d): optional TIF → DDS over the associated texture outputs.
        let textures = textures.map(|report| {
            let written = report.groups.iter().map(|group| group.written.len()).sum();
            let assoc = associated.as_ref().expect("report implies associated set");
            let dds = match (&rc_exe, assoc.generate_dds) {
                (Some(rc_exe), true) => {
                    let _ = sender.send(ModelExportEvent::Stage(
                        "Compiling associated DDS via RC…".to_owned(),
                    ));
                    let tifs = dds_jobs(&report);
                    Some(run_dds_pass(
                        rc_exe,
                        &tifs,
                        &assoc.output_dir,
                        assoc.delete_tif,
                        None,
                    ))
                }
                _ => None,
            };
            AssociatedTexturesReport {
                groups: report.groups.len(),
                written,
                dds,
            }
        });

        let _ = sender.send(ModelExportEvent::Completed(ModelExportReport {
            outputs,
            rc,
            textures,
        }));
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

    /// End-to-end evidence for item 4 (Export associated textures with model):
    /// process the PropAxe FBX's referenced texture groups into a texture output
    /// dir, convert with texture_dir pointing there, RC → CGF, then DDS with
    /// delete-tif. Ignored by default (needs Z: fixtures + RC); run with:
    ///   set CE_RC_EXE=...\rc.exe && cargo test -p texproc-gui -- --ignored --nocapture export_with_associated
    #[test]
    #[ignore = "requires the PropAxe referenced textures (Z:) and a real RC.exe"]
    fn export_with_associated_textures_produces_cgf_and_dds() {
        use std::time::{SystemTime, UNIX_EPOCH};

        let rc = std::env::var_os("CE_RC_EXE")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe")
            });
        assert!(rc.is_file(), "RC not found at {}", rc.display());

        let fbx = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("fixtures")
            .join("KB3D_ENC_PropAxe_A_grp.fbx");
        assert!(fbx.is_file(), "fixture missing: {}", fbx.display());

        // Collect the FBX's referenced textures that exist on disk (mirrors the
        // GUI's ingest), then scan them into the associated texture groups.
        let model = ConverterModel::load(&fbx).unwrap();
        let model_dir = fbx.parent().unwrap();
        let mut referenced = Vec::new();
        for texture in model
            .materials
            .iter()
            .flat_map(|material| material.textures.iter())
        {
            if let Some(path) = [
                PathBuf::from(&texture.absolute_filename),
                model_dir.join(&texture.relative_filename),
                model_dir.join(&texture.filename),
            ]
            .into_iter()
            .find(|path| path.is_file())
            {
                referenced.push(path);
            }
        }
        assert!(!referenced.is_empty(), "no referenced textures resolved");
        let suffixes = SuffixTable::embedded().unwrap();
        let scan = texproc::scan_inputs(&referenced, &suffixes).unwrap();
        assert!(!scan.groups.is_empty());

        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("texproc-gui-assoc-{}-{nonce}", std::process::id()));
        let tex_out = root.join("textures");
        let model_out = root.join("model");
        fs::create_dir_all(&tex_out).unwrap();
        fs::create_dir_all(&model_out).unwrap();

        let associated = AssociatedTextures {
            scan,
            settings: TextureSettings::default(),
            output_dir: tex_out.clone(),
            generate_dds: true,
            delete_tif: true,
        };
        let receiver = start_model_export(
            fbx.clone(),
            None,
            None,
            Some(tex_out.clone()),
            model_out.clone(),
            BTreeMap::new(),
            Some(rc),
            Some(associated),
        );

        let mut report = None;
        while let Ok(event) = receiver.recv() {
            match event {
                ModelExportEvent::Stage(stage) => eprintln!("stage: {stage}"),
                ModelExportEvent::Completed(value) => {
                    report = Some(value);
                    break;
                }
                ModelExportEvent::Failed(error) => panic!("export failed: {error}"),
            }
        }
        let report = report.expect("export completed");

        // Stage (c): CGF produced.
        match &report.rc {
            RcExportOutcome::Succeeded { cgf, .. } => {
                assert!(cgf.is_file(), "CGF missing: {}", cgf.display());
                eprintln!(
                    "CGF: {} ({} bytes)",
                    cgf.display(),
                    fs::metadata(cgf).unwrap().len()
                );
            }
            other => panic!("RC did not succeed: {:?}", rc_label(other)),
        }
        // Stage (b): MTL exists and references texture files.
        let mtl = fs::read_to_string(&report.outputs.mtl).unwrap();
        assert!(mtl.contains("Texture "), "MTL has no texture references");
        eprintln!("MTL: {}", report.outputs.mtl.display());
        // Stage (a)+(d): associated textures processed; DDS present, TIFs gone.
        let textures = report.textures.expect("associated textures ran");
        let dds = textures.dds.expect("DDS pass ran");
        eprintln!(
            "associated: {} groups, {} files, DDS {}/{}",
            textures.groups, textures.written, dds.succeeded, dds.total
        );
        assert_eq!(dds.succeeded, dds.total, "DDS failures: {:?}", dds.failures);
        let produced = fs::read_dir(&tex_out).unwrap().filter_map(|e| e.ok());
        let (mut dds_count, mut tif_count) = (0, 0);
        for entry in produced {
            match entry
                .path()
                .extension()
                .and_then(|ext| ext.to_str())
                .map(str::to_ascii_lowercase)
                .as_deref()
            {
                Some("dds") => dds_count += 1,
                Some("tif") => tif_count += 1,
                _ => {}
            }
        }
        eprintln!("output dir: {dds_count} .dds, {tif_count} .tif remaining");
        assert!(dds_count > 0, "no DDS produced");
        assert_eq!(
            tif_count, 0,
            "delete-tif should have removed every source TIF"
        );

        fs::remove_dir_all(&root).ok();
    }

    fn rc_label(outcome: &RcExportOutcome) -> String {
        match outcome {
            RcExportOutcome::NotConfigured => "not configured".to_owned(),
            RcExportOutcome::Succeeded { return_code, .. } => format!("ok ({return_code})"),
            RcExportOutcome::Failed { error, .. } => format!("failed: {error}"),
        }
    }

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

        let job = start_process(
            scan,
            TextureSettings::default(),
            out.clone(),
            Some(rc),
            false,
        );
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
