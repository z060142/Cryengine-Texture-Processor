//! Bottom timeline / work center (SPEC.md §9): status line, session task
//! track, session progress, and the persistent big verbs.

use eframe::egui::{self, Margin, RichText, Stroke, Ui, Vec2};

use super::theme;
use super::widgets;

pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
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
                                    for card in &app.ui.session_tasks {
                                        // Phase B wires clicks/cancel to modals.
                                        let _ = widgets::task_chip(ui, card, false);
                                    }
                                });
                        },
                    );
                });
            });
        });
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

/// Session progress: the running job's completion (idle shows an empty bar).
fn session_progress(app: &crate::WorkflowApp, ui: &mut Ui) {
    let t = app.t();
    let progress = if let Some(process) = &app.process {
        if process.total > 0 {
            process.completed as f32 / process.total as f32
        } else {
            0.0
        }
    } else if let Some(batch) = app.model.batch.as_ref().filter(|batch| !batch.done) {
        if batch.total > 0 {
            batch.current.saturating_sub(1) as f32 / batch.total as f32
        } else {
            0.0
        }
    } else {
        0.0
    };
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
