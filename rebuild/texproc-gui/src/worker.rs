use std::{
    collections::BTreeMap,
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicUsize, Ordering},
        mpsc::{self, Receiver},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

use converter::{
    convert::ConvertOutputs,
    diagnostic::Diagnostic as ConverterDiagnostic,
    index_assigner::{assign_sub_indices, inputs_from_model, Assignment},
    model::ConverterModel,
    request::ConversionOverrides,
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
    /// The adaptive RC pool changed its target concurrency. `from == 0` is the
    /// initial target; later events carry the previous → new trajectory.
    DdsWorkers {
        from: usize,
        to: usize,
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
    /// Target-concurrency trajectory of the adaptive RC pool: the initial value
    /// followed by every adjustment. Length 1 means the pool never adjusted.
    pub n_trajectory: Vec<usize>,
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
                    Some(run_dds_pool(
                        rc_exe,
                        &tifs,
                        &output_root,
                        delete_tif,
                        &worker_cancel,
                        |completed, total, name| {
                            let _ = sender.send(ProcessEvent::DdsProgress {
                                completed,
                                total,
                                name: name.to_owned(),
                            });
                        },
                        |from, to| {
                            let _ = sender.send(ProcessEvent::DdsWorkers { from, to });
                        },
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

/// Measured RC internal thread count (reviewer's R7 baseline: one RC instance
/// is ~6-threaded at 4K). The initial external concurrency divides logical
/// cores by this so we don't oversubscribe. Constant, not configurable.
const RC_INTERNAL_THREADS: usize = 6;
/// Default ceiling on external RC concurrency; `TEXPROC_RC_MAX` overrides.
const RC_MAX_DEFAULT: usize = 8;
const GIB: u64 = 1024 * 1024 * 1024;

/// Adaptive-pool decision for whether to change target concurrency `N`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Grow,
    Shrink,
    Hold,
}

/// Pure feedback rule for the adaptive RC pool, evaluated when a file completes.
/// Hysteresis: never adjusts unless ≥1s has passed since the last change.
/// Shrink (safety) wins over grow: high CPU or a thin RAM reserve backs off;
/// otherwise spare CPU and RAM headroom grow one worker, capped at `nmax`,
/// floored at 1.
pub fn adjust_decision(
    cpu_pct: f64,
    avail_ram_bytes: u64,
    current_n: usize,
    nmax: usize,
    since_last_adjust: Duration,
) -> Decision {
    if since_last_adjust < Duration::from_secs(1) {
        return Decision::Hold;
    }
    // Back-pressure first: saturated CPU or less than the 4 GB reserve.
    if cpu_pct > 92.0 || avail_ram_bytes < 4 * GIB {
        return if current_n > 1 {
            Decision::Shrink
        } else {
            Decision::Hold
        };
    }
    // Headroom: spare CPU and enough RAM for one more (N+1)×2 GB worker.
    if cpu_pct < 70.0 && avail_ram_bytes > (current_n as u64 + 1) * 2 * GIB && current_n < nmax {
        return Decision::Grow;
    }
    Decision::Hold
}

/// Initial target concurrency: `clamp(logical_cores / RC_INTERNAL_THREADS, 1, 4)`.
fn initial_target(logical_cores: usize) -> usize {
    (logical_cores / RC_INTERNAL_THREADS).clamp(1, 4)
}

/// Parse `TEXPROC_RC_MAX`; empty/non-numeric/zero falls back to the default.
fn rc_max_from(raw: Option<&str>) -> usize {
    raw.map(str::trim)
        .filter(|value| !value.is_empty())
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|&value| value > 0)
        .unwrap_or(RC_MAX_DEFAULT)
}

/// Adaptive multi-RC worker pool over the produced TIFFs. Queue semantics match
/// the old sequential pass — one RC process per file (`RC.exe <tif> /refresh
/// /userdialog=0`, cwd = output dir), per-file failure recorded and the batch
/// continues, DDS lands next to the TIFF, `delete_tif` removes a source only
/// after its DDS is produced. What changed: up to `N` RC processes run at once,
/// where `N` starts at `clamp(cores/6, 1, 4)` and adapts (see `adjust_decision`)
/// on each completion using live CPU (`GetSystemTimes`) and available RAM
/// (`GlobalMemoryStatusEx`). `on_progress(completed, total, name)` fires per
/// completion; `on_workers(from, to)` fires on the initial target and every
/// change so the trajectory is visible in the UI stream.
///
/// Cancel: on `cancel`, we stop launching new RC processes AND terminate every
/// in-flight child (`Child::kill` → TerminateProcess on Windows), reaping each,
/// so no orphan rc.exe survives a cancel.
#[allow(clippy::too_many_arguments)]
fn run_dds_pool(
    rc_exe: &Path,
    jobs: &[PathBuf],
    output_root: &Path,
    delete_tif: bool,
    cancel: &AtomicBool,
    mut on_progress: impl FnMut(usize, usize, &str),
    mut on_workers: impl FnMut(usize, usize),
) -> DdsSummary {
    let total = jobs.len();
    let mut succeeded = 0;
    let mut failures = Vec::new();

    let cores = thread::available_parallelism().map_or(1, |value| value.get());
    let nmax = rc_max_from(std::env::var("TEXPROC_RC_MAX").ok().as_deref());
    let mut target = initial_target(cores).clamp(1, nmax);
    let mut trajectory = vec![target];
    on_workers(0, target);

    if total == 0 {
        return DdsSummary {
            total,
            succeeded,
            failures,
            n_trajectory: trajectory,
        };
    }

    struct Running {
        child: Child,
        tif: PathBuf,
        name: String,
    }

    let mut cpu = CpuSampler::new();
    let mut last_adjust = Instant::now();
    let mut next = 0;
    let mut completed = 0;
    let mut running: Vec<Running> = Vec::new();

    loop {
        if cancel.load(Ordering::Relaxed) {
            for mut job in running.drain(..) {
                let _ = job.child.kill();
                let _ = job.child.wait();
            }
            break;
        }

        // Launch up to the current target.
        while running.len() < target && next < total {
            let tif = jobs[next].clone();
            next += 1;
            let name = file_name_of(&tif);
            match spawn_rc(rc_exe, &tif, output_root) {
                Ok(child) => running.push(Running { child, tif, name }),
                Err(error) => {
                    completed += 1;
                    on_progress(completed, total, &name);
                    failures.push(format!("{name}: failed to start RC: {error}"));
                }
            }
        }

        if running.is_empty() && next >= total {
            break;
        }

        // Reap any finished children (non-blocking).
        let mut progressed = false;
        let mut index = 0;
        while index < running.len() {
            match running[index].child.try_wait() {
                Ok(Some(status)) => {
                    let job = running.remove(index);
                    completed += 1;
                    progressed = true;
                    let dds = job.tif.with_extension("dds");
                    if status.success() && dds.is_file() {
                        succeeded += 1;
                        if delete_tif {
                            let _ = fs::remove_file(&job.tif);
                        }
                    } else {
                        let code = status.code().unwrap_or(-1);
                        failures.push(format!(
                            "{}: RC exited with {code}, DDS was not produced",
                            job.name
                        ));
                    }
                    on_progress(completed, total, &job.name);
                }
                Ok(None) => index += 1,
                Err(error) => {
                    let job = running.remove(index);
                    completed += 1;
                    progressed = true;
                    failures.push(format!("{}: RC wait failed: {error}", job.name));
                    on_progress(completed, total, &job.name);
                }
            }
        }

        // Feedback: re-evaluate target only when ≥1s has elapsed, giving a clean
        // CPU sampling window and the required hysteresis.
        if progressed && last_adjust.elapsed() >= Duration::from_secs(1) {
            let cpu_pct = cpu.sample();
            let avail = available_ram_bytes();
            let decision = adjust_decision(cpu_pct, avail, target, nmax, last_adjust.elapsed());
            let previous = target;
            match decision {
                Decision::Grow => target += 1,
                Decision::Shrink => target = target.saturating_sub(1).max(1),
                Decision::Hold => {}
            }
            if target != previous {
                trajectory.push(target);
                on_workers(previous, target);
                last_adjust = Instant::now();
            }
        }

        if !progressed {
            thread::sleep(Duration::from_millis(50));
        }
    }

    DdsSummary {
        total,
        succeeded,
        failures,
        n_trajectory: trajectory,
    }
}

fn file_name_of(path: &Path) -> String {
    path.file_name()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_owned()
}

/// Spawn one detached RC → DDS process. stdio is null (the GUI has no console)
/// so the pool never blocks on a child's pipe buffer.
fn spawn_rc(rc_exe: &Path, tif: &Path, output_root: &Path) -> std::io::Result<Child> {
    let mut command = Command::new(rc_exe);
    command
        .arg(tif)
        .arg("/refresh")
        .arg("/userdialog=0")
        .current_dir(output_root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    command.spawn()
}

/// Rolling system-CPU-utilization sampler over `GetSystemTimes`. On Windows the
/// kernel time already includes idle, so utilization = 1 − Δidle/(Δkernel+Δuser).
struct CpuSampler {
    last: Option<(u64, u64, u64)>,
}

impl CpuSampler {
    fn new() -> Self {
        let mut sampler = Self { last: None };
        sampler.last = read_system_times();
        sampler
    }

    /// Utilization (0–100) since the previous sample; 0 if unavailable.
    fn sample(&mut self) -> f64 {
        let Some(current) = read_system_times() else {
            return 0.0;
        };
        let pct = match self.last {
            Some((idle0, kernel0, user0)) => {
                let idle = current.0.saturating_sub(idle0);
                let kernel = current.1.saturating_sub(kernel0);
                let user = current.2.saturating_sub(user0);
                let total = kernel + user;
                if total == 0 {
                    0.0
                } else {
                    (1.0 - idle as f64 / total as f64) * 100.0
                }
            }
            None => 0.0,
        };
        self.last = Some(current);
        pct
    }
}

#[cfg(windows)]
fn read_system_times() -> Option<(u64, u64, u64)> {
    #[repr(C)]
    #[derive(Clone, Copy, Default)]
    struct FileTime {
        low: u32,
        high: u32,
    }
    impl FileTime {
        fn as_u64(self) -> u64 {
            (u64::from(self.high) << 32) | u64::from(self.low)
        }
    }
    extern "system" {
        fn GetSystemTimes(idle: *mut FileTime, kernel: *mut FileTime, user: *mut FileTime) -> i32;
    }
    let mut idle = FileTime::default();
    let mut kernel = FileTime::default();
    let mut user = FileTime::default();
    // SAFETY: three valid, writable FILETIME out-parameters as the API requires.
    let ok = unsafe { GetSystemTimes(&mut idle, &mut kernel, &mut user) };
    (ok != 0).then(|| (idle.as_u64(), kernel.as_u64(), user.as_u64()))
}

#[cfg(not(windows))]
fn read_system_times() -> Option<(u64, u64, u64)> {
    None
}

#[cfg(windows)]
fn available_ram_bytes() -> u64 {
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
    // SAFETY: correctly sized, zeroed MEMORYSTATUSEX with its length field set.
    let ok = unsafe { GlobalMemoryStatusEx(&mut status) };
    if ok != 0 && status.avail_phys > 0 {
        status.avail_phys
    } else {
        // Unknown: report a large value so RAM never forces a needless shrink.
        u64::MAX
    }
}

#[cfg(not(windows))]
fn available_ram_bytes() -> u64 {
    u64::MAX
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
    Completed(Box<ModelExportReport>),
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
    conversion: ConversionOverrides,
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
        let result = converter::convert::convert_file_with_options(
            &input,
            existing_optional(&manifest),
            existing_optional(&overrides),
            texture_dir.as_deref(),
            None,
            &output_dir,
            &physicalize_overrides,
            &conversion,
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
                    // The model-export flow is not separately cancellable; a
                    // never-set flag drives the same pool used by the DDS stage.
                    let cancel = AtomicBool::new(false);
                    Some(run_dds_pool(
                        rc_exe,
                        &tifs,
                        &assoc.output_dir,
                        assoc.delete_tif,
                        &cancel,
                        |_, _, _| {},
                        |from, to| {
                            let _ = sender.send(ModelExportEvent::Stage(format!(
                                "RC workers: {from} → {to}"
                            )));
                        },
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

        let _ = sender.send(ModelExportEvent::Completed(Box::new(ModelExportReport {
            outputs,
            rc,
            textures,
        })));
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
            ConversionOverrides::default(),
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
            failed: Vec::new(),
            cancelled: false,
            elapsed_seconds: 0.0,
            rayon_threads: 1,
            memory_budget_bytes: 0,
            waves: 1,
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

    const GIB: u64 = 1024 * 1024 * 1024;

    #[test]
    fn hold_within_one_second_hysteresis() {
        // Idle CPU + huge RAM would grow, but <1s since last adjust holds.
        assert_eq!(
            adjust_decision(10.0, 64 * GIB, 3, 8, Duration::from_millis(500)),
            Decision::Hold
        );
    }

    #[test]
    fn grow_on_spare_cpu_and_ram() {
        assert_eq!(
            adjust_decision(50.0, 64 * GIB, 3, 8, Duration::from_secs(2)),
            Decision::Grow
        );
    }

    #[test]
    fn shrink_on_saturated_cpu() {
        assert_eq!(
            adjust_decision(95.0, 64 * GIB, 4, 8, Duration::from_secs(2)),
            Decision::Shrink
        );
    }

    #[test]
    fn shrink_on_thin_ram_reserve() {
        // Below the 4 GB reserve → shrink even with idle CPU.
        assert_eq!(
            adjust_decision(10.0, 3 * GIB, 4, 8, Duration::from_secs(2)),
            Decision::Shrink
        );
    }

    #[test]
    fn floor_at_one_worker() {
        // Back-pressure at N=1 cannot shrink below the floor.
        assert_eq!(
            adjust_decision(99.0, GIB, 1, 8, Duration::from_secs(2)),
            Decision::Hold
        );
    }

    #[test]
    fn cap_at_nmax() {
        assert_eq!(
            adjust_decision(10.0, 64 * GIB, 8, 8, Duration::from_secs(2)),
            Decision::Hold
        );
    }

    #[test]
    fn grow_blocked_when_ram_below_next_worker_need() {
        // N=3 → needs > (3+1)*2 = 8 GB free to grow; 7 GB holds.
        assert_eq!(
            adjust_decision(10.0, 7 * GIB, 3, 8, Duration::from_secs(2)),
            Decision::Hold
        );
        // 9 GB clears the (N+1)*2 GB reserve boundary → grow.
        assert_eq!(
            adjust_decision(10.0, 9 * GIB, 3, 8, Duration::from_secs(2)),
            Decision::Grow
        );
    }

    #[test]
    fn rc_max_override_parsing() {
        assert_eq!(rc_max_from(None), RC_MAX_DEFAULT);
        assert_eq!(rc_max_from(Some("")), RC_MAX_DEFAULT);
        assert_eq!(rc_max_from(Some("  ")), RC_MAX_DEFAULT);
        assert_eq!(rc_max_from(Some("0")), RC_MAX_DEFAULT);
        assert_eq!(rc_max_from(Some("abc")), RC_MAX_DEFAULT);
        assert_eq!(rc_max_from(Some("1")), 1);
        assert_eq!(rc_max_from(Some(" 12 ")), 12);
    }

    #[test]
    fn initial_target_clamps_cores_over_six() {
        assert_eq!(initial_target(1), 1); // 0 → floored to 1
        assert_eq!(initial_target(6), 1);
        assert_eq!(initial_target(20), 3); // reviewer's 20-core box → 3
        assert_eq!(initial_target(64), 4); // capped at 4
    }

    /// Adaptive DDS pool benchmark: sequential (`TEXPROC_RC_MAX=1`) vs adaptive
    /// over a ≥16-file 4K TIFF corpus produced by the texproc batch library from
    /// a handful of KB3D groups. Reports both wall clocks, the N trajectory, and
    /// asserts dds count == tif count. Ignored by default (needs Z: corpus + RC):
    ///   set CE_RC_EXE=...\rc.exe
    ///   cargo test -p texproc-gui -- --ignored --nocapture benchmark_adaptive_vs_sequential
    #[test]
    #[ignore = "requires the KB3D 4K corpus (Z:) and a real RC.exe"]
    fn benchmark_adaptive_vs_sequential_dds() {
        use std::time::{Instant, SystemTime, UNIX_EPOCH};

        let rc = std::env::var_os("CE_RC_EXE")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe")
            });
        assert!(rc.is_file(), "RC not found at {}", rc.display());

        let corpus = std::env::var_os("TEXPROC_BENCH_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(r"Z:\enchanted\KB3DTextures\4k"));
        assert!(corpus.is_dir(), "corpus missing: {}", corpus.display());

        // Build a ≥16-file 4K TIFF corpus from a few KB3D groups.
        let suffixes = SuffixTable::embedded().unwrap();
        let full = texproc::scan_inputs(&[corpus], &suffixes).unwrap();
        let mut scan = full;
        scan.groups.truncate(6);
        assert!(!scan.groups.is_empty());

        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let out =
            std::env::temp_dir().join(format!("texproc-gui-bench-{}-{nonce}", std::process::id()));
        fs::create_dir_all(&out).unwrap();
        let cancel = AtomicBool::new(false);
        let report =
            process_scan_parallel(&scan, &TextureSettings::default(), &out, &cancel, |_| {})
                .unwrap();
        let tifs = dds_jobs(&report);
        assert!(tifs.len() >= 16, "corpus too small: {} TIFFs", tifs.len());
        eprintln!(
            "corpus: {} 4K TIFFs from {} groups",
            tifs.len(),
            scan.groups.len()
        );

        let run = |nmax: Option<&str>| -> (Duration, DdsSummary) {
            match nmax {
                Some(value) => std::env::set_var("TEXPROC_RC_MAX", value),
                None => std::env::remove_var("TEXPROC_RC_MAX"),
            }
            let start = Instant::now();
            let summary = run_dds_pool(&rc, &tifs, &out, false, &cancel, |_, _, _| {}, |_, _| {});
            (start.elapsed(), summary)
        };

        let (seq_wall, seq) = run(Some("1"));
        let (adaptive_wall, adaptive) = run(None);
        std::env::remove_var("TEXPROC_RC_MAX");

        eprintln!(
            "sequential (Nmax=1): {:.1}s, {}/{} DDS, N trajectory {:?}",
            seq_wall.as_secs_f64(),
            seq.succeeded,
            seq.total,
            seq.n_trajectory
        );
        eprintln!(
            "adaptive:            {:.1}s, {}/{} DDS, N trajectory {:?}",
            adaptive_wall.as_secs_f64(),
            adaptive.succeeded,
            adaptive.total,
            adaptive.n_trajectory
        );
        eprintln!(
            "speedup: {:.2}x",
            seq_wall.as_secs_f64() / adaptive_wall.as_secs_f64()
        );

        assert_eq!(adaptive.succeeded, tifs.len(), "adaptive DDS incomplete");
        assert_eq!(seq.n_trajectory, vec![1], "Nmax=1 must never adjust");
        fs::remove_dir_all(&out).ok();
    }

    /// Cancel during an adaptive DDS pool: assert it returns without draining the
    /// queue (so children were terminated, not awaited) and that no rc.exe
    /// survives. Ignored by default (needs a 4K corpus + RC):
    ///   set CE_RC_EXE=...\rc.exe
    ///   cargo test -p texproc-gui -- --ignored --nocapture cancel_terminates
    #[test]
    #[ignore = "requires the KB3D 4K corpus (Z:) and a real RC.exe"]
    fn cancel_terminates_inflight_rc() {
        use std::sync::Arc;
        use std::time::{Instant, SystemTime, UNIX_EPOCH};

        let rc = std::env::var_os("CE_RC_EXE")
            .map(PathBuf::from)
            .unwrap_or_else(|| {
                PathBuf::from(r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe")
            });
        assert!(rc.is_file(), "RC not found at {}", rc.display());
        let corpus = std::env::var_os("TEXPROC_BENCH_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(r"Z:\enchanted\KB3DTextures\4k"));
        assert!(corpus.is_dir());

        let suffixes = SuffixTable::embedded().unwrap();
        let mut scan = texproc::scan_inputs(&[corpus], &suffixes).unwrap();
        scan.groups.truncate(8);
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let out =
            std::env::temp_dir().join(format!("texproc-gui-cancel-{}-{nonce}", std::process::id()));
        fs::create_dir_all(&out).unwrap();
        let cancel = AtomicBool::new(false);
        let report =
            process_scan_parallel(&scan, &TextureSettings::default(), &out, &cancel, |_| {})
                .unwrap();
        let tifs = dds_jobs(&report);
        assert!(tifs.len() >= 16);

        let flag = Arc::new(AtomicBool::new(false));
        let worker_flag = Arc::clone(&flag);
        let rc_clone = rc.clone();
        let out_clone = out.clone();
        let tifs_clone = tifs.clone();
        let handle = thread::spawn(move || {
            run_dds_pool(
                &rc_clone,
                &tifs_clone,
                &out_clone,
                false,
                &worker_flag,
                |_, _, _| {},
                |_, _| {},
            )
        });
        thread::sleep(Duration::from_secs(3));
        flag.store(true, Ordering::Relaxed);
        let start = Instant::now();
        let summary = handle.join().unwrap();
        let cancel_latency = start.elapsed();
        eprintln!(
            "cancelled: {}/{} completed, returned {:.2}s after cancel",
            summary.total - (tifs.len() - summary.succeeded - summary.failures.len()),
            tifs.len(),
            cancel_latency.as_secs_f64()
        );
        // The pool broke out on cancel rather than compiling every TIFF.
        assert!(
            summary.succeeded < tifs.len(),
            "cancel did not stop the queue"
        );
        fs::remove_dir_all(&out).ok();
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
                ProcessEvent::Progress { .. } | ProcessEvent::DdsWorkers { .. } => {}
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
