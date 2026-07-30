//! Bottom timeline / work center (SPEC.md §9): status line, session task
//! track (live capsules for running jobs + stored finished capsules),
//! completion toasts (SPEC §10), session progress, and the persistent big
//! verbs. Job-completion detection lives entirely here in the UI layer —
//! `observe` diffs the worker state against the previous frame's snapshot, so
//! main.rs never signals "finished" explicitly.

use std::sync::atomic::Ordering;

use eframe::egui::{self, Margin, RichText, Stroke, Ui, Vec2};

use crate::i18n::fill;

use super::theme;
use super::widgets::{self, TaskCard, TaskState};
use super::JobSnapshot;

/// Live capsules use ids far above the stored-card counter so egui interact
/// ids never collide with `UiState::next_task_id` allocations.
const LIVE_ID_BASE: u64 = u64::MAX - 8;

/// A currently running job rendered as a live (unstored) capsule.
#[derive(Clone, Copy)]
enum LiveJob {
    Scan,
    Convert,
    Dds,
    Loads,
    Export,
    Batch,
}

/// Chip interaction deferred until after the panel closure (keeps the borrow
/// on `app` sequential).
#[derive(Clone, Copy)]
enum ChipAction {
    OpenProcess,
    CancelProcess,
    OpenExport,
    OpenBatch,
    CancelBatch,
}

pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    // Edge detection first: finished jobs become stored capsules + toasts
    // before this frame draws the track.
    observe(app);
    let live = live_cards(app);
    let t = app.t();
    let mut action: Option<ChipAction> = None;
    egui::TopBottomPanel::bottom("timeline")
        .exact_height(theme::TIMELINE_H)
        .frame(
            egui::Frame::new()
                .fill(theme::TIMELINE_BG)
                .inner_margin(Margin::symmetric(14, 8)),
        )
        .show(ctx, |ui| {
            ui.horizontal_centered(|ui| {
                // Left: WORK CENTER + status line (the status bar's new home).
                ui.allocate_ui_with_layout(
                    Vec2::new(200.0, ui.available_height()),
                    egui::Layout::top_down(egui::Align::LEFT),
                    |ui| {
                        ui.add_space(4.0);
                        ui.label(
                            RichText::new(t.work_center)
                                .size(11.0)
                                .strong()
                                .color(theme::INK),
                        );
                        let status = app.status.clone();
                        ui.add(
                            egui::Label::new(
                                RichText::new(&status).size(10.0).color(theme::MUTED2),
                            )
                            .truncate(),
                        )
                        .on_hover_text(&status);
                    },
                );
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    // [E] persistent action cluster (rightmost).
                    actions(app, ui);
                    vseparator(ui);
                    session_progress(app, ui);
                    // Middle: session task track fills what remains.
                    let remaining = ui.available_size();
                    ui.allocate_ui_with_layout(
                        remaining,
                        egui::Layout::left_to_right(egui::Align::Center),
                        |ui| {
                            egui::ScrollArea::horizontal()
                                .id_salt("timeline_track")
                                .show(ui, |ui| {
                                    ui.spacing_mut().item_spacing.x = 8.0;
                                    // Live capsules for running jobs, in the
                                    // fixed SPEC order.
                                    for (card, job) in &live {
                                        let cancellable = matches!(
                                            job,
                                            LiveJob::Convert | LiveJob::Dds | LiveJob::Batch
                                        );
                                        let response =
                                            widgets::task_chip(ui, card, cancellable);
                                        if response.cancel_clicked {
                                            action = match job {
                                                LiveJob::Convert | LiveJob::Dds => {
                                                    Some(ChipAction::CancelProcess)
                                                }
                                                LiveJob::Batch => Some(ChipAction::CancelBatch),
                                                _ => action,
                                            };
                                        } else if response.clicked {
                                            action = match job {
                                                LiveJob::Convert | LiveJob::Dds => {
                                                    Some(ChipAction::OpenProcess)
                                                }
                                                LiveJob::Export => Some(ChipAction::OpenExport),
                                                LiveJob::Batch => Some(ChipAction::OpenBatch),
                                                // Scan / FBX loads have no modal.
                                                LiveJob::Scan | LiveJob::Loads => action,
                                            };
                                        }
                                    }
                                    // Finished capsules, newest first.
                                    for card in app.ui.session_tasks.iter().rev() {
                                        let _ = widgets::task_chip(ui, card, false);
                                    }
                                });
                        },
                    );
                });
            });
        });
    if let Some(action) = action {
        match action {
            ChipAction::OpenProcess => app.process_modal_open = true,
            ChipAction::CancelProcess => {
                if let Some(process) = app.process.as_ref() {
                    process.job.cancel.store(true, Ordering::Relaxed);
                    app.status = t.cancelling_process.to_owned();
                }
            }
            ChipAction::OpenExport => app.model.export_modal_open = true,
            ChipAction::OpenBatch => {
                if let Some(batch) = app.model.batch.as_mut() {
                    batch.modal_open = true;
                }
            }
            ChipAction::CancelBatch => {
                if let Some(batch) = app.model.batch.as_ref() {
                    batch.cancel.store(true, Ordering::Relaxed);
                    app.status = t.cancelling_batch.to_owned();
                }
            }
        }
    }
}

/// Diff the worker state against the previous frame (SPEC §9/§10): completion
/// edges push finished capsules + completion toasts, then the live counters
/// and the dominant job's session fraction are recorded for the next frame.
fn observe(app: &mut crate::WorkflowApp) {
    let t = app.t();
    let snapshot = JobSnapshot {
        scan: app.texture.scan_receiver.is_some(),
        process: app.process.is_some(),
        dds: app.process.as_ref().is_some_and(|process| process.dds_active),
        loads: app.model.load_receivers.len(),
        export: app.model.export_receiver.is_some(),
        batch: app.model.batch.as_ref().is_some_and(|batch| !batch.done),
        entries: app.model.entries.len(),
    };
    let finished = app.ui.work.finished_jobs(snapshot);
    let stamp = app.ui.work.stamp();

    if finished.scan {
        // Status already carries "Imported N textures: M groups, …" (§10).
        let files = app.texture.files.len();
        let groups = app
            .texture
            .document
            .as_ref()
            .map_or(0, |document| document.scan().groups.len());
        let status = app.status.clone();
        app.ui.push_finished_task(
            t.task_scan,
            format!("{stamp} · {files} → {groups}"),
            TaskState::Done,
        );
        app.ui.push_toast(t.toast_task_done, status, false);
    }
    if finished.process {
        // Convert capsule + toast; counts come from the summary, or from the
        // last live counters when the worker died without leaving one.
        let (state, toast_subtitle) = match app.process_summary.as_ref() {
            Some(summary) => {
                let failed = summary.cancelled || !summary.failed.is_empty();
                (
                    if failed {
                        TaskState::Failed
                    } else {
                        TaskState::Done
                    },
                    fill(
                        t.processing_summary,
                        &[
                            &summary.groups.to_string(),
                            &summary.written.to_string(),
                            &format!("{:.1}", summary.elapsed_seconds),
                        ],
                    ),
                )
            }
            None => (TaskState::Failed, app.status.clone()),
        };
        let done = app.ui.work.prev_convert_done;
        let total = app.ui.work.prev_convert_total;
        app.ui
            .push_finished_task(t.task_convert, format!("{stamp} · {done}/{total}"), state);
        if finished.process_had_dds {
            let (dds_done, dds_total, dds_state) = match app
                .process_summary
                .as_ref()
                .and_then(|summary| summary.dds.as_ref())
            {
                Some(dds) => (
                    dds.succeeded,
                    dds.total,
                    if dds.failures.is_empty() {
                        TaskState::Done
                    } else {
                        TaskState::Failed
                    },
                ),
                None => (
                    app.ui.work.prev_dds_done,
                    app.ui.work.prev_dds_total,
                    state,
                ),
            };
            app.ui.push_finished_task(
                t.task_dds,
                format!("{stamp} · {dds_done}/{dds_total}"),
                dds_state,
            );
        }
        let failed = state == TaskState::Failed;
        app.ui.push_toast(
            if failed {
                t.toast_task_failed
            } else {
                t.toast_task_done
            },
            toast_subtitle,
            failed,
        );
    }
    if let Some(count) = finished.loads {
        // Finished-load capsule only; FBX loads are not a §10 toast trigger.
        app.ui.push_finished_task(
            t.task_load_fbx,
            format!("{stamp} · +{count}"),
            TaskState::Done,
        );
    }
    if finished.export {
        // Success = a summary was produced (§10); RC failure detail stays in
        // the export modal. export_cgf is cleared at export start, so a
        // present file name always belongs to this run.
        let ok = app.model.export_summary.is_some();
        let subtitle = match app
            .model
            .export_cgf
            .as_ref()
            .and_then(|cgf| cgf.file_name())
            .and_then(|name| name.to_str())
        {
            Some(name) => format!("{stamp} · {name}"),
            None => stamp.clone(),
        };
        app.ui.push_finished_task(
            t.task_export_model,
            subtitle,
            if ok { TaskState::Done } else { TaskState::Failed },
        );
        app.ui.push_toast(
            if ok {
                t.toast_task_done
            } else {
                t.toast_task_failed
            },
            t.ce_model_export,
            !ok,
        );
    }
    if finished.batch {
        let (succeeded, failed) = app
            .model
            .batch
            .as_ref()
            .map_or((0, 0), |batch| (batch.succeeded.len(), batch.failed.len()));
        let counts = fill(
            t.succeeded_failed,
            &[&succeeded.to_string(), &failed.to_string()],
        );
        let state = if failed > 0 {
            TaskState::Failed
        } else {
            TaskState::Done
        };
        app.ui
            .push_finished_task(t.export_all_verb, format!("{stamp} · {counts}"), state);
        app.ui.push_toast(
            if failed > 0 {
                t.toast_task_failed
            } else {
                t.toast_task_done
            },
            counts,
            failed > 0,
        );
    }

    // Record live counters + the dominant running job's session fraction
    // (idle keeps showing the last value, SPEC §9).
    let fraction = if let Some(process) = app.process.as_ref() {
        let work = &mut app.ui.work;
        work.prev_convert_done = process.completed;
        work.prev_convert_total = process.total;
        work.prev_dds_done = process.dds_completed;
        work.prev_dds_total = process.dds_total;
        if process.dds_active && process.dds_total > 0 {
            Some(process.dds_completed as f32 / process.dds_total as f32)
        } else if process.total > 0 {
            Some(process.completed as f32 / process.total as f32)
        } else {
            None
        }
    } else if let Some(batch) = app.model.batch.as_ref().filter(|batch| !batch.done) {
        (batch.total > 0).then(|| batch.current.saturating_sub(1) as f32 / batch.total as f32)
    } else {
        None
    };
    if let Some(fraction) = fraction {
        app.ui.work.last_session_fraction = fraction;
    }
}

/// Build the live capsules for currently running jobs, in the fixed SPEC §9
/// order: scan → convert → DDS pool → FBX loads → single export → batch.
fn live_cards(app: &crate::WorkflowApp) -> Vec<(TaskCard, LiveJob)> {
    let t = app.t();
    let mut cards = Vec::new();
    if app.texture.scan_receiver.is_some() {
        cards.push((
            TaskCard {
                id: LIVE_ID_BASE,
                title: t.task_scan.to_owned(),
                subtitle: t.scanning.to_owned(),
                state: TaskState::Running,
                progress: None,
            },
            LiveJob::Scan,
        ));
    }
    if let Some(process) = app.process.as_ref() {
        let progress =
            (process.total > 0).then(|| process.completed as f32 / process.total as f32);
        cards.push((
            TaskCard {
                id: LIVE_ID_BASE + 1,
                title: t.task_convert.to_owned(),
                subtitle: format!(
                    "{}/{} · {}",
                    process.completed, process.total, process.current_group
                ),
                state: TaskState::Running,
                progress,
            },
            LiveJob::Convert,
        ));
        if process.dds_active {
            let progress = (process.dds_total > 0)
                .then(|| process.dds_completed as f32 / process.dds_total as f32);
            cards.push((
                TaskCard {
                    id: LIVE_ID_BASE + 2,
                    title: t.task_dds.to_owned(),
                    subtitle: format!(
                        "{}/{} · {}",
                        process.dds_completed,
                        process.dds_total,
                        fill(t.task_workers, &[&process.dds_workers.to_string()])
                    ),
                    state: TaskState::Running,
                    progress,
                },
                LiveJob::Dds,
            ));
        }
    }
    let loads = app.model.load_receivers.len();
    if loads > 0 {
        cards.push((
            TaskCard {
                id: LIVE_ID_BASE + 3,
                title: t.task_load_fbx.to_owned(),
                subtitle: format!("× {loads}"),
                state: TaskState::Running,
                progress: None,
            },
            LiveJob::Loads,
        ));
    }
    if app.model.export_receiver.is_some() {
        cards.push((
            TaskCard {
                id: LIVE_ID_BASE + 4,
                title: t.task_export_model.to_owned(),
                subtitle: app.model.export_stage.clone(),
                state: TaskState::Running,
                progress: None,
            },
            LiveJob::Export,
        ));
    }
    if let Some(batch) = app.model.batch.as_ref().filter(|batch| !batch.done) {
        let progress =
            (batch.total > 0).then(|| batch.current.saturating_sub(1) as f32 / batch.total as f32);
        cards.push((
            TaskCard {
                id: LIVE_ID_BASE + 5,
                title: t.export_all_verb.to_owned(),
                subtitle: format!(
                    "{}/{} · {}",
                    batch.current.max(1),
                    batch.total,
                    batch.current_name
                ),
                state: TaskState::Running,
                progress,
            },
            LiveJob::Batch,
        ));
    }
    cards
}

fn vseparator(ui: &mut Ui) {
    let (rect, _) = ui.allocate_exact_size(Vec2::new(1.0, 36.0), egui::Sense::hover());
    ui.painter().rect_filled(rect, 0.0, theme::BORDER);
}

/// Convert All (primary) + Export All, with the existing enable conditions.
fn actions(app: &mut crate::WorkflowApp, ui: &mut Ui) {
    let t = app.t();
    let processing = app.process.is_some();
    let group_count = app
        .texture
        .document
        .as_ref()
        .map_or(0, |document| document.scan().groups.len());
    let exporting = app.model.export_receiver.is_some()
        || app.model.batch.as_ref().is_some_and(|batch| !batch.done);
    // Right-to-left: Convert All ends up rightmost.
    let convert = ui.add_enabled(
        !processing && group_count > 0,
        egui::Button::new(
            RichText::new(t.convert_all)
                .size(12.5)
                .strong()
                .color(egui::Color32::WHITE),
        )
        .fill(theme::ACCENT)
        .stroke(Stroke::new(1.0, theme::ACCENT))
        .min_size(Vec2::new(0.0, 34.0)),
    );
    if convert.clicked() {
        app.start_texture_process();
    }
    let export = ui.add_enabled(
        !app.model.entries.is_empty() && !exporting,
        egui::Button::new(RichText::new(t.export_all_verb).size(12.5).strong())
            .min_size(Vec2::new(0.0, 34.0)),
    );
    if export.on_hover_text(t.export_all_hover).clicked() {
        app.save_preferences();
        app.start_batch_export();
    }
}

/// Session progress: the running dominant job's completion fraction, kept at
/// its last value while idle (tracked in `WorkTracker`, SPEC §9).
fn session_progress(app: &crate::WorkflowApp, ui: &mut Ui) {
    let t = app.t();
    let progress = app.ui.work.last_session_fraction;
    ui.allocate_ui_with_layout(
        Vec2::new(120.0, ui.available_height()),
        egui::Layout::top_down(egui::Align::LEFT),
        |ui| {
            ui.add_space(10.0);
            ui.horizontal(|ui| {
                ui.label(
                    RichText::new(t.session_label)
                        .size(10.0)
                        .color(theme::MUTED2),
                );
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(
                        RichText::new(format!("{}%", (progress * 100.0).round() as u32))
                            .size(10.0)
                            .color(theme::MUTED2),
                    );
                });
            });
            ui.add(
                egui::ProgressBar::new(progress)
                    .desired_width(120.0)
                    .desired_height(6.0)
                    .fill(theme::OK),
            );
        },
    );
}
