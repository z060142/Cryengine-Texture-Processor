#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod prefs;
mod worker;

use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::{
        atomic::Ordering,
        mpsc::{Receiver, TryRecvError},
    },
    time::Duration,
};

use eframe::egui::{
    self, Color32, ComboBox, FontData, FontDefinitions, FontFamily, Grid, ProgressBar, RichText,
    ScrollArea, TextEdit, TextureHandle, ViewportBuilder,
};
use prefs::{embedded_texture_directory, AppPreferences};
use texproc::{
    load_texture_settings, save_texture_settings, ArmOrder, DiffFormat, OutputResolution,
    ScanEntry, ScanGroup, TextureSettings,
};
use texproc_gui::{ReviewDocument, ASSIGNABLE_SOURCE_TYPES};
use worker::{
    ModelEvent, ModelExportEvent, ModelReview, PreviewEvent, ProcessEvent, ProcessJob, ScanEvent,
};

const APP_TITLE: &str = "CryEngine 貼圖處理器";

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
        Box::new(move |creation| {
            install_zh_tw_font(&creation.egui_ctx);
            Ok(Box::new(WorkflowApp::new(initial_path)))
        }),
    )
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum WorkflowTab {
    Textures,
    Model,
}

struct TextureState {
    roots: Vec<PathBuf>,
    files: Vec<PathBuf>,
    document: Option<ReviewDocument>,
    scan_receiver: Option<Receiver<ScanEvent>>,
    selected_file: Option<usize>,
    selected_group: Option<usize>,
    selected_unknown: Option<usize>,
    assignment_type: String,
    group_search: String,
    review_only: bool,
}

impl Default for TextureState {
    fn default() -> Self {
        Self {
            roots: Vec::new(),
            files: Vec::new(),
            document: None,
            scan_receiver: None,
            selected_file: None,
            selected_group: None,
            selected_unknown: None,
            assignment_type: ASSIGNABLE_SOURCE_TYPES[0].to_owned(),
            group_search: String::new(),
            review_only: false,
        }
    }
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
}

struct ProcessSummary {
    written: usize,
    groups: usize,
    cancelled: bool,
    elapsed_seconds: f64,
    output_directory: PathBuf,
}

#[derive(Default)]
struct ModelState {
    receiver: Option<Receiver<ModelEvent>>,
    review: Option<ModelReview>,
    selected_material: Option<usize>,
    export_receiver: Option<Receiver<ModelExportEvent>>,
    export_summary: Option<String>,
}

struct WorkflowApp {
    tab: WorkflowTab,
    preferences: AppPreferences,
    settings: TextureSettings,
    texture: TextureState,
    preview: PreviewState,
    process: Option<ProcessState>,
    process_summary: Option<ProcessSummary>,
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
            model: ModelState::default(),
            status: "就緒。拖放貼圖、資料夾或 FBX 到視窗即可開始。".to_owned(),
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
            self.status = "找不到可加入的貼圖檔案或資料夾。".to_owned();
            return;
        }
        self.tab = WorkflowTab::Textures;
        self.texture.scan_receiver = Some(worker::start_scan(self.texture.roots.clone()));
        self.status = "正在掃描與分組貼圖…".to_owned();
    }

    fn clear_textures(&mut self) {
        self.texture = TextureState::default();
        self.preview = PreviewState::default();
        self.process_summary = None;
        self.status = "已清除所有暫態貼圖與分組。".to_owned();
    }

    fn start_model_load(&mut self, path: PathBuf) {
        if !path.is_file() {
            self.status = format!("FBX 不存在：{}", path.display());
            return;
        }
        self.preferences.model_path = path.to_string_lossy().into_owned();
        self.model.receiver = Some(worker::start_model_load(path));
        self.model.review = None;
        self.model.selected_material = None;
        self.model.export_summary = None;
        self.tab = WorkflowTab::Model;
        self.status = "正在讀取 FBX 材質與貼圖參照…".to_owned();
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
            self.status = "尚未加入可處理的貼圖。".to_owned();
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
            self.texture.selected_unknown = Some(0);
            self.texture.review_only = true;
            self.status = format!(
                "請先為 `{}` 的 unknown 貼圖指定型別，再開始處理。",
                blocked.base_name
            );
            return;
        }
        let output = PathBuf::from(self.preferences.texture_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = "請先設定貼圖輸出目錄。".to_owned();
            return;
        }
        if let Err(error) = fs::create_dir_all(&output) {
            self.status = format!("無法建立貼圖輸出目錄：{error}");
            return;
        }

        let scan = document.scan().clone();
        let total = scan.groups.len();
        self.process = Some(ProcessState {
            job: worker::start_process(scan, self.settings, output),
            completed: 0,
            total,
            current_group: "準備中".to_owned(),
            written: 0,
        });
        self.process_summary = None;
        self.status = format!("正在處理 {total} 個貼圖群組…");
    }

    fn start_model_export(&mut self) {
        let Some(review) = &self.model.review else {
            self.status = "請先載入 FBX。".to_owned();
            return;
        };
        let output = PathBuf::from(self.preferences.model_output_directory.trim());
        if output.as_os_str().is_empty() {
            self.status = "請先設定模型輸出目錄。".to_owned();
            return;
        }
        let manifest = optional_path(&self.preferences.manifest_path);
        let overrides = optional_path(&self.preferences.overrides_path);
        let texture_dir = optional_path(&self.preferences.texture_output_directory);
        self.model.export_receiver = Some(worker::start_model_export(
            review.path.clone(),
            manifest,
            overrides,
            texture_dir,
            output,
        ));
        self.model.export_summary = None;
        self.status = "正在輸出 CryEngine .mtl 與 request JSON…".to_owned();
    }

    fn send_model_textures_to_processing(&mut self) {
        let Some(review) = &self.model.review else {
            self.status = "請先載入 FBX。".to_owned();
            return;
        };
        match extract_model_texture_paths(review) {
            Ok(paths) if paths.is_empty() => {
                self.status = "FBX 沒有可送入處理的外部或內嵌貼圖。".to_owned();
            }
            Ok(paths) => {
                let count = paths.len();
                self.add_texture_roots(paths);
                self.status = format!("已從 FBX 送入 {count} 個貼圖參照並開始分組。");
            }
            Err(error) => {
                self.status = error;
            }
        }
    }

    fn assign_unknown(&mut self) {
        let (Some(group_index), Some(unknown_index), Some(document)) = (
            self.texture.selected_group,
            self.texture.selected_unknown,
            &mut self.texture.document,
        ) else {
            self.status = "請先選擇 unknown 貼圖。".to_owned();
            return;
        };
        self.status = match document.assign_unknown(
            group_index,
            unknown_index,
            &self.texture.assignment_type,
        ) {
            Ok(()) => {
                let remaining = document.scan().groups[group_index].unknown.len();
                if remaining == 0 && self.texture.review_only {
                    let next_group = document
                        .scan()
                        .groups
                        .iter()
                        .position(|group| !group.unknown.is_empty());
                    if let Some(next_group) = next_group {
                        self.texture.selected_group = Some(next_group);
                        self.texture.selected_unknown = Some(0);
                    } else {
                        self.texture.review_only = false;
                        self.texture.selected_group = Some(0);
                        self.texture.selected_unknown = None;
                    }
                } else {
                    self.texture.selected_unknown =
                        (remaining > 0).then_some(unknown_index.min(remaining - 1));
                }
                format!("已將貼圖指派為 `{}`。", self.texture.assignment_type)
            }
            Err(error) => error,
        };
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
                    Err(TryRecvError::Disconnected) => {
                        Some(ScanEvent::Failed("貼圖掃描背景工作意外中止。".to_owned()))
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
                let selected_group = scan
                    .groups
                    .iter()
                    .position(|group| !group.unknown.is_empty())
                    .or((groups > 0).then_some(0));
                self.texture.selected_group = selected_group;
                self.texture.selected_unknown = selected_group
                    .and_then(|index| (!scan.groups[index].unknown.is_empty()).then_some(0));
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
                    "已加入 {} 個貼圖，辨識 {groups} 組，{unknown} 個 unknown。",
                    self.texture.files.len()
                );
                if let Some((path, source_type)) = preview_request {
                    self.request_preview(path, source_type);
                }
            }
            ScanEvent::Failed(error) => {
                self.status = format!("貼圖掃描失敗：{error}");
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
                    process.current_group = group;
                    process.written += written;
                }
                Ok(ProcessEvent::Finished(result)) => {
                    finished = Some(result);
                    break;
                }
                Err(TryRecvError::Empty) => break,
                Err(TryRecvError::Disconnected) => {
                    finished = Some(Err("貼圖處理背景工作意外中止。".to_owned()));
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
                    format!("處理已取消；完成 {} 個群組。", report.groups.len())
                } else {
                    format!(
                        "處理完成：{} 個群組，{written} 個輸出檔。",
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
                self.status = format!("貼圖處理失敗：{error}");
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
                self.status =
                    format!("FBX 載入完成：{materials} 個材質槽，{references} 個貼圖參照。");
            }
            ModelEvent::Failed(error) => {
                self.status = format!("FBX 載入失敗：{error}");
            }
        }
    }

    fn poll_model_export(&mut self) {
        let event = self
            .model
            .export_receiver
            .as_ref()
            .and_then(|receiver| receiver.try_recv().ok());
        let Some(event) = event else {
            return;
        };
        self.model.export_receiver = None;
        match event {
            ModelExportEvent::Completed(outputs) => {
                let summary = format!(
                    "{}\n{}\n{} diagnostic(s)",
                    outputs.mtl.display(),
                    outputs.request.display(),
                    outputs.material_diagnostics.len()
                );
                self.model.export_summary = Some(summary);
                self.status = "模型材質輸出完成。".to_owned();
            }
            ModelExportEvent::Failed(error) => {
                self.status = format!("模型材質輸出失敗：{error}");
            }
        }
    }

    fn save_preferences(&mut self) {
        if let Err(error) = self.preferences.save() {
            self.status = error;
        }
    }

    fn save_settings(&mut self) {
        let path = PathBuf::from(self.preferences.settings_path.trim());
        match save_texture_settings(&path, &self.settings) {
            Ok(()) => {
                self.save_preferences();
                self.status = format!("設定已儲存：{}", path.display());
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
                self.status = format!("設定已載入：{}", path.display());
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
                ui.label("貼圖轉換主流程");
                if self.model.review.is_some() {
                    ui.separator();
                    ui.weak("FBX 材質工具已就緒");
                }
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.weak("可直接拖放檔案或資料夾");
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
                {
                    ui.spinner();
                }
            });
        });
    }

    fn left_panel(&mut self, context: &egui::Context) {
        egui::SidePanel::left("imports")
            .resizable(true)
            .default_width(320.0)
            .min_width(270.0)
            .max_width(430.0)
            .show(context, |ui| {
                ui.horizontal(|ui| {
                    ui.selectable_value(&mut self.tab, WorkflowTab::Textures, "貼圖導入");
                    ui.selectable_value(&mut self.tab, WorkflowTab::Model, "模型導入");
                });
                ui.separator();
                match self.tab {
                    WorkflowTab::Textures => self.texture_import_panel(ui),
                    WorkflowTab::Model => self.model_import_panel(ui),
                }
            });
    }

    fn texture_import_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("貼圖導入");
        ui.label("加入單張貼圖、整個資料夾，或直接拖放。");
        ui.add_space(6.0);
        ui.add(
            TextEdit::singleline(&mut self.preferences.import_path)
                .hint_text("貼圖檔案或資料夾路徑"),
        );
        ui.horizontal_wrapped(|ui| {
            if ui.button("加入檔案").clicked() {
                let paths = split_paths(&self.preferences.import_path)
                    .into_iter()
                    .filter(|path| path.is_file())
                    .collect::<Vec<_>>();
                self.add_texture_roots(paths);
            }
            if ui.button("加入資料夾").clicked() {
                let path = PathBuf::from(self.preferences.import_path.trim());
                self.add_texture_roots((path.is_dir()).then_some(path).into_iter().collect());
            }
            if ui.button("清除全部").clicked() {
                self.clear_textures();
            }
        });
        if self.texture.scan_receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("掃描中…");
            });
        }
        ui.add_space(8.0);
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong(format!("已導入貼圖 ({})", self.texture.files.len()));
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
        ui.heading("模型導入");
        ui.label("FBX 材質轉換是獨立的選配流程。");
        ui.add_space(6.0);
        ui.add(TextEdit::singleline(&mut self.preferences.model_path).hint_text("FBX 檔案路徑"));
        if ui
            .add_enabled(self.model.receiver.is_none(), egui::Button::new("載入 FBX"))
            .clicked()
        {
            self.start_model_load(PathBuf::from(self.preferences.model_path.trim()));
        }
        if self.model.receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("讀取模型中…");
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
                ui.label(format!("材質槽：{}", review.material_slots.len()));
                ui.label(format!("Meshes：{}", review.model.meshes.len()));
                ui.label(format!("Nodes：{}", review.model.node_count));
                ui.label(format!("診斷：{}", review.diagnostics.len()));
            });
            ui.add_space(8.0);
            if ui.button("將引用／內嵌貼圖送入貼圖轉換").clicked() {
                self.send_model_textures_to_processing();
            }
        } else {
            ui.weak("尚未載入模型。也可以直接將 car.fbx 拖入視窗。");
        }
    }

    fn right_panel(&mut self, context: &egui::Context) {
        egui::SidePanel::right("export_settings")
            .resizable(true)
            .default_width(370.0)
            .min_width(330.0)
            .max_width(470.0)
            .show(context, |ui| {
                ScrollArea::vertical().show(ui, |ui| {
                    ui.heading("輸出設定");
                    ui.add_space(5.0);
                    self.output_directory_fields(ui);
                    ui.separator();
                    self.texture_settings_panel(ui);
                    ui.separator();
                    self.settings_file_panel(ui);
                    ui.separator();
                    match self.tab {
                        WorkflowTab::Textures => self.texture_actions(ui),
                        WorkflowTab::Model => self.model_actions(ui),
                    }
                });
            });
    }

    fn output_directory_fields(&mut self, ui: &mut egui::Ui) {
        ui.strong("貼圖輸出目錄");
        if ui
            .add(
                TextEdit::singleline(&mut self.preferences.texture_output_directory)
                    .hint_text(r"C:\output\textures"),
            )
            .changed()
        {
            self.save_preferences();
        }
        ui.add_space(5.0);
        ui.strong("模型輸出目錄");
        if ui
            .add(
                TextEdit::singleline(&mut self.preferences.model_output_directory)
                    .hint_text(r"C:\output\model"),
            )
            .changed()
        {
            self.save_preferences();
        }
    }

    fn texture_settings_panel(&mut self, ui: &mut egui::Ui) {
        ui.strong("貼圖輸出設定");
        Grid::new("primary_texture_settings")
            .num_columns(2)
            .spacing([12.0, 6.0])
            .show(ui, |ui| {
                ui.label("輸出解析度");
                ComboBox::from_id_salt("resolution")
                    .selected_text(resolution_label(self.settings.output_resolution))
                    .show_ui(ui, |ui| {
                        for (label, value) in [
                            ("原始", OutputResolution::Original),
                            ("4096", OutputResolution::Max(4096)),
                            ("2048", OutputResolution::Max(2048)),
                            ("1024", OutputResolution::Max(1024)),
                            ("512", OutputResolution::Max(512)),
                            ("64（驗證）", OutputResolution::Max(64)),
                        ] {
                            ui.selectable_value(&mut self.settings.output_resolution, value, label);
                        }
                    });
                ui.end_row();
                ui.label("漫反射格式");
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
        ui.checkbox(&mut self.settings.normal_flip_green, "翻轉法線圖綠色通道");
        ui.checkbox(
            &mut self.settings.process_metallic,
            "轉換 Metallic 為 Albedo + Reflection",
        );
        ui.checkbox(
            &mut self.settings.generate_missing_spec,
            "產生缺少的 Specular",
        );

        ui.add_space(5.0);
        ui.strong("輸出貼圖類型");
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

        ui.collapsing("進階設定", |ui| {
            ui.checkbox(&mut self.settings.normalize_height, "正規化高度圖");
            ui.checkbox(&mut self.settings.dither, "Dither");
            ui.checkbox(
                &mut self.settings.generate_missing_emissive,
                "產生缺少的 Emissive",
            );
            ui.checkbox(&mut self.settings.generate_missing_sss, "產生缺少的 SSS");
            ui.checkbox(
                &mut self.settings.generate_sss_from_diffuse,
                "由 Diffuse 產生 SSS",
            );
            Grid::new("advanced_texture_settings")
                .num_columns(2)
                .show(ui, |ui| {
                    ui.label("ARM 順序");
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
                    ui.label("Height → Normal 強度");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.normal_from_height_strength)
                            .speed(0.1)
                            .range(0.0..=100.0),
                    );
                    ui.end_row();
                    ui.label("Emissive 亮度");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.emissive_brightness)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label("SSS 強度");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_intensity)
                            .speed(0.05)
                            .range(0.0..=20.0),
                    );
                    ui.end_row();
                    ui.label("SSS 對比");
                    ui.add(
                        egui::DragValue::new(&mut self.settings.sss_contrast)
                            .speed(0.05)
                            .range(0.0..=5.0),
                    );
                    ui.end_row();
                });
        });
    }

    fn settings_file_panel(&mut self, ui: &mut egui::Ui) {
        ui.strong("設定檔（與 CLI --settings 相容）");
        ui.add(
            TextEdit::singleline(&mut self.preferences.settings_path)
                .hint_text("texproc-settings.json"),
        );
        ui.horizontal(|ui| {
            if ui.button("載入設定").clicked() {
                self.load_settings();
            }
            if ui.button("儲存設定").clicked() {
                self.save_settings();
            }
        });
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
        ui.label(format!("{group_count} 個群組／{unknown} 個 unknown"));
        let processing = self.process.is_some();
        if ui
            .add_enabled(
                !processing && group_count > 0,
                egui::Button::new(RichText::new("處理貼圖").strong().size(18.0))
                    .min_size([ui.available_width(), 42.0].into()),
            )
            .clicked()
        {
            self.start_texture_process();
        }
        if let Some(process) = &mut self.process {
            let progress = if process.total == 0 {
                0.0
            } else {
                process.completed as f32 / process.total as f32
            };
            ui.add(ProgressBar::new(progress).show_percentage().text(format!(
                "{} / {} · {}",
                process.completed, process.total, process.current_group
            )));
            if ui.button("取消").clicked() {
                process.job.cancel.store(true, Ordering::Relaxed);
                self.status = "正在取消；已開始的群組會先安全完成。".to_owned();
            }
        }
        if let Some(summary) = &self.process_summary {
            ui.group(|ui| {
                ui.strong(if summary.cancelled {
                    "處理已取消"
                } else {
                    "處理完成"
                });
                ui.label(format!(
                    "{} 個群組／{} 個檔案／{:.2} 秒",
                    summary.groups, summary.written, summary.elapsed_seconds
                ));
                ui.hyperlink_to("開啟輸出目錄", file_url(&summary.output_directory));
            });
        }
    }

    fn model_actions(&mut self, ui: &mut egui::Ui) {
        ui.strong("FBX 材質輸出");
        ui.label("選配 manifest");
        ui.add(
            TextEdit::singleline(&mut self.preferences.manifest_path)
                .hint_text("material_manifest.json（可留空）"),
        );
        ui.label("選配 overrides");
        ui.add(
            TextEdit::singleline(&mut self.preferences.overrides_path)
                .hint_text("overrides.json（可留空）"),
        );
        if ui
            .add_enabled(
                self.model.review.is_some() && self.model.export_receiver.is_none(),
                egui::Button::new(RichText::new("輸出 Material (.mtl + request)").strong())
                    .min_size([ui.available_width(), 40.0].into()),
            )
            .clicked()
        {
            self.save_preferences();
            self.start_model_export();
        }
        if self.model.export_receiver.is_some() {
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label("輸出中…");
            });
        }
        if let Some(summary) = &self.model.export_summary {
            ui.label(summary);
            ui.hyperlink_to(
                "開啟模型輸出目錄",
                file_url(Path::new(&self.preferences.model_output_directory)),
            );
        }
    }

    fn central_panel(&mut self, context: &egui::Context) {
        egui::CentralPanel::default().show(context, |ui| match self.tab {
            WorkflowTab::Textures => self.texture_workspace(ui),
            WorkflowTab::Model => self.model_workspace(ui),
        });
    }

    fn texture_workspace(&mut self, ui: &mut egui::Ui) {
        self.preview_panel(ui);
        ui.separator();
        self.groups_panel(ui);
    }

    fn preview_panel(&mut self, ui: &mut egui::Ui) {
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.horizontal(|ui| {
                ui.strong("貼圖預覽");
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
            ui.add_space(4.0);
            let available = egui::vec2(ui.available_width(), 285.0);
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
                            RichText::new(format!("無法預覽：{error}"))
                                .color(Color32::from_rgb(210, 90, 75)),
                        );
                    },
                );
            } else {
                ui.allocate_ui_with_layout(
                    available,
                    egui::Layout::centered_and_justified(egui::Direction::TopDown),
                    |ui| {
                        ui.weak("從左側貼圖清單或下方群組選擇貼圖");
                    },
                );
            }
        });
    }

    fn groups_panel(&mut self, ui: &mut egui::Ui) {
        let Some(document) = &self.texture.document else {
            ui.centered_and_justified(|ui| {
                ui.weak("加入貼圖後，偵測群組會顯示在這裡。");
            });
            return;
        };
        let groups = document.scan().groups.clone();
        let query = self.texture.group_search.trim().to_lowercase();
        ui.horizontal(|ui| {
            ui.heading("偵測到的貼圖組");
            ui.weak(format!("({})", groups.len()));
            ui.separator();
            ui.add(
                TextEdit::singleline(&mut self.texture.group_search)
                    .desired_width(180.0)
                    .hint_text("搜尋群組"),
            );
            ui.checkbox(&mut self.texture.review_only, "只看待處理");
        });
        ui.add_space(4.0);

        let mut preview_request = None;
        let mut assign_requested = false;
        ui.columns(2, |columns| {
            columns[0].vertical(|ui| {
                Grid::new("group_list_headers")
                    .num_columns(3)
                    .show(ui, |ui| {
                        ui.strong("基本名稱");
                        ui.strong("已識別");
                        ui.strong("Unknown");
                        ui.end_row();
                    });
                ui.separator();
                ScrollArea::vertical()
                    .id_salt("group_list")
                    .max_height(245.0)
                    .show(ui, |ui| {
                        Grid::new("group_list_rows")
                            .num_columns(3)
                            .striped(true)
                            .spacing([8.0, 4.0])
                            .show(ui, |ui| {
                                for (index, group) in groups.iter().enumerate() {
                                    if self.texture.review_only && group.unknown.is_empty() {
                                        continue;
                                    }
                                    if !query.is_empty()
                                        && !group.base_name.to_lowercase().contains(&query)
                                    {
                                        continue;
                                    }
                                    if ui
                                        .selectable_label(
                                            self.texture.selected_group == Some(index),
                                            &group.base_name,
                                        )
                                        .clicked()
                                    {
                                        self.texture.selected_group = Some(index);
                                        self.texture.selected_unknown =
                                            (!group.unknown.is_empty()).then_some(0);
                                        self.texture.assignment_type =
                                            ASSIGNABLE_SOURCE_TYPES[0].to_owned();
                                        preview_request = first_group_entry(group).map(|entry| {
                                            (PathBuf::from(&entry.path), entry.source_type.clone())
                                        });
                                    }
                                    ui.label(group.slots.len().to_string());
                                    let unknown = group.unknown.len();
                                    ui.label(if unknown == 0 {
                                        RichText::new("—").weak()
                                    } else {
                                        RichText::new(unknown.to_string())
                                            .strong()
                                            .color(Color32::from_rgb(220, 160, 55))
                                    });
                                    ui.end_row();
                                }
                            });
                    });
            });

            columns[1].vertical(|ui| {
                let group = self
                    .texture
                    .selected_group
                    .and_then(|index| groups.get(index));
                let Some(group) = group else {
                    ui.weak("選擇群組以檢視詳情。");
                    return;
                };
                ui.strong(format!("組詳情 · {}", group.base_name));
                ui.label(format!("貼圖類型：{}", detected_type_summary(group)));
                ScrollArea::vertical()
                    .id_salt("group_detail")
                    .max_height(105.0)
                    .show(ui, |ui| {
                        for source_type in ASSIGNABLE_SOURCE_TYPES {
                            if let Some(entry) = group.slots.get(source_type) {
                                if ui
                                    .selectable_label(
                                        false,
                                        format!("{source_type}: {}", entry.filename),
                                    )
                                    .on_hover_text(&entry.path)
                                    .clicked()
                                {
                                    preview_request =
                                        Some((PathBuf::from(&entry.path), source_type.to_owned()));
                                }
                            }
                        }
                    });
                ui.separator();
                ui.strong("Unknown 貼圖");
                for (index, entry) in group.unknown.iter().enumerate() {
                    if ui
                        .selectable_label(
                            self.texture.selected_unknown == Some(index),
                            &entry.filename,
                        )
                        .on_hover_text(&entry.path)
                        .clicked()
                    {
                        self.texture.selected_unknown = Some(index);
                        preview_request = Some((PathBuf::from(&entry.path), "unknown".to_owned()));
                    }
                }
                if !group.unknown.is_empty() {
                    let occupant = group
                        .slots
                        .get(self.texture.assignment_type.as_str())
                        .map(|entry| entry.filename.as_str());
                    ui.horizontal(|ui| {
                        ui.label("指定型別");
                        ComboBox::from_id_salt("unknown_assignment")
                            .selected_text(&self.texture.assignment_type)
                            .show_ui(ui, |ui| {
                                for source_type in ASSIGNABLE_SOURCE_TYPES {
                                    ui.selectable_value(
                                        &mut self.texture.assignment_type,
                                        source_type.to_owned(),
                                        source_type,
                                    );
                                }
                            });
                        if ui
                            .add_enabled(
                                self.texture.selected_unknown.is_some() && occupant.is_none(),
                                egui::Button::new("套用"),
                            )
                            .clicked()
                        {
                            assign_requested = true;
                        }
                    });
                    if let Some(filename) = occupant {
                        ui.label(
                            RichText::new(format!("DEF-19：目標型別已有 {filename}，請選空槽。"))
                                .color(Color32::from_rgb(210, 80, 70)),
                        );
                    }
                } else {
                    ui.label(
                        RichText::new("此群組已完成分類。").color(Color32::from_rgb(70, 165, 95)),
                    );
                }
            });
        });
        if let Some((path, source_type)) = preview_request {
            self.request_preview(path, source_type);
        }
        if assign_requested {
            self.assign_unknown();
        }
    }

    fn model_workspace(&mut self, ui: &mut egui::Ui) {
        let Some(review) = &self.model.review else {
            ui.centered_and_justified(|ui| {
                ui.vertical_centered(|ui| {
                    ui.heading("FBX 材質檢視");
                    ui.label("從左側輸入 FBX 路徑，或將 FBX 拖入視窗。");
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
            ui.label(format!("{} 個材質槽", review.material_slots.len()));
            ui.separator();
            ui.label(format!("{} 個診斷", review.diagnostics.len()));
        });
        ui.separator();
        ScrollArea::vertical().show(ui, |ui| {
            ui.group(|ui| {
                ui.set_width(ui.available_width());
                ui.strong("RC 材質槽");
                Grid::new("model_materials")
                    .num_columns(5)
                    .striped(true)
                    .spacing([12.0, 5.0])
                    .show(ui, |ui| {
                        ui.strong("FBX");
                        ui.strong("Sub");
                        ui.strong("材質");
                        ui.strong("Polygons");
                        ui.strong("貼圖");
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
                        ui.strong(format!("材質詳情 · {}", slot.name));
                        ui.label(format!(
                            "指派依據：{}",
                            slot.assignment_reason
                                .as_deref()
                                .unwrap_or("slot projection")
                        ));
                        if let Some(material) = slot
                            .source_order
                            .and_then(|source_order| review.model.materials.get(source_order))
                        {
                            if material.textures.is_empty() {
                                ui.weak("沒有貼圖參照");
                            }
                            for texture in &material.textures {
                                ui.horizontal_wrapped(|ui| {
                                    ui.label(RichText::new(&texture.shader_prop).strong());
                                    ui.label(if texture.embedded {
                                        format!(
                                            "{}（內嵌，{} bytes）",
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
                ui.strong("材質槽診斷");
                if review.diagnostics.is_empty() {
                    ui.label(
                        RichText::new("沒有需要處理的材質槽診斷。")
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
    }

    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        let _ = self.preferences.save();
    }
}

fn install_zh_tw_font(context: &egui::Context) {
    let candidates = [
        Path::new(r"C:\Windows\Fonts\msjh.ttc"),
        Path::new(r"C:\Windows\Fonts\mingliu.ttc"),
    ];
    let Some(bytes) = candidates.iter().find_map(|path| fs::read(path).ok()) else {
        return;
    };
    let mut fonts = FontDefinitions::default();
    fonts
        .font_data
        .insert("zh_tw".to_owned(), FontData::from_owned(bytes).into());
    for family in [FontFamily::Proportional, FontFamily::Monospace] {
        fonts
            .families
            .entry(family)
            .or_default()
            .insert(0, "zh_tw".to_owned());
    }
    context.set_fonts(fonts);
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

fn detected_type_summary(group: &ScanGroup) -> String {
    let values = ASSIGNABLE_SOURCE_TYPES
        .iter()
        .filter(|source_type| group.slots.contains_key(**source_type))
        .copied()
        .collect::<Vec<_>>();
    if values.is_empty() {
        "—".to_owned()
    } else {
        values.join(", ")
    }
}

fn resolution_label(value: OutputResolution) -> String {
    match value {
        OutputResolution::Original => "原始".to_owned(),
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
                    "無法建立內嵌貼圖暫存目錄 {}：{error}",
                    embedded_directory.display()
                )
            })?;
            let filename = Path::new(&texture.filename)
                .file_name()
                .filter(|name| !name.is_empty())
                .map(PathBuf::from)
                .unwrap_or_else(|| PathBuf::from(format!("embedded_{index}.png")));
            let path = embedded_directory.join(filename);
            fs::write(&path, &texture.content)
                .map_err(|error| format!("無法寫出內嵌貼圖 {}：{error}", path.display()))?;
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
