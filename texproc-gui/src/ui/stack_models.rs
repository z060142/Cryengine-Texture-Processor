//! Models parameter stack (SPEC.md §8): FBX List, Transform and Export
//! Options panel bodies. Behaviors are ports of the v1 model panels (enable
//! rules, manifest-aware defaults, axis detection captions, export gating).

use eframe::egui::{self, ComboBox, RichText, ScrollArea, TextEdit};

use texproc_gui::{axes_parallel, compose_forward_up};

use crate::file_dialog::{choose_file_open, choose_files_multi};
use crate::i18n::fill;

use super::icons::Icon;
use super::theme;
use super::widgets::{self, PcountStyle};
use super::UiMode;

pub fn draw(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let mode = UiMode::Models;
    let selected = app.selected_entry_index();

    // ---- FBX List ----------------------------------------------------------
    let models_chip = (!app.model.entries.is_empty())
        .then(|| fill(t.models_chip, &[&app.model.entries.len().to_string()]));
    let open = app.ui.is_open(mode, "mdl.fbx");
    let response = widgets::collapsible_panel(
        ui,
        "mdl.fbx",
        "FBX List",
        Icon::Cube,
        open,
        0,
        models_chip.as_deref().map(|chip| (chip, PcountStyle::Normal)),
        t.reset_to_defaults,
        |ui| fbx_list_body(app, ui),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "mdl.fbx");
    }

    // ---- Transform ---------------------------------------------------------
    let transform_modified = selected.map_or(0, |index| {
        let conversion = &app.model.entries[index].conversion;
        usize::from(app.preferences.conversion_unit != "file")
            + usize::from(app.preferences.conversion_scale != 1.0)
            + usize::from(conversion.forward != conversion.detected_forward)
            + usize::from(conversion.up != conversion.detected_up)
            + usize::from(conversion.merge_all_nodes)
            + usize::from(conversion.scene_origin)
    });
    let open = app.ui.is_open(mode, "mdl.transform");
    let response = widgets::collapsible_panel(
        ui,
        "mdl.transform",
        "Transform",
        Icon::Transform,
        open,
        transform_modified,
        None,
        t.reset_to_defaults,
        |ui| transform_body(app, ui, selected),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "mdl.transform");
    }
    if response.reset_clicked {
        app.preferences.conversion_unit = "file".to_owned();
        app.preferences.conversion_scale = 1.0;
        if let Some(index) = selected {
            let conversion = &mut app.model.entries[index].conversion;
            conversion.forward = conversion.detected_forward.clone();
            conversion.up = conversion.detected_up.clone();
            conversion.merge_all_nodes = false;
            conversion.scene_origin = false;
        }
        app.save_preferences();
        app.ui.push_toast(t.toast_reset, "Transform", false);
    }

    // ---- Export Options ----------------------------------------------------
    let export_modified = usize::from(!app.preferences.manifest_path.trim().is_empty())
        + usize::from(!app.preferences.overrides_path.trim().is_empty())
        + usize::from(app.preferences.export_associated_textures)
        + usize::from(app.preferences.delete_request_json);
    let open = app.ui.is_open(mode, "mdl.export");
    let response = widgets::collapsible_panel(
        ui,
        "mdl.export",
        "Export Options",
        Icon::Export,
        open,
        export_modified,
        None,
        t.reset_to_defaults,
        |ui| export_body(app, ui, selected),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "mdl.export");
    }
    if response.reset_clicked {
        app.preferences.manifest_path.clear();
        app.preferences.overrides_path.clear();
        app.preferences.export_associated_textures = false;
        app.preferences.delete_request_json = false;
        app.save_preferences();
        app.ui.push_toast(t.toast_reset, "Export Options", false);
    }
}

// ---- FBX List --------------------------------------------------------------

fn fbx_list_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let add_fbx = ui.add(
        egui::Button::new(t.add_fbx).min_size(egui::Vec2::new(ui.available_width(), 30.0)),
    );
    if add_fbx.clicked() {
        match choose_files_multi(t.dlg_select_fbx_files, crate::FBX_FILTER) {
            Ok(files) if !files.is_empty() => app.load_model_files(files),
            Ok(_) => {}
            Err(error) => app.status = error,
        }
    }
    ui.horizontal(|ui| {
        ui.add(
            TextEdit::singleline(&mut app.preferences.model_path)
                .desired_width(ui.available_width() - 86.0)
                .hint_text(t.fbx_path_hint),
        );
        if ui.button(t.add_path).clicked() {
            let paths = crate::split_paths(&app.preferences.model_path)
                .into_iter()
                .filter(|path| path.exists())
                .collect::<Vec<_>>();
            if paths.is_empty() {
                app.status = t.enter_fbx_path_first.to_owned();
            } else {
                app.load_model_files(paths);
            }
        }
    });
    if !app.model.load_receivers.is_empty() {
        ui.horizontal(|ui| {
            ui.spinner();
            ui.label(
                RichText::new(fill(
                    t.loading_models,
                    &[&app.model.load_receivers.len().to_string()],
                ))
                .color(theme::MUTED),
            );
        });
    }
    ui.add_space(3.0);

    let modifiers = ui.input(|input| input.modifiers);
    let mut clicked = None;
    ScrollArea::vertical()
        .id_salt("mdl_fbx_list")
        .max_height(230.0)
        .auto_shrink([false, true])
        .show(ui, |ui| {
            ui.spacing_mut().item_spacing.y = 3.0;
            for (index, entry) in app.model.entries.iter().enumerate() {
                let name = entry
                    .review
                    .path
                    .file_name()
                    .and_then(|value| value.to_str())
                    .unwrap_or("FBX");
                let diagnostics = entry.review.diagnostics.len();
                let sub = fill(
                    t.model_sub_line,
                    &[
                        &entry.review.material_slots.len().to_string(),
                        &diagnostics.to_string(),
                        &entry.helper_nodes.to_string(),
                    ],
                );
                let sub_color = if diagnostics > 0 {
                    theme::WARN
                } else {
                    theme::MUTED2
                };
                let key = entry.review.path.to_string_lossy().into_owned();
                let row = widgets::grow_row(
                    ui,
                    ("mdl_row", index),
                    app.model.selected.contains(&index),
                    false,
                    &key,
                    name,
                    &sub,
                    sub_color,
                    |_| {},
                );
                if row
                    .on_hover_text(entry.review.path.display().to_string())
                    .clicked()
                {
                    clicked = Some(index);
                }
            }
        });
    if let Some(index) = clicked {
        crate::apply_click_selection(
            &mut app.model.selected,
            &mut app.model.selection_anchor,
            index,
            modifiers.ctrl,
            modifiers.shift,
        );
    }
    let has_selection = !app.model.selected.is_empty();
    ui.horizontal(|ui| {
        if ui
            .add_enabled(has_selection, egui::Button::new(t.remove_selected))
            .clicked()
        {
            app.remove_selected_models();
        }
        if ui.button(t.clear_all).clicked() {
            app.clear_models();
        }
    });

    // Single-selection summary (the v1 model_summary block).
    if let Some(index) = app.selected_entry_index() {
        ui.add_space(6.0);
        widgets::section_label(ui, t.summary_label);
        let entry = &app.model.entries[index];
        let review = &entry.review;
        let lines = [
            fill(t.summary_material_slots, &[&review.material_slots.len().to_string()]),
            fill(t.summary_meshes, &[&review.model.meshes.len().to_string()]),
            fill(t.summary_nodes, &[&review.model.node_count.to_string()]),
            fill(t.summary_helper_nodes, &[&entry.helper_nodes.to_string()]),
            fill(t.summary_diagnostics, &[&review.diagnostics.len().to_string()]),
        ];
        for line in lines {
            ui.label(RichText::new(line).size(theme::FONT_SMALL).color(theme::MUTED));
        }
        let axes = &review.model.axes;
        if axes.declared {
            ui.label(
                RichText::new(axes.summary())
                    .size(theme::FONT_SMALL)
                    .color(theme::MUTED),
            );
        } else {
            ui.label(
                RichText::new(axes.summary())
                    .size(theme::FONT_SMALL)
                    .color(theme::WARN),
            )
            .on_hover_text(t.axes_undeclared_hover);
        }
        ui.add_space(3.0);
        if ui.button(t.resend_textures).clicked() {
            app.ingest_entry_textures(index);
        }
    }
}

// ---- Transform -------------------------------------------------------------

fn transform_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui, selected: Option<usize>) {
    let t = app.t();
    let Some(index) = selected else {
        ui.label(RichText::new(t.select_single_model).color(theme::MUTED2));
        return;
    };
    // Take the entry's conversion out so preferences (Unit/Scale + save) can be
    // touched freely, then write it back — the v1 borrow pattern.
    let mut conversion = std::mem::take(&mut app.model.entries[index].conversion);

    widgets::section_label(ui, t.axis_section_label);
    crate::axis_dropdown(ui, t.forward_label, "v2_forward", &mut conversion.forward);
    crate::axis_dropdown(ui, t.up_label, "v2_up", &mut conversion.up);
    let detected = compose_forward_up(&conversion.detected_forward, &conversion.detected_up);
    let current = compose_forward_up(&conversion.forward, &conversion.up);
    ui.horizontal(|ui| {
        ui.label(
            RichText::new(fill(t.detected_axes, &[&detected]))
                .size(theme::FONT_SMALL)
                .color(theme::MUTED2),
        );
        if current != detected {
            ui.label(
                RichText::new(fill(t.axis_override, &[&current]))
                    .size(theme::FONT_SMALL)
                    .color(theme::WARN),
            );
        }
    });
    if axes_parallel(&conversion.forward, &conversion.up) {
        ui.label(RichText::new(t.axes_parallel_warning).color(theme::HAZARD));
    }

    ui.add_space(4.0);
    ui.horizontal(|ui| {
        ui.label(t.unit_label);
        let mut unit_changed = false;
        ComboBox::from_id_salt("v2_conversion_unit")
            .selected_text(&app.preferences.conversion_unit)
            .show_ui(ui, |ui| {
                for value in crate::UNIT_SIZE_VALUES {
                    if ui
                        .selectable_value(
                            &mut app.preferences.conversion_unit,
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
            app.save_preferences();
        }
        ui.label(t.scale_label);
        if ui
            .add(
                egui::DragValue::new(&mut app.preferences.conversion_scale)
                    .speed(0.01)
                    .range(0.0001..=100_000.0),
            )
            .changed()
        {
            app.save_preferences();
        }
    });
    ui.checkbox(&mut conversion.merge_all_nodes, t.merge_all_nodes);
    ui.checkbox(&mut conversion.scene_origin, t.scene_origin);

    app.model.entries[index].conversion = conversion;
}

// ---- Export Options --------------------------------------------------------

fn export_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui, selected: Option<usize>) {
    let t = app.t();
    ui.label(
        RichText::new(t.optional_manifest)
            .size(theme::FONT_SMALL)
            .color(theme::MUTED),
    );
    let (mut changed, browse) = widgets::path_row(
        ui,
        "v2_manifest",
        &mut app.preferences.manifest_path,
        t.hint_manifest,
        t.browse,
    );
    if browse {
        let initial = app.preferences.manifest_path.clone();
        if let Some(path) = app.dialog_result(choose_file_open(
            t.dlg_select_manifest,
            crate::JSON_FILTER,
            &initial,
        )) {
            app.preferences.manifest_path = path.to_string_lossy().into_owned();
            changed = true;
        }
    }
    ui.label(
        RichText::new(t.optional_overrides)
            .size(theme::FONT_SMALL)
            .color(theme::MUTED),
    );
    let (overrides_changed, overrides_browse) = widgets::path_row(
        ui,
        "v2_overrides",
        &mut app.preferences.overrides_path,
        t.hint_overrides,
        t.browse,
    );
    changed |= overrides_changed;
    if overrides_browse {
        let initial = app.preferences.overrides_path.clone();
        if let Some(path) = app.dialog_result(choose_file_open(
            t.dlg_select_overrides,
            crate::JSON_FILTER,
            &initial,
        )) {
            app.preferences.overrides_path = path.to_string_lossy().into_owned();
            changed = true;
        }
    }
    if changed {
        app.save_preferences();
    }
    if ui
        .checkbox(&mut app.preferences.export_associated_textures, t.export_associated)
        .on_hover_text(t.export_associated_hover)
        .changed()
    {
        app.save_preferences();
    }
    if ui
        .checkbox(&mut app.preferences.delete_request_json, t.delete_request_json)
        .on_hover_text(t.delete_request_hover)
        .changed()
    {
        app.save_preferences();
    }
    ui.add_space(4.0);
    super::stack_textures::rc_path_section(app, ui);

    ui.add_space(8.0);
    let single_ok = selected.is_some_and(|index| {
        let conversion = &app.model.entries[index].conversion;
        !axes_parallel(&conversion.forward, &conversion.up)
    });
    let exporting = app.model.export_receiver.is_some()
        || app.model.batch.as_ref().is_some_and(|batch| !batch.done);
    let export = ui
        .add_enabled_ui(single_ok && !exporting, |ui| {
            widgets::block_button(ui, t.export_ce_model_btn)
        })
        .inner;
    if export.on_hover_text(t.export_ce_model_hover).clicked() {
        app.save_preferences();
        app.start_model_export();
    }
    if app.model.export_receiver.is_some() && ui.button(t.show_export_progress).clicked() {
        app.model.export_modal_open = true;
    }
    if app.model.batch.is_some() && ui.button(t.show_batch_progress).clicked() {
        if let Some(batch) = app.model.batch.as_mut() {
            batch.modal_open = true;
        }
    }
}
