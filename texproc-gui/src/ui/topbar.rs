//! Top global bar (SPEC.md §3): brand, language, per-mode output directory,
//! Profile menu (settings file), diagnostics chip.

use std::path::Path;

use eframe::egui::{
    self, Color32, ComboBox, CornerRadius, FontId, Margin, Pos2, RichText, Sense, Stroke,
    StrokeKind, TextEdit, Ui, Vec2,
};

use crate::file_dialog::{choose_file_open, choose_file_save, choose_folder};
use crate::i18n::{fill, Language};

use super::theme;
use super::UiMode;

pub fn draw(app: &mut crate::WorkflowApp, ctx: &egui::Context) {
    let t = app.t();
    egui::TopBottomPanel::top("topbar")
        .exact_height(theme::TOPBAR_H)
        .frame(
            egui::Frame::new()
                .fill(theme::TOPBAR_BG)
                .inner_margin(Margin::symmetric(14, 0)),
        )
        .show(ctx, |ui| {
            ui.horizontal_centered(|ui| {
                brand(ui);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    // Rightmost first: diagnostics chip.
                    let count = app.diagnostics().len();
                    let (text, fg, bg, border) = if count > 0 {
                        (
                            fill(t.diag_chip_n, &[&count.to_string()]),
                            theme::WARN,
                            theme::WARN_WEAK,
                            theme::WARN_BORDER,
                        )
                    } else {
                        (
                            t.diag_chip_ok.to_owned(),
                            theme::OK,
                            theme::OK_WEAK,
                            theme::OK_BORDER,
                        )
                    };
                    if chip_button(ui, &text, fg, bg, border)
                        .on_hover_text(t.show_diagnostics_hover)
                        .clicked()
                    {
                        app.ui.diag_open = !app.ui.diag_open;
                    }
                    vseparator(ui);
                    profile_menu(app, ui);
                    vseparator(ui);
                    output_field(app, ui);
                    vseparator(ui);
                    language_combo(app, ui);
                });
            });
        });
}

/// Brand block: 22px accent tile + title + version tag.
fn brand(ui: &mut Ui) {
    let (logo, _) = ui.allocate_exact_size(Vec2::splat(22.0), Sense::hover());
    let painter = ui.painter();
    // Diagonal ACCENT→ACCENT2 gradient under a rounded border inset.
    let mut mesh = egui::Mesh::default();
    for (pos, color) in [
        (logo.left_top(), theme::ACCENT),
        (logo.right_top(), theme::ACCENT),
        (logo.right_bottom(), theme::ACCENT2),
        (logo.left_bottom(), theme::ACCENT2),
    ] {
        mesh.colored_vertex(pos, color);
    }
    mesh.add_triangle(0, 1, 2);
    mesh.add_triangle(0, 2, 3);
    painter.add(egui::Shape::mesh(mesh));
    // Round the tile by stroking the corners with the bar background.
    painter.rect_stroke(
        logo.expand(1.5),
        CornerRadius::same(7),
        Stroke::new(3.0, theme::TOPBAR_BG),
        StrokeKind::Middle,
    );
    ui.add_space(2.0);
    ui.label(
        RichText::new(crate::APP_TITLE)
            .size(13.5)
            .strong()
            .color(theme::INK),
    );
    ui.label(RichText::new("v2.1").size(11.0).color(theme::MUTED2));
}

/// 1×22 vertical separator.
fn vseparator(ui: &mut Ui) {
    let (rect, _) = ui.allocate_exact_size(Vec2::new(1.0, 22.0), Sense::hover());
    ui.painter().rect_filled(rect, 0.0, theme::BORDER);
}

/// Rounded chip-shaped button (diagnostics).
fn chip_button(
    ui: &mut Ui,
    text: &str,
    fg: Color32,
    bg: Color32,
    border: Color32,
) -> egui::Response {
    let galley = ui
        .painter()
        .layout_no_wrap(text.to_owned(), FontId::proportional(11.5), fg);
    let size = galley.size() + Vec2::new(33.0, 11.0);
    let (rect, response) = ui.allocate_exact_size(size, Sense::click());
    ui.painter().rect(
        rect,
        CornerRadius::same(theme::RADIUS_CHIP),
        bg,
        Stroke::new(1.0, border),
        StrokeKind::Inside,
    );
    // Leading status dot.
    ui.painter()
        .circle_filled(Pos2::new(rect.left() + 12.0, rect.center().y), 3.5, fg);
    ui.painter().galley(
        Pos2::new(rect.left() + 22.0, rect.center().y - galley.size().y / 2.0),
        galley,
        fg,
    );
    response
}

/// `Profile ▾` menu mapped onto the existing settings-file actions.
fn profile_menu(app: &mut crate::WorkflowApp, ui: &mut Ui) {
    let t = app.t();
    ui.menu_button(format!("{} ▾", t.profile_btn), |ui| {
        ui.set_min_width(180.0);
        let name = Path::new(app.preferences.settings_path.trim())
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("texproc-settings.json")
            .to_owned();
        ui.weak(name);
        ui.separator();
        if ui.button(t.profile_load).clicked() {
            let initial = app.preferences.settings_path.clone();
            if let Some(path) = app.dialog_result(choose_file_open(
                t.dlg_select_settings,
                crate::JSON_FILTER,
                &initial,
            )) {
                app.preferences.settings_path = path.to_string_lossy().into_owned();
                app.load_settings();
            }
        }
        if ui.button(t.profile_save).clicked() {
            app.save_settings();
        }
        if ui.button(t.profile_save_as).clicked() {
            let default_name = Path::new(app.preferences.settings_path.trim())
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("texproc-settings.json")
                .to_owned();
            if let Some(path) = app.dialog_result(choose_file_save(
                t.dlg_save_settings_as,
                crate::JSON_FILTER,
                &default_name,
            )) {
                app.preferences.settings_path = path.to_string_lossy().into_owned();
                app.save_settings();
            }
        }
    });
}

/// Per-mode output directory: label + 210px field + `…` browse. Any change
/// saves immediately (existing behavior).
fn output_field(app: &mut crate::WorkflowApp, ui: &mut Ui) {
    let t = app.t();
    let mode = app.ui.mode;
    let mut changed = false;
    // Right-to-left layout: browse button, field, then label.
    if ui.button("…").clicked() {
        let (title, initial) = match mode {
            UiMode::Textures => (
                t.dlg_select_texture_output,
                app.preferences.texture_output_directory.clone(),
            ),
            UiMode::Models => (
                t.dlg_select_model_output,
                app.preferences.model_output_directory.clone(),
            ),
        };
        if let Some(folder) = app.dialog_result(choose_folder(title, &initial)) {
            let target = match mode {
                UiMode::Textures => &mut app.preferences.texture_output_directory,
                UiMode::Models => &mut app.preferences.model_output_directory,
            };
            *target = folder.to_string_lossy().into_owned();
            changed = true;
        }
    }
    let (value, hint) = match mode {
        UiMode::Textures => (
            &mut app.preferences.texture_output_directory,
            r"C:\output\textures",
        ),
        UiMode::Models => (
            &mut app.preferences.model_output_directory,
            r"C:\output\model",
        ),
    };
    changed |= ui
        .add(
            TextEdit::singleline(value)
                .desired_width(210.0)
                .font(FontId::proportional(12.0))
                .hint_text(hint),
        )
        .changed();
    let label = match mode {
        UiMode::Textures => t.out_tex_label,
        UiMode::Models => t.out_mdl_label,
    };
    ui.label(
        RichText::new(label)
            .size(theme::FONT_SECTION)
            .strong()
            .color(theme::MUTED2),
    );
    if changed {
        app.save_preferences();
    }
}

/// Language selector bound to `preferences.language` (existing behavior).
fn language_combo(app: &mut crate::WorkflowApp, ui: &mut Ui) {
    let current = Language::from_code(&app.preferences.language);
    ComboBox::from_id_salt("topbar_lang")
        .selected_text(current.endonym())
        .width(104.0)
        .show_ui(ui, |ui| {
            for language in [Language::En, Language::ZhCn] {
                if ui
                    .selectable_label(language == current, language.endonym())
                    .clicked()
                {
                    app.preferences.language = language.code().to_owned();
                    app.save_preferences();
                }
            }
        });
    ui.label(
        RichText::new("LANG")
            .size(theme::FONT_SECTION)
            .strong()
            .color(theme::MUTED2),
    );
}
