#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod file_dialog;
mod prefs;
mod worker;

use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::Ordering,
        mpsc::{Receiver, TryRecvError},
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
use prefs::{embedded_texture_directory, AppPreferences};
use texproc::{
    load_texture_settings, save_texture_settings, ArmOrder, DiffFormat, OutputResolution,
    ScanEntry, ScanGroup, Severity, TextureSettings,
};
use texproc_gui::{ReviewDocument, ASSIGNABLE_SOURCE_TYPES};
use worker::{
    ModelEvent, ModelExportEvent, ModelReview, PreviewEvent, ProcessEvent, ProcessJob,
    RcExportOutcome, ScanEvent,
};

const APP_TITLE: &str = "CryEngine Texture Processor";
const DEFAULT_RC_EXE: &str = r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe";
const PHYSICALIZE_VALUES: [&str; 5] = ["no", "default", "obstruct", "no_collide", "proxy_only"];
/// Compact map-type columns shown in the groups table (source type, header).
const GROUP_COLUMNS: [(&str, &str); 12] = [
    ("diffuse", "Dif"),
    ("normal", "Nrm"),
    ("specular", "Spc"),
    ("glossiness", "Gls"),
    ("roughness", "Rgh"),
    ("displacement", "Hgt"),
    ("metallic", "Met"),
    ("ao", "AO"),
    ("alpha", "Alp"),
    ("emissive", "Emi"),
    ("sss", "SSS"),
    ("arm", "ARM"),
];
const GROUP_CELL_W: f32 = 26.0;
const GROUP_UNKNOWN_W: f32 = 150.0;
const GROUP_ROW_H: f32 = 24.0;
const IMAGE_FILTER: &str = "Images (png, jpg, jpeg, tif, tiff, exr)\0*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.exr\0All files (*.*)\0*.*\0";
const FBX_FILTER: &str = "FBX models (*.fbx)\0*.fbx\0All files (*.*)\0*.*\0";
const JSON_FILTER: &str = "JSON files (*.json)\0*.json\0All files (*.*)\0*.*\0";

fn main() -> eframe::Result {
    let initial_path = std::env::args_os().nth(1).map(PathBuf::from);
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_inner_size([1440.0, 900.0])
            .with_min_inner_size([1100.0, 680.0]),
        ..Default::default()
    };
    eframe::run_native(
        APP_TITLE,
        options,
        Box::new(move |_creation| Ok(Box::new(WorkflowApp::new(initial_path)))),
    )
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
    selected_file: Option<usize>,
    selected_group: Option<usize>,
    group_search: String,
    review_only: bool,
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
}

struct ProcessSummary {
    written: usize,
    groups: usize,
    cancelled: bool,
    elapsed_seconds: f64,
    output_directory: PathBuf,
}

/// One line in the status-bar diagnostics popover.
struct DiagItem {
    severity: &'static str,
    title: String,
    message: String,
}

#[derive(Default)]
struct ModelState {
    receiver: Option<Receiver<ModelEvent>>,
    review: Option<ModelReview>,
    selected_material: Option<usize>,
    export_receiver: Option<Receiver<ModelExportEvent>>,
    export_summary: Option<String>,
    export_modal_open: bool,
    export_stage: String,
    export_cgf: Option<PathBuf>,
    physicalize_overrides: BTreeMap<String, String>,
    rc_missing_warning: bool,
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
    fn new(initial_path: Option<PathBuf>) -> Self {
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
            status: "Ready. Drop textures, folders, or an FBX file to begin.".to_owned(),
        };
        if let Some(path) = initial_path {
            app.receive_paths(vec![path]);
        }
        app
    }

    fn receive_paths(&mut self, paths: Vec<PathBuf>) {
        let mut texture_paths = Vec::new();
        for path in paths {
            if path
                .extension()
                .and_then(|value| value.to_str())
                .is_some_and(|extension| extension.eq_ignore_ascii_case("fbx"))
            {
                self.start_model_load(path);
            } else {
                texture_paths.push(path);
            }
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
            self.status = "No texture files or folders were found.".to_owned();
            return;
        }
        self.tab = WorkflowTab::Textures;
        self.texture.scan_receiver = Some(worker::start_scan(self.texture.roots.clone()));
        self.status = "Scanning and grouping textures…".to_owned();
    }

    fn clear_textures(&mut self) {
        self.texture = TextureState::default();
        self.preview = PreviewState::default();
        self.process_summary = None;
        self.status = "Cleared imported textures and transient groups.".to_owned();
    }

    fn start_model_load(&mut self, path: PathBuf) {
        if !path.is_file() {
            self.status = format!("FBX does not exist: {}", path.display());
            return;
        }
        self.preferences.model_path = path.to_string_lossy().into_owned();
        self.model.receiver = Some(worker::start_model_load(path));
        self.model.review = None;
        self.model.selected_material = None;
        self.model.export_summary = None;
        self.model.physicalize_overrides.clear();
        self.model.rc_missing_warning = false;
        self.tab = WorkflowTab::Model;
        self.status = "Loading FBX materials and texture references…".to_owned();
        self.save_preferences();
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
            self.status = "No textures are ready for processing.".to_owned();
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
            self.status = format!(
                "Assign a type to the unknown texture in `{}` before processing.",
                blocked.base_name
            );
            return;
        }
        let output = PathBuf::from(self.preferences.texture_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = "Set a texture output directory first.".to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = format!("Could not create texture output directory: {error}");
            return;
        }

        let scan = document.scan().clone();
        let total = scan.groups.len();
        let group_names = scan
            .groups
            .iter()
            .map(|group| group.base_name.clone())
            .collect();
        self.process = Some(ProcessState {
            job: worker::start_process(scan, self.settings, output),
            completed: 0,
            total,
            current_group: "Preparing".to_owned(),
            written: 0,
            group_names,
            completed_groups: BTreeSet::new(),
        });
        self.process_summary = None;
        self.process_modal_open = true;
        self.status = format!("Processing {total} texture groups…");
    }

    fn start_model_export(&mut self) {
        let Some(review) = &self.model.review else {
            self.status = "Load an FBX file first.".to_owned();
            return;
        };
        let output = PathBuf::from(self.preferences.model_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = "Set a model output directory first.".to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = format!("Could not create model output directory: {error}");
            return;
        }
        let manifest = optional_path(&self.preferences.manifest_path);
        let overrides = optional_path(&self.preferences.overrides_path);
        let texture_dir = optional_path(&self.preferences.texture_output_directory);
        let rc_resolution = resolve_rc_path(&self.preferences.rc_path);
        self.model.rc_missing_warning = rc_resolution.path.is_none();
        self.model.export_receiver = Some(worker::start_model_export(
            review.path.clone(),
            manifest,
            overrides,
            texture_dir,
            output,
            self.model.physicalize_overrides.clone(),
            rc_resolution.path,
        ));
        self.model.export_summary = None;
        self.model.export_cgf = None;
        self.model.export_modal_open = true;
        self.model.export_stage = "Preparing export…".to_owned();
        self.status = "Exporting CryEngine intermediates and CE model…".to_owned();
    }

    fn send_model_textures_to_processing(&mut self) {
        let Some(review) = &self.model.review else {
            self.status = "Load an FBX file first.".to_owned();
            return;
        };
        match extract_model_texture_paths(review) {
            Ok(paths) if paths.is_empty() => {
                self.status = "The FBX has no external or embedded textures to process.".to_owned();
            }
            Ok(paths) => {
                let count = paths.len();
                self.add_texture_roots(paths);
                self.status =
                    format!("Sent {count} FBX texture references to the texture workflow.");
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
        if self.texture.scan_receiver.is_some()
            || self.preview.receiver.is_some()
            || self.process.is_some()
            || self.model.receiver.is_some()
            || self.model.export_receiver.is_some()
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
                    Err(TryRecvError::Disconnected) => Some(ScanEvent::Failed(
                        "The texture scan worker stopped unexpectedly.".to_owned(),
                    )),
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
                self.status = format!(
                    "Imported {} textures: {groups} groups, {unknown} unknown.",
                    self.texture.files.len()
                );
                if let Some((path, source_type)) = preview_request {
                    self.request_preview(path, source_type);
                }
            }
            ScanEvent::Failed(error) => {
                self.status = format!("Texture scan failed: {error}");
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
        let Some(process) = &mut self.process else {
            return;
        };
        let mut finished = None;
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
                Ok(ProcessEvent::Finished(result)) => {
                    finished = Some(result);
                    break;
                }
                Err(TryRecvError::Empty) => break,
                Err(TryRecvError::Disconnected) => {
                    finished = Some(Err(
                        "The texture processing worker stopped unexpectedly.".to_owned()
                    ));
                    break;
                }
            }
        }
        let Some(result) = finished else {
            return;
        };
        let output = PathBuf::from(&self.preferences.texture_output_directory);
        match result {
            Ok(report) => {
                let written = report.groups.iter().map(|group| group.written.len()).sum();
                self.status = if report.cancelled {
                    format!("Processing cancelled after {} groups.", report.groups.len())
                } else {
                    format!(
                        "Processing complete: {} groups, {written} output files.",
                        report.groups.len()
                    )
                };
                self.process_summary = Some(ProcessSummary {
                    written,
                    groups: report.groups.len(),
                    cancelled: report.cancelled,
                    elapsed_seconds: report.elapsed_seconds,
                    output_directory: output,
                });
            }
            Err(error) => {
                self.status = format!("Texture processing failed: {error}");
            }
        }
        self.process = None;
    }

    fn poll_model(&mut self) {
        let event = self
            .model
            .receiver
            .as_ref()
            .and_then(|receiver| receiver.try_recv().ok());
        let Some(event) = event else {
            return;
        };
        self.model.receiver = None;
        match event {
            ModelEvent::Completed(review) => {
                let materials = review.material_slots.len();
                let references = review
                    .model
                    .materials
                    .iter()
                    .map(|material| material.textures.len())
                    .sum::<usize>();
                self.model.review = Some(*review);
                self.model.selected_material = (materials > 0).then_some(0);
                self.status = format!(
                    "FBX loaded: {materials} material slots, {references} texture references."
                );
            }
            ModelEvent::Failed(error) => {
                self.status = format!("FBX load failed: {error}");
            }
        }
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
                let rc_summary = match &report.rc {
                    RcExportOutcome::NotConfigured => {
                        self.model.rc_missing_warning = true;
                        self.status = "RC not configured — intermediate files exported".to_owned();
                        "CGF: not exported (RC not configured)".to_owned()
                    }
                    RcExportOutcome::Succeeded { cgf, return_code } => {
                        self.model.rc_missing_warning = false;
                        self.model.export_cgf = Some(cgf.clone());
                        self.status = format!("CE model export completed: {}", cgf.display());
                        format!("CGF: {} (RC exit {return_code})", cgf.display())
                    }
                    RcExportOutcome::Failed { error, return_code } => {
                        self.model.rc_missing_warning = false;
                        self.status =
                            format!("RC export failed — intermediate files exported: {error}");
                        return_code.map_or_else(
                            || format!("CGF: export failed ({error})"),
                            |code| format!("CGF: export failed (RC exit {code}; {error})"),
                        )
                    }
                };
                let summary = format!(
                    "MTL: {}\nRequest: {}\n{rc_summary}\n{} diagnostic(s)",
                    report.outputs.mtl.display(),
                    report.outputs.request.display(),
                    report.outputs.material_diagnostics.len()
                );
                self.model.export_summary = Some(summary);
            }
            ModelExportEvent::Failed(error) => {
                self.model.export_receiver = None;
                self.model.export_summary = Some(format!("Export failed: {error}"));
                self.status = format!("CE model export failed: {error}");
            }
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
                self.status = format!("Settings saved: {}", path.display());
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
                self.status = format!("Settings loaded: {}", path.display());
            }
            Err(error) => self.status = error.to_string(),
        }
    }

    fn top_bar(&mut self, context: &egui::Context) {
        egui::TopBottomPanel::top("top_bar").show(context, |ui| {
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                ui.heading(APP_TITLE);
                ui.separator();
                ui.label("Texture conversion workflow");
                if self.model.review.is_some() {
                    ui.separator();
                    ui.weak("FBX material tool ready");
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.weak("Drop files or folders anywhere");
                });
            });
            ui.add_space(6.0);
        });
    }

    fn status_bar(&mut self, context: &egui::Context) {
        egui::TopBottomPanel::bottom("status_bar").show(context, |ui| {
            ui.horizontal(|ui| {
                ui.label(&self.status);
                if self.texture.scan_receiver.is_some()
                    || self.model.receiver.is_some()
                    || self.model.export_receiver.is_some()
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
                            format!("● {count} diagnostics"),
                        )
                    } else {
                        (
                            Color32::from_rgb(70, 165, 95),
                            "● No diagnostics".to_owned(),
                        )
                    };
                    if ui
                        .add(egui::Button::new(RichText::new(text).color(color)).frame(false))
                        .on_hover_text("Show diagnostics")
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
        let mut items = Vec::new();
        if let Some(document) = &self.texture.document {
            for group in &document.scan().groups {
                for entry in &group.unknown {
                    items.push(DiagItem {
                        severity: "Warning",
                        title: format!("Unknown map · {}", group.base_name),
                        message: format!(
                            "`{}` has no recognized suffix; assign a type in the groups table.",
                            entry.filename
                        ),
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
        if let Some(review) = &self.model.review {
            let resolution = resolve_rc_path(&self.preferences.rc_path);
            if resolution.path.is_none() {
                items.push(DiagItem {
                    severity: "Warning",
                    title: "RC not configured".to_owned(),
                    message: "Export CE Model will keep intermediate files only.".to_owned(),
                });
            } else if resolution.configured_invalid {
                items.push(DiagItem {
                    severity: "Warning",
                    title: "RC Path invalid".to_owned(),
                    message: format!(
                        "Configured RC Path is invalid; using {}.",
                        resolution.source
                    ),
                });
            }
            for diagnostic in &review.diagnostics {
                items.push(DiagItem {
                    severity: "Info",
                    title: format!("{} material", diagnostic.material),
                    message: diagnostic.message.clone(),
                });
            }
        }
        items
    }

    fn diagnostics_popover(&mut self, context: &egui::Context) {
        if !self.show_diagnostics {
            return;
        }
        let items = self.diagnostics();
        let mut open = true;
        egui::Window::new("Diagnostics")
            .anchor(Align2::RIGHT_BOTTOM, [-8.0, -34.0])
            .resizable(false)
            .collapsible(false)
            .open(&mut open)
            .default_width(420.0)
            .show(context, |ui| {
                if items.is_empty() {
                    ui.colored_label(Color32::from_rgb(70, 165, 95), "No diagnostics");
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
        let mut cancel = false;
        let mut close = false;
        Modal::new(Id::new("process_modal")).show(context, |ui| {
            ui.set_width(520.0);
            if let Some(process) = &self.process {
                ui.heading("Processing Textures…");
                ui.label(format!(
                    "{} of {} groups · {}",
                    process.completed, process.total, process.current_group
                ));
                let progress = if process.total == 0 {
                    0.0
                } else {
                    process.completed as f32 / process.total as f32
                };
                ui.add(ProgressBar::new(progress).show_percentage());
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
                    cancel = ui.button("Cancel").clicked();
                });
            } else if let Some(summary) = &self.process_summary {
                ui.heading(if summary.cancelled {
                    "Processing Cancelled"
                } else {
                    "Processing Complete"
                });
                ui.label(format!(
                    "{} groups · {} output files · {:.2} s",
                    summary.groups, summary.written, summary.elapsed_seconds
                ));
                ui.add_space(6.0);
                ui.hyperlink_to("Open output folder", file_url(&summary.output_directory));
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    close = ui.button("Close").clicked();
                });
            } else {
                close = true;
            }
        });
        if cancel {
            if let Some(process) = &self.process {
                process.job.cancel.store(true, Ordering::Relaxed);
                self.status =
                    "Cancelling; groups already in progress will finish safely.".to_owned();
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
        let running = self.model.export_receiver.is_some();
        let mut close = false;
        Modal::new(Id::new("export_modal")).show(context, |ui| {
            ui.set_width(520.0);
            if running {
                ui.heading("Exporting CE Model…");
                ui.horizontal(|ui| {
                    ui.spinner();
                    ui.label(&self.model.export_stage);
                });
                ui.add_space(6.0);
                ui.weak("Convert (.mtl + request) → Resource Compiler (CGF)");
            } else if let Some(summary) = &self.model.export_summary {
                ui.heading("CE Model Export");
                ui.label(summary);
                ui.add_space(6.0);
                if let Some(cgf) = &self.model.export_cgf {
                    ui.label(format!("CGF: {}", cgf.display()));
                }
                ui.hyperlink_to(
                    "Open output folder",
                    file_url(Path::new(&self.preferences.model_output_directory)),
                );
                ui.add_space(8.0);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    close = ui.button("Close").clicked();
                });
            } else {
                close = true;
            }
        });
        if close {
            self.model.export_modal_open = false;
        }
    }

    fn left_panel(&mut self, context: &egui::Context) {
        egui::SidePanel::left("imports")
            .resizable(true)
            .default_width(320.0)
            .min_width(270.0)
            .max_width(430.0)
            .show(context, |ui| {
                ui.horizontal(|ui| {
                    ui.selectable_value(&mut self.tab, WorkflowTab::Textures, "Texture Import");
                    ui.selectable_value(&mut self.tab, WorkflowTab::Model, "Model Import");
                });
                ui.separator();
                match self.tab {
                    WorkflowTab::Textures => self.texture_import_panel(ui),
                    WorkflowTab::Model => self.model_import_panel(ui),
                }
            });
    }

    fn texture_import_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("Texture Import");
        ui.label("Add individual textures, a folder, or drop them here.");
        ui.add_space(6.0);
        ui.add(
            TextEdit::singleline(&mut self.preferences.import_path)
                .hint_text("Texture file or folder path"),
        );
        ui.horizontal_wrapped(|ui| {
            if ui.button("Add Files…").clicked() {
                match choose_files_multi("Select Texture Files", IMAGE_FILTER) {
                    Ok(files) if !files.is_empty() => self.add_texture_roots(files),
                    Ok(_) => {}
                    Err(error) => self.status = error,
                }
            }
            if ui.button("Add Folder…").clicked() {
                let initial = self.preferences.import_path.clone();
                if let Some(folder) =
                    self.dialog_result(choose_folder("Select Texture Folder", &initial))
                {
                    self.add_texture_roots(vec![folder]);
                }
            }
            if ui.button("Add Path").clicked() {
                let paths = split_paths(&self.preferences.import_path)
                    .into_iter()
                    .filter(|path| path.exists())
                    .collect::<Vec<_>>();
                self.add_texture_roots(paths);
            }
            if ui.button("Clear All").clicked() {
                self.clear_textures();
            }
        });
        if self.texture.scan_receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("Scanning…");
            });
        }
        ui.add_space(8.0);
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(format!("Imported Textures ({})", self.texture.files.len()));
            ui.separator();
            let mut preview_request = None;
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
                            .selectable_label(self.texture.selected_file == Some(index), label)
                            .on_hover_text(path.display().to_string())
                            .clicked()
                        {
                            self.texture.selected_file = Some(index);
                            preview_request = Some(path.clone());
                        }
                    }
                });
            if let Some(path) = preview_request {
                let source_type = source_type_for_path(self.texture.document.as_ref(), &path);
                self.request_preview(path, source_type);
            }
        });
    }

    fn model_import_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("Model Import");
        ui.label("FBX conversion is an independent optional workflow.");
        ui.add_space(6.0);
        let (_, browse) = path_row(
            ui,
            "model_path",
            &mut self.preferences.model_path,
            "FBX file path",
        );
        if browse {
            let initial = self.preferences.model_path.clone();
            if let Some(path) =
                self.dialog_result(choose_file_open("Select FBX File", FBX_FILTER, &initial))
            {
                self.preferences.model_path = path.to_string_lossy().into_owned();
                self.save_preferences();
            }
        }
        if ui
            .add_enabled(self.model.receiver.is_none(), egui::Button::new("Load FBX"))
            .clicked()
        {
            self.start_model_load(PathBuf::from(self.preferences.model_path.trim()));
        }
        if self.model.receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("Loading model…");
            });
        }
        ui.add_space(8.0);
        if let Some(review) = &self.model.review {
            ui.group(|ui| {
                ui.set_width(ui.available_width());
                ui.strong(
                    review
                        .path
                        .file_name()
                        .and_then(|name| name.to_str())
                        .unwrap_or("FBX"),
                );
                ui.label(format!("Material slots: {}", review.material_slots.len()));
                ui.label(format!("Meshes: {}", review.model.meshes.len()));
                ui.label(format!("Nodes: {}", review.model.node_count));
                ui.label(format!("Diagnostics: {}", review.diagnostics.len()));
            });
            ui.add_space(8.0);
            if ui
                .button("Send Referenced / Embedded Textures to Texture Conversion")
                .clicked()
            {
                self.send_model_textures_to_processing();
            }
        } else {
            ui.weak("No model loaded. You can also drop car.fbx into the window.");
        }
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
                    ui.heading("Output Settings");
                    ui.add_space(2.0);
                    ScrollArea::vertical().show(ui, |ui| {
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
        ui.horizontal(|ui| {
            if ui.button("Save Settings").clicked() {
                self.save_settings();
            }
            if ui.button("Load Settings").clicked() {
                self.load_settings();
            }
        });
    }

    fn output_directory_fields(&mut self, ui: &mut egui::Ui) {
        ui.strong("Texture Output Directory");
        let (mut changed, browse) = path_row(
            ui,
            "texture_output",
            &mut self.preferences.texture_output_directory,
            r"C:\output\textures",
        );
        if browse {
            let initial = self.preferences.texture_output_directory.clone();
            if let Some(folder) =
                self.dialog_result(choose_folder("Select Texture Output Directory", &initial))
            {
                self.preferences.texture_output_directory = folder.to_string_lossy().into_owned();
                changed = true;
            }
        }
        if changed {
            self.save_preferences();
        }
        ui.add_space(5.0);
        ui.strong("Model Output Directory");
        let (mut changed, browse) = path_row(
            ui,
            "model_output",
            &mut self.preferences.model_output_directory,
            r"C:\output\model",
        );
        if browse {
            let initial = self.preferences.model_output_directory.clone();
            if let Some(folder) =
                self.dialog_result(choose_folder("Select Model Output Directory", &initial))
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
        Grid::new("primary_texture_settings")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label("Output Resolution");
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
                ui.label("Diffuse Format");
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
        ui.checkbox(
            &mut self.settings.normal_flip_green,
            "Flip Normal Map Green Channel",
        );
        ui.checkbox(
            &mut self.settings.process_metallic,
            "Convert Metallic to Albedo + Reflection",
        );
        ui.checkbox(
            &mut self.settings.generate_missing_spec,
            "Generate Missing Specular",
        );
    }

    fn advanced_settings(&mut self, ui: &mut egui::Ui) {
        ui.collapsing("Advanced", |ui| {
            ui.strong("Output Texture Types");
            Grid::new("texture_type_toggles")
                .num_columns(2)
                .show(ui, |ui| {
                    ui.checkbox(&mut self.settings.texture_types.diff, "Diffuse (_diff)");
                    ui.checkbox(&mut self.settings.texture_types.spec, "Specular (_spec)");
                    ui.end_row();
                    ui.checkbox(
                        &mut self.settings.texture_types.ddna,
                        "Normal + Gloss (_ddna)",
                    );
                    ui.checkbox(
                        &mut self.settings.texture_types.displ,
                        "Displacement (_displ)",
                    );
                    ui.end_row();
                    ui.checkbox(&mut self.settings.texture_types.emissive, "Emissive (_em)");
                    ui.checkbox(&mut self.settings.texture_types.sss, "SSS (_sss)");
                    ui.end_row();
                });
            ui.add_space(6.0);
            ui.checkbox(&mut self.settings.normalize_height, "Normalize Height Map");
            ui.checkbox(&mut self.settings.dither, "Dither");
            ui.checkbox(
                &mut self.settings.generate_missing_emissive,
                "Generate Missing Emissive",
            );
            ui.checkbox(
                &mut self.settings.generate_missing_sss,
                "Generate Missing SSS",
            );
            ui.checkbox(
                &mut self.settings.generate_sss_from_diffuse,
                "Generate SSS from Diffuse",
            );
            Grid::new("advanced_texture_settings")
                .num_columns(2)
                .show(ui, |ui| {
                    ui.label("ARM Order");
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
                    ui.label("Height → Normal Strength");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.normal_from_height_strength)
                            .speed(0.1)
                            .range(0.0..=100.0),
                    );
                    ui.end_row();
                    ui.label("Emissive Brightness");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.emissive_brightness)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label("SSS Intensity");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_intensity)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label("SSS Contrast");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_contrast)
                            .speed(0.05)
                            .range(0.0..=5.0),
                    );
                    ui.end_row();
                });
        });
    }

    fn settings_file_inputs(&mut self, ui: &mut egui::Ui) {
        ui.strong("Settings File (CLI --settings compatible)");
        let (_, browse) = path_row(
            ui,
            "settings_path",
            &mut self.preferences.settings_path,
            "texproc-settings.json",
        );
        if browse {
            let initial = self.preferences.settings_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                "Select Settings File",
                JSON_FILTER,
                &initial,
            )) {
                self.preferences.settings_path = path.to_string_lossy().into_owned();
                self.load_settings();
            }
        }
        if ui.button("Save As…").clicked() {
            let default_name = Path::new(self.preferences.settings_path.trim())
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("texproc-settings.json")
                .to_owned();
            if let Some(path) = self.dialog_result(choose_file_save(
                "Save Settings As",
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
        ui.label(format!("{group_count} groups / {unknown} unknown"));
        let processing = self.process.is_some();
        if ui
            .add_enabled(
                !processing && group_count > 0,
                egui::Button::new(RichText::new("Process Textures").strong().size(18.0))
                    .min_size([ui.available_width(), 42.0].into()),
            )
            .clicked()
        {
            self.start_texture_process();
        }
        if processing && ui.button("Show progress").clicked() {
            self.process_modal_open = true;
        }
        if let Some(summary) = &self.process_summary {
            if !self.process_modal_open {
                ui.hyperlink_to("Open output folder", file_url(&summary.output_directory));
            }
        }
    }

    fn model_export_inputs(&mut self, ui: &mut egui::Ui) {
        ui.strong("CE Model Export");
        ui.label("Optional Manifest");
        let (mut changed, browse) = path_row(
            ui,
            "manifest_path",
            &mut self.preferences.manifest_path,
            "material_manifest.json (optional)",
        );
        if browse {
            let initial = self.preferences.manifest_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                "Select Material Manifest",
                JSON_FILTER,
                &initial,
            )) {
                self.preferences.manifest_path = path.to_string_lossy().into_owned();
                changed = true;
            }
        }
        ui.label("Optional Overrides");
        let (overrides_changed, overrides_browse) = path_row(
            ui,
            "overrides_path",
            &mut self.preferences.overrides_path,
            "overrides.json (optional)",
        );
        changed |= overrides_changed;
        if overrides_browse {
            let initial = self.preferences.overrides_path.clone();
            if let Some(path) = self.dialog_result(choose_file_open(
                "Select Overrides File",
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
        self.rc_path_field(ui);
    }

    fn model_export_action(&mut self, ui: &mut egui::Ui) {
        if ui
            .add_enabled(
                self.model.review.is_some() && self.model.export_receiver.is_none(),
                egui::Button::new(RichText::new("Export CE Model").strong().size(16.0))
                    .min_size([ui.available_width(), 36.0].into()),
            )
            .clicked()
        {
            self.save_preferences();
            self.start_model_export();
        }
        if self.model.export_receiver.is_some() && ui.button("Show export progress").clicked() {
            self.model.export_modal_open = true;
        }
    }

    fn rc_path_field(&mut self, ui: &mut egui::Ui) {
        ui.label("RC Path");
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
            browse = ui.button("Browse…").clicked();
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
                    (Some(path), source) => format!(
                        "Configured RC Path is invalid. Using {source}: {}",
                        path.display()
                    ),
                    (None, _) => {
                        "RC not configured — Export CE Model will keep intermediate files only."
                            .to_owned()
                    }
                })
                .color(Color32::from_rgb(210, 70, 65)),
            );
        } else if let Some(path) = &resolution.path {
            ui.weak(format!("Using {}: {}", resolution.source, path.display()));
        } else {
            ui.label(
                RichText::new(
                    "RC not configured — Export CE Model will keep intermediate files only.",
                )
                .color(Color32::from_rgb(210, 70, 65)),
            );
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
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.strong("Preview");
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
                            RichText::new(format!("{} unknown", group.unknown.len()))
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
                        RichText::new(format!("Preview unavailable: {error}"))
                            .color(Color32::from_rgb(210, 90, 75)),
                    );
                },
            );
        } else {
            ui.allocate_ui_with_layout(
                available,
                egui::Layout::centered_and_justified(egui::Direction::TopDown),
                |ui| {
                    ui.weak("Select a group to preview");
                },
            );
        }
    }

    fn groups_panel(&mut self, ui: &mut egui::Ui) {
        let Some(document) = &self.texture.document else {
            ui.centered_and_justified(|ui| {
                ui.weak("Detected groups will appear here after textures are imported.");
            });
            return;
        };
        let groups = document.scan().groups.clone();
        let query = self.texture.group_search.trim().to_lowercase();
        let unknown_groups = groups.iter().filter(|g| !g.unknown.is_empty()).count();
        ui.horizontal(|ui| {
            ui.heading("Detected Texture Groups");
            ui.weak(format!("({} groups)", groups.len()));
            if unknown_groups > 0 {
                ui.colored_label(
                    Color32::from_rgb(200, 130, 40),
                    format!("· {unknown_groups} to assign"),
                );
            }
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.checkbox(&mut self.texture.review_only, "Unknown only");
                ui.add(
                    TextEdit::singleline(&mut self.texture.group_search)
                        .desired_width(160.0)
                        .hint_text("Search groups"),
                );
            });
        });
        ui.add_space(4.0);

        let cells_w = GROUP_CELL_W * GROUP_COLUMNS.len() as f32;
        let name_w = (ui.available_width() - cells_w - GROUP_UNKNOWN_W - 32.0).max(120.0);
        let row_w = name_w + cells_w + GROUP_UNKNOWN_W;

        // Fixed header aligned with the scrollable rows below.
        ui.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = 4.0;
            fixed_cell(ui, name_w, GROUP_ROW_H, egui::Align::LEFT, |ui| {
                ui.strong("Group");
            });
            for (_, label) in GROUP_COLUMNS {
                fixed_cell(ui, GROUP_CELL_W, GROUP_ROW_H, egui::Align::Center, |ui| {
                    ui.label(RichText::new(label).small().weak());
                });
            }
            fixed_cell(ui, GROUP_UNKNOWN_W, GROUP_ROW_H, egui::Align::LEFT, |ui| {
                ui.strong("Unknown");
            });
        });
        ui.separator();

        let visible = groups
            .iter()
            .enumerate()
            .filter(|(_, group)| !(self.texture.review_only && group.unknown.is_empty()))
            .filter(|(_, group)| {
                query.is_empty() || group.base_name.to_lowercase().contains(&query)
            })
            .map(|(index, _)| index)
            .collect::<Vec<_>>();

        let mut preview_request = None;
        let mut assign = None;
        ScrollArea::vertical()
            .id_salt("group_table")
            .auto_shrink([false, false])
            .show(ui, |ui| {
                for &index in &visible {
                    let group = &groups[index];
                    let selected = self.texture.selected_group == Some(index);
                    let has_unknown = !group.unknown.is_empty();
                    let fill = match (selected, has_unknown) {
                        (true, true) => Color32::from_rgba_unmultiplied(225, 155, 45, 70),
                        (false, true) => Color32::from_rgba_unmultiplied(220, 150, 40, 38),
                        (true, false) => Color32::from_rgba_unmultiplied(90, 140, 230, 55),
                        (false, false) => Color32::TRANSPARENT,
                    };
                    egui::Frame::new()
                        .fill(fill)
                        .inner_margin(egui::Margin::symmetric(4, 1))
                        .show(ui, |ui| {
                            ui.set_width(row_w);
                            ui.horizontal(|ui| {
                                ui.spacing_mut().item_spacing.x = 4.0;
                                fixed_cell(ui, name_w, GROUP_ROW_H, egui::Align::LEFT, |ui| {
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
                                });
                                for (source_type, _) in GROUP_COLUMNS {
                                    fixed_cell(
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
                                                ui.allocate_exact_size([13.0, 13.0].into(), sense);
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
                                    );
                                }
                                fixed_cell(
                                    ui,
                                    GROUP_UNKNOWN_W,
                                    GROUP_ROW_H,
                                    egui::Align::LEFT,
                                    |ui| {
                                        if !has_unknown {
                                            ui.weak("—");
                                            return;
                                        }
                                        let mut pick = String::new();
                                        ComboBox::from_id_salt(("assign", index))
                                            .width(GROUP_UNKNOWN_W - 12.0)
                                            .selected_text(
                                                RichText::new(format!(
                                                    "Assign ({})…",
                                                    group.unknown.len()
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
                                                        .on_disabled_hover_text(
                                                            "DEF-19: type already filled",
                                                        );
                                                    });
                                                }
                                            });
                                        if !pick.is_empty() {
                                            assign = Some((index, pick));
                                        }
                                    },
                                );
                            });
                        });
                }
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
                format!("Assigned `{source_type}` in `{base_name}`.")
            }
            Err(error) => error,
        };
    }

    fn model_workspace(&mut self, ui: &mut egui::Ui) {
        let Some(review) = &self.model.review else {
            ui.centered_and_justified(|ui| {
                ui.vertical_centered(|ui| {
                    ui.heading("FBX Material Review");
                    ui.label("Enter an FBX path on the left, or drop an FBX into the window.");
                });
            });
            return;
        };
        ui.horizontal(|ui| {
            ui.heading(
                review
                    .path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or("FBX"),
            );
            ui.separator();
            ui.label(format!("{} material slots", review.material_slots.len()));
            ui.separator();
            ui.label(format!("{} diagnostics", review.diagnostics.len()));
        });
        ui.separator();
        ScrollArea::vertical().show(ui, |ui| {
            ui.group(|ui| {
                ui.set_width(ui.available_width());
                ui.strong("RC Material Slots");
                Grid::new("model_materials")
                    .num_columns(6)
                    .striped(true)
                    .spacing([12.0, 5.0])
                    .show(ui, |ui| {
                        ui.strong("FBX");
                        ui.strong("Sub");
                        ui.strong("Material");
                        ui.strong("Physicalize");
                        ui.strong("Polygons");
                        ui.strong("Textures");
                        ui.end_row();
                        for (index, slot) in review.material_slots.iter().enumerate() {
                            let selected = self.model.selected_material == Some(index);
                            if ui
                                .selectable_label(
                                    selected,
                                    slot.fbx_material_id
                                        .and_then(|id| id.checked_sub(1))
                                        .map_or_else(|| "—".to_owned(), |value| value.to_string()),
                                )
                                .clicked()
                            {
                                self.model.selected_material = Some(index);
                            }
                            ui.label(slot.sub_index.to_string());
                            ui.label(&slot.name);
                            let inferred = resolve_physicalize(
                                slot.physicalize
                                    .as_deref()
                                    .map(|value| ("physicalize", value)),
                                &slot.name,
                            )
                            .value
                            .as_str()
                            .to_owned();
                            let mut physicalize = self
                                .model
                                .physicalize_overrides
                                .get(&slot.name)
                                .cloned()
                                .unwrap_or_else(|| inferred.clone());
                            ComboBox::from_id_salt(("physicalize", index))
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
                            if physicalize == inferred {
                                self.model.physicalize_overrides.remove(&slot.name);
                            } else {
                                self.model
                                    .physicalize_overrides
                                    .insert(slot.name.clone(), physicalize);
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
                                .and_then(|source_order| review.model.materials.get(source_order))
                                .map_or(0, |material| material.textures.len());
                            ui.label(textures.to_string());
                            ui.end_row();
                        }
                    });
            });
            ui.add_space(8.0);
            if let Some(index) = self.model.selected_material {
                if let Some(slot) = review.material_slots.get(index) {
                    ui.group(|ui| {
                        ui.set_width(ui.available_width());
                        ui.strong(format!("Material Details · {}", slot.name));
                        ui.label(format!(
                            "Assignment source: {}",
                            slot.assignment_reason
                                .as_deref()
                                .unwrap_or("slot projection")
                        ));
                        if let Some(material) = slot
                            .source_order
                            .and_then(|source_order| review.model.materials.get(source_order))
                        {
                            if material.textures.is_empty() {
                                ui.weak("No texture references");
                            }
                            for texture in &material.textures {
                                ui.horizontal_wrapped(|ui| {
                                    ui.label(RichText::new(&texture.shader_prop).strong());
                                    ui.label(if texture.embedded {
                                        format!(
                                            "{} (embedded, {} bytes)",
                                            texture.filename, texture.content_size
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
                ui.strong("Material Slot Diagnostics");
                if review.diagnostics.is_empty() {
                    ui.label(
                        RichText::new("No material slot diagnostics require attention.")
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
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        let _ = self.preferences.save();
    }
}

/// A single-line path field with a trailing `Browse…` button.
/// Returns `(text_changed, browse_clicked)`.
fn path_row(ui: &mut egui::Ui, salt: &str, value: &mut String, hint: &str) -> (bool, bool) {
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
            browse = ui.button("Browse…").clicked();
        });
    });
    (changed, browse)
}

/// A fixed-width, vertically centred table cell so the groups-table header and
/// rows line up column-for-column regardless of content.
fn fixed_cell(
    ui: &mut egui::Ui,
    width: f32,
    height: f32,
    main_align: egui::Align,
    add: impl FnOnce(&mut egui::Ui),
) {
    let layout = egui::Layout::left_to_right(egui::Align::Center).with_main_align(main_align);
    ui.allocate_ui_with_layout(egui::vec2(width, height), layout, |ui| {
        ui.set_min_height(height);
        add(ui);
    });
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

fn extract_model_texture_paths(review: &ModelReview) -> Result<Vec<PathBuf>, String> {
    let model_directory = review.path.parent().unwrap_or_else(|| Path::new("."));
    let embedded_directory = embedded_texture_directory(&review.path);
    let mut seen = BTreeSet::new();
    let mut paths = Vec::new();
    for (index, texture) in review
        .model
        .materials
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
        let path = if let Some(path) = external {
            path
        } else if texture.embedded && !texture.content.is_empty() {
            fs::create_dir_all(&embedded_directory).map_err(|error| {
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
            path
        } else {
            continue;
        };
        let key = path.to_string_lossy().to_lowercase();
        if seen.insert(key) {
            paths.push(path);
        }
    }
    Ok(paths)
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
}
