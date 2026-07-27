#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod file_dialog;
mod i18n;
mod prefs;
mod worker;

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{Receiver, TryRecvError},
        Arc,
    },
    time::Duration,
};

use converter::rc_policy::resolve_physicalize;
use eframe::egui::{
    self, Align2, Color32, ComboBox, Grid, Id, Modal, ProgressBar, RichText, ScrollArea, Sense,
    Stroke, TextEdit, TextureHandle, ViewportBuilder,
};
use file_dialog::{
    choose_file_open, choose_file_save, choose_files_multi, choose_folder, choose_rc_executable,
};
use i18n::{fill, Language, Strings};
use prefs::{embedded_texture_directory, AppPreferences};
use texproc::{
    load_texture_settings, save_texture_settings, ArmOrder, DiffFormat, FailedGroup,
    OutputResolution, ScanEntry, ScanGroup, ScanResult, Severity, SuffixTable, TextureSettings,
};
use texproc_gui::{
    axes_parallel, compose_forward_up, helper_node_count, parse_forward_up, ReviewDocument,
    ASSIGNABLE_SOURCE_TYPES, AXIS_TOKENS,
};
use worker::{
    BatchExportEvent, DdsSummary, ModelEvent, ModelExportEvent, ModelJob, ModelReview,
    PreviewEvent, ProcessEvent, ProcessJob, RcExportOutcome, ScanEvent,
};

const APP_TITLE: &str = "CryEngine Texture Processor";
const DEFAULT_RC_EXE: &str = r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe";
const PHYSICALIZE_VALUES: [&str; 5] = ["no", "default", "obstruct", "no_collide", "proxy_only"];
/// Legal `unit_size` values for the Conversion Settings Unit dropdown. The RC
/// import schema (output_formats/rc_import_schema.py) accepts unit_size as a
/// free string; this mirrors the CryEngine Sandbox FBX-import unit choices,
/// with `file` (use the FBX's own unit) as the native-car default.
const UNIT_SIZE_VALUES: [&str; 6] = ["file", "mm", "cm", "m", "inch", "foot"];
/// GUI default physicalize seed for every material (the practical golden flow is
/// all `no`). Seeded as explicit metadata; a loaded manifest still wins.
const DEFAULT_PHYSICALIZE: &str = "no";

/// Apply a click to a row-index multi-selection (shared by the texture list and
/// the material table): plain = select only, Ctrl = toggle, Shift = range from
/// the anchor.
fn apply_click_selection(
    selected: &mut BTreeSet<usize>,
    anchor: &mut Option<usize>,
    index: usize,
    ctrl: bool,
    shift: bool,
) {
    if shift {
        if let Some(start) = *anchor {
            let (low, high) = (start.min(index), start.max(index));
            *selected = (low..=high).collect();
            return;
        }
    } else if ctrl {
        if !selected.remove(&index) {
            selected.insert(index);
        }
        *anchor = Some(index);
        return;
    }
    *selected = BTreeSet::from([index]);
    *anchor = Some(index);
}

/// Seed explicit `no` physicalize for every material name (item 1 default). Used
/// on model load so an export sends `no` even if the material table is never
/// opened.
fn seed_default_physicalize<'a>(
    names: impl IntoIterator<Item = &'a str>,
) -> BTreeMap<String, String> {
    names
        .into_iter()
        .map(|name| (name.to_owned(), DEFAULT_PHYSICALIZE.to_owned()))
        .collect()
}

/// A labeled ±X/±Y/±Z axis dropdown bound to `token`.
fn axis_dropdown(ui: &mut egui::Ui, label: &str, id: &str, token: &mut String) {
    ui.horizontal(|ui| {
        ui.label(label);
        egui::ComboBox::from_id_salt(id)
            .selected_text(token.as_str())
            .show_ui(ui, |ui| {
                for value in AXIS_TOKENS {
                    ui.selectable_value(token, value.to_owned(), value);
                }
            });
    });
}

/// Bulk-set physicalize for the selected material rows in one action.
fn apply_bulk_physicalize(
    overrides: &mut BTreeMap<String, String>,
    names: &[&str],
    selected: &BTreeSet<usize>,
    value: &str,
) {
    for &index in selected {
        if let Some(name) = names.get(index) {
            overrides.insert((*name).to_owned(), value.to_owned());
        }
    }
}
/// Map-type columns shown in the groups table (source type, header). Ordered to
/// match the demo3 blueprint's primary columns, then the remaining tracked types.
const GROUP_COLUMNS: [(&str, &str); 12] = [
    ("diffuse", "Color"),
    ("normal", "Normal"),
    ("specular", "Spec"),
    ("glossiness", "Gloss"),
    ("roughness", "Rough"),
    ("metallic", "Metal"),
    ("displacement", "Height"),
    ("ao", "AO"),
    ("alpha", "Alpha"),
    ("emissive", "Emiss"),
    ("sss", "SSS"),
    ("arm", "ARM"),
];
const GROUP_CELL_W: f32 = 38.0;
const GROUP_UNKNOWN_W: f32 = 134.0;
const GROUP_ROW_H: f32 = 26.0;
const IMAGE_FILTER: &str = "Images (png, jpg, jpeg, tif, tiff, exr, hdr, tga, bmp, webp)\0*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.exr;*.hdr;*.tga;*.bmp;*.webp\0All files (*.*)\0*.*\0";
const FBX_FILTER: &str = "FBX models (*.fbx)\0*.fbx\0All files (*.*)\0*.*\0";
const JSON_FILTER: &str = "JSON files (*.json)\0*.json\0All files (*.*)\0*.*\0";

fn main() -> eframe::Result {
    install_crash_logger();
    // Synthetic-panic trigger: a GUI has no console, so this lets us verify the
    // crash.log mechanism end to end (set TEXPROC_GUI_TEST_PANIC=1 and launch).
    if std::env::var_os("TEXPROC_GUI_TEST_PANIC").is_some() {
        panic!("synthetic crash-log test panic");
    }
    // Any number of paths may be passed (textures, folders, and/or FBX files) —
    // FBX args load as separate model-list entries (batch import / screenshots).
    let initial_paths = std::env::args_os().skip(1).map(PathBuf::from).collect();
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_inner_size([1440.0, 900.0])
            .with_min_inner_size([1100.0, 680.0]),
        ..Default::default()
    };
    eframe::run_native(
        APP_TITLE,
        options,
        Box::new(move |creation| {
            install_cjk_font(&creation.egui_ctx);
            Ok(Box::new(WorkflowApp::new(initial_paths)))
        }),
    )
}

/// System font used as a CJK fallback so zh-cn text renders. Not embedded in the
/// binary (licensing + size); loaded from disk at startup.
const CJK_FONT_PATH: &str = r"C:\Windows\Fonts\msyh.ttc";

/// Register a CJK fallback font so Simplified Chinese glyphs render. Loaded
/// unconditionally (it only adds fallback glyphs; English is unaffected). A
/// missing/unreadable font file is a graceful no-op — never a panic.
fn install_cjk_font(context: &egui::Context) {
    if let Some(fonts) = load_cjk_fonts(Path::new(CJK_FONT_PATH)) {
        context.set_fonts(fonts);
    }
}

/// Build `FontDefinitions` with `path` appended as a fallback on both the
/// proportional and monospace families. Returns `None` when the file cannot be
/// read, so the caller keeps egui's defaults. Structured this way so the
/// fallback path is unit-testable with a bogus path (never panics).
fn load_cjk_fonts(path: &Path) -> Option<egui::FontDefinitions> {
    let data = fs::read(path).ok()?;
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert(
        "cjk_fallback".to_owned(),
        std::sync::Arc::new(egui::FontData::from_owned(data)),
    );
    for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
        fonts
            .families
            .entry(family)
            .or_default()
            .push("cjk_fallback".to_owned());
    }
    Some(fonts)
}

/// crash.log lives next to the executable so a windowed build (no console) still
/// leaves a trace when it aborts or panics.
fn crash_log_path() -> Option<PathBuf> {
    std::env::current_exe()
        .ok()
        .map(|exe| exe.with_file_name("crash.log"))
}

/// Install a panic hook that appends a timestamped panic message + backtrace to
/// crash.log, then chains to the default hook. Caught batch panics are logged
/// too; an outright abort (e.g. OOM) is not a Rust panic and cannot be hooked —
/// the batch memory budget is what keeps that from happening.
fn install_crash_logger() {
    let previous = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let backtrace = std::backtrace::Backtrace::force_capture();
        append_crash_log(&format!("{info}\n{backtrace}"));
        previous(info);
    }));
}

/// Append one timestamped record to crash.log. Kept separate from the hook so it
/// can be unit-tested without triggering a real panic.
fn append_crash_log(message: &str) {
    if let Some(path) = crash_log_path() {
        append_crash_log_to(&path, message);
    }
}

fn append_crash_log_to(path: &Path, message: &str) {
    let seconds = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|since| since.as_secs())
        .unwrap_or(0);
    let record = format!("[epoch {seconds}] {message}\n\n");
    use std::io::Write;
    if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(record.as_bytes());
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum WorkflowTab {
    Textures,
    Model,
}

#[derive(Default)]
struct TextureState {
    roots: Vec<PathBuf>,
    files: Vec<PathBuf>,
    document: Option<ReviewDocument>,
    scan_receiver: Option<Receiver<ScanEvent>>,
    /// Multi-selection into `files` (click / Ctrl+click / Shift+click).
    selected_files: BTreeSet<usize>,
    /// Anchor for Shift-range selection.
    selection_anchor: Option<usize>,
    selected_group: Option<usize>,
    group_search: String,
    review_only: bool,
    /// Set when a scan was triggered by auto-ingesting an FBX's textures, so the
    /// scan-complete status can honestly report the FBX import.
    pending_fbx_import: Option<(usize, usize)>,
    /// Overrides the scan-complete status line for one scan (Remove Selected /
    /// Add Related), so their message survives the regroup that follows.
    pending_import_status: Option<String>,
    /// Group keys that had unknowns at scan time — lets the Unassigned column
    /// show "✓ Assigned" (all resolved) versus "—" (never had unknowns).
    ever_unknown: BTreeSet<String>,
}

#[derive(Default)]
struct PreviewState {
    receiver: Option<Receiver<PreviewEvent>>,
    requested_path: Option<PathBuf>,
    loaded_path: Option<PathBuf>,
    texture: Option<TextureHandle>,
    dimensions: Option<(u32, u32)>,
    source_type: String,
    error: Option<String>,
}

struct ProcessState {
    job: ProcessJob,
    completed: usize,
    total: usize,
    current_group: String,
    written: usize,
    group_names: Vec<String>,
    completed_groups: BTreeSet<String>,
    dds_active: bool,
    dds_completed: usize,
    dds_total: usize,
    dds_current: String,
    dds_workers: usize,
}

struct ProcessSummary {
    written: usize,
    groups: usize,
    cancelled: bool,
    elapsed_seconds: f64,
    output_directory: PathBuf,
    dds: Option<DdsSummary>,
    /// Groups that errored or panicked during the batch (batch continued).
    failed: Vec<FailedGroup>,
}

/// One line in the status-bar diagnostics popover.
struct DiagItem {
    severity: &'static str,
    title: String,
    message: String,
}

/// One imported FBX in the model list. All per-model state lives here so
/// switching the selected model never leaks edits (physicalize, axis overrides)
/// between models.
struct ModelEntry {
    review: ModelReview,
    physicalize_overrides: BTreeMap<String, String>,
    conversion: ConversionSettings,
    selected_material: Option<usize>,
    selected_materials: BTreeSet<usize>,
    material_selection_anchor: Option<usize>,
    bulk_physicalize: String,
    /// Meshless non-root scene nodes (RC helper/anchor nodes).
    helper_nodes: usize,
    /// Lowercased absolute paths of textures ingested from this FBX — the origin
    /// set that "Export associated textures with model" processes for this model.
    fbx_ingested: BTreeSet<String>,
}

#[derive(Default)]
struct ModelState {
    /// Pending FBX loads (multi-select import loads N files at once).
    load_receivers: Vec<Receiver<ModelEvent>>,
    entries: Vec<ModelEntry>,
    /// Multi-selection into `entries`; exactly one selection drives the center.
    selected: BTreeSet<usize>,
    selection_anchor: Option<usize>,
    // Single-model export (Export CE Model on the selected model).
    export_receiver: Option<Receiver<ModelExportEvent>>,
    export_summary: Option<String>,
    export_modal_open: bool,
    export_stage: String,
    export_cgf: Option<PathBuf>,
    rc_missing_warning: bool,
    // Batch export (Export All).
    batch: Option<BatchState>,
}

/// Export All progress/summary state.
struct BatchState {
    receiver: Receiver<BatchExportEvent>,
    cancel: Arc<AtomicBool>,
    total: usize,
    current: usize,
    current_name: String,
    stage: String,
    succeeded: Vec<String>,
    failed: Vec<(String, String)>,
    done: bool,
    modal_open: bool,
}

/// Conversion Settings panel state (R9 item 2), Sandbox-mirror. Unit/Scale come
/// from prefs and persist; Forward/Up re-detect per loaded FBX and never persist.
#[derive(Default)]
struct ConversionSettings {
    /// RC `forward_up_axes` token as auto-detected from the FBX (for the
    /// "Detected: …" caption and override highlight).
    detected_forward: String,
    detected_up: String,
    forward: String,
    up: String,
    merge_all_nodes: bool,
    scene_origin: bool,
}

struct WorkflowApp {
    tab: WorkflowTab,
    preferences: AppPreferences,
    settings: TextureSettings,
    texture: TextureState,
    preview: PreviewState,
    process: Option<ProcessState>,
    process_summary: Option<ProcessSummary>,
    process_modal_open: bool,
    show_diagnostics: bool,
    model: ModelState,
    status: String,
}

impl WorkflowApp {
    fn new(initial_paths: Vec<PathBuf>) -> Self {
        let preferences = AppPreferences::load();
        let settings = load_texture_settings(Path::new(&preferences.settings_path))
            .unwrap_or_else(|_| TextureSettings::default());
        let mut app = Self {
            tab: WorkflowTab::Textures,
            preferences,
            settings,
            texture: TextureState::default(),
            preview: PreviewState::default(),
            process: None,
            process_summary: None,
            process_modal_open: false,
            show_diagnostics: false,
            model: ModelState::default(),
            status: String::new(),
        };
        app.status = app.t().status_ready.to_owned();
        if !initial_paths.is_empty() {
            app.receive_paths(initial_paths);
        }
        app
    }

    /// The active language's string table. `&'static` — never borrows `self`, so
    /// it can be called and held while `self` is mutated in the same statement.
    fn t(&self) -> &'static Strings {
        Language::from_code(&self.preferences.language).strings()
    }

    fn receive_paths(&mut self, paths: Vec<PathBuf>) {
        let mut texture_paths = Vec::new();
        let mut fbx_paths = Vec::new();
        for path in paths {
            if is_fbx(&path) {
                fbx_paths.push(path);
            } else {
                texture_paths.push(path);
            }
        }
        if !fbx_paths.is_empty() {
            self.load_model_files(fbx_paths);
        }
        if !texture_paths.is_empty() {
            self.add_texture_roots(texture_paths);
        }
    }

    fn add_texture_roots(&mut self, roots: Vec<PathBuf>) {
        let mut seen = self
            .texture
            .roots
            .iter()
            .map(|path| path.to_string_lossy().to_lowercase())
            .collect::<BTreeSet<_>>();
        for root in roots {
            if root.exists() && seen.insert(root.to_string_lossy().to_lowercase()) {
                self.texture.roots.push(root);
            }
        }
        if self.texture.roots.is_empty() {
            self.status = self.t().no_texture_files_found.to_owned();
            return;
        }
        self.tab = WorkflowTab::Textures;
        self.texture.scan_receiver = Some(worker::start_scan(self.texture.roots.clone()));
        self.status = self.t().scanning_grouping.to_owned();
    }

    fn clear_textures(&mut self) {
        self.texture = TextureState::default();
        self.preview = PreviewState::default();
        self.process_summary = None;
        self.status = self.t().cleared_textures.to_owned();
    }

    /// Start loading one or more FBX files; each completes into its own model-list
    /// entry (batch import). Existing entries are kept.
    fn load_model_files(&mut self, paths: Vec<PathBuf>) {
        let mut started = 0;
        for path in paths {
            if !path.is_file() {
                self.status = fill(self.t().fbx_not_exist, &[&path.display().to_string()]);
                continue;
            }
            self.preferences.model_path = path.to_string_lossy().into_owned();
            self.model
                .load_receivers
                .push(worker::start_model_load(path));
            started += 1;
        }
        if started == 0 {
            return;
        }
        self.tab = WorkflowTab::Model;
        self.status = fill(self.t().loading_fbx, &[&started.to_string()]);
        self.save_preferences();
    }

    /// Index of the single selected model, or `None` when 0 or >1 are selected.
    fn selected_entry_index(&self) -> Option<usize> {
        (self.model.selected.len() == 1)
            .then(|| self.model.selected.iter().next().copied())
            .flatten()
    }

    fn clear_models(&mut self) {
        self.model.entries.clear();
        self.model.selected.clear();
        self.model.selection_anchor = None;
        self.status = self.t().cleared_models.to_owned();
    }

    /// Multi-select removal from the model list, mirroring Remove Selected on the
    /// texture list. Selection indices become stale after removal, so clear them.
    fn remove_selected_models(&mut self) {
        if self.model.selected.is_empty() {
            return;
        }
        let selected = std::mem::take(&mut self.model.selected);
        let removed = selected.len();
        let mut index = 0;
        self.model.entries.retain(|_| {
            let keep = !selected.contains(&index);
            index += 1;
            keep
        });
        self.model.selection_anchor = None;
        self.status = fill(self.t().removed_models, &[&removed.to_string()]);
    }

    fn request_preview(&mut self, path: PathBuf, source_type: impl Into<String>) {
        if self.preview.requested_path.as_ref() == Some(&path)
            || self.preview.loaded_path.as_ref() == Some(&path)
        {
            return;
        }
        self.preview = PreviewState {
            receiver: Some(worker::start_preview(path.clone())),
            requested_path: Some(path),
            source_type: source_type.into(),
            ..PreviewState::default()
        };
    }

    fn start_texture_process(&mut self) {
        let Some(document) = &self.texture.document else {
            self.status = self.t().no_textures_ready.to_owned();
            return;
        };
        if let Some((index, blocked)) = document
            .scan()
            .groups
            .iter()
            .enumerate()
            .find(|(_, group)| group.slots.is_empty() && !group.unknown.is_empty())
        {
            self.texture.selected_group = Some(index);
            self.texture.review_only = true;
            self.status = fill(self.t().assign_before_processing, &[&blocked.base_name]);
            return;
        }
        let output = PathBuf::from(self.preferences.texture_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = self.t().set_texture_output_first.to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = fill(self.t().create_texture_output_fail, &[&error.to_string()]);
            return;
        }

        let scan = document.scan().clone();
        let total = scan.groups.len();
        let group_names = scan
            .groups
            .iter()
            .map(|group| group.base_name.clone())
            .collect();
        let rc_exe = self
            .preferences
            .generate_dds
            .then(|| resolve_rc_path(&self.preferences.rc_path).path)
            .flatten();
        self.process = Some(ProcessState {
            job: worker::start_process(
                scan,
                self.settings,
                output,
                rc_exe,
                self.preferences.delete_tif_after_dds,
            ),
            completed: 0,
            total,
            current_group: "Preparing".to_owned(),
            written: 0,
            group_names,
            completed_groups: BTreeSet::new(),
            dds_active: false,
            dds_completed: 0,
            dds_total: 0,
            dds_current: String::new(),
            dds_workers: 0,
        });
        self.process_summary = None;
        self.process_modal_open = true;
        self.status = fill(self.t().processing_n_groups, &[&total.to_string()]);
    }

    /// Build the export job for one model-list entry, shared by single Export CE
    /// Model and batch Export All. Errors on illegal (parallel) axes so a bad
    /// model can't be sent to RC.
    fn build_model_job(&self, entry_index: usize) -> Result<ModelJob, String> {
        let entry = &self.model.entries[entry_index];
        let name = entry_name(entry);
        if axes_parallel(&entry.conversion.forward, &entry.conversion.up) {
            return Err(fill(self.t().job_axes_error, &[&name]));
        }
        let conversion = converter::request::ConversionOverrides {
            unit_size: Some(self.preferences.conversion_unit.clone()),
            scale: Some(self.preferences.conversion_scale),
            forward_up_axes: Some(compose_forward_up(
                &entry.conversion.forward,
                &entry.conversion.up,
            )),
            merge_all_nodes: Some(entry.conversion.merge_all_nodes),
            scene_origin: Some(entry.conversion.scene_origin),
        };
        // Item 4: when enabled, process this model's FBX-ingested texture groups
        // into the texture output directory and point MTL resolution there.
        let (associated, texture_dir) = if self.preferences.export_associated_textures {
            match self.build_associated_textures(entry_index)? {
                Some(associated) => {
                    let dir = Some(associated.output_dir.clone());
                    (Some(associated), dir)
                }
                None => (
                    None,
                    optional_path(&self.preferences.texture_output_directory),
                ),
            }
        } else {
            (
                None,
                optional_path(&self.preferences.texture_output_directory),
            )
        };
        Ok(ModelJob {
            name,
            input: entry.review.path.clone(),
            manifest: optional_path(&self.preferences.manifest_path),
            overrides: optional_path(&self.preferences.overrides_path),
            texture_dir,
            physicalize_overrides: entry.physicalize_overrides.clone(),
            conversion,
            associated,
        })
    }

    fn start_model_export(&mut self) {
        let Some(index) = self.selected_entry_index() else {
            self.status = self.t().select_single_export.to_owned();
            return;
        };
        let output = PathBuf::from(self.preferences.model_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = self.t().set_model_output_first.to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = fill(self.t().create_model_output_fail, &[&error.to_string()]);
            return;
        }
        let job = match self.build_model_job(index) {
            Ok(job) => job,
            Err(error) => {
                self.status = error;
                return;
            }
        };
        if self.preferences.export_associated_textures && job.associated.is_none() {
            self.status = self.t().no_ingested_export_model_only.to_owned();
        }
        let rc_resolution = resolve_rc_path(&self.preferences.rc_path);
        self.model.rc_missing_warning = rc_resolution.path.is_none();
        self.model.export_receiver = Some(worker::start_model_export(
            job,
            rc_resolution.path,
            output,
            self.preferences.delete_request_json,
        ));
        self.model.export_summary = None;
        self.model.export_cgf = None;
        self.model.export_modal_open = true;
        self.model.export_stage = self.t().preparing_export.to_owned();
        self.status = self.t().exporting_intermediates.to_owned();
    }

    /// Export All: iterate every loaded model sequentially in a worker.
    fn start_batch_export(&mut self) {
        if self.model.entries.is_empty() {
            self.status = self.t().load_fbx_first.to_owned();
            return;
        }
        let output = PathBuf::from(self.preferences.model_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = self.t().set_model_output_first.to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = fill(self.t().create_model_output_fail, &[&error.to_string()]);
            return;
        }
        let mut jobs = Vec::with_capacity(self.model.entries.len());
        for index in 0..self.model.entries.len() {
            match self.build_model_job(index) {
                Ok(job) => jobs.push(job),
                Err(error) => {
                    self.status = error;
                    return;
                }
            }
        }
        let total = jobs.len();
        let rc_resolution = resolve_rc_path(&self.preferences.rc_path);
        self.model.rc_missing_warning = rc_resolution.path.is_none();
        let job = worker::start_batch_export(
            jobs,
            rc_resolution.path,
            output,
            self.preferences.delete_request_json,
        );
        self.model.batch = Some(BatchState {
            receiver: job.receiver,
            cancel: job.cancel,
            total,
            current: 0,
            current_name: String::new(),
            stage: self.t().preparing.to_owned(),
            succeeded: Vec::new(),
            failed: Vec::new(),
            done: false,
            modal_open: true,
        });
        self.status = fill(self.t().exporting_n_models, &[&total.to_string()]);
    }

    /// Build the associated-texture set for item 4: the current groups that
    /// contain at least one file ingested from this model's FBX (and have
    /// processable slots). `Ok(None)` means there is nothing to process.
    fn build_associated_textures(
        &self,
        entry_index: usize,
    ) -> Result<Option<worker::AssociatedTextures>, String> {
        let Some(document) = &self.texture.document else {
            return Ok(None);
        };
        let ingested = &self.model.entries[entry_index].fbx_ingested;
        if ingested.is_empty() {
            return Ok(None);
        }
        let groups = document
            .scan()
            .groups
            .iter()
            .filter(|group| !group.slots.is_empty() && group_contains_ingested(group, ingested))
            .cloned()
            .collect::<Vec<_>>();
        if groups.is_empty() {
            return Ok(None);
        }
        let output_dir = PathBuf::from(self.preferences.texture_output_directory.trim());
        if output_dir.as_os_str().is_empty() {
            return Err(self.t().set_texture_output_before_assoc.to_owned());
        }
        fs::create_dir_all(&output_dir)
            .map_err(|error| fill(self.t().create_texture_output_fail, &[&error.to_string()]))?;
        Ok(Some(worker::AssociatedTextures {
            scan: ScanResult {
                version: 1,
                groups,
                diagnostics: Vec::new(),
            },
            settings: self.settings,
            output_dir,
            generate_dds: self.preferences.generate_dds,
            delete_tif: self.preferences.delete_tif_after_dds,
        }))
    }

    /// Apply a click on an imported-texture row to the multi-selection.
    fn apply_selection_click(&mut self, index: usize, ctrl: bool, shift: bool) {
        apply_click_selection(
            &mut self.texture.selected_files,
            &mut self.texture.selection_anchor,
            index,
            ctrl,
            shift,
        );
    }

    /// Multi-select: remove the selected imported textures and regroup. Roots are
    /// flattened to the surviving file paths so folder inputs cannot re-add the
    /// removed files on the next scan.
    fn remove_selected_textures(&mut self) {
        if self.texture.selected_files.is_empty() {
            return;
        }
        let removed = self.texture.selected_files.len();
        let remaining = self
            .texture
            .files
            .iter()
            .enumerate()
            .filter(|(index, _)| !self.texture.selected_files.contains(index))
            .map(|(_, path)| path.clone())
            .collect::<Vec<_>>();
        if remaining.is_empty() {
            self.clear_textures();
            self.status = fill(self.t().removed_textures_empty, &[&removed.to_string()]);
            return;
        }
        self.texture.roots = remaining;
        self.texture.selected_files.clear();
        self.texture.selection_anchor = None;
        self.texture.pending_import_status =
            Some(fill(self.t().removed_textures, &[&removed.to_string()]));
        self.texture.scan_receiver = Some(worker::start_scan(self.texture.roots.clone()));
        self.status = self.t().regrouping.to_owned();
    }

    /// Add Related: for the selected texture(s), pull in sibling textures of the
    /// same group from disk. Each unique directory is read exactly once and
    /// candidates are matched by filename only — no image decode at candidate
    /// stage (owner's performance red line).
    fn add_related_textures(&mut self) {
        let selected = self
            .texture
            .selected_files
            .iter()
            .filter_map(|&index| self.texture.files.get(index).cloned())
            .collect::<Vec<_>>();
        if selected.is_empty() {
            self.status = self.t().select_textures_first.to_owned();
            return;
        }
        let suffixes = match SuffixTable::embedded() {
            Ok(value) => value,
            Err(error) => {
                self.status = error.to_string();
                return;
            }
        };
        let wanted = texproc_gui::related_wanted_bases(&selected, &suffixes);
        let already = self
            .texture
            .files
            .iter()
            .map(|path| path.to_string_lossy().to_lowercase())
            .collect::<BTreeSet<_>>();
        let mut to_add = Vec::new();
        let mut dirs_scanned = 0;
        for (directory, bases) in &wanted {
            let Ok(entries) = fs::read_dir(directory) else {
                continue;
            };
            dirs_scanned += 1;
            let filenames = entries
                .filter_map(|entry| entry.ok())
                .filter_map(|entry| entry.file_name().to_str().map(str::to_owned))
                .collect::<Vec<_>>();
            to_add.extend(texproc_gui::related_matches_in_dir(
                directory, &filenames, bases, &already, &suffixes,
            ));
        }
        let added = to_add.len();
        if added == 0 {
            self.status = fill(self.t().no_related_found, &[&dirs_scanned.to_string()]);
            return;
        }
        self.texture.pending_import_status = Some(fill(
            self.t().added_related,
            &[&added.to_string(), &dirs_scanned.to_string()],
        ));
        self.add_texture_roots(to_add);
    }

    /// Pull referenced + embedded textures out of the loaded FBX and feed them
    /// into the texture groups. Shared by automatic ingestion on FBX load and
    /// the manual re-send button. Keeps the caller's tab; the scan-complete
    /// status honestly reports the FBX import via `pending_fbx_import`.
    fn ingest_entry_textures(&mut self, entry_index: usize) {
        let ingest = {
            let review = &self.model.entries[entry_index].review;
            extract_model_texture_paths(review)
        };
        match ingest {
            Ok(ingest) if ingest.paths.is_empty() => {
                self.status = self.t().no_textures_in_fbx.to_owned();
            }
            Ok(ingest) => {
                let tab = self.tab;
                self.texture.pending_fbx_import = Some((ingest.paths.len(), ingest.embedded));
                // Record ingestion origin (on this model's entry) so "Export
                // associated textures with model" can pick out exactly its groups.
                self.model.entries[entry_index].fbx_ingested.extend(
                    ingest
                        .paths
                        .iter()
                        .map(|path| path.to_string_lossy().to_lowercase()),
                );
                self.add_texture_roots(ingest.paths);
                self.tab = tab;
            }
            Err(error) => {
                self.status = error;
            }
        }
    }

    fn poll_workers(&mut self, context: &egui::Context) {
        self.poll_scan();
        self.poll_preview(context);
        self.poll_process();
        self.poll_model();
        self.poll_model_export();
        self.poll_batch_export();
        if self.texture.scan_receiver.is_some()
            || self.preview.receiver.is_some()
            || self.process.is_some()
            || !self.model.load_receivers.is_empty()
            || self.model.export_receiver.is_some()
            || self.model.batch.as_ref().is_some_and(|batch| !batch.done)
        {
            context.request_repaint_after(Duration::from_millis(80));
        }
    }

    fn poll_scan(&mut self) {
        let event =
            self.texture
                .scan_receiver
                .as_ref()
                .and_then(|receiver| match receiver.try_recv() {
                    Ok(event) => Some(event),
                    Err(TryRecvError::Empty) => None,
                    Err(TryRecvError::Disconnected) => {
                        Some(ScanEvent::Failed(self.t().scan_worker_stopped.to_owned()))
                    }
                });
        let Some(event) = event else {
            return;
        };
        self.texture.scan_receiver = None;
        match event {
            ScanEvent::Completed { scan, input_files } => {
                let groups = scan.groups.len();
                let unknown = scan
                    .groups
                    .iter()
                    .map(|group| group.unknown.len())
                    .sum::<usize>();
                self.texture.files = input_files;
                // File indices changed; drop any stale multi-selection.
                self.texture.selected_files.clear();
                self.texture.selection_anchor = None;
                self.texture.ever_unknown = scan
                    .groups
                    .iter()
                    .filter(|group| !group.unknown.is_empty())
                    .map(|group| group.key.clone())
                    .collect();
                let selected_group = scan
                    .groups
                    .iter()
                    .position(|group| !group.unknown.is_empty())
                    .or((groups > 0).then_some(0));
                self.texture.selected_group = selected_group;
                let preview_request = selected_group
                    .and_then(|index| first_group_entry(&scan.groups[index]))
                    .map(|entry| (PathBuf::from(&entry.path), entry.source_type.clone()));
                self.texture.review_only = unknown > 0;
                self.texture.document = ReviewDocument::from_scan(PathBuf::new(), scan)
                    .map_or_else(
                        |error| {
                            self.status = error;
                            None
                        },
                        Some,
                    );
                self.status = if let Some(message) = self.texture.pending_import_status.take() {
                    message
                } else if let Some((count, embedded)) = self.texture.pending_fbx_import.take() {
                    fill(
                        self.t().imported_from_fbx,
                        &[
                            &count.to_string(),
                            &embedded.to_string(),
                            &groups.to_string(),
                            &unknown.to_string(),
                        ],
                    )
                } else {
                    fill(
                        self.t().imported_textures_status,
                        &[
                            &self.texture.files.len().to_string(),
                            &groups.to_string(),
                            &unknown.to_string(),
                        ],
                    )
                };
                if let Some((path, source_type)) = preview_request {
                    self.request_preview(path, source_type);
                }
            }
            ScanEvent::Failed(error) => {
                self.status = fill(self.t().scan_failed, &[&error]);
            }
        }
    }

    fn poll_preview(&mut self, context: &egui::Context) {
        let event = self
            .preview
            .receiver
            .as_ref()
            .and_then(|receiver| receiver.try_recv().ok());
        let Some(event) = event else {
            return;
        };
        self.preview.receiver = None;
        match event {
            PreviewEvent::Completed(image)
                if self.preview.requested_path.as_ref() == Some(&image.path) =>
            {
                self.preview.texture = Some(context.load_texture(
                    "texture_preview",
                    image.color,
                    egui::TextureOptions::LINEAR,
                ));
                self.preview.loaded_path = Some(image.path);
                self.preview.dimensions = Some((image.width, image.height));
                self.preview.error = None;
            }
            PreviewEvent::Failed { path, error }
                if self.preview.requested_path.as_ref() == Some(&path) =>
            {
                self.preview.error = Some(error);
                self.preview.loaded_path = Some(path);
            }
            _ => {}
        }
    }

    fn poll_process(&mut self) {
        // Captured before the &mut self.process borrow below (t() needs &self).
        let strings = self.t();
        let Some(process) = &mut self.process else {
            return;
        };
        let mut finished = None;
        let mut worker_note = None;
        loop {
            match process.job.receiver.try_recv() {
                Ok(ProcessEvent::Progress {
                    completed,
                    total,
                    group,
                    written,
                }) => {
                    process.completed = completed;
                    process.total = total;
                    process.completed_groups.insert(group.clone());
                    process.current_group = group;
                    process.written += written;
                }
                Ok(ProcessEvent::DdsProgress {
                    completed,
                    total,
                    name,
                }) => {
                    process.dds_active = true;
                    process.dds_completed = completed;
                    process.dds_total = total;
                    process.dds_current = name;
                }
                Ok(ProcessEvent::DdsWorkers { from, to }) => {
                    process.dds_workers = to;
                    if from > 0 {
                        worker_note =
                            Some(fill(strings.rc_workers_note, &[&from.to_string(), &to.to_string()]));
                    }
                }
                Ok(ProcessEvent::Finished(result)) => {
                    finished = Some(result);
                    break;
                }
                Err(TryRecvError::Empty) => break,
                Err(TryRecvError::Disconnected) => {
                    finished = Some(Err(strings.process_worker_stopped.to_owned()));
                    break;
                }
            }
        }
        if let Some(note) = worker_note {
            self.status = note;
        }
        let Some(result) = finished else {
            return;
        };
        let output = PathBuf::from(&self.preferences.texture_output_directory);
        match result {
            Ok(complete) => {
                let report = complete.report;
                let dds = complete.dds;
                let written: usize = report.groups.iter().map(|group| group.written.len()).sum();
                let dds_note = dds.as_ref().map_or_else(String::new, |dds| {
                    let trajectory = dds
                        .n_trajectory
                        .iter()
                        .map(usize::to_string)
                        .collect::<Vec<_>>()
                        .join("→");
                    fill(
                        strings.dds_status_note,
                        &[&dds.succeeded.to_string(), &dds.total.to_string(), &trajectory],
                    )
                });
                let failed = report.failed.clone();
                let failed_note = if failed.is_empty() {
                    String::new()
                } else {
                    fill(strings.status_failed_note, &[&failed.len().to_string()])
                };
                let budget_mb = report.memory_budget_bytes / (1024 * 1024);
                self.status = if report.cancelled {
                    fill(
                        strings.processing_cancelled_status,
                        &[&report.groups.len().to_string()],
                    )
                } else {
                    fill(
                        strings.processing_complete_status,
                        &[
                            &report.groups.len().to_string(),
                            &written.to_string(),
                            &dds_note,
                            &failed_note,
                            &budget_mb.to_string(),
                            &report.waves.to_string(),
                        ],
                    )
                };
                self.process_summary = Some(ProcessSummary {
                    written,
                    groups: report.groups.len(),
                    cancelled: report.cancelled,
                    elapsed_seconds: report.elapsed_seconds,
                    output_directory: output,
                    dds,
                    failed,
                });
            }
            Err(error) => {
                self.status = fill(strings.processing_failed, &[&error]);
            }
        }
        self.process = None;
    }

    fn poll_model(&mut self) {
        if self.model.load_receivers.is_empty() {
            return;
        }
        // Drain any loads that finished this frame; keep the rest pending.
        let mut pending = Vec::new();
        let mut completed = Vec::new();
        for receiver in std::mem::take(&mut self.model.load_receivers) {
            match receiver.try_recv() {
                Ok(event) => completed.push(event),
                Err(TryRecvError::Empty) => pending.push(receiver),
                Err(TryRecvError::Disconnected) => {}
            }
        }
        self.model.load_receivers = pending;
        for event in completed {
            match event {
                ModelEvent::Completed(review) => self.add_model_entry(*review),
                ModelEvent::Failed(error) => {
                    self.status = fill(self.t().fbx_load_failed, &[&error]);
                }
            }
        }
    }

    /// Push a freshly loaded model into the list, running the per-file behaviors:
    /// physicalize seed "no" (R8), Forward/Up detection (R9), helper-node count,
    /// then auto-ingest its textures (R3).
    fn add_model_entry(&mut self, review: ModelReview) {
        let materials = review.material_slots.len();
        let references = review
            .model
            .materials
            .iter()
            .map(|material| material.textures.len())
            .sum::<usize>();
        // Seed explicit "no" physicalize for every material (item 1 default). A
        // configured manifest still wins, so only seed when no manifest is loaded.
        let physicalize_overrides = if self.preferences.manifest_path.trim().is_empty() {
            seed_default_physicalize(review.material_slots.iter().map(|s| s.name.as_str()))
        } else {
            BTreeMap::new()
        };
        // Re-detect Forward/Up per FBX (never persisted).
        let (forward, up) = parse_forward_up(&review.model.axes.forward_up_axes)
            .unwrap_or_else(|| ("-Z".to_owned(), "+Y".to_owned()));
        let conversion = ConversionSettings {
            detected_forward: forward.clone(),
            detected_up: up.clone(),
            forward,
            up,
            merge_all_nodes: false,
            scene_origin: false,
        };
        let helper_nodes = helper_node_count(&review.model);
        let index = self.model.entries.len();
        self.model.entries.push(ModelEntry {
            review,
            physicalize_overrides,
            conversion,
            selected_material: (materials > 0).then_some(0),
            selected_materials: BTreeSet::new(),
            material_selection_anchor: None,
            bulk_physicalize: DEFAULT_PHYSICALIZE.to_owned(),
            helper_nodes,
            fbx_ingested: BTreeSet::new(),
        });
        // Select the newly added model so it drives the center panel.
        self.model.selected = BTreeSet::from([index]);
        self.model.selection_anchor = Some(index);
        self.tab = WorkflowTab::Model;
        self.status = fill(
            self.t().fbx_loaded,
            &[&materials.to_string(), &references.to_string()],
        );
        // Auto-ingest this FBX's referenced + embedded textures into the groups.
        self.ingest_entry_textures(index);
    }

    fn poll_model_export(&mut self) {
        let Some(receiver) = self.model.export_receiver.as_ref() else {
            return;
        };
        let event = match receiver.try_recv() {
            Ok(event) => event,
            Err(TryRecvError::Empty) => return,
            Err(TryRecvError::Disconnected) => {
                self.model.export_receiver = None;
                return;
            }
        };
        match event {
            ModelExportEvent::Stage(stage) => {
                self.model.export_stage = stage;
            }
            ModelExportEvent::Completed(report) => {
                self.model.export_receiver = None;
                let strings = self.t();
                let rc_summary = match &report.rc {
                    RcExportOutcome::NotConfigured => {
                        self.model.rc_missing_warning = true;
                        self.status = strings.rc_not_configured_exported.to_owned();
                        strings.cgf_not_exported.to_owned()
                    }
                    RcExportOutcome::Succeeded { cgf, return_code } => {
                        self.model.rc_missing_warning = false;
                        self.model.export_cgf = Some(cgf.clone());
                        self.status =
                            fill(strings.ce_export_completed, &[&cgf.display().to_string()]);
                        fill(
                            strings.cgf_rc_exit,
                            &[&cgf.display().to_string(), &return_code.to_string()],
                        )
                    }
                    RcExportOutcome::Failed { error, return_code } => {
                        self.model.rc_missing_warning = false;
                        self.status = fill(strings.rc_export_failed_status, &[error]);
                        return_code.map_or_else(
                            || fill(strings.cgf_export_failed, &[error]),
                            |code| {
                                fill(strings.cgf_export_failed_code, &[&code.to_string(), error])
                            },
                        )
                    }
                };
                // Item 3a: the worker deletes the request JSON on full success (RC
                // produced a CGF); .mtl and .mtl.cryasset are kept.
                let request_line = if report.request_deleted {
                    strings.request_deleted.to_owned()
                } else {
                    fill(strings.request_path, &[&report.outputs.request.display().to_string()])
                };
                let textures_line = match &report.textures {
                    Some(textures) => {
                        let dds = textures.dds.as_ref().map_or_else(String::new, |dds| {
                            fill(
                                strings.assoc_dds_note,
                                &[&dds.succeeded.to_string(), &dds.total.to_string()],
                            )
                        });
                        fill(
                            strings.assoc_textures_line,
                            &[&textures.groups.to_string(), &textures.written.to_string(), &dds],
                        )
                    }
                    None => String::new(),
                };
                let summary = fill(
                    strings.export_summary_template,
                    &[
                        &report.outputs.mtl.display().to_string(),
                        &request_line,
                        &rc_summary,
                        &textures_line,
                        &report.outputs.material_diagnostics.len().to_string(),
                    ],
                );
                self.model.export_summary = Some(summary);
            }
            ModelExportEvent::Failed(error) => {
                self.model.export_receiver = None;
                self.model.export_summary = Some(fill(self.t().export_failed, &[&error]));
                self.status = fill(self.t().ce_export_failed, &[&error]);
            }
        }
    }

    fn poll_batch_export(&mut self) {
        let mut finished = None;
        {
            let Some(batch) = self.model.batch.as_mut() else {
                return;
            };
            loop {
                match batch.receiver.try_recv() {
                    Ok(BatchExportEvent::Progress {
                        index,
                        total,
                        name,
                        stage,
                    }) => {
                        batch.current = index;
                        batch.total = total;
                        batch.current_name = name;
                        batch.stage = stage;
                    }
                    Ok(BatchExportEvent::ModelDone { name, ok, detail }) => {
                        if ok {
                            batch.succeeded.push(format!("{name} — {detail}"));
                        } else {
                            batch.failed.push((name, detail));
                        }
                    }
                    Ok(BatchExportEvent::Finished) => {
                        batch.done = true;
                        finished = Some((batch.succeeded.len(), batch.failed.len()));
                        break;
                    }
                    Err(TryRecvError::Empty) => break,
                    Err(TryRecvError::Disconnected) => {
                        batch.done = true;
                        finished = Some((batch.succeeded.len(), batch.failed.len()));
                        break;
                    }
                }
            }
        }
        if let Some((succeeded, failed)) = finished {
            self.status = fill(
                self.t().batch_complete_status,
                &[&succeeded.to_string(), &failed.to_string()],
            );
        }
    }

    fn save_preferences(&mut self) {
        if let Err(error) = self.preferences.save() {
            self.status = error;
        }
    }

    /// Unwrap a single-selection dialog result, surfacing API errors in the
    /// status area. User cancel (`Ok(None)`) is a silent no-op.
    fn dialog_result(&mut self, result: Result<Option<PathBuf>, String>) -> Option<PathBuf> {
        match result {
            Ok(value) => value,
            Err(error) => {
                self.status = error;
                None
            }
        }
    }

    fn save_settings(&mut self) {
        let path = PathBuf::from(self.preferences.settings_path.trim());
        match save_texture_settings(&path, &self.settings) {
            Ok(()) => {
                self.save_preferences();
                self.status = fill(self.t().settings_saved, &[&path.display().to_string()]);
            }
            Err(error) => self.status = error.to_string(),
        }
    }

    fn load_settings(&mut self) {
        let path = PathBuf::from(self.preferences.settings_path.trim());
        match load_texture_settings(&path) {
            Ok(settings) => {
                self.settings = settings;
                self.save_preferences();
                self.status = fill(self.t().settings_loaded, &[&path.display().to_string()]);
            }
            Err(error) => self.status = error.to_string(),
        }
    }

    fn top_bar(&mut self, context: &egui::Context) {
        let t = self.t();
        egui::TopBottomPanel::top("top_bar").show(context, |ui| {
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                ui.heading(APP_TITLE);
                ui.separator();
                ui.label(t.subtitle);
                if !self.model.entries.is_empty() {
                    ui.separator();
                    ui.weak(fill(t.models_loaded, &[&self.model.entries.len().to_string()]));
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.weak(t.drop_hint);
                });
            });
            ui.add_space(6.0);
        });
    }

    fn status_bar(&mut self, context: &egui::Context) {
        let t = self.t();
        egui::TopBottomPanel::bottom("status_bar").show(context, |ui| {
            ui.horizontal(|ui| {
                ui.label(&self.status);
                if self.texture.scan_receiver.is_some()
                    || !self.model.load_receivers.is_empty()
                    || self.model.export_receiver.is_some()
                    || self.model.batch.as_ref().is_some_and(|batch| !batch.done)
                    || self.process.is_some()
                {
                    ui.spinner();
                }
                // Right-aligned clickable diagnostics chip → popover.
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let count = self.diagnostics().len();
                    let (color, text) = if count > 0 {
                        (
                            Color32::from_rgb(200, 130, 40),
                            fill(t.diag_chip_some, &[&count.to_string()]),
                        )
                    } else {
                        (Color32::from_rgb(70, 165, 95), t.diag_chip_none.to_owned())
                    };
                    if ui
                        .add(egui::Button::new(RichText::new(text).color(color)).frame(false))
                        .on_hover_text(t.show_diagnostics_hover)
                        .clicked()
                    {
                        self.show_diagnostics = !self.show_diagnostics;
                    }
                });
            });
        });
    }

    /// Transient diagnostics surfaced in the status-bar popover: unresolved
    /// texture unknowns, group conflict notes (DEF-19), RC fallback state, and
    /// FBX material-slot diagnostics.
    fn diagnostics(&self) -> Vec<DiagItem> {
        let t = self.t();
        let mut items = Vec::new();
        if let Some(document) = &self.texture.document {
            for group in &document.scan().groups {
                for entry in &group.unknown {
                    items.push(DiagItem {
                        severity: "Warning",
                        title: fill(t.diag_unknown_map_title, &[&group.base_name]),
                        message: fill(t.diag_unknown_map_msg, &[&entry.filename]),
                    });
                }
                for diagnostic in &group.diagnostics {
                    items.push(DiagItem {
                        severity: severity_label(diagnostic.severity),
                        title: format!("{} · {}", diagnostic.code, group.base_name),
                        message: diagnostic.message.clone(),
                    });
                }
            }
        }
        if let Some(review) = self
            .selected_entry_index()
            .map(|index| &self.model.entries[index].review)
        {
            let resolution = resolve_rc_path(&self.preferences.rc_path);
            if resolution.path.is_none() {
                items.push(DiagItem {
                    severity: "Warning",
                    title: t.diag_rc_not_configured_title.to_owned(),
                    message: t.rc_keep_intermediate.to_owned(),
                });
            } else if resolution.configured_invalid {
                items.push(DiagItem {
                    severity: "Warning",
                    title: t.diag_rc_invalid_title.to_owned(),
                    message: fill(t.diag_rc_invalid_msg, &[resolution.source]),
                });
            }
            for diagnostic in &review.diagnostics {
                items.push(DiagItem {
                    severity: "Info",
                    title: fill(t.diag_material_title, &[&diagnostic.material]),
                    message: diagnostic.message.clone(),
                });
            }
        }
        if let Some(summary) = self.process_summary.as_ref() {
            for failed in &summary.failed {
                items.push(DiagItem {
                    severity: "Error",
                    title: fill(t.diag_group_failed_title, &[&failed.base_name]),
                    message: failed.message.clone(),
                });
            }
            if let Some(dds) = summary.dds.as_ref() {
                for failure in &dds.failures {
                    items.push(DiagItem {
                        severity: "Error",
                        title: t.diag_dds_failed_title.to_owned(),
                        message: failure.clone(),
                    });
                }
            }
        }
        if let Some(batch) = self.model.batch.as_ref() {
            for (name, detail) in &batch.failed {
                items.push(DiagItem {
                    severity: "Error",
                    title: fill(t.diag_model_failed_title, &[name]),
                    message: detail.clone(),
                });
            }
        }
        items
    }

    fn diagnostics_popover(&mut self, context: &egui::Context) {
        if !self.show_diagnostics {
            return;
        }
        let t = self.t();
        let items = self.diagnostics();
        let mut open = true;
        egui::Window::new(t.diagnostics_title)
            .anchor(Align2::RIGHT_BOTTOM, [-8.0, -34.0])
            .resizable(false)
            .collapsible(false)
            .open(&mut open)
            .default_width(420.0)
            .show(context, |ui| {
                if items.is_empty() {
                    ui.colored_label(Color32::from_rgb(70, 165, 95), t.no_diagnostics);
                    return;
                }
                ScrollArea::vertical().max_height(300.0).show(ui, |ui| {
                    for item in &items {
                        ui.horizontal_top(|ui| {
                            let color = match item.severity {
                                "Error" => Color32::from_rgb(210, 70, 65),
                                "Warning" => Color32::from_rgb(200, 130, 40),
                                _ => Color32::from_rgb(53, 87, 183),
                            };
                            ui.label(RichText::new(item.severity).small().strong().color(color));
                            ui.vertical(|ui| {
                                ui.strong(&item.title);
                                ui.label(&item.message);
                            });
                        });
                        ui.separator();
                    }
                });
            });
        self.show_diagnostics = open;
    }

    fn process_modal(&mut self, context: &egui::Context) {
        if !self.process_modal_open {
            return;
        }
        let t = self.t();
        let mut cancel = false;
        let mut close = false;
        Modal::new(Id::new("process_modal")).show(context, |ui| {
            ui.set_width(520.0);
            if let Some(process) = &self.process {
                ui.heading(t.processing_textures_heading);
                ui.label(fill(
                    t.processing_progress,
                    &[
                        &process.completed.to_string(),
                        &process.total.to_string(),
                        &process.current_group,
                    ],
                ));
                let progress = if process.total == 0 {
                    0.0
                } else {
                    process.completed as f32 / process.total as f32
                };
                ui.add(ProgressBar::new(progress).show_percentage());
                if process.dds_active {
                    ui.add_space(6.0);
                    ui.label(fill(
                        t.dds_compiling,
                        &[
                            &process.dds_completed.to_string(),
                            &process.dds_total.to_string(),
                            &process.dds_current,
                            &process.dds_workers.to_string(),
                        ],
                    ));
                    let dds_progress = if process.dds_total == 0 {
                        0.0
                    } else {
                        process.dds_completed as f32 / process.dds_total as f32
                    };
                    ui.add(ProgressBar::new(dds_progress).show_percentage());
                }
                ui.add_space(6.0);
                ScrollArea::vertical()
                    .max_height(280.0)
                    .auto_shrink([false, false])
                    .show(ui, |ui| {
                        for name in &process.group_names {
                            ui.horizontal(|ui| {
                                if process.completed_groups.contains(name) {
                                    ui.colored_label(Color32::from_rgb(70, 165, 95), "✓");
                                    ui.label(name);
                                } else {
                                    ui.weak("•");
                                    ui.weak(name);
                                }
                            });
                        }
                    });
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    cancel = ui.button(t.cancel).clicked();
                });
            } else if let Some(summary) = &self.process_summary {
                ui.heading(if summary.cancelled {
                    t.processing_cancelled_heading
                } else {
                    t.processing_complete_heading
                });
                ui.label(fill(
                    t.processing_summary,
                    &[
                        &summary.groups.to_string(),
                        &summary.written.to_string(),
                        &format!("{:.2}", summary.elapsed_seconds),
                    ],
                ));
                if !summary.failed.is_empty() {
                    ui.colored_label(
                        Color32::from_rgb(210, 70, 65),
                        fill(t.groups_failed_summary, &[&summary.failed.len().to_string()]),
                    );
                }
                if let Some(dds) = &summary.dds {
                    let color = if dds.failures.is_empty() {
                        Color32::from_rgb(70, 165, 95)
                    } else {
                        Color32::from_rgb(200, 130, 40)
                    };
                    ui.colored_label(
                        color,
                        fill(
                            t.dds_compiled_summary,
                            &[&dds.succeeded.to_string(), &dds.total.to_string()],
                        ),
                    );
                    if !dds.failures.is_empty() {
                        ui.label(fill(t.dds_failed_note, &[&dds.failures.len().to_string()]));
                    }
                }
                ui.add_space(6.0);
                ui.hyperlink_to(t.open_output_folder, file_url(&summary.output_directory));
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    close = ui.button(t.close).clicked();
                });
            } else {
                close = true;
            }
        });
        if cancel {
            if let Some(process) = &self.process {
                process.job.cancel.store(true, Ordering::Relaxed);
                self.status = t.cancelling_process.to_owned();
            }
        }
        if close {
            self.process_modal_open = false;
        }
    }

    fn export_modal(&mut self, context: &egui::Context) {
        if !self.model.export_modal_open {
            return;
        }
        let t = self.t();
        let running = self.model.export_receiver.is_some();
        let mut close = false;
        Modal::new(Id::new("export_modal")).show(context, |ui| {
            ui.set_width(520.0);
            if running {
                ui.heading(t.exporting_ce_model_heading);
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(&self.model.export_stage);
                });
                ui.add_space(6.0);
                if self.preferences.export_associated_textures {
                    ui.weak(t.export_pipeline_with_textures);
                } else {
                    ui.weak(t.export_pipeline);
                }
            } else if let Some(summary) = &self.model.export_summary {
                ui.heading(t.ce_model_export);
                ui.label(summary);
                ui.add_space(6.0);
                if let Some(cgf) = &self.model.export_cgf {
                    ui.label(format!("CGF: {}", cgf.display()));
                }
                ui.hyperlink_to(
                    t.open_output_folder,
                    file_url(Path::new(&self.preferences.model_output_directory)),
                );
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    close = ui.button(t.close).clicked();
                });
            } else {
                close = true;
            }
        });
        if close {
            self.model.export_modal_open = false;
        }
    }

    fn batch_modal(&mut self, context: &egui::Context) {
        let t = self.t();
        let Some(batch) = self.model.batch.as_ref() else {
            return;
        };
        if !batch.modal_open {
            return;
        }
        let mut cancel = false;
        let mut close = false;
        let model_output = self.preferences.model_output_directory.clone();
        Modal::new(Id::new("batch_modal")).show(context, |ui| {
            ui.set_width(560.0);
            if !batch.done {
                ui.heading(t.exporting_models_heading);
                ui.label(fill(
                    t.batch_model_progress,
                    &[
                        &batch.current.max(1).to_string(),
                        &batch.total.to_string(),
                        &batch.current_name,
                    ],
                ));
                ui.label(&batch.stage);
                let progress = if batch.total == 0 {
                    0.0
                } else {
                    batch.current.saturating_sub(1) as f32 / batch.total as f32
                };
                ui.add(ProgressBar::new(progress).show_percentage());
                ui.add_space(6.0);
                ui.label(fill(
                    t.batch_done_failed,
                    &[&batch.succeeded.len().to_string(), &batch.failed.len().to_string()],
                ));
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    cancel = ui.button(t.cancel).clicked();
                });
            } else {
                ui.heading(t.export_all_complete_heading);
                ui.label(fill(
                    t.succeeded_failed,
                    &[&batch.succeeded.len().to_string(), &batch.failed.len().to_string()],
                ));
                ui.add_space(6.0);
                ScrollArea::vertical().max_height(300.0).show(ui, |ui| {
                    for ok in &batch.succeeded {
                        ui.horizontal(|ui| {
                            ui.colored_label(Color32::from_rgb(70, 165, 95), "✓");
                            ui.label(ok);
                        });
                    }
                    for (name, detail) in &batch.failed {
                        ui.horizontal_top(|ui| {
                            ui.colored_label(Color32::from_rgb(210, 70, 65), "✗");
                            ui.label(format!("{name}: {detail}"));
                        });
                    }
                });
                ui.add_space(6.0);
                ui.hyperlink_to(t.open_output_folder, file_url(Path::new(&model_output)));
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    close = ui.button(t.close).clicked();
                });
            }
        });
        if cancel {
            if let Some(batch) = self.model.batch.as_ref() {
                batch.cancel.store(true, Ordering::Relaxed);
            }
            self.status = t.cancelling_batch.to_owned();
        }
        if close {
            if let Some(batch) = self.model.batch.as_mut() {
                batch.modal_open = false;
            }
        }
    }

    fn left_panel(&mut self, context: &egui::Context) {
        egui::SidePanel::left("imports")
            .resizable(true)
            .default_width(320.0)
            .min_width(270.0)
            .max_width(430.0)
            .show(context, |ui| {
                let t = self.t();
                ui.horizontal(|ui| {
                    ui.selectable_value(&mut self.tab, WorkflowTab::Textures, t.tab_texture_import);
                    ui.selectable_value(&mut self.tab, WorkflowTab::Model, t.tab_model_import);
                });
                ui.separator();
                match self.tab {
                    WorkflowTab::Textures => self.texture_import_panel(ui),
                    WorkflowTab::Model => self.model_import_panel(ui),
                }
            });
    }

    fn texture_import_panel(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.heading(t.texture_import);
        ui.label(t.texture_import_desc);
        ui.add_space(6.0);
        ui.add(
            TextEdit::singleline(&mut self.preferences.import_path).hint_text(t.texture_path_hint),
        );
        ui.horizontal_wrapped(|ui| {
            if ui.button(t.add_files).clicked() {
                match choose_files_multi(t.dlg_select_texture_files, IMAGE_FILTER) {
                    Ok(files) if !files.is_empty() => self.add_texture_roots(files),
                    Ok(_) => {}
                    Err(error) => self.status = error,
                }
            }
            if ui.button(t.add_folder).clicked() {
                let initial = self.preferences.import_path.clone();
                if let Some(folder) =
                    self.dialog_result(choose_folder(t.dlg_select_texture_folder, &initial))
                {
                    self.add_texture_roots(vec![folder]);
                }
            }
            if ui.button(t.add_path).clicked() {
                let paths = split_paths(&self.preferences.import_path)
                    .into_iter()
                    .filter(|path| path.exists())
                    .collect::<Vec<_>>();
                self.add_texture_roots(paths);
            }
            if ui.button(t.clear_all).clicked() {
                self.clear_textures();
            }
            let has_selection = !self.texture.selected_files.is_empty();
            if ui
                .add_enabled(has_selection, egui::Button::new(t.remove_selected))
                .clicked()
            {
                self.remove_selected_textures();
            }
            if ui
                .add_enabled(has_selection, egui::Button::new(t.add_related))
                .on_hover_text(t.add_related_hover)
                .clicked()
            {
                self.add_related_textures();
            }
        });
        if self.texture.scan_receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label(t.scanning);
            });
        }
        ui.add_space(8.0);
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(fill(
                t.imported_textures_count,
                &[
                    &self.texture.files.len().to_string(),
                    &self.texture.selected_files.len().to_string(),
                ],
            ));
            ui.weak(t.multi_select_hint);
            ui.separator();
            let modifiers = ui.input(|input| input.modifiers);
            let mut clicked = None;
            ScrollArea::vertical()
                .id_salt("imported_texture_list")
                .max_height(ui.available_height() - 80.0)
                .show(ui, |ui| {
                    for (index, path) in self.texture.files.iter().enumerate() {
                        let label = path
                            .file_name()
                            .and_then(|name| name.to_str())
                            .unwrap_or_default();
                        if ui
                            .selectable_label(self.texture.selected_files.contains(&index), label)
                            .on_hover_text(path.display().to_string())
                            .clicked()
                        {
                            clicked = Some((index, path.clone()));
                        }
                    }
                });
            if let Some((index, path)) = clicked {
                self.apply_selection_click(index, modifiers.ctrl, modifiers.shift);
                let source_type = source_type_for_path(self.texture.document.as_ref(), &path);
                self.request_preview(path, source_type);
            }
        });
    }

    fn model_import_panel(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.heading(t.model_import);
        ui.label(t.model_import_desc);
        ui.add_space(6.0);
        ui.add(TextEdit::singleline(&mut self.preferences.model_path).hint_text(t.fbx_path_hint));
        ui.horizontal_wrapped(|ui| {
            if ui.button(t.add_fbx).clicked() {
                match choose_files_multi(t.dlg_select_fbx_files, FBX_FILTER) {
                    Ok(files) if !files.is_empty() => self.load_model_files(files),
                    Ok(_) => {}
                    Err(error) => self.status = error,
                }
            }
            if ui.button(t.add_path).clicked() {
                let paths = split_paths(&self.preferences.model_path)
                    .into_iter()
                    .filter(|path| path.exists())
                    .collect::<Vec<_>>();
                if paths.is_empty() {
                    self.status = t.enter_fbx_path_first.to_owned();
                } else {
                    self.load_model_files(paths);
                }
            }
            if ui.button(t.clear_all).clicked() {
                self.clear_models();
            }
            let has_selection = !self.model.selected.is_empty();
            if ui
                .add_enabled(has_selection, egui::Button::new(t.remove_selected))
                .clicked()
            {
                self.remove_selected_models();
            }
        });
        if !self.model.load_receivers.is_empty() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label(fill(
                    t.loading_models,
                    &[&self.model.load_receivers.len().to_string()],
                ));
            });
        }
        ui.add_space(8.0);
        // Model list — same visual pattern as the Imported Textures list.
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(fill(
                t.loaded_models_count,
                &[
                    &self.model.entries.len().to_string(),
                    &self.model.selected.len().to_string(),
                ],
            ));
            ui.weak(t.multi_select_hint);
            ui.separator();
            let modifiers = ui.input(|input| input.modifiers);
            let mut clicked = None;
            ScrollArea::vertical()
                .id_salt("model_list")
                .max_height(230.0)
                .show(ui, |ui| {
                    for (index, entry) in self.model.entries.iter().enumerate() {
                        let name = entry
                            .review
                            .path
                            .file_name()
                            .and_then(|value| value.to_str())
                            .unwrap_or("FBX");
                        if ui
                            .selectable_label(self.model.selected.contains(&index), name)
                            .on_hover_text(entry.review.path.display().to_string())
                            .clicked()
                        {
                            clicked = Some(index);
                        }
                        let diagnostics = entry.review.diagnostics.len();
                        ui.horizontal(|ui| {
                            ui.add_space(4.0);
                            badge(
                                ui,
                                fill(t.badge_mat, &[&entry.review.material_slots.len().to_string()]),
                                Color32::from_rgb(70, 110, 190),
                            );
                            badge(
                                ui,
                                fill(t.badge_diag, &[&diagnostics.to_string()]),
                                if diagnostics > 0 {
                                    Color32::from_rgb(200, 130, 40)
                                } else {
                                    Color32::from_rgb(110, 110, 115)
                                },
                            );
                            badge(
                                ui,
                                fill(t.badge_helper, &[&entry.helper_nodes.to_string()]),
                                Color32::from_rgb(110, 110, 115),
                            );
                        });
                    }
                });
            if let Some(index) = clicked {
                apply_click_selection(
                    &mut self.model.selected,
                    &mut self.model.selection_anchor,
                    index,
                    modifiers.ctrl,
                    modifiers.shift,
                );
            }
        });
        ui.add_space(8.0);
        if let Some(index) = self.selected_entry_index() {
            self.model_summary(ui, index);
            ui.add_space(8.0);
            self.conversion_settings(ui, index);
            ui.add_space(8.0);
            if ui.button(t.resend_textures).clicked() {
                self.ingest_entry_textures(index);
            }
        } else if self.model.entries.is_empty() {
            ui.weak(t.no_models_loaded);
        } else {
            ui.weak(t.select_single_model);
        }
    }

    /// Per-model summary shown under the list for the single selected model.
    fn model_summary(&self, ui: &mut egui::Ui, index: usize) {
        let t = self.t();
        let entry = &self.model.entries[index];
        let review = &entry.review;
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(
                review
                    .path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or("FBX"),
            );
            ui.label(fill(t.summary_material_slots, &[&review.material_slots.len().to_string()]));
            ui.label(fill(t.summary_meshes, &[&review.model.meshes.len().to_string()]));
            ui.label(fill(t.summary_nodes, &[&review.model.node_count.to_string()]));
            ui.label(fill(t.summary_helper_nodes, &[&entry.helper_nodes.to_string()]));
            ui.label(fill(t.summary_diagnostics, &[&review.diagnostics.len().to_string()]));
            let axes = &review.model.axes;
            if axes.declared {
                ui.label(axes.summary());
            } else {
                ui.colored_label(Color32::from_rgb(0xE0, 0xA0, 0x30), axes.summary())
                    .on_hover_text(t.axes_undeclared_hover);
            }
        });
    }

    /// Conversion Settings panel (R9 item 2): Sandbox-mirror RC import fields for
    /// the selected model. Forward/Up are per-model; Unit/Scale stay global prefs.
    /// Manual values win over auto-detection when the request is built.
    fn conversion_settings(&mut self, ui: &mut egui::Ui, index: usize) {
        // Take the entry's conversion out so we can freely touch self.preferences
        // (Unit/Scale + save) without a borrow conflict, then write it back.
        let mut conv = std::mem::take(&mut self.model.entries[index].conversion);
        let t = self.t();
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(t.conversion_settings_heading);

            // Unit (persisted) + Scale (persisted).
            ui.horizontal(|ui| {
                ui.label(t.unit_label);
                let mut unit_changed = false;
                egui::ComboBox::from_id_salt("conversion_unit")
                    .selected_text(&self.preferences.conversion_unit)
                    .show_ui(ui, |ui| {
                        for value in UNIT_SIZE_VALUES {
                            if ui
                                .selectable_value(
                                    &mut self.preferences.conversion_unit,
                                    value.to_owned(),
                                    value,
                                )
                                .changed()
                            {
                                unit_changed = true;
                            }
                        }
                    });
                if unit_changed {
                    self.save_preferences();
                }
            });
            ui.horizontal(|ui| {
                ui.label(t.scale_label);
                if ui
                    .add(
                        egui::DragValue::new(&mut self.preferences.conversion_scale)
                            .speed(0.01)
                            .range(0.0001..=100_000.0),
                    )
                    .changed()
                {
                    self.save_preferences();
                }
            });

            // Forward / Up (re-detected per FBX, not persisted). A value that
            // differs from detection is marked as an override.
            let detected = compose_forward_up(&conv.detected_forward, &conv.detected_up);
            axis_dropdown(ui, t.forward_label, "conversion_forward", &mut conv.forward);
            axis_dropdown(ui, t.up_label, "conversion_up", &mut conv.up);
            let current = compose_forward_up(&conv.forward, &conv.up);
            ui.horizontal(|ui| {
                ui.weak(fill(t.detected_axes, &[&detected]));
                if current != detected {
                    ui.colored_label(
                        Color32::from_rgb(0xE0, 0xA0, 0x30),
                        fill(t.axis_override, &[&current]),
                    );
                }
            });
            if axes_parallel(&conv.forward, &conv.up) {
                ui.colored_label(Color32::from_rgb(210, 70, 65), t.axes_parallel_warning);
            }

            ui.checkbox(&mut conv.merge_all_nodes, t.merge_all_nodes);
            ui.checkbox(&mut conv.scene_origin, t.scene_origin);
        });
        self.model.entries[index].conversion = conv;
    }

    fn right_panel(&mut self, context: &egui::Context) {
        egui::SidePanel::right("export_settings")
            .resizable(true)
            .default_width(380.0)
            .min_width(340.0)
            .max_width(480.0)
            .show(context, |ui| {
                // Action buttons stay pinned at the bottom; settings scroll above.
                egui::TopBottomPanel::bottom("right_actions").show_inside(ui, |ui| {
                    ui.add_space(6.0);
                    self.right_actions(ui);
                    ui.add_space(2.0);
                });
                egui::CentralPanel::default().show_inside(ui, |ui| {
                    ui.add_space(4.0);
                    ui.heading(self.t().output_settings_heading);
                    ui.add_space(2.0);
                    ScrollArea::vertical().show(ui, |ui| {
                        self.language_selector(ui);
                        ui.separator();
                        self.output_directory_fields(ui);
                        ui.separator();
                        self.common_settings(ui);
                        self.advanced_settings(ui);
                        ui.separator();
                        self.model_export_inputs(ui);
                        ui.separator();
                        self.settings_file_inputs(ui);
                    });
                });
            });
    }

    fn right_actions(&mut self, ui: &mut egui::Ui) {
        self.texture_actions(ui);
        ui.add_space(6.0);
        self.model_export_action(ui);
        ui.separator();
        let t = self.t();
        ui.horizontal(|ui| {
            if ui.button(t.save_settings_btn).clicked() {
                self.save_settings();
            }
            if ui.button(t.load_settings_btn).clicked() {
                self.load_settings();
            }
        });
    }

    /// Language combo. egui is immediate-mode, so a switch re-renders the whole
    /// UI with the new strings on the next frame.
    fn language_selector(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        let current = Language::from_code(&self.preferences.language);
        ui.horizontal(|ui| {
            ui.label(t.language_label);
            ComboBox::from_id_salt("language")
                .selected_text(current.endonym())
                .show_ui(ui, |ui| {
                    for language in [Language::En, Language::ZhCn] {
                        if ui
                            .selectable_label(language == current, language.endonym())
                            .clicked()
                        {
                            self.preferences.language = language.code().to_owned();
                            self.save_preferences();
                        }
                    }
                });
        });
    }

    fn output_directory_fields(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.strong(t.texture_output_dir);
        let (mut changed, browse) = path_row(
            ui,
            "texture_output",
            &mut self.preferences.texture_output_directory,
            r"C:\output\textures",
            t.browse,
        );
        if browse {
            let initial = self.preferences.texture_output_directory.clone();
            if let Some(folder) =
                self.dialog_result(choose_folder(t.dlg_select_texture_output, &initial))
            {
                self.preferences.texture_output_directory = folder.to_string_lossy().into_owned();
                changed = true;
            }
        }
        if changed {
            self.save_preferences();
        }
        ui.add_space(5.0);
        ui.strong(t.model_output_dir);
        let (mut changed, browse) = path_row(
            ui,
            "model_output",
            &mut self.preferences.model_output_directory,
            r"C:\output\model",
            t.browse,
        );
        if browse {
            let initial = self.preferences.model_output_directory.clone();
            if let Some(folder) =
                self.dialog_result(choose_folder(t.dlg_select_model_output, &initial))
            {
                self.preferences.model_output_directory = folder.to_string_lossy().into_owned();
                changed = true;
            }
        }
        if changed {
            self.save_preferences();
        }
    }

    fn common_settings(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        Grid::new("primary_texture_settings")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label(t.output_resolution_label);
                ComboBox::from_id_salt("resolution")
                    .selected_text(resolution_label(self.settings.output_resolution))
                    .show_ui(ui, |ui| {
                        for (label, value) in [
                            ("Original", OutputResolution::Original),
                            ("4096", OutputResolution::Max(4096)),
                            ("2048", OutputResolution::Max(2048)),
                            ("1024", OutputResolution::Max(1024)),
                            ("512", OutputResolution::Max(512)),
                            ("256", OutputResolution::Max(256)),
                        ] {
                            ui.selectable_value(&mut self.settings.output_resolution, value, label);
                        }
                    });
                ui.end_row();
                ui.label(t.diffuse_format_label);
                ComboBox::from_id_salt("diff_format")
                    .selected_text(match self.settings.diff_format {
                        DiffFormat::Albedo => "albedo",
                        DiffFormat::DiffuseAo => "diffuse_ao",
                    })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(
                            &mut self.settings.diff_format,
                            DiffFormat::Albedo,
                            "albedo",
                        );
                        ui.selectable_value(
                            &mut self.settings.diff_format,
                            DiffFormat::DiffuseAo,
                            "diffuse_ao",
                        );
                    });
                ui.end_row();
            });
        ui.checkbox(&mut self.settings.normal_flip_green, t.flip_normal_green);
        ui.checkbox(&mut self.settings.process_metallic, t.convert_metallic);
        ui.checkbox(&mut self.settings.generate_missing_spec, t.generate_missing_spec);
        let rc_available = resolve_rc_path(&self.preferences.rc_path).path.is_some();
        if rc_available {
            if ui
                .checkbox(&mut self.preferences.generate_dds, t.generate_dds)
                .changed()
            {
                self.save_preferences();
            }
        } else {
            self.preferences.generate_dds = false;
            ui.add_enabled_ui(false, |ui| {
                let mut off = false;
                ui.checkbox(&mut off, t.generate_dds);
            })
            .response
            .on_hover_text(t.rc_not_configured);
        }
        if ui
            .checkbox(&mut self.preferences.delete_tif_after_dds, t.delete_tif)
            .on_hover_text(t.delete_tif_hover)
            .changed()
        {
            self.save_preferences();
        }
    }

    fn advanced_settings(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.collapsing(t.advanced_heading, |ui| {
            ui.strong(t.output_texture_types);
            Grid::new("texture_type_toggles")
                .num_columns(2)
                .show(ui, |ui| {
                    ui.checkbox(&mut self.settings.texture_types.diff, t.tt_diff);
                    ui.checkbox(&mut self.settings.texture_types.spec, t.tt_spec);
                    ui.end_row();
                    ui.checkbox(&mut self.settings.texture_types.ddna, t.tt_ddna);
                    ui.checkbox(&mut self.settings.texture_types.displ, t.tt_displ);
                    ui.end_row();
                    ui.checkbox(&mut self.settings.texture_types.emissive, t.tt_emissive);
                    ui.checkbox(&mut self.settings.texture_types.sss, t.tt_sss);
                    ui.end_row();
                });
            ui.add_space(6.0);
            ui.checkbox(&mut self.settings.normalize_height, t.normalize_height);
            ui.checkbox(&mut self.settings.dither, t.dither);
            ui.checkbox(
                &mut self.settings.generate_missing_emissive,
                t.generate_missing_emissive,
            );
            ui.checkbox(&mut self.settings.generate_missing_sss, t.generate_missing_sss);
            ui.checkbox(
                &mut self.settings.generate_sss_from_diffuse,
                t.generate_sss_from_diffuse,
            );
            ui.add_space(6.0);
            // "Metal Gate" is a proper feature name — untranslated per policy.
            ui.checkbox(&mut self.settings.metal_gate, "Metal Gate")
                .on_hover_text(t.metal_gate_hover);
            Grid::new("advanced_texture_settings")
                .num_columns(2)
                .show(ui, |ui| {
                    ui.label(t.arm_order_label);
                    ComboBox::from_id_salt("arm_order")
                        .selected_text(match self.settings.arm_order {
                            ArmOrder::Arm => "ARM",
                            ArmOrder::Orm => "ORM",
                            ArmOrder::Rma => "RMA",
                        })
                        .show_ui(ui, |ui| {
                            ui.selectable_value(&mut self.settings.arm_order, ArmOrder::Arm, "ARM");
                            ui.selectable_value(&mut self.settings.arm_order, ArmOrder::Orm, "ORM");
                            ui.selectable_value(&mut self.settings.arm_order, ArmOrder::Rma, "RMA");
                        });
                    ui.end_row();
                    ui.label(t.height_normal_strength);
                    ui.add(
                        egui::DragValue::new(&mut self.settings.normal_from_height_strength)
                            .speed(0.1)
                            .range(0.0..=100.0),
                    );
                    ui.end_row();
                    ui.label(t.emissive_brightness_label);
                    ui.add(
                        egui::DragValue::new(&mut self.settings.emissive_brightness)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label(t.sss_intensity_label);
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_intensity)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label(t.sss_contrast_label);
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_contrast)
                            .speed(0.05)
                            .range(0.0..=5.0),
                    );
                    ui.end_row();

                    ui.add_enabled_ui(self.settings.metal_gate, |ui| {
                        Grid::new("metal_gate_settings")
                            .num_columns(2)
                            .show(ui, |ui| {
                                ui.label(t.mg_metallic_cut);
                                ui.add(
                                    egui::DragValue::new(
                                        &mut self.settings.metal_gate_metallic_cut,
                                    )
                                    .speed(0.01)
                                    .range(0.0..=1.0),
                                );
                                ui.end_row();
                                ui.label(t.mg_spec_min);
                                ui.add(
                                    egui::DragValue::new(&mut self.settings.metal_gate_spec_min)
                                        .speed(0.01)
                                        .range(0.0..=1.0),
                                );
                                ui.end_row();
                                ui.label(t.mg_gloss_cut);
                                ui.add(
                                    egui::DragValue::new(&mut self.settings.metal_gate_gloss_cut)
                                        .speed(0.01)
                                        .range(0.0..=1.0),
                                );
                                ui.end_row();
                                ui.label(t.mg_transition);
                                ui.add(
                                    egui::DragValue::new(&mut self.settings.metal_gate_transition)
                                        .speed(0.01)
                                        .range(0.0..=0.5),
                                );
                                ui.end_row();
                            });
                    });
                    ui.end_row();
                });
        });
    }

    fn settings_file_inputs(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.strong(t.settings_file_label);
        let (_, browse) = path_row(
            ui,
            "settings_path",
            &mut self.preferences.settings_path,
            "texproc-settings.json",
            t.browse,
        );
        if browse {
            let initial = self.preferences.settings_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                t.dlg_select_settings,
                JSON_FILTER,
                &initial,
            )) {
                self.preferences.settings_path = path.to_string_lossy().into_owned();
                self.load_settings();
            }
        }
        if ui.button(t.save_as).clicked() {
            let default_name = Path::new(self.preferences.settings_path.trim())
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("texproc-settings.json")
                .to_owned();
            if let Some(path) = self.dialog_result(choose_file_save(
                t.dlg_save_settings_as,
                JSON_FILTER,
                &default_name,
            )) {
                self.preferences.settings_path = path.to_string_lossy().into_owned();
                self.save_settings();
            }
        }
    }

    fn texture_actions(&mut self, ui: &mut egui::Ui) {
        let group_count = self
            .texture
            .document
            .as_ref()
            .map_or(0, |document| document.scan().groups.len());
        let unknown = self
            .texture
            .document
            .as_ref()
            .map_or(0, ReviewDocument::unresolved_unknown_count);
        let t = self.t();
        ui.label(fill(
            t.groups_unknown_count,
            &[&group_count.to_string(), &unknown.to_string()],
        ));
        let processing = self.process.is_some();
        if ui
            .add_enabled(
                !processing && group_count > 0,
                egui::Button::new(RichText::new(t.process_textures_btn).strong().size(18.0))
                    .min_size([ui.available_width(), 42.0].into()),
            )
            .clicked()
        {
            self.start_texture_process();
        }
        if processing && ui.button(t.show_progress).clicked() {
            self.process_modal_open = true;
        }
        if let Some(summary) = &self.process_summary {
            if !self.process_modal_open {
                ui.hyperlink_to(t.open_output_folder, file_url(&summary.output_directory));
            }
        }
    }

    fn model_export_inputs(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.strong(t.ce_model_export);
        ui.label(t.optional_manifest);
        let (mut changed, browse) = path_row(
            ui,
            "manifest_path",
            &mut self.preferences.manifest_path,
            t.hint_manifest,
            t.browse,
        );
        if browse {
            let initial = self.preferences.manifest_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                t.dlg_select_manifest,
                JSON_FILTER,
                &initial,
            )) {
                self.preferences.manifest_path = path.to_string_lossy().into_owned();
                changed = true;
            }
        }
        ui.label(t.optional_overrides);
        let (overrides_changed, overrides_browse) = path_row(
            ui,
            "overrides_path",
            &mut self.preferences.overrides_path,
            t.hint_overrides,
            t.browse,
        );
        changed |= overrides_changed;
        if overrides_browse {
            let initial = self.preferences.overrides_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                t.dlg_select_overrides,
                JSON_FILTER,
                &initial,
            )) {
                self.preferences.overrides_path = path.to_string_lossy().into_owned();
                changed = true;
            }
        }
        if changed {
            self.save_preferences();
        }
        if ui
            .checkbox(&mut self.preferences.export_associated_textures, t.export_associated)
            .on_hover_text(t.export_associated_hover)
            .changed()
        {
            self.save_preferences();
        }
        if ui
            .checkbox(&mut self.preferences.delete_request_json, t.delete_request_json)
            .on_hover_text(t.delete_request_hover)
            .changed()
        {
            self.save_preferences();
        }
        self.rc_path_field(ui);
    }

    fn model_export_action(&mut self, ui: &mut egui::Ui) {
        let single_ok = self.selected_entry_index().is_some_and(|index| {
            let conv = &self.model.entries[index].conversion;
            !axes_parallel(&conv.forward, &conv.up)
        });
        let exporting = self.model.export_receiver.is_some()
            || self.model.batch.as_ref().is_some_and(|batch| !batch.done);
        let t = self.t();
        if ui
            .add_enabled(
                single_ok && !exporting,
                egui::Button::new(RichText::new(t.export_ce_model_btn).strong().size(16.0))
                    .min_size([ui.available_width(), 36.0].into()),
            )
            .on_hover_text(t.export_ce_model_hover)
            .clicked()
        {
            self.save_preferences();
            self.start_model_export();
        }
        if ui
            .add_enabled(
                !self.model.entries.is_empty() && !exporting,
                egui::Button::new(RichText::new(t.export_all_btn).strong().size(16.0))
                    .min_size([ui.available_width(), 34.0].into()),
            )
            .on_hover_text(t.export_all_hover)
            .clicked()
        {
            self.save_preferences();
            self.start_batch_export();
        }
        if self.model.export_receiver.is_some() && ui.button(t.show_export_progress).clicked() {
            self.model.export_modal_open = true;
        }
        if self.model.batch.is_some() && ui.button(t.show_batch_progress).clicked() {
            if let Some(batch) = self.model.batch.as_mut() {
                batch.modal_open = true;
            }
        }
    }

    fn rc_path_field(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.label(t.rc_path_label);
        let resolution = resolve_rc_path(&self.preferences.rc_path);
        let invalid = resolution.configured_invalid || resolution.path.is_none();
        let stroke = if invalid {
            Stroke::new(1.5, Color32::from_rgb(210, 70, 65))
        } else {
            ui.visuals().widgets.inactive.bg_stroke
        };
        let mut changed = false;
        let mut browse = false;
        ui.horizontal(|ui| {
            egui::Frame::new()
                .stroke(stroke)
                .inner_margin(egui::Margin::same(2))
                .show(ui, |ui| {
                    changed = ui
                        .add(
                            TextEdit::singleline(&mut self.preferences.rc_path)
                                .desired_width((ui.available_width() - 74.0).max(120.0))
                                .hint_text(r"C:\CryEngine\Tools\rc\rc.exe"),
                        )
                        .changed();
                });
            browse = ui.button(t.browse).clicked();
        });
        if browse {
            match choose_rc_executable(&self.preferences.rc_path) {
                Ok(Some(path)) => {
                    self.preferences.rc_path = path.to_string_lossy().into_owned();
                    changed = true;
                }
                Ok(None) => {}
                Err(error) => {
                    self.status = error;
                }
            }
        }
        if changed {
            self.save_preferences();
        }

        let resolution = resolve_rc_path(&self.preferences.rc_path);
        if resolution.configured_invalid {
            ui.label(
                RichText::new(match (&resolution.path, resolution.source) {
                    (Some(path), source) => {
                        fill(t.rc_invalid_using, &[source, &path.display().to_string()])
                    }
                    (None, _) => t.rc_not_configured_full.to_owned(),
                })
                .color(Color32::from_rgb(210, 70, 65)),
            );
        } else if let Some(path) = &resolution.path {
            ui.weak(fill(t.rc_using, &[resolution.source, &path.display().to_string()]));
        } else {
            ui.label(RichText::new(t.rc_not_configured_full).color(Color32::from_rgb(210, 70, 65)));
        }
    }

    fn central_panel(&mut self, context: &egui::Context) {
        egui::CentralPanel::default().show(context, |ui| {
            egui::TopBottomPanel::top("preview_pane")
                .resizable(true)
                .default_height(300.0)
                .min_height(150.0)
                .show_inside(ui, |ui| self.preview_panel(ui));
            egui::CentralPanel::default().show_inside(ui, |ui| match self.tab {
                WorkflowTab::Textures => self.groups_panel(ui),
                WorkflowTab::Model => self.model_workspace(ui),
            });
        });
    }

    fn preview_panel(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.strong(t.preview_heading);
            if let Some(path) = self
                .preview
                .loaded_path
                .as_ref()
                .or(self.preview.requested_path.as_ref())
            {
                ui.separator();
                ui.label(
                    path.file_name()
                        .and_then(|name| name.to_str())
                        .unwrap_or_default(),
                );
                if !self.preview.source_type.is_empty() {
                    ui.separator();
                    ui.weak(&self.preview.source_type);
                }
                if let Some((width, height)) = self.preview.dimensions {
                    ui.separator();
                    ui.weak(format!("{width} × {height}"));
                }
            }
            if self.preview.receiver.is_some() {
                ui.spinner();
            }
        });
        // Map badges for the selected group (which slots are filled).
        if self.tab == WorkflowTab::Textures {
            if let Some(group) = self
                .texture
                .selected_group
                .zip(self.texture.document.as_ref())
                .and_then(|(index, document)| document.scan().groups.get(index))
            {
                ui.horizontal_wrapped(|ui| {
                    ui.strong(&group.base_name);
                    for source_type in ASSIGNABLE_SOURCE_TYPES {
                        if group.slots.contains_key(source_type) {
                            ui.label(
                                RichText::new(source_type)
                                    .small()
                                    .color(Color32::WHITE)
                                    .background_color(Color32::from_rgb(70, 110, 190)),
                            );
                        }
                    }
                    if !group.unknown.is_empty() {
                        ui.label(
                            RichText::new(fill(t.unknown_badge, &[&group.unknown.len().to_string()]))
                                .small()
                                .strong()
                                .color(Color32::WHITE)
                                .background_color(Color32::from_rgb(200, 130, 40)),
                        );
                    }
                });
            }
        }
        ui.add_space(4.0);
        let available = egui::vec2(
            ui.available_width(),
            (ui.available_height() - 6.0).max(120.0),
        );
        if let Some(texture) = &self.preview.texture {
            let source = texture.size_vec2();
            let scale = (available.x / source.x)
                .min(available.y / source.y)
                .min(1.0);
            ui.allocate_ui_with_layout(
                available,
                egui::Layout::centered_and_justified(egui::Direction::TopDown),
                |ui| {
                    ui.add(egui::Image::new(texture).fit_to_exact_size(source * scale));
                },
            );
        } else if let Some(error) = &self.preview.error {
            ui.allocate_ui_with_layout(
                available,
                egui::Layout::centered_and_justified(egui::Direction::TopDown),
                |ui| {
                    ui.label(
                        RichText::new(fill(t.preview_unavailable, &[error]))
                            .color(Color32::from_rgb(210, 90, 75)),
                    );
                },
            );
        } else {
            ui.allocate_ui_with_layout(
                available,
                egui::Layout::centered_and_justified(egui::Direction::TopDown),
                |ui| {
                    ui.weak(t.select_group_preview);
                },
            );
        }
    }

    fn groups_panel(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        let Some(document) = &self.texture.document else {
            ui.centered_and_justified(|ui| {
                ui.weak(t.groups_empty);
            });
            return;
        };
        let groups = document.scan().groups.clone();
        let query = self.texture.group_search.trim().to_lowercase();
        let unknown_groups = groups.iter().filter(|g| !g.unknown.is_empty()).count();
        ui.horizontal(|ui| {
            ui.heading(t.detected_groups_heading);
            ui.weak(fill(t.groups_paren_count, &[&groups.len().to_string()]));
            if unknown_groups > 0 {
                ui.colored_label(
                    Color32::from_rgb(200, 130, 40),
                    fill(t.to_assign, &[&unknown_groups.to_string()]),
                );
            }
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.checkbox(&mut self.texture.review_only, t.unknown_only);
                ui.add(
                    TextEdit::singleline(&mut self.texture.group_search)
                        .desired_width(160.0)
                        .hint_text(t.search_groups_hint),
                );
            });
        });
        ui.add_space(4.0);

        let visible = groups
            .iter()
            .enumerate()
            .filter(|(_, group)| !(self.texture.review_only && group.unknown.is_empty()))
            .filter(|(_, group)| {
                query.is_empty() || group.base_name.to_lowercase().contains(&query)
            })
            .map(|(index, _)| index)
            .collect::<Vec<_>>();

        // One egui::Grid holds the header row AND every group row, so all
        // columns share identical x positions regardless of name length. The
        // name column is width-clamped + truncated so a long stem can never
        // push the indicator columns out of alignment. Full-row selection /
        // amber highlights are painted as a single rect behind each row.
        let type_total = GROUP_CELL_W * GROUP_COLUMNS.len() as f32;
        let name_w =
            (ui.available_width() - type_total - GROUP_UNKNOWN_W - 30.0).clamp(150.0, 232.0);

        let mut preview_request = None;
        let mut assign = None;
        ScrollArea::both()
            .id_salt("group_table")
            .auto_shrink([false, false])
            .show(ui, |ui| {
                Grid::new("groups_grid")
                    .num_columns(GROUP_COLUMNS.len() + 2)
                    .spacing([2.0, 3.0])
                    .min_row_height(GROUP_ROW_H)
                    .show(ui, |ui| {
                        // Header as the grid's first row → columns are aligned
                        // with the rows by construction (deviation: the header
                        // scrolls with the rows — the pre-approved fallback).
                        fixed_cell(ui, name_w, GROUP_ROW_H, egui::Align::LEFT, |ui| {
                            ui.strong(t.group_col);
                        });
                        for (_, label) in GROUP_COLUMNS {
                            fixed_cell(ui, GROUP_CELL_W, GROUP_ROW_H, egui::Align::Center, |ui| {
                                ui.label(RichText::new(label).small().strong());
                            });
                        }
                        fixed_cell(ui, GROUP_UNKNOWN_W, GROUP_ROW_H, egui::Align::LEFT, |ui| {
                            ui.strong(t.unassigned_col);
                        });
                        ui.end_row();

                        for &index in &visible {
                            let group = &groups[index];
                            let selected = self.texture.selected_group == Some(index);
                            let has_unknown = !group.unknown.is_empty();
                            let was_unknown = self.texture.ever_unknown.contains(&group.key);
                            let row_fill = match (selected, has_unknown) {
                                (true, true) => Color32::from_rgba_unmultiplied(225, 155, 45, 90),
                                (false, true) => Color32::from_rgba_unmultiplied(220, 150, 40, 45),
                                (true, false) => Color32::from_rgba_unmultiplied(90, 140, 230, 65),
                                (false, false) => Color32::TRANSPARENT,
                            };
                            // Reserve a shape slot before the cells so the row
                            // background paints behind them; fill it once the
                            // full-row rect is known (paints the row, not cells).
                            let bg = ui.painter().add(egui::Shape::Noop);
                            let mut row_rect = egui::Rect::NOTHING;

                            row_rect = row_rect.union(fixed_cell(
                                ui,
                                name_w,
                                GROUP_ROW_H,
                                egui::Align::LEFT,
                                |ui| {
                                    let label =
                                        egui::Label::new(RichText::new(&group.base_name).strong())
                                            .truncate()
                                            .sense(Sense::click());
                                    if ui.add(label).on_hover_text(&group.base_name).clicked() {
                                        self.texture.selected_group = Some(index);
                                        preview_request = first_group_entry(group).map(|entry| {
                                            (PathBuf::from(&entry.path), entry.source_type.clone())
                                        });
                                    }
                                },
                            ));
                            for (source_type, _) in GROUP_COLUMNS {
                                row_rect = row_rect.union(fixed_cell(
                                    ui,
                                    GROUP_CELL_W,
                                    GROUP_ROW_H,
                                    egui::Align::Center,
                                    |ui| {
                                        let entry = group.slots.get(source_type);
                                        let sense = if entry.is_some() {
                                            Sense::click()
                                        } else {
                                            Sense::hover()
                                        };
                                        let (rect, response) =
                                            ui.allocate_exact_size([14.0, 14.0].into(), sense);
                                        let color = if entry.is_some() {
                                            Color32::from_rgb(80, 170, 100)
                                        } else {
                                            Color32::from_rgba_unmultiplied(130, 130, 135, 70)
                                        };
                                        ui.painter().rect_filled(rect, 3.0, color);
                                        if let Some(entry) = entry {
                                            if response.on_hover_text(source_type).clicked() {
                                                self.texture.selected_group = Some(index);
                                                preview_request = Some((
                                                    PathBuf::from(&entry.path),
                                                    source_type.to_owned(),
                                                ));
                                            }
                                        }
                                    },
                                ));
                            }
                            row_rect = row_rect.union(fixed_cell(
                                ui,
                                GROUP_UNKNOWN_W,
                                GROUP_ROW_H,
                                egui::Align::LEFT,
                                |ui| {
                                    if has_unknown {
                                        let mut pick = String::new();
                                        ComboBox::from_id_salt(("assign", index))
                                            .width(GROUP_UNKNOWN_W - 10.0)
                                            .selected_text(
                                                RichText::new(fill(
                                                    t.assign_combo,
                                                    &[&group.unknown.len().to_string()],
                                                ))
                                                .color(Color32::from_rgb(200, 130, 40)),
                                            )
                                            .show_ui(ui, |ui| {
                                                for source_type in ASSIGNABLE_SOURCE_TYPES {
                                                    let occupied =
                                                        group.slots.contains_key(source_type);
                                                    ui.add_enabled_ui(!occupied, |ui| {
                                                        ui.selectable_value(
                                                            &mut pick,
                                                            source_type.to_owned(),
                                                            source_type,
                                                        )
                                                        .on_disabled_hover_text(t.def19_hover);
                                                    });
                                                }
                                            });
                                        if !pick.is_empty() {
                                            assign = Some((index, pick));
                                        }
                                    } else if was_unknown {
                                        ui.colored_label(Color32::from_rgb(70, 165, 95), t.assigned_check);
                                    } else {
                                        ui.weak("—");
                                    }
                                },
                            ));

                            ui.end_row();

                            if row_fill != Color32::TRANSPARENT && row_rect.is_finite() {
                                let rect = row_rect.expand2(egui::vec2(2.0, 2.0));
                                ui.painter()
                                    .set(bg, egui::Shape::rect_filled(rect, 3.0, row_fill));
                            }
                        }
                    });
            });
        if let Some((path, source_type)) = preview_request {
            self.request_preview(path, source_type);
        }
        if let Some((index, source_type)) = assign {
            self.assign_group_unknown(index, &source_type);
        }
    }

    /// Inline assignment from the groups table: assign the group's first
    /// unknown to `source_type`, updating the transient diagnostics count.
    fn assign_group_unknown(&mut self, group_index: usize, source_type: &str) {
        let Some(document) = &mut self.texture.document else {
            return;
        };
        let base_name = document
            .scan()
            .groups
            .get(group_index)
            .map_or_else(String::new, |group| group.base_name.clone());
        self.status = match document.assign_unknown(group_index, 0, source_type) {
            Ok(()) => {
                self.texture.selected_group = Some(group_index);
                fill(self.t().assigned_status, &[source_type, &base_name])
            }
            Err(error) => error,
        };
    }

    fn model_workspace(&mut self, ui: &mut egui::Ui) {
        let t = self.t();
        let Some(index) = self.selected_entry_index() else {
            ui.centered_and_justified(|ui| {
                ui.vertical_centered(|ui| {
                    ui.heading(t.fbx_material_review_heading);
                    if self.model.entries.is_empty() {
                        ui.label(t.add_fbx_left);
                    } else {
                        ui.label(t.select_single_model_left);
                    }
                });
            });
            return;
        };
        let manifest_configured = !self.preferences.manifest_path.trim().is_empty();
        let modifiers = ui.input(|input| input.modifiers);
        // Take the entry's mutable working state out so we can borrow `review`
        // immutably for the whole render without a self.model borrow conflict.
        let mut phys = std::mem::take(&mut self.model.entries[index].physicalize_overrides);
        let mut selected_material = self.model.entries[index].selected_material;
        let mut selected_materials =
            std::mem::take(&mut self.model.entries[index].selected_materials);
        let mut selection_anchor = self.model.entries[index].material_selection_anchor;
        let mut bulk = std::mem::take(&mut self.model.entries[index].bulk_physicalize);
        {
            let review = &self.model.entries[index].review;
            ui.horizontal(|ui| {
                ui.heading(
                    review
                        .path
                        .file_name()
                        .and_then(|name| name.to_str())
                        .unwrap_or("FBX"),
                );
                ui.separator();
                ui.label(fill(t.material_slots_count, &[&review.material_slots.len().to_string()]));
                ui.separator();
                ui.label(fill(t.diagnostics_count, &[&review.diagnostics.len().to_string()]));
            });
            ui.separator();
            ScrollArea::vertical().show(ui, |ui| {
                ui.group(|ui| {
                    ui.set_width(ui.available_width());
                    ui.strong(t.rc_material_slots);
                    ui.weak(t.multi_select_fbx_hint);
                    let selected_count = selected_materials.len();
                    if selected_count > 0 {
                        ui.horizontal(|ui| {
                            ComboBox::from_id_salt("bulk_physicalize")
                                .selected_text(&bulk)
                                .show_ui(ui, |ui| {
                                    for value in PHYSICALIZE_VALUES {
                                        ui.selectable_value(&mut bulk, value.to_owned(), value);
                                    }
                                });
                            if ui
                                .button(fill(t.set_physicalize_btn, &[&selected_count.to_string()]))
                                .clicked()
                            {
                                let names: Vec<&str> = review
                                    .material_slots
                                    .iter()
                                    .map(|slot| slot.name.as_str())
                                    .collect();
                                apply_bulk_physicalize(
                                    &mut phys,
                                    &names,
                                    &selected_materials,
                                    &bulk,
                                );
                            }
                        });
                    }
                    Grid::new("model_materials")
                        .num_columns(6)
                        .striped(true)
                        .spacing([12.0, 5.0])
                        .show(ui, |ui| {
                            // "FBX" and "Physicalize" are proper terms — untranslated.
                            ui.strong("FBX");
                            ui.strong(t.col_sub);
                            ui.strong(t.col_material);
                            ui.strong("Physicalize");
                            ui.strong(t.col_polygons);
                            ui.strong(t.col_textures);
                            ui.end_row();
                            for (row, slot) in review.material_slots.iter().enumerate() {
                                let selected = selected_materials.contains(&row);
                                if ui
                                    .selectable_label(
                                        selected,
                                        slot.fbx_material_id
                                            .and_then(|id| id.checked_sub(1))
                                            .map_or_else(
                                                || "—".to_owned(),
                                                |value| value.to_string(),
                                            ),
                                    )
                                    .clicked()
                                {
                                    apply_click_selection(
                                        &mut selected_materials,
                                        &mut selection_anchor,
                                        row,
                                        modifiers.ctrl,
                                        modifiers.shift,
                                    );
                                    selected_material = Some(row);
                                }
                                ui.label(slot.sub_index.to_string());
                                ui.label(&slot.name);
                                // Default physicalize is "no" (item 1). A configured
                                // manifest still wins, so with a manifest the default
                                // is the policy-inferred value and only user changes
                                // become overrides; without a manifest every material
                                // carries an explicit seeded value.
                                let default_value = if manifest_configured {
                                    resolve_physicalize(
                                        slot.physicalize
                                            .as_deref()
                                            .map(|value| ("physicalize", value)),
                                        &slot.name,
                                    )
                                    .value
                                    .as_str()
                                    .to_owned()
                                } else {
                                    DEFAULT_PHYSICALIZE.to_owned()
                                };
                                let mut physicalize = phys
                                    .get(&slot.name)
                                    .cloned()
                                    .unwrap_or_else(|| default_value.clone());
                                ComboBox::from_id_salt(("physicalize", row))
                                    .selected_text(&physicalize)
                                    .show_ui(ui, |ui| {
                                        for value in PHYSICALIZE_VALUES {
                                            ui.selectable_value(
                                                &mut physicalize,
                                                value.to_owned(),
                                                value,
                                            );
                                        }
                                    });
                                if manifest_configured && physicalize == default_value {
                                    phys.remove(&slot.name);
                                } else {
                                    phys.insert(slot.name.clone(), physicalize);
                                }
                                let assignment = slot.source_order.and_then(|source_order| {
                                    review
                                        .assignments
                                        .iter()
                                        .find(|assignment| assignment.source_order == source_order)
                                });
                                ui.label(
                                    assignment
                                        .and_then(|assignment| assignment.polygon_count)
                                        .unwrap_or(0)
                                        .to_string(),
                                );
                                let textures = slot
                                    .source_order
                                    .and_then(|source_order| {
                                        review.model.materials.get(source_order)
                                    })
                                    .map_or(0, |material| material.textures.len());
                                ui.label(textures.to_string());
                                ui.end_row();
                            }
                        });
                });
                ui.add_space(8.0);
                if let Some(selected) = selected_material {
                    if let Some(slot) = review.material_slots.get(selected) {
                        ui.group(|ui| {
                            ui.set_width(ui.available_width());
                            ui.strong(fill(t.material_details, &[&slot.name]));
                            ui.label(fill(
                                t.assignment_source,
                                &[slot.assignment_reason.as_deref().unwrap_or("slot projection")],
                            ));
                            if let Some(material) = slot
                                .source_order
                                .and_then(|source_order| review.model.materials.get(source_order))
                            {
                                if material.textures.is_empty() {
                                    ui.weak(t.no_texture_references);
                                }
                                for texture in &material.textures {
                                    ui.horizontal_wrapped(|ui| {
                                        ui.label(RichText::new(&texture.shader_prop).strong());
                                        ui.label(if texture.embedded {
                                            fill(
                                                t.embedded_texture,
                                                &[
                                                    &texture.filename,
                                                    &texture.content_size.to_string(),
                                                ],
                                            )
                                        } else {
                                            texture.absolute_filename.clone()
                                        });
                                    });
                                }
                            }
                        });
                    }
                }
                ui.add_space(8.0);
                ui.group(|ui| {
                    ui.set_width(ui.available_width());
                    ui.strong(t.material_slot_diagnostics);
                    if review.diagnostics.is_empty() {
                        ui.label(
                            RichText::new(t.no_material_diagnostics)
                                .color(Color32::from_rgb(70, 165, 95)),
                        );
                    }
                    for diagnostic in &review.diagnostics {
                        ui.label(format!(
                            "[{}] {} · {}",
                            diagnostic.severity, diagnostic.material, diagnostic.message
                        ));
                    }
                });
            });
        }
        let entry = &mut self.model.entries[index];
        entry.physicalize_overrides = phys;
        entry.selected_material = selected_material;
        entry.selected_materials = selected_materials;
        entry.material_selection_anchor = selection_anchor;
        entry.bulk_physicalize = bulk;
    }
}

impl eframe::App for WorkflowApp {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        let dropped = context.input(|input| input.raw.dropped_files.clone());
        let paths = dropped
            .into_iter()
            .filter_map(|file| file.path)
            .collect::<Vec<_>>();
        if !paths.is_empty() {
            self.receive_paths(paths);
        }
        self.poll_workers(context);
        self.top_bar(context);
        self.status_bar(context);
        self.left_panel(context);
        self.right_panel(context);
        self.central_panel(context);
        self.diagnostics_popover(context);
        self.process_modal(context);
        self.export_modal(context);
        self.batch_modal(context);
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        let _ = self.preferences.save();
    }
}

/// A single-line path field with a trailing `Browse…` button.
/// Returns `(text_changed, browse_clicked)`.
fn path_row(
    ui: &mut egui::Ui,
    salt: &str,
    value: &mut String,
    hint: &str,
    browse_label: &str,
) -> (bool, bool) {
    let mut changed = false;
    let mut browse = false;
    ui.push_id(salt, |ui| {
        ui.horizontal(|ui| {
            changed = ui
                .add(
                    TextEdit::singleline(value)
                        .desired_width((ui.available_width() - 74.0).max(120.0))
                        .hint_text(hint),
                )
                .changed();
            browse = ui.button(browse_label).clicked();
        });
    });
    (changed, browse)
}

/// A fixed-width, vertically centred grid cell so the groups-table header and
/// rows line up column-for-column regardless of content. Width is clamped
/// (min == max) so a long label truncates instead of expanding the cell and
/// pushing later columns out of alignment. Returns the allocated cell rect so
/// the caller can paint a full-row background behind the whole row.
fn fixed_cell(
    ui: &mut egui::Ui,
    width: f32,
    height: f32,
    main_align: egui::Align,
    add: impl FnOnce(&mut egui::Ui),
) -> egui::Rect {
    let layout = egui::Layout::left_to_right(egui::Align::Center).with_main_align(main_align);
    ui.allocate_ui_with_layout(egui::vec2(width, height), layout, |ui| {
        ui.set_min_width(width);
        ui.set_max_width(width);
        ui.set_min_height(height);
        add(ui);
    })
    .response
    .rect
}

fn is_fbx(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .is_some_and(|extension| extension.eq_ignore_ascii_case("fbx"))
}

fn entry_name(entry: &ModelEntry) -> String {
    entry
        .review
        .path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("FBX")
        .to_owned()
}

/// A small colored pill label, matching the badges used for texture map types.
fn badge(ui: &mut egui::Ui, text: impl Into<String>, color: Color32) {
    ui.label(
        RichText::new(text.into())
            .small()
            .color(Color32::WHITE)
            .background_color(color),
    );
}

fn split_paths(text: &str) -> Vec<PathBuf> {
    text.split(['\n', ';'])
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(|value| PathBuf::from(value.trim_matches('"')))
        .collect()
}

fn optional_path(text: &str) -> Option<PathBuf> {
    let path = PathBuf::from(text.trim());
    (!path.as_os_str().is_empty()).then_some(path)
}

fn source_type_for_path(document: Option<&ReviewDocument>, path: &Path) -> String {
    let key = path.to_string_lossy();
    document
        .into_iter()
        .flat_map(|document| &document.scan().groups)
        .flat_map(|group| group.slots.values().chain(group.unknown.iter()))
        .find(|entry| entry.path.eq_ignore_ascii_case(&key))
        .map_or_else(|| "unknown".to_owned(), |entry| entry.source_type.clone())
}

/// True when any of the group's textures (slots or unknown) is in the
/// FBX-ingested origin set (`ingested` holds lowercased absolute paths).
fn group_contains_ingested(group: &ScanGroup, ingested: &BTreeSet<String>) -> bool {
    group
        .slots
        .values()
        .chain(group.unknown.iter())
        .any(|entry| ingested.contains(&entry.path.to_lowercase()))
}

fn first_group_entry(group: &ScanGroup) -> Option<&ScanEntry> {
    group
        .slots
        .values()
        .next()
        .or_else(|| group.unknown.first())
}

fn severity_label(severity: Severity) -> &'static str {
    match severity {
        Severity::Warning => "Warning",
        Severity::Error => "Error",
    }
}

fn resolution_label(value: OutputResolution) -> String {
    match value {
        OutputResolution::Original => "Original".to_owned(),
        OutputResolution::Max(maximum) => maximum.to_string(),
    }
}

fn file_url(path: &Path) -> String {
    format!("file:///{}", path.to_string_lossy().replace('\\', "/"))
}

/// Referenced (on-disk) + embedded (extracted to a cache dir) textures pulled
/// from a loaded FBX, deduplicated by absolute path.
struct TextureIngest {
    paths: Vec<PathBuf>,
    embedded: usize,
}

fn extract_model_texture_paths(review: &ModelReview) -> Result<TextureIngest, String> {
    let model_directory = review.path.parent().unwrap_or_else(|| Path::new("."));
    let embedded_directory = embedded_texture_directory(&review.path);
    collect_model_textures(
        &review.model.materials,
        model_directory,
        &embedded_directory,
    )
}

fn collect_model_textures(
    materials: &[converter::model::MaterialRecord],
    model_directory: &Path,
    embedded_directory: &Path,
) -> Result<TextureIngest, String> {
    let mut seen = BTreeSet::new();
    let mut paths = Vec::new();
    let mut embedded = 0;
    for (index, texture) in materials
        .iter()
        .flat_map(|material| material.textures.iter())
        .enumerate()
    {
        let external = [
            PathBuf::from(&texture.absolute_filename),
            model_directory.join(&texture.relative_filename),
            model_directory.join(&texture.filename),
        ]
        .into_iter()
        .find(|path| path.is_file());
        let (path, is_embedded) = if let Some(path) = external {
            (path, false)
        } else if texture.embedded && !texture.content.is_empty() {
            fs::create_dir_all(embedded_directory).map_err(|error| {
                format!(
                    "Could not create embedded texture cache {}: {error}",
                    embedded_directory.display()
                )
            })?;
            let filename = Path::new(&texture.filename)
                .file_name()
                .filter(|name| !name.is_empty())
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from(format!("embedded_{index}.png")));
            let path = embedded_directory.join(filename);
            fs::write(&path, &texture.content).map_err(|error| {
                format!(
                    "Could not write embedded texture {}: {error}",
                    path.display()
                )
            })?;
            (path, true)
        } else {
            continue;
        };
        let key = path.to_string_lossy().to_lowercase();
        if seen.insert(key) {
            if is_embedded {
                embedded += 1;
            }
            paths.push(path);
        }
    }
    Ok(TextureIngest { paths, embedded })
}

struct RcPathResolution {
    path: Option<PathBuf>,
    source: &'static str,
    configured_invalid: bool,
}

fn resolve_rc_path(configured: &str) -> RcPathResolution {
    let environment = std::env::var_os("CE_RC_EXE").map(PathBuf::from);
    resolve_rc_path_candidates(
        configured,
        environment.as_deref(),
        Path::new(DEFAULT_RC_EXE),
    )
}

fn resolve_rc_path_candidates(
    configured: &str,
    environment: Option<&Path>,
    default: &Path,
) -> RcPathResolution {
    let configured = configured.trim();
    if !configured.is_empty() {
        let path = PathBuf::from(configured);
        if path.is_file() {
            return RcPathResolution {
                path: Some(path),
                source: "RC Path",
                configured_invalid: false,
            };
        }
    }
    let configured_invalid = !configured.is_empty();
    if let Some(path) = environment {
        if path.is_file() {
            return RcPathResolution {
                path: Some(path.to_owned()),
                source: "CE_RC_EXE",
                configured_invalid,
            };
        }
    }
    if default.is_file() {
        return RcPathResolution {
            path: Some(default.to_owned()),
            source: "default RC",
            configured_invalid,
        };
    }
    RcPathResolution {
        path: None,
        source: "",
        configured_invalid,
    }
}

#[cfg(test)]
mod ingest_tests {
    use super::*;
    use converter::model::{MaterialRecord, TextureRef};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn texture(filename: &str, absolute: &str, embedded: bool, content: &[u8]) -> TextureRef {
        TextureRef {
            material_prop: "prop".to_owned(),
            shader_prop: "Diffuse".to_owned(),
            filename: filename.to_owned(),
            absolute_filename: absolute.to_owned(),
            relative_filename: filename.to_owned(),
            embedded,
            content_size: content.len(),
            content: content.to_vec(),
        }
    }

    fn material(textures: Vec<TextureRef>) -> MaterialRecord {
        MaterialRecord {
            name: "Mat".to_owned(),
            typed_id: 0,
            element_id: 0,
            textures,
        }
    }

    #[test]
    fn collect_dedups_references_and_counts_embedded() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir =
            std::env::temp_dir().join(format!("texproc-gui-ingest-{}-{nonce}", std::process::id()));
        let embedded_dir = dir.join("embedded");
        fs::create_dir_all(&dir).unwrap();
        let on_disk = dir.join("wood_diffuse.png");
        fs::write(&on_disk, b"png").unwrap();
        let on_disk_str = on_disk.to_string_lossy().into_owned();

        let materials = vec![
            material(vec![
                texture("wood_diffuse.png", &on_disk_str, false, b""),
                // Duplicate reference to the same file → deduped.
                texture("wood_diffuse.png", &on_disk_str, false, b""),
                // Missing on disk, not embedded → skipped entirely.
                texture("gone_normal.png", r"D:\missing\gone_normal.png", false, b""),
            ]),
            material(vec![
                // Embedded blob → extracted to the cache dir, counted.
                texture("emb_spec.png", "", true, b"embedded-bytes"),
            ]),
        ];

        let ingest = collect_model_textures(&materials, &dir, &embedded_dir).unwrap();
        assert_eq!(ingest.paths.len(), 2, "one referenced + one embedded");
        assert_eq!(ingest.embedded, 1);
        assert!(embedded_dir.join("emb_spec.png").is_file());

        fs::remove_dir_all(&dir).unwrap();
    }
}

#[cfg(test)]
mod physicalize_tests {
    use super::*;

    #[test]
    fn seed_defaults_every_material_to_no() {
        let seeded = seed_default_physicalize(["Body", "Glass", "Body"]);
        assert_eq!(seeded.len(), 2, "deduped by name");
        assert_eq!(seeded.get("Body").map(String::as_str), Some("no"));
        assert_eq!(seeded.get("Glass").map(String::as_str), Some("no"));
    }

    #[test]
    fn bulk_apply_sets_only_selected_rows() {
        let mut overrides = seed_default_physicalize(["A", "B", "C"]);
        let names = ["A", "B", "C"];
        let selected = BTreeSet::from([0usize, 2]);
        apply_bulk_physicalize(&mut overrides, &names, &selected, "proxy_only");
        assert_eq!(overrides.get("A").map(String::as_str), Some("proxy_only"));
        assert_eq!(
            overrides.get("B").map(String::as_str),
            Some("no"),
            "unselected untouched"
        );
        assert_eq!(overrides.get("C").map(String::as_str), Some("proxy_only"));
    }

    #[test]
    fn bulk_apply_ignores_out_of_range_indices() {
        let mut overrides = BTreeMap::new();
        let names = ["A"];
        apply_bulk_physicalize(
            &mut overrides,
            &names,
            &BTreeSet::from([0usize, 5]),
            "obstruct",
        );
        assert_eq!(overrides.len(), 1);
        assert_eq!(overrides.get("A").map(String::as_str), Some("obstruct"));
    }

    #[test]
    fn per_model_physicalize_edits_do_not_leak_between_models() {
        // Each model-list entry owns its own physicalize map (R10 per-model state
        // isolation). Editing one model's map must never touch another's.
        let mut model_a = seed_default_physicalize(["Body", "Glass"]);
        let model_b = seed_default_physicalize(["Body", "Glass"]);
        apply_bulk_physicalize(
            &mut model_a,
            &["Body", "Glass"],
            &BTreeSet::from([0usize]),
            "proxy_only",
        );
        assert_eq!(model_a.get("Body").map(String::as_str), Some("proxy_only"));
        assert_eq!(
            model_b.get("Body").map(String::as_str),
            Some("no"),
            "the other model's physicalize is untouched"
        );
    }
}

#[cfg(test)]
mod selection_tests {
    use super::*;

    #[test]
    fn plain_ctrl_and_shift_clicks_match_convention() {
        let mut selected = BTreeSet::new();
        let mut anchor = None;
        // Plain click selects only.
        apply_click_selection(&mut selected, &mut anchor, 2, false, false);
        assert_eq!(selected, BTreeSet::from([2]));
        assert_eq!(anchor, Some(2));
        // Ctrl+click toggles additional rows.
        apply_click_selection(&mut selected, &mut anchor, 4, true, false);
        assert_eq!(selected, BTreeSet::from([2, 4]));
        // Ctrl+click again toggles off.
        apply_click_selection(&mut selected, &mut anchor, 2, true, false);
        assert_eq!(selected, BTreeSet::from([4]));
        // Shift+click selects the range from the anchor (last was 2).
        apply_click_selection(&mut selected, &mut anchor, 0, false, false);
        apply_click_selection(&mut selected, &mut anchor, 3, false, true);
        assert_eq!(selected, BTreeSet::from([0, 1, 2, 3]));
    }
}

#[cfg(test)]
mod rc_path_tests {
    use super::*;

    fn existing_file() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml")
    }

    #[test]
    fn configured_rc_path_has_highest_priority() {
        let configured = existing_file();
        let environment = existing_file();
        let default = existing_file();
        let resolution =
            resolve_rc_path_candidates(&configured.to_string_lossy(), Some(&environment), &default);

        assert_eq!(resolution.path.as_deref(), Some(configured.as_path()));
        assert_eq!(resolution.source, "RC Path");
        assert!(!resolution.configured_invalid);
    }

    #[test]
    fn invalid_configured_path_falls_back_to_environment() {
        let environment = existing_file();
        let default = existing_file();
        let resolution =
            resolve_rc_path_candidates("missing-configured-rc.exe", Some(&environment), &default);

        assert_eq!(resolution.path.as_deref(), Some(environment.as_path()));
        assert_eq!(resolution.source, "CE_RC_EXE");
        assert!(resolution.configured_invalid);
    }

    #[test]
    fn missing_all_rc_candidates_is_explicit() {
        let resolution = resolve_rc_path_candidates(
            "missing-configured-rc.exe",
            Some(Path::new("missing-environment-rc.exe")),
            Path::new("missing-default-rc.exe"),
        );

        assert!(resolution.path.is_none());
        assert_eq!(resolution.source, "");
        assert!(resolution.configured_invalid);
    }

    #[test]
    fn crash_log_appends_timestamped_records() {
        let path = std::env::temp_dir().join(format!(
            "texproc-gui-crashlog-{}-{}.log",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        append_crash_log_to(&path, "first panic");
        append_crash_log_to(&path, "second panic");
        let contents = fs::read_to_string(&path).unwrap();
        assert!(contents.contains("first panic"));
        assert!(contents.contains("second panic"));
        assert!(contents.contains("[epoch "));
        // Two records appended, not overwritten.
        assert_eq!(contents.matches("[epoch ").count(), 2);
        let _ = fs::remove_file(&path);
    }

    #[test]
    fn missing_cjk_font_is_graceful_none_not_panic() {
        // A bogus path must yield None (English stays usable), never a panic.
        assert!(load_cjk_fonts(Path::new("Z:\\no-such-font.ttc")).is_none());
    }

    #[test]
    fn present_cjk_font_registers_fallback() {
        // Only asserts when the system font exists (it does on Windows CI/dev);
        // otherwise the graceful-None path above already covers correctness.
        if Path::new(CJK_FONT_PATH).is_file() {
            let fonts = load_cjk_fonts(Path::new(CJK_FONT_PATH)).expect("font loads");
            assert!(fonts.font_data.contains_key("cjk_fallback"));
            assert!(fonts.families[&egui::FontFamily::Proportional]
                .iter()
                .any(|name| name == "cjk_fallback"));
        }
    }
}
