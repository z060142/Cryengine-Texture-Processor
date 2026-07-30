//! Left mode rail (SPEC.md §4): Textures/Models mode buttons with memdots,
//! disabled Proxy/PBR placeholders, Help button at the bottom.

use eframe::egui::{self, Margin, Sense, Vec2};

use super::icons::Icon;
use super::widgets;
use super::{theme, UiMode};

pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
    egui::SidePanel::left("rail")
        .exact_width(theme::RAIL_W)
        .resizable(false)
        .frame(
            egui::Frame::new()
                .fill(theme::RAIL_BG)
                .inner_margin(Margin {
                    left: 8,
                    right: 8,
                    top: 10,
                    bottom: 10,
                }),
        )
        .show(ctx, |ui| {
            ui.spacing_mut().item_spacing.y = 6.0;
            ui.vertical_centered(|ui| {
                let mode = app.ui.mode;
                if widgets::rail_button(
                    ui,
                    Icon::Textures,
                    t.mode_textures,
                    mode == UiMode::Textures,
                    true,
                    app.ui.has_any_open(UiMode::Textures),
                    None,
                )
                .clicked()
                {
                    app.ui.mode = UiMode::Textures;
                }
                if widgets::rail_button(
                    ui,
                    Icon::Models,
                    t.mode_models,
                    mode == UiMode::Models,
                    true,
                    app.ui.has_any_open(UiMode::Models),
                    Some(app.model.entries.len()),
                )
                .clicked()
                {
                    app.ui.mode = UiMode::Models;
                }
                // Planned modes — design placeholders only (SPEC §0 exclusions).
                widgets::rail_button(ui, Icon::Proxy, t.mode_proxy, false, false, false, None)
                    .on_hover_text(t.planned_tooltip);
                widgets::rail_button(ui, Icon::Pbr, t.mode_pbr, false, false, false, None)
                    .on_hover_text(t.planned_tooltip);
            });
            ui.with_layout(egui::Layout::bottom_up(egui::Align::Center), |ui| {
                let (rect, response) = ui.allocate_exact_size(Vec2::splat(28.0), Sense::click());
                let color = if response.hovered() {
                    theme::INK
                } else {
                    theme::MUTED2
                };
                super::icons::draw(ui.painter(), rect.shrink(3.0), Icon::Help, color, 1.5);
                if response.clicked() {
                    app.ui
                        .push_toast(t.help_toast_title, t.help_toast_body, false);
                }
            });
        });
}
