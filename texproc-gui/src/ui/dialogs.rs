//! Floating layers (SPEC.md §10): the three existing modals ported verbatim in
//! behavior (process / export / batch) plus the diagnostics popover, restyled
//! with theme colors and anchored under the topbar chip.

use std::path::Path;
use std::sync::atomic::Ordering;

use eframe::egui::{
    self, Align2, CornerRadius, Id, Margin, Modal, ProgressBar, RichText, ScrollArea, Stroke,
};

use crate::file_url;
use crate::i18n::fill;

use super::theme;

pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    process_modal(app, ctx);
    export_modal(app, ctx);
    batch_modal(app, ctx);
    diagnostics_popover(app, ctx);
}

fn process_modal(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    if !app.process_modal_open {
        return;
    }
    let t = app.t();
    let mut cancel = false;
    let mut close = false;
    Modal::new(Id::new("process_modal")).show(ctx, |ui| {
        ui.set_width(520.0);
        if let Some(process) = &app.process {
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
            ui.add(
                ProgressBar::new(progress)
                    .show_percentage()
                    .fill(theme::ACCENT),
            );
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
                ui.add(
                    ProgressBar::new(dds_progress)
                        .show_percentage()
                        .fill(theme::ACCENT),
                );
            }
            ui.add_space(6.0);
            ScrollArea::vertical()
                .max_height(280.0)
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    for name in &process.group_names {
                        ui.horizontal(|ui| {
                            if process.completed_groups.contains(name) {
                                ui.colored_label(theme::OK, "✓");
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
        } else if let Some(summary) = &app.process_summary {
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
                    theme::HAZARD,
                    fill(
                        t.groups_failed_summary,
                        &[&summary.failed.len().to_string()],
                    ),
                );
            }
            if let Some(dds) = &summary.dds {
                let color = if dds.failures.is_empty() {
                    theme::OK
                } else {
                    theme::WARN
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
        if let Some(process) = &app.process {
            process.job.cancel.store(true, Ordering::Relaxed);
            app.status = t.cancelling_process.to_owned();
        }
    }
    if close {
        app.process_modal_open = false;
    }
}

fn export_modal(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    if !app.model.export_modal_open {
        return;
    }
    let t = app.t();
    let running = app.model.export_receiver.is_some();
    let mut close = false;
    Modal::new(Id::new("export_modal")).show(ctx, |ui| {
        ui.set_width(520.0);
        if running {
            ui.heading(t.exporting_ce_model_heading);
            ui.horizontal(|ui| {
                ui.spinner();
                ui.label(&app.model.export_stage);
            });
            ui.add_space(6.0);
            if app.preferences.export_associated_textures {
                ui.weak(t.export_pipeline_with_textures);
            } else {
                ui.weak(t.export_pipeline);
            }
        } else if let Some(summary) = &app.model.export_summary {
            ui.heading(t.ce_model_export);
            ui.label(summary);
            ui.add_space(6.0);
            if let Some(cgf) = &app.model.export_cgf {
                ui.label(format!("CGF: {}", cgf.display()));
            }
            ui.hyperlink_to(
                t.open_output_folder,
                file_url(Path::new(&app.preferences.model_output_directory)),
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
        app.model.export_modal_open = false;
    }
}

fn batch_modal(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
    let Some(batch) = app.model.batch.as_ref() else {
        return;
    };
    if !batch.modal_open {
        return;
    }
    let mut cancel = false;
    let mut close = false;
    let model_output = app.preferences.model_output_directory.clone();
    Modal::new(Id::new("batch_modal")).show(ctx, |ui| {
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
            ui.add(
                ProgressBar::new(progress)
                    .show_percentage()
                    .fill(theme::ACCENT),
            );
            ui.add_space(6.0);
            ui.label(fill(
                t.batch_done_failed,
                &[
                    &batch.succeeded.len().to_string(),
                    &batch.failed.len().to_string(),
                ],
            ));
            ui.add_space(8.0);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                cancel = ui.button(t.cancel).clicked();
            });
        } else {
            ui.heading(t.export_all_complete_heading);
            ui.label(fill(
                t.succeeded_failed,
                &[
                    &batch.succeeded.len().to_string(),
                    &batch.failed.len().to_string(),
                ],
            ));
            ui.add_space(6.0);
            ScrollArea::vertical().max_height(300.0).show(ui, |ui| {
                for ok in &batch.succeeded {
                    ui.horizontal(|ui| {
                        ui.colored_label(theme::OK, "✓");
                        ui.label(ok);
                    });
                }
                for (name, detail) in &batch.failed {
                    ui.horizontal_top(|ui| {
                        ui.colored_label(theme::HAZARD, "✗");
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
        if let Some(batch) = app.model.batch.as_ref() {
            batch.cancel.store(true, Ordering::Relaxed);
        }
        app.status = t.cancelling_batch.to_owned();
    }
    if close {
        if let Some(batch) = app.model.batch.as_mut() {
            batch.modal_open = false;
        }
    }
}

/// Diagnostics popover anchored under the topbar chip (right side). A click
/// anywhere below the topbar and outside the popover closes it; a click on the
/// topbar chip itself toggles it (handled in topbar.rs).
fn diagnostics_popover(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    if !app.ui.diag_open {
        return;
    }
    let t = app.t();
    let items = app.diagnostics();
    let response = egui::Window::new("diagnostics_popover_v2")
        .title_bar(false)
        .anchor(Align2::RIGHT_TOP, [-8.0, theme::TOPBAR_H + 4.0])
        .resizable(false)
        .default_width(390.0)
        .frame(
            egui::Frame::new()
                .fill(theme::PANEL)
                .stroke(Stroke::new(1.0, theme::BORDER2))
                .corner_radius(CornerRadius::same(10))
                .inner_margin(Margin::same(0)),
        )
        .show(ctx, |ui| {
            ui.set_width(390.0);
            egui::Frame::new()
                .inner_margin(Margin::symmetric(14, 11))
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(
                            RichText::new(t.diagnostics_title)
                                .size(12.5)
                                .strong()
                                .color(theme::INK),
                        );
                        ui.label(
                            RichText::new(format!("({})", items.len()))
                                .size(12.5)
                                .color(theme::MUTED2),
                        );
                    });
                });
            let rect = ui.min_rect();
            ui.painter().hline(
                rect.left()..=rect.right(),
                rect.bottom(),
                Stroke::new(1.0, theme::BORDER),
            );
            if items.is_empty() {
                egui::Frame::new()
                    .inner_margin(Margin::symmetric(14, 11))
                    .show(ui, |ui| {
                        ui.colored_label(theme::OK, t.no_diagnostics);
                    });
                return;
            }
            ScrollArea::vertical().max_height(300.0).show(ui, |ui| {
                egui::Frame::new()
                    .inner_margin(Margin::symmetric(14, 10))
                    .show(ui, |ui| {
                        for item in &items {
                            ui.horizontal_top(|ui| {
                                let color = match item.severity {
                                    "Error" => theme::HAZARD,
                                    "Warning" => theme::WARN,
                                    _ => theme::ACCENT_TEXT,
                                };
                                ui.label(
                                    RichText::new(item.severity).size(9.5).strong().color(color),
                                );
                                ui.vertical(|ui| {
                                    ui.label(
                                        RichText::new(&item.title)
                                            .size(10.5)
                                            .strong()
                                            .color(theme::MUTED),
                                    );
                                    ui.label(RichText::new(&item.message).size(11.5));
                                });
                            });
                            ui.separator();
                        }
                    });
            });
        });
    if let Some(inner) = response {
        let clicked_outside = ctx.input(|input| {
            input.pointer.any_pressed()
                && input.pointer.interact_pos().is_some_and(|pos| {
                    !inner.response.rect.contains(pos) && pos.y > theme::TOPBAR_H
                })
        });
        if clicked_outside {
            app.ui.diag_open = false;
        }
    }
}
