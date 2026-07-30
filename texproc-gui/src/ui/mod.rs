//! v2 UI composition (SPEC.md §2): mode/panel state, preset machinery, and the
//! per-frame panel ordering. All drawing routes through `draw`.

pub mod dialogs;
pub mod icons;
pub mod rail;
pub mod stack_models;
pub mod stack_textures;
pub mod stage_models;
pub mod stage_textures;
pub mod theme;
pub mod timeline;
pub mod topbar;
pub mod widgets;

use std::collections::BTreeMap;
use std::time::Instant;

use eframe::egui::{self, Align2, FontId, Pos2, Sense, Stroke, Vec2};
use serde_json::{json, Value};

use widgets::{TaskCard, TaskState, Toast};

/// Rail-selected working mode. Replaces the v1 `WorkflowTab` 1:1 (the rail
/// also shows disabled Proxy/PBR placeholders that have no mode).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum UiMode {
    Textures,
    Models,
}

impl UiMode {
    pub fn panel_ids(self) -> &'static [&'static str] {
        match self {
            UiMode::Textures => &["tex.import", "tex.groups", "tex.convert", "tex.rc"],
            UiMode::Models => &["mdl.fbx", "mdl.transform", "mdl.export"],
        }
    }

    /// Prefs key for this mode's workspace memory.
    fn key(self) -> &'static str {
        match self {
            UiMode::Textures => "textures",
            UiMode::Models => "models",
        }
    }
}

/// Panel → preset membership (SPEC §5 table). `minimal` closes everything;
/// `review` / `export` open exactly the panels tagged with that preset.
fn panel_preset(id: &str) -> &'static str {
    match id {
        "tex.import" | "tex.groups" | "mdl.fbx" => "review",
        "tex.convert" | "tex.rc" | "mdl.transform" | "mdl.export" => "export",
        _ => "",
    }
}

const PRESET_IDS: [&str; 4] = ["minimal", "review", "export", "custom"];

/// Per-mode stack memory: open state per panel, active preset, and the Custom
/// snapshot (panel_ids order).
pub struct PanelMemory {
    pub open: BTreeMap<String, bool>,
    pub preset: String,
    pub custom: Vec<bool>,
}

impl PanelMemory {
    /// First-run default: preset "review" applied.
    fn default_for(mode: UiMode) -> Self {
        let mut memory = Self {
            open: BTreeMap::new(),
            preset: "review".to_owned(),
            custom: Vec::new(),
        };
        for id in mode.panel_ids() {
            memory
                .open
                .insert((*id).to_owned(), panel_preset(id) == "review");
        }
        memory
    }

    fn to_value(&self) -> Value {
        json!({
            "preset": self.preset,
            "custom": self.custom,
            "open": self.open.iter().map(|(k, v)| (k.clone(), Value::Bool(*v)))
                .collect::<serde_json::Map<_, _>>(),
        })
    }
}

// ---- work tracker (Phase B3) ------------------------------------------------

/// Which background jobs are live this frame — a pure snapshot of the
/// `WorkflowApp` worker state, so edge detection stays unit-testable without
/// an egui context (SPEC §9/§10).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct JobSnapshot {
    pub scan: bool,
    pub process: bool,
    /// The running process entered its RC/DDS phase.
    pub dds: bool,
    /// Pending FBX load receivers.
    pub loads: usize,
    pub export: bool,
    pub batch: bool,
    /// Loaded model count (measures how many FBX a load wave produced).
    pub entries: usize,
}

/// Jobs whose completion edge fired this frame.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct FinishedJobs {
    pub scan: bool,
    pub process: bool,
    /// The finished process had run its RC/DDS phase.
    pub process_had_dds: bool,
    /// `Some(n)` when the FBX load wave drained; `n` = models it added.
    pub loads: Option<usize>,
    pub export: bool,
    pub batch: bool,
}

/// Prev-frame job snapshot for completion-transition detection. Lives entirely
/// in the UI layer: `timeline::draw` feeds it a `JobSnapshot` every frame and
/// turns the returned edges into stored task cards + completion toasts, so
/// main.rs never has to signal "finished" explicitly.
pub struct WorkTracker {
    /// Session start. Task stamps are "+MM:SS" offsets from here — std has no
    /// local wall-clock formatting and new deps are banned, so cards carry
    /// session-relative times instead of HH:MM.
    pub started: Instant,
    pub scan_was_running: bool,
    pub process_was_running: bool,
    pub dds_was_active: bool,
    pub loads_pending_prev: usize,
    /// Model count when the current FBX load wave began.
    pub entries_at_load_start: usize,
    pub export_was_running: bool,
    pub batch_was_running: bool,
    // Last-seen live counters — the finished-card fallback when a job dies
    // without leaving a summary behind.
    pub prev_convert_done: usize,
    pub prev_convert_total: usize,
    pub prev_dds_done: usize,
    pub prev_dds_total: usize,
    /// Last non-idle session fraction; idle keeps showing it (SPEC §9).
    pub last_session_fraction: f32,
}

impl Default for WorkTracker {
    fn default() -> Self {
        Self {
            started: Instant::now(),
            scan_was_running: false,
            process_was_running: false,
            dds_was_active: false,
            loads_pending_prev: 0,
            entries_at_load_start: 0,
            export_was_running: false,
            batch_was_running: false,
            prev_convert_done: 0,
            prev_convert_total: 0,
            prev_dds_done: 0,
            prev_dds_total: 0,
            last_session_fraction: 0.0,
        }
    }
}

impl WorkTracker {
    /// Compare this frame against the previous one, record the new snapshot,
    /// and report which jobs finished on this edge.
    pub fn finished_jobs(&mut self, now: JobSnapshot) -> FinishedJobs {
        // A new load wave begins: remember how many models existed before it.
        if self.loads_pending_prev == 0 && now.loads > 0 {
            self.entries_at_load_start = now.entries;
        }
        let process_finished = self.process_was_running && !now.process;
        let finished = FinishedJobs {
            scan: self.scan_was_running && !now.scan,
            process: process_finished,
            process_had_dds: process_finished && self.dds_was_active,
            loads: (self.loads_pending_prev > 0 && now.loads == 0)
                .then(|| now.entries.saturating_sub(self.entries_at_load_start)),
            export: self.export_was_running && !now.export,
            batch: self.batch_was_running && !now.batch,
        };
        self.scan_was_running = now.scan;
        self.process_was_running = now.process;
        // The DDS flag latches while the process lives so the finish edge still
        // knows a DDS phase ran; it resets once that edge has been reported.
        if now.process {
            self.dds_was_active = now.dds;
        } else {
            self.dds_was_active = false;
        }
        self.loads_pending_prev = now.loads;
        self.export_was_running = now.export;
        self.batch_was_running = now.batch;
        finished
    }

    /// "+MM:SS" since session start, stamped onto finished task cards.
    pub fn stamp(&self) -> String {
        let seconds = self.started.elapsed().as_secs();
        format!("+{:02}:{:02}", seconds / 60, seconds % 60)
    }
}

/// Whole-chrome UI state, persisted through `prefs.ui_workspace`.
pub struct UiState {
    pub mode: UiMode,
    pub textures: PanelMemory,
    pub models: PanelMemory,
    pub toasts: Vec<Toast>,
    pub session_tasks: Vec<TaskCard>,
    pub next_task_id: u64,
    pub diag_open: bool,
    /// Job-completion edge detector + session progress memory (Phase B3).
    pub work: WorkTracker,
}

impl Default for UiState {
    fn default() -> Self {
        Self {
            mode: UiMode::Textures,
            textures: PanelMemory::default_for(UiMode::Textures),
            models: PanelMemory::default_for(UiMode::Models),
            toasts: Vec::new(),
            session_tasks: Vec::new(),
            next_task_id: 1,
            diag_open: false,
            work: WorkTracker::default(),
        }
    }
}

impl UiState {
    pub fn memory(&self, mode: UiMode) -> &PanelMemory {
        match mode {
            UiMode::Textures => &self.textures,
            UiMode::Models => &self.models,
        }
    }

    fn memory_mut(&mut self, mode: UiMode) -> &mut PanelMemory {
        match mode {
            UiMode::Textures => &mut self.textures,
            UiMode::Models => &mut self.models,
        }
    }

    /// Apply a preset button press (mockup `applyPreset`): `minimal` collapses
    /// all, `review`/`export` open their tagged panels, `custom` restores the
    /// snapshot taken at the last manual toggle.
    pub fn apply_preset(&mut self, mode: UiMode, preset: &str) {
        if !PRESET_IDS.contains(&preset) {
            return;
        }
        let ids = mode.panel_ids();
        let memory = self.memory_mut(mode);
        if preset == "custom" {
            if memory.custom.len() == ids.len() {
                for (index, id) in ids.iter().enumerate() {
                    memory.open.insert((*id).to_owned(), memory.custom[index]);
                }
            }
        } else {
            for id in ids {
                memory.open.insert(
                    (*id).to_owned(),
                    preset != "minimal" && panel_preset(id) == preset,
                );
            }
        }
        memory.preset = preset.to_owned();
    }

    /// A manual panel toggle: snapshot the layout and switch to Custom
    /// (mockup `markCustom`).
    pub fn mark_custom(&mut self, mode: UiMode) {
        let ids = mode.panel_ids();
        let memory = self.memory_mut(mode);
        memory.custom = ids
            .iter()
            .map(|id| memory.open.get(*id).copied().unwrap_or(false))
            .collect();
        memory.preset = "custom".to_owned();
    }

    pub fn is_open(&self, mode: UiMode, id: &str) -> bool {
        self.memory(mode).open.get(id).copied().unwrap_or(false)
    }

    pub fn set_open(&mut self, mode: UiMode, id: &str, open: bool) {
        self.memory_mut(mode).open.insert(id.to_owned(), open);
    }

    pub fn has_any_open(&self, mode: UiMode) -> bool {
        mode.panel_ids().iter().any(|id| self.is_open(mode, id))
    }

    /// Toggle from a header click: flip + become Custom.
    pub fn toggle_panel(&mut self, mode: UiMode, id: &str) {
        let open = self.is_open(mode, id);
        self.set_open(mode, id, !open);
        self.mark_custom(mode);
    }

    pub fn push_toast(
        &mut self,
        title: impl Into<String>,
        subtitle: impl Into<String>,
        error: bool,
    ) {
        self.toasts.push(Toast::new(title, subtitle, error));
    }

    /// Store a finished task capsule on the timeline track (SPEC §9): newest
    /// last, only the newest 8 kept.
    pub fn push_finished_task(
        &mut self,
        title: impl Into<String>,
        subtitle: impl Into<String>,
        state: TaskState,
    ) {
        let id = self.next_task_id;
        self.next_task_id += 1;
        self.session_tasks.push(TaskCard {
            id,
            title: title.into(),
            subtitle: subtitle.into(),
            state,
            progress: None,
        });
        let excess = self.session_tasks.len().saturating_sub(8);
        if excess > 0 {
            self.session_tasks.drain(..excess);
        }
    }

    /// Serialize the persistent slice (panel memory only — toasts/tasks are
    /// session-transient) for `prefs.ui_workspace`.
    pub fn to_value(&self) -> Value {
        json!({
            UiMode::Textures.key(): self.textures.to_value(),
            UiMode::Models.key(): self.models.to_value(),
        })
    }

    /// Restore from `prefs.ui_workspace`; missing/garbage input falls back to
    /// the per-mode "review" default field by field.
    pub fn from_value(value: &Value) -> Self {
        let mut state = Self::default();
        for (mode, memory) in [
            (UiMode::Textures, &mut state.textures),
            (UiMode::Models, &mut state.models),
        ] {
            let Some(entry) = value.get(mode.key()) else {
                continue;
            };
            if let Some(preset) = entry.get("preset").and_then(Value::as_str) {
                if PRESET_IDS.contains(&preset) {
                    memory.preset = preset.to_owned();
                }
            }
            if let Some(open) = entry.get("open").and_then(Value::as_object) {
                for id in mode.panel_ids() {
                    if let Some(flag) = open.get(*id).and_then(Value::as_bool) {
                        memory.open.insert((*id).to_owned(), flag);
                    }
                }
            }
            if let Some(custom) = entry.get("custom").and_then(Value::as_array) {
                memory.custom = custom
                    .iter()
                    .map(|flag| flag.as_bool().unwrap_or(false))
                    .collect();
            }
        }
        state
    }
}

/// Full-frame composition per SPEC §2: topbar → timeline → rail → right stack
/// → central stage → floating layers (modals, popover, toasts).
pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    topbar::draw(app, ctx);
    timeline::draw(app, ctx);
    rail::draw(app, ctx);
    draw_stack(app, ctx);
    draw_stage(app, ctx);
    dialogs::draw(app, ctx);
    widgets::toast_overlay(ctx, &mut app.ui.toasts);
}

/// Right parameter stack: stackhead + preset bar + scrolling panel stack.
fn draw_stack(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
    egui::SidePanel::right("stack")
        .exact_width(theme::STACK_W)
        .resizable(false)
        .frame(egui::Frame::new().fill(theme::BG))
        .show(ctx, |ui| {
            let mode = app.ui.mode;
            ui.spacing_mut().item_spacing.y = 0.0;
            // stackhead
            let title = match mode {
                UiMode::Textures => t.stack_title_textures,
                UiMode::Models => t.stack_title_models,
            };
            let (head_rect, _) =
                ui.allocate_exact_size(Vec2::new(ui.available_width(), 34.0), Sense::hover());
            let painter = ui.painter().clone();
            painter.text(
                Pos2::new(head_rect.left() + 14.0, head_rect.center().y),
                Align2::LEFT_CENTER,
                title,
                FontId::proportional(12.5),
                theme::INK,
            );
            painter.hline(
                head_rect.left()..=head_rect.right(),
                head_rect.bottom(),
                Stroke::new(1.0, theme::BORDER),
            );
            // preset bar
            let active = app.ui.memory(mode).preset.clone();
            let dirty = active == "custom";
            let bar = egui::Frame::new()
                .fill(theme::PRESETBAR_BG)
                .inner_margin(egui::Margin::symmetric(12, 9))
                .show(ui, |ui| {
                    ui.set_width(ui.available_width());
                    ui.horizontal(|ui| {
                        widgets::section_label(ui, t.workspace_label);
                        let labels = [
                            t.preset_minimal,
                            t.preset_review,
                            t.preset_export,
                            t.preset_custom,
                        ];
                        widgets::preset_bar(ui, &active, dirty, labels)
                    })
                    .inner
                });
            if let Some(preset) = bar.inner {
                app.ui.apply_preset(mode, preset);
            }
            let bar_rect = bar.response.rect;
            ui.painter().hline(
                bar_rect.left()..=bar_rect.right(),
                bar_rect.bottom(),
                Stroke::new(1.0, theme::BORDER),
            );
            // panel stack
            egui::ScrollArea::vertical()
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    egui::Frame::new()
                        .inner_margin(egui::Margin::same(10))
                        .show(ui, |ui| match mode {
                            UiMode::Textures => stack_textures::draw(app, ui),
                            UiMode::Models => stack_models::draw(app, ui),
                        });
                });
        });
}

/// Central stage: 40px stagebar, faint 44px grid, mode-routed viewport.
fn draw_stage(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
    let mode = app.ui.mode;
    let title = match mode {
        UiMode::Textures => t.mode_textures,
        UiMode::Models => t.mode_models,
    };
    let subtitle = match mode {
        UiMode::Textures => app
            .texture
            .selected_group
            .zip(app.texture.document.as_ref())
            .and_then(|(index, document)| document.scan().groups.get(index))
            .map(|group| group.base_name.clone())
            .unwrap_or_else(|| t.stage_sub_texture_preview.to_owned()),
        UiMode::Models => app
            .selected_entry_index()
            .and_then(|index| {
                app.model.entries[index]
                    .review
                    .path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .map(str::to_owned)
            })
            .unwrap_or_else(|| t.stage_sub_material_slots.to_owned()),
    };
    egui::CentralPanel::default()
        .frame(theme::stage_frame())
        .show(ctx, |ui| {
            let (bar_rect, _) = ui.allocate_exact_size(
                Vec2::new(ui.available_width(), theme::STAGEBAR_H),
                Sense::hover(),
            );
            let painter = ui.painter().clone();
            painter.rect_filled(bar_rect, 0.0, theme::STAGEBAR_BG);
            painter.hline(
                bar_rect.left()..=bar_rect.right(),
                bar_rect.bottom(),
                Stroke::new(1.0, theme::STAGEBAR_LINE),
            );
            let title_rect = painter.text(
                Pos2::new(bar_rect.left() + 12.0, bar_rect.center().y),
                Align2::LEFT_CENTER,
                title,
                FontId::proportional(12.5),
                theme::INK,
            );
            painter.text(
                Pos2::new(title_rect.right() + 8.0, bar_rect.center().y),
                Align2::LEFT_CENTER,
                subtitle,
                FontId::proportional(11.0),
                theme::MUTED2,
            );
            // Stagebar gadget (SPEC §6.1): once an output exists, keep the
            // open-output-folder link reachable outside the modals.
            let output_dir = match mode {
                UiMode::Textures => app
                    .process_summary
                    .as_ref()
                    .map(|summary| summary.output_directory.clone()),
                UiMode::Models => (app.model.export_cgf.is_some()
                    || app.model.export_summary.is_some()
                    || app.model.batch.is_some())
                .then(|| std::path::PathBuf::from(&app.preferences.model_output_directory)),
            };
            if let Some(directory) = output_dir {
                let link_rect = egui::Rect::from_min_max(
                    Pos2::new(bar_rect.right() - 220.0, bar_rect.top()),
                    Pos2::new(bar_rect.right() - 12.0, bar_rect.bottom()),
                );
                let mut link_ui = ui.new_child(
                    egui::UiBuilder::new().max_rect(link_rect).layout(
                        egui::Layout::right_to_left(egui::Align::Center),
                    ),
                );
                link_ui.hyperlink_to(t.open_output_folder, crate::file_url(&directory));
            }
            // Faint 44px grid over the viewport region.
            let viewport = ui.available_rect_before_wrap();
            paint_grid(&painter, viewport);
            match mode {
                UiMode::Textures => stage_textures::draw(app, ui),
                UiMode::Models => stage_models::draw(app, ui),
            }
        });
}

fn paint_grid(painter: &egui::Painter, rect: egui::Rect) {
    const STEP: f32 = 44.0;
    let stroke = Stroke::new(1.0, theme::GRID);
    let mut x = rect.left() + STEP;
    while x < rect.right() {
        painter.vline(x, rect.top()..=rect.bottom(), stroke);
        x += STEP;
    }
    let mut y = rect.top() + STEP;
    while y < rect.bottom() {
        painter.hline(rect.left()..=rect.right(), y, stroke);
        y += STEP;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn presets_open_their_tagged_panels() {
        let mut state = UiState::default();
        // First-run default is "review".
        assert_eq!(state.textures.preset, "review");
        assert!(state.is_open(UiMode::Textures, "tex.import"));
        assert!(state.is_open(UiMode::Textures, "tex.groups"));
        assert!(!state.is_open(UiMode::Textures, "tex.convert"));

        state.apply_preset(UiMode::Textures, "export");
        assert!(!state.is_open(UiMode::Textures, "tex.import"));
        assert!(state.is_open(UiMode::Textures, "tex.convert"));
        assert!(state.is_open(UiMode::Textures, "tex.rc"));

        state.apply_preset(UiMode::Textures, "minimal");
        assert!(!state.has_any_open(UiMode::Textures));
    }

    #[test]
    fn manual_toggle_snapshots_custom_and_round_trips() {
        let mut state = UiState::default();
        state.toggle_panel(UiMode::Textures, "tex.rc");
        assert_eq!(state.textures.preset, "custom");
        assert!(state.is_open(UiMode::Textures, "tex.rc"));
        // Switch away and back: Custom restores the snapshot.
        state.apply_preset(UiMode::Textures, "minimal");
        assert!(!state.is_open(UiMode::Textures, "tex.rc"));
        state.apply_preset(UiMode::Textures, "custom");
        assert!(state.is_open(UiMode::Textures, "tex.rc"));
        assert!(state.is_open(UiMode::Textures, "tex.import"));
    }

    #[test]
    fn workspace_value_round_trips_and_tolerates_garbage() {
        let mut state = UiState::default();
        state.apply_preset(UiMode::Models, "export");
        state.toggle_panel(UiMode::Textures, "tex.convert");
        let value = state.to_value();
        let restored = UiState::from_value(&value);
        assert_eq!(restored.models.preset, "export");
        assert_eq!(restored.textures.preset, "custom");
        assert!(restored.is_open(UiMode::Textures, "tex.convert"));
        assert_eq!(restored.textures.custom, state.textures.custom);
        // Garbage/missing input falls back to defaults.
        let fallback = UiState::from_value(&serde_json::json!({"textures": 3}));
        assert_eq!(fallback.textures.preset, "review");
        assert!(fallback.is_open(UiMode::Textures, "tex.import"));
        let null = UiState::from_value(&Value::Null);
        assert_eq!(null.models.preset, "review");
    }

    // B3: work-tracker transition detection.
    #[test]
    fn work_tracker_detects_completion_edges() {
        let mut tracker = WorkTracker::default();
        let idle = JobSnapshot::default();
        // Nothing ran, nothing finishes; the idle edge is not re-reported.
        assert_eq!(tracker.finished_jobs(idle), FinishedJobs::default());
        // Scan runs, then stops.
        tracker.finished_jobs(JobSnapshot { scan: true, ..idle });
        let finished = tracker.finished_jobs(idle);
        assert!(finished.scan);
        assert!(!finished.process && finished.loads.is_none());
        // Convert that entered its DDS phase; the edge reports both, once.
        tracker.finished_jobs(JobSnapshot { process: true, ..idle });
        tracker.finished_jobs(JobSnapshot { process: true, dds: true, ..idle });
        let finished = tracker.finished_jobs(idle);
        assert!(finished.process && finished.process_had_dds);
        assert_eq!(tracker.finished_jobs(idle), FinishedJobs::default());
        // A later DDS-less convert must not inherit the old DDS flag.
        tracker.finished_jobs(JobSnapshot { process: true, ..idle });
        let finished = tracker.finished_jobs(idle);
        assert!(finished.process && !finished.process_had_dds);
        // FBX load wave: 2 pending over 1 existing model -> 3 total = +2.
        tracker.finished_jobs(JobSnapshot { loads: 2, entries: 1, ..idle });
        let finished = tracker.finished_jobs(JobSnapshot { entries: 3, ..idle });
        assert_eq!(finished.loads, Some(2));
        // Export and batch edges fire independently.
        tracker.finished_jobs(JobSnapshot { export: true, batch: true, ..idle });
        let finished = tracker.finished_jobs(idle);
        assert!(finished.export && finished.batch);
    }

    // B3: stored capsules keep only the newest 8.
    #[test]
    fn finished_tasks_cap_at_eight() {
        let mut state = UiState::default();
        for index in 0..11 {
            state.push_finished_task(
                format!("task {index}"),
                "sub",
                widgets::TaskState::Done,
            );
        }
        assert_eq!(state.session_tasks.len(), 8);
        // Oldest evicted, newest kept, ids strictly increasing.
        assert_eq!(state.session_tasks[0].title, "task 3");
        assert_eq!(state.session_tasks[7].title, "task 10");
        assert!(state.session_tasks.windows(2).all(|w| w[0].id < w[1].id));
    }
}
