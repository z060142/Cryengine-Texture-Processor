#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod file_dialog;
mod i18n;
mod prefs;
mod ui;
mod worker;

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::AtomicBool,
        mpsc::{Receiver, TryRecvError},
        Arc,
    },
    time::Duration,
};

use eframe::egui::{self, TextureHandle, ViewportBuilder};
use i18n::{fill, Language, Strings};
use prefs::{embedded_texture_directory, AppPreferences};
use texproc::{
    load_texture_settings, save_texture_settings, FailedGroup, OutputResolution, ScanEntry,
    ScanGroup, ScanResult, Severity, SuffixTable, TextureSettings,
};
use texproc_gui::{
    axes_parallel, compose_forward_up, helper_node_count, parse_forward_up, ReviewDocument,
    AXIS_TOKENS,
};
use worker::{
    BatchExportEvent, DdsSummary, ModelEvent, ModelExportEvent, ModelJob, ModelReview,
    PreviewEvent, ProcessEvent, ProcessJob, RcExportOutcome, ScanEvent,
};

pub(crate) const APP_TITLE: &str = "CryEngine Texture Processor";
const DEFAULT_RC_EXE: &str = r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe";
#[allow(dead_code)] // Phase B: material-slot physicalize combos (SPEC §6.3).
pub(crate) const PHYSICALIZE_VALUES: [&str; 5] =
    ["no", "default", "obstruct", "no_collide", "proxy_only"];
/// Legal `unit_size` values for the Conversion Settings Unit dropdown. The RC
/// import schema (output_formats/rc_import_schema.py) accepts unit_size as a
/// free string; this mirrors the CryEngine Sandbox FBX-import unit choices,
/// with `file` (use the FBX's own unit) as the native-car default.
#[allow(dead_code)] // Phase B: Transform panel unit combo (SPEC §8).
pub(crate) const UNIT_SIZE_VALUES: [&str; 6] = ["file", "mm", "cm", "m", "inch", "foot"];
/// GUI default physicalize seed for every material (the practical golden flow is
/// all `no`). Seeded as explicit metadata; a loaded manifest still wins.
const DEFAULT_PHYSICALIZE: &str = "no";

/// Apply a click to a row-index multi-selection (shared by the texture list and
/// the material table): plain = select only, Ctrl = toggle, Shift = range from
/// the anchor.
#[allow(dead_code)] // Phase B: list multi-select (unit-tested; SPEC §7/§8).
pub(crate) fn apply_click_selection(
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
#[allow(dead_code)] // Phase B: Transform panel axis combos (SPEC §8).
pub(crate) fn axis_dropdown(ui: &mut egui::Ui, label: &str, id: &str, token: &mut String) {
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
#[allow(dead_code)] // Phase B: bulk physicalize row (unit-tested; SPEC §6.3).
pub(crate) fn apply_bulk_physicalize(
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
#[allow(dead_code)] // Phase B: type-dot order in group rows (SPEC §7).
pub(crate) const GROUP_COLUMNS: [(&str, &str); 12] = [
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
#[allow(dead_code)] // Phase B: Import panel file dialog (SPEC §7).
pub(crate) const IMAGE_FILTER: &str = "Images (png, jpg, jpeg, tif, tiff, exr, hdr, tga, bmp, webp)\0*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.exr;*.hdr;*.tga;*.bmp;*.webp\0All files (*.*)\0*.*\0";
#[allow(dead_code)] // Phase B: FBX List panel file dialog (SPEC §8).
pub(crate) const FBX_FILTER: &str = "FBX models (*.fbx)\0*.fbx\0All files (*.*)\0*.*\0";
pub(crate) const JSON_FILTER: &str = "JSON files (*.json)\0*.json\0All files (*.*)\0*.*\0";

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
            ui::theme::apply_style(&creation.egui_ctx);
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
    #[allow(dead_code)] // Phase B: Group Review search box (SPEC §7).
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
    #[allow(dead_code)] // Phase B: preview HUD chip (SPEC §6.2).
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
    // Phase B reads these again in the material-slot workspace (SPEC §6.3).
    #[allow(dead_code)]
    selected_material: Option<usize>,
    #[allow(dead_code)]
    selected_materials: BTreeSet<usize>,
    #[allow(dead_code)]
    material_selection_anchor: Option<usize>,
    #[allow(dead_code)]
    bulk_physicalize: String,
    /// Meshless non-root scene nodes (RC helper/anchor nodes).
    #[allow(dead_code)] // Phase B: FBX List sub-line + summary (SPEC §8).
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
    #[allow(dead_code)] // Phase B: Transform panel "Detected:" caption (SPEC §8).
    detected_forward: String,
    #[allow(dead_code)] // Phase B: Transform panel "Detected:" caption (SPEC §8).
    detected_up: String,
    forward: String,
    up: String,
    merge_all_nodes: bool,
    scene_origin: bool,
}

pub(crate) struct WorkflowApp {
    pub(crate) preferences: AppPreferences,
    pub(crate) settings: TextureSettings,
    pub(crate) texture: TextureState,
    pub(crate) preview: PreviewState,
    pub(crate) process: Option<ProcessState>,
    pub(crate) process_summary: Option<ProcessSummary>,
    pub(crate) process_modal_open: bool,
    pub(crate) model: ModelState,
    pub(crate) status: String,
    /// v2 chrome state: active mode, per-mode panel memory, toasts, session
    /// tasks, diagnostics popover flag. Persisted via `prefs.ui_workspace`.
    pub(crate) ui: ui::UiState,
}

impl WorkflowApp {
    fn new(initial_paths: Vec<PathBuf>) -> Self {
        let preferences = AppPreferences::load();
        let settings = load_texture_settings(Path::new(&preferences.settings_path))
            .unwrap_or_else(|_| TextureSettings::default());
        let workspace = ui::UiState::from_value(&preferences.ui_workspace);
        let mut app = Self {
            preferences,
            settings,
            texture: TextureState::default(),
            preview: PreviewState::default(),
            process: None,
            process_summary: None,
            process_modal_open: false,
            model: ModelState::default(),
            status: String::new(),
            ui: workspace,
        };
        app.status = app.t().status_ready.to_owned();
        if !initial_paths.is_empty() {
            app.receive_paths(initial_paths);
        }
        app
    }

    /// The active language's string table. `&'static` — never borrows `self`, so
    /// it can be called and held while `self` is mutated in the same statement.
    pub(crate) fn t(&self) -> &'static Strings {
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

    pub(crate) fn add_texture_roots(&mut self, roots: Vec<PathBuf>) {
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
        self.ui.mode = ui::UiMode::Textures;
        self.texture.scan_receiver = Some(worker::start_scan(self.texture.roots.clone()));
        self.status = self.t().scanning_grouping.to_owned();
    }

    #[allow(dead_code)] // Phase B: Import panel Clear All (SPEC §7).
    pub(crate) fn clear_textures(&mut self) {
        self.texture = TextureState::default();
        self.preview = PreviewState::default();
        self.process_summary = None;
        self.status = self.t().cleared_textures.to_owned();
    }

    /// Start loading one or more FBX files; each completes into its own model-list
    /// entry (batch import). Existing entries are kept.
    pub(crate) fn load_model_files(&mut self, paths: Vec<PathBuf>) {
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
        self.ui.mode = ui::UiMode::Models;
        self.status = fill(self.t().loading_fbx, &[&started.to_string()]);
        self.save_preferences();
    }

    /// Index of the single selected model, or `None` when 0 or >1 are selected.
    pub(crate) fn selected_entry_index(&self) -> Option<usize> {
        (self.model.selected.len() == 1)
            .then(|| self.model.selected.iter().next().copied())
            .flatten()
    }

    #[allow(dead_code)] // Phase B: FBX List Clear All (SPEC §8).
    pub(crate) fn clear_models(&mut self) {
        self.model.entries.clear();
        self.model.selected.clear();
        self.model.selection_anchor = None;
        self.status = self.t().cleared_models.to_owned();
    }

    /// Multi-select removal from the model list, mirroring Remove Selected on the
    /// texture list. Selection indices become stale after removal, so clear them.
    #[allow(dead_code)] // Phase B: FBX List Remove Selected (SPEC §8).
    pub(crate) fn remove_selected_models(&mut self) {
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

    pub(crate) fn request_preview(&mut self, path: PathBuf, source_type: impl Into<String>) {
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

    pub(crate) fn start_texture_process(&mut self) {
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

    #[allow(dead_code)] // Phase B: Export Options primary action (SPEC §8).
    pub(crate) fn start_model_export(&mut self) {
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
    pub(crate) fn start_batch_export(&mut self) {
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
    #[allow(dead_code)] // Phase B: Import list multi-select (SPEC §7).
    pub(crate) fn apply_selection_click(&mut self, index: usize, ctrl: bool, shift: bool) {
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
    #[allow(dead_code)] // Phase B: Import panel Remove Selected (SPEC §7).
    pub(crate) fn remove_selected_textures(&mut self) {
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
    #[allow(dead_code)] // Phase B: Import panel Add Related (SPEC §7).
    pub(crate) fn add_related_textures(&mut self) {
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
    pub(crate) fn ingest_entry_textures(&mut self, entry_index: usize) {
        let ingest = {
            let review = &self.model.entries[entry_index].review;
            extract_model_texture_paths(review)
        };
        match ingest {
            Ok(ingest) if ingest.paths.is_empty() => {
                self.status = self.t().no_textures_in_fbx.to_owned();
            }
            Ok(ingest) => {
                let mode = self.ui.mode;
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
                self.ui.mode = mode;
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
        self.ui.mode = ui::UiMode::Models;
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

    pub(crate) fn save_preferences(&mut self) {
        // Keep the workspace snapshot (panel memory + presets) in the same file.
        self.preferences.ui_workspace = self.ui.to_value();
        if let Err(error) = self.preferences.save() {
            self.status = error;
        }
    }

    /// Unwrap a single-selection dialog result, surfacing API errors in the
    /// status area. User cancel (`Ok(None)`) is a silent no-op.
    pub(crate) fn dialog_result(
        &mut self,
        result: Result<Option<PathBuf>, String>,
    ) -> Option<PathBuf> {
        match result {
            Ok(value) => value,
            Err(error) => {
                self.status = error;
                None
            }
        }
    }

    pub(crate) fn save_settings(&mut self) {
        let path = PathBuf::from(self.preferences.settings_path.trim());
        match save_texture_settings(&path, &self.settings) {
            Ok(()) => {
                self.save_preferences();
                self.status = fill(self.t().settings_saved, &[&path.display().to_string()]);
            }
            Err(error) => self.status = error.to_string(),
        }
    }

    pub(crate) fn load_settings(&mut self) {
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

    /// Transient diagnostics surfaced in the topbar popover: unresolved
    /// texture unknowns, group conflict notes (DEF-19), RC fallback state, and
    /// FBX material-slot diagnostics.
    pub(crate) fn diagnostics(&self) -> Vec<DiagItem> {
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

    /// Inline assignment from the groups table: assign the group's first
    /// unknown to `source_type`, updating the transient diagnostics count.
    #[allow(dead_code)] // Phase B: Group Review "assign unknown" flow (SPEC §7).
    pub(crate) fn assign_group_unknown(&mut self, group_index: usize, source_type: &str) {
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
        ui::draw(self, context);
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        self.preferences.ui_workspace = self.ui.to_value();
        let _ = self.preferences.save();
    }
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

#[allow(dead_code)] // Phase B: Add Path multi-path fields (SPEC §7/§8).
pub(crate) fn split_paths(text: &str) -> Vec<PathBuf> {
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

#[allow(dead_code)] // Phase B: preview request from the Import list (SPEC §7).
pub(crate) fn source_type_for_path(document: Option<&ReviewDocument>, path: &Path) -> String {
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

pub(crate) fn first_group_entry(group: &ScanGroup) -> Option<&ScanEntry> {
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

#[allow(dead_code)] // Phase B: Conversion Settings resolution combo (SPEC §7).
pub(crate) fn resolution_label(value: OutputResolution) -> String {
    match value {
        OutputResolution::Original => "Original".to_owned(),
        OutputResolution::Max(maximum) => maximum.to_string(),
    }
}

pub(crate) fn file_url(path: &Path) -> String {
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

pub(crate) fn resolve_rc_path(configured: &str) -> RcPathResolution {
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
