//! Textures parameter stack (SPEC.md §7): Import, Group Review, Conversion
//! Settings and RC / DDS Export panel bodies, wired to the existing workflow
//! state. Behaviors are ports of the v1 panels (enable rules, hover texts,
//! status writes) into the v2 shells.

use std::path::PathBuf;

use eframe::egui::{self, ComboBox, Grid, RichText, ScrollArea, Sense, Stroke, TextEdit, Vec2};

use texproc::TextureSettings;
use texproc_gui::ASSIGNABLE_SOURCE_TYPES;

use crate::file_dialog::{choose_files_multi, choose_folder, choose_rc_executable};
use crate::i18n::fill;

use super::icons::Icon;
use super::theme;
use super::widgets::{self, PcountStyle};
use super::UiMode;

pub fn draw(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let mode = UiMode::Textures;

    // ---- Import ------------------------------------------------------------
    let files_chip = (!app.texture.files.is_empty())
        .then(|| fill(t.files_chip, &[&app.texture.files.len().to_string()]));
    let open = app.ui.is_open(mode, "tex.import");
    let response = widgets::collapsible_panel(
        ui,
        "tex.import",
        "Import",
        Icon::Import,
        open,
        0,
        files_chip.as_deref().map(|chip| (chip, PcountStyle::Normal)),
        t.reset_to_defaults,
        |ui| import_body(app, ui),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "tex.import");
    }

    // ---- Group Review ------------------------------------------------------
    let (group_count, unknown_groups) = app.texture.document.as_ref().map_or((0, 0), |document| {
        let groups = &document.scan().groups;
        (
            groups.len(),
            groups.iter().filter(|group| !group.unknown.is_empty()).count(),
        )
    });
    let groups_chip = if unknown_groups > 0 {
        Some((
            fill(t.unassigned_chip, &[&unknown_groups.to_string()]),
            PcountStyle::Hot,
        ))
    } else if group_count > 0 {
        Some((
            fill(t.groups_chip, &[&group_count.to_string()]),
            PcountStyle::Normal,
        ))
    } else {
        None
    };
    let open = app.ui.is_open(mode, "tex.groups");
    let response = widgets::collapsible_panel(
        ui,
        "tex.groups",
        "Group Review",
        Icon::ListLines,
        open,
        0,
        groups_chip.as_ref().map(|(chip, style)| (chip.as_str(), *style)),
        t.reset_to_defaults,
        |ui| groups_body(app, ui),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "tex.groups");
    }

    // ---- Conversion Settings -----------------------------------------------
    let modified = conversion_modified_count(&app.settings);
    let open = app.ui.is_open(mode, "tex.convert");
    let response = widgets::collapsible_panel(
        ui,
        "tex.convert",
        "Conversion Settings",
        Icon::Gear,
        open,
        modified,
        None,
        t.reset_to_defaults,
        |ui| conversion_body(app, ui),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "tex.convert");
    }
    if response.reset_clicked {
        app.settings = TextureSettings::default();
        app.ui.push_toast(t.toast_reset, "Conversion Settings", false);
    }

    // ---- RC / DDS Export ---------------------------------------------------
    let rc_modified = usize::from(app.preferences.generate_dds)
        + usize::from(app.preferences.delete_tif_after_dds)
        + usize::from(!app.preferences.rc_path.trim().is_empty());
    let pool_chip = app
        .process
        .as_ref()
        .filter(|process| process.dds_active)
        .map(|process| {
            fill(
                t.dds_pool_chip,
                &[
                    &process.dds_completed.to_string(),
                    &process.dds_total.to_string(),
                ],
            )
        });
    let open = app.ui.is_open(mode, "tex.rc");
    let response = widgets::collapsible_panel(
        ui,
        "tex.rc",
        "RC / DDS Export",
        Icon::Rc,
        open,
        rc_modified,
        pool_chip.as_deref().map(|chip| (chip, PcountStyle::New)),
        t.reset_to_defaults,
        |ui| rc_body(app, ui),
    );
    if response.toggled {
        app.ui.toggle_panel(mode, "tex.rc");
    }
    if response.reset_clicked {
        app.preferences.generate_dds = false;
        app.preferences.delete_tif_after_dds = false;
        app.preferences.rc_path.clear();
        app.save_preferences();
        app.ui.push_toast(t.toast_reset, "RC / DDS Export", false);
    }
}

// ---- Import ----------------------------------------------------------------

fn import_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    ui.horizontal(|ui| {
        if ui.button(t.add_files).clicked() {
            match choose_files_multi(t.dlg_select_texture_files, crate::IMAGE_FILTER) {
                Ok(files) if !files.is_empty() => app.add_texture_roots(files),
                Ok(_) => {}
                Err(error) => app.status = error,
            }
        }
        if ui.button(t.add_folder).clicked() {
            let initial = app.preferences.import_path.clone();
            if let Some(folder) =
                app.dialog_result(choose_folder(t.dlg_select_texture_folder, &initial))
            {
                app.add_texture_roots(vec![folder]);
            }
        }
    });
    ui.horizontal(|ui| {
        ui.add(
            TextEdit::singleline(&mut app.preferences.import_path)
                .desired_width(ui.available_width() - 86.0)
                .hint_text(t.texture_path_hint),
        );
        if ui.button(t.add_path).clicked() {
            let paths = crate::split_paths(&app.preferences.import_path)
                .into_iter()
                .filter(|path| path.exists())
                .collect::<Vec<_>>();
            app.add_texture_roots(paths);
        }
    });
    if app.texture.scan_receiver.is_some() {
        ui.horizontal(|ui| {
            ui.spinner();
            ui.label(RichText::new(t.scanning).color(theme::MUTED));
        });
    }
    ui.add_space(3.0);
    ui.label(
        RichText::new(fill(
            t.imported_textures_count,
            &[
                &app.texture.files.len().to_string(),
                &app.texture.selected_files.len().to_string(),
            ],
        ))
        .size(theme::FONT_SMALL)
        .color(theme::MUTED2),
    )
    .on_hover_text(t.multi_select_hint);
    let modifiers = ui.input(|input| input.modifiers);
    let mut clicked = None;
    egui::Frame::new()
        .fill(theme::STAGE)
        .stroke(Stroke::new(1.0, theme::BORDER))
        .corner_radius(egui::CornerRadius::same(theme::RADIUS_CTRL))
        .inner_margin(egui::Margin::same(4))
        .show(ui, |ui| {
            ui.set_width(ui.available_width());
            ScrollArea::vertical()
                .id_salt("tex_import_files")
                .max_height(190.0)
                .auto_shrink([false, true])
                .show(ui, |ui| {
                    for (index, path) in app.texture.files.iter().enumerate() {
                        let label = path
                            .file_name()
                            .and_then(|name| name.to_str())
                            .unwrap_or_default();
                        if ui
                            .selectable_label(app.texture.selected_files.contains(&index), label)
                            .on_hover_text(path.display().to_string())
                            .clicked()
                        {
                            clicked = Some((index, path.clone()));
                        }
                    }
                });
        });
    if let Some((index, path)) = clicked {
        app.apply_selection_click(index, modifiers.ctrl, modifiers.shift);
        let source_type = crate::source_type_for_path(app.texture.document.as_ref(), &path);
        app.request_preview(path, source_type);
    }
    let has_selection = !app.texture.selected_files.is_empty();
    ui.horizontal(|ui| {
        if ui
            .add_enabled(has_selection, egui::Button::new(t.remove_selected))
            .clicked()
        {
            app.remove_selected_textures();
        }
        if ui
            .add_enabled(has_selection, egui::Button::new(t.add_related))
            .on_hover_text(t.add_related_hover)
            .clicked()
        {
            app.add_related_textures();
        }
        if ui.button(t.clear_all).clicked() {
            app.clear_textures();
        }
    });
}

// ---- Group Review ----------------------------------------------------------

fn groups_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let Some(document) = &app.texture.document else {
        ui.label(RichText::new(t.groups_empty).color(theme::MUTED2));
        return;
    };
    let groups = document.scan().groups.clone();
    let query = app.texture.group_search.trim().to_lowercase();

    ui.horizontal(|ui| {
        ui.add(
            TextEdit::singleline(&mut app.texture.group_search)
                .desired_width(130.0)
                .hint_text(t.search_groups_hint),
        );
        ui.checkbox(&mut app.texture.review_only, t.unknown_only);
    });
    let visible = groups
        .iter()
        .enumerate()
        .filter(|(_, group)| !(app.texture.review_only && group.unknown.is_empty()))
        .filter(|(_, group)| query.is_empty() || group.base_name.to_lowercase().contains(&query))
        .map(|(index, _)| index)
        .collect::<Vec<_>>();
    ui.label(
        RichText::new(fill(
            t.groups_of_chip,
            &[&visible.len().to_string(), &groups.len().to_string()],
        ))
        .size(theme::FONT_SMALL)
        .color(theme::MUTED2),
    );
    ui.add_space(2.0);

    let mut preview_request: Option<(PathBuf, String)> = None;
    let mut select_group: Option<usize> = None;
    ScrollArea::vertical()
        .id_salt("tex_group_list")
        .max_height(300.0)
        .auto_shrink([false, true])
        .show(ui, |ui| {
            ui.spacing_mut().item_spacing.y = 3.0;
            for &index in &visible {
                let group = &groups[index];
                let selected = app.texture.selected_group == Some(index);
                let has_unknown = !group.unknown.is_empty();
                let (sub, sub_color) = if has_unknown {
                    (
                        fill(t.unassigned_n, &[&group.unknown.len().to_string()]),
                        theme::WARN,
                    )
                } else {
                    (
                        fill(t.linked_maps, &[&group.slots.len().to_string()]),
                        theme::LINKED_TEXT,
                    )
                };
                let row = widgets::grow_row(
                    ui,
                    ("tex_group", index),
                    selected,
                    has_unknown && !selected,
                    &group.key,
                    &group.base_name,
                    &sub,
                    sub_color,
                    |ui| {
                        // Right-to-left child: draw the optional unknown dot
                        // first (rightmost), then the 12 type columns reversed
                        // so they read left→right in GROUP_COLUMNS order.
                        ui.spacing_mut().item_spacing.x = 3.0;
                        if has_unknown {
                            let (rect, response) =
                                ui.allocate_exact_size(Vec2::splat(7.0), Sense::hover());
                            ui.painter().rect_filled(rect, 2.0, theme::WARN);
                            response.on_hover_text(fill(
                                t.unassigned_n,
                                &[&group.unknown.len().to_string()],
                            ));
                        }
                        for (source_type, label) in crate::GROUP_COLUMNS.iter().rev() {
                            let entry = group.slots.get(*source_type);
                            let sense = if entry.is_some() {
                                Sense::click()
                            } else {
                                Sense::hover()
                            };
                            let (rect, response) =
                                ui.allocate_exact_size(Vec2::splat(7.0), sense);
                            let color = if entry.is_some() {
                                theme::OK
                            } else {
                                theme::DOT_EMPTY
                            };
                            ui.painter().rect_filled(rect, 2.0, color);
                            if let Some(entry) = entry {
                                if response
                                    .on_hover_text(format!("{label} — {}", entry.filename))
                                    .clicked()
                                {
                                    select_group = Some(index);
                                    preview_request = Some((
                                        PathBuf::from(&entry.path),
                                        (*source_type).to_owned(),
                                    ));
                                }
                            } else {
                                response.on_hover_text(*label);
                            }
                        }
                    },
                );
                if row.clicked() {
                    select_group = Some(index);
                    preview_request = crate::first_group_entry(group)
                        .map(|entry| (PathBuf::from(&entry.path), entry.source_type.clone()));
                }
            }
        });

    // Assign-unknown workflow for the selected group (SPEC §7): the first
    // unknown entry gets a type combo; occupied types are DEF-19 blocked.
    let mut assign: Option<(usize, String)> = None;
    if let Some(index) = app.texture.selected_group {
        if let Some(group) = groups.get(index) {
            if let Some(unknown) = group.unknown.first() {
                ui.add_space(6.0);
                widgets::section_label(ui, t.assign_unknown_label);
                ui.label(
                    RichText::new(&unknown.filename)
                        .size(theme::FONT_SMALL)
                        .color(theme::MUTED),
                );
                let mut pick = String::new();
                ComboBox::from_id_salt(("tex_assign", index))
                    .width(ui.available_width() - 8.0)
                    .selected_text(
                        RichText::new(fill(
                            t.assign_combo,
                            &[&group.unknown.len().to_string()],
                        ))
                        .color(theme::WARN),
                    )
                    .show_ui(ui, |ui| {
                        for source_type in ASSIGNABLE_SOURCE_TYPES {
                            let occupied = group.slots.contains_key(source_type);
                            ui.add_enabled_ui(!occupied, |ui| {
                                ui.selectable_value(&mut pick, source_type.to_owned(), source_type)
                                    .on_disabled_hover_text(t.def19_hover);
                            });
                        }
                    });
                if !pick.is_empty() {
                    assign = Some((index, pick));
                }
            } else if app.texture.ever_unknown.contains(&group.key) {
                ui.add_space(4.0);
                ui.label(RichText::new(t.assigned_check).color(theme::OK));
            }
        }
    }

    if let Some(index) = select_group {
        app.texture.selected_group = Some(index);
    }
    if let Some((path, source_type)) = preview_request {
        app.request_preview(path, source_type);
    }
    if let Some((index, source_type)) = assign {
        app.assign_group_unknown(index, &source_type);
    }
}

// ---- Conversion Settings ---------------------------------------------------

/// Count of settings differing from `TextureSettings::default()`, for the ●N
/// badge. Sub-fields count individually so the number stays meaningful.
fn conversion_modified_count(settings: &TextureSettings) -> usize {
    let default = TextureSettings::default();
    let mut count = 0usize;
    count += usize::from(settings.output_resolution != default.output_resolution);
    count += usize::from(settings.diff_format != default.diff_format);
    count += usize::from(settings.normal_flip_green != default.normal_flip_green);
    count += usize::from(settings.process_metallic != default.process_metallic);
    count += usize::from(settings.generate_missing_spec != default.generate_missing_spec);
    count += usize::from(settings.texture_types.diff != default.texture_types.diff);
    count += usize::from(settings.texture_types.spec != default.texture_types.spec);
    count += usize::from(settings.texture_types.ddna != default.texture_types.ddna);
    count += usize::from(settings.texture_types.displ != default.texture_types.displ);
    count += usize::from(settings.texture_types.emissive != default.texture_types.emissive);
    count += usize::from(settings.texture_types.sss != default.texture_types.sss);
    count += usize::from(settings.normalize_height != default.normalize_height);
    count += usize::from(settings.dither != default.dither);
    count += usize::from(settings.generate_missing_emissive != default.generate_missing_emissive);
    count += usize::from(settings.generate_missing_sss != default.generate_missing_sss);
    count += usize::from(settings.generate_sss_from_diffuse != default.generate_sss_from_diffuse);
    count += usize::from(settings.metal_gate != default.metal_gate);
    count += usize::from(settings.arm_order != default.arm_order);
    count +=
        usize::from(settings.normal_from_height_strength != default.normal_from_height_strength);
    count += usize::from(settings.emissive_brightness != default.emissive_brightness);
    count += usize::from(settings.sss_intensity != default.sss_intensity);
    count += usize::from(settings.sss_contrast != default.sss_contrast);
    count += usize::from(settings.metal_gate_metallic_cut != default.metal_gate_metallic_cut);
    count += usize::from(settings.metal_gate_spec_min != default.metal_gate_spec_min);
    count += usize::from(settings.metal_gate_gloss_cut != default.metal_gate_gloss_cut);
    count += usize::from(settings.metal_gate_transition != default.metal_gate_transition);
    count
}

fn conversion_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    use texproc::{ArmOrder, DiffFormat, OutputResolution};

    ui.columns(2, |cols| {
        cols[0].label(
            RichText::new(t.output_resolution_label)
                .size(theme::FONT_SMALL)
                .color(theme::MUTED),
        );
        ComboBox::from_id_salt("v2_resolution")
            .width(cols[0].available_width())
            .selected_text(crate::resolution_label(app.settings.output_resolution))
            .show_ui(&mut cols[0], |ui| {
                for (label, value) in [
                    ("Original", OutputResolution::Original),
                    ("4096", OutputResolution::Max(4096)),
                    ("2048", OutputResolution::Max(2048)),
                    ("1024", OutputResolution::Max(1024)),
                    ("512", OutputResolution::Max(512)),
                    ("256", OutputResolution::Max(256)),
                ] {
                    ui.selectable_value(&mut app.settings.output_resolution, value, label);
                }
            });
        cols[1].label(
            RichText::new(t.diffuse_format_label)
                .size(theme::FONT_SMALL)
                .color(theme::MUTED),
        );
        ComboBox::from_id_salt("v2_diff_format")
            .width(cols[1].available_width())
            .selected_text(match app.settings.diff_format {
                DiffFormat::Albedo => "albedo",
                DiffFormat::DiffuseAo => "diffuse_ao",
            })
            .show_ui(&mut cols[1], |ui| {
                ui.selectable_value(&mut app.settings.diff_format, DiffFormat::Albedo, "albedo");
                ui.selectable_value(
                    &mut app.settings.diff_format,
                    DiffFormat::DiffuseAo,
                    "diffuse_ao",
                );
            });
    });
    ui.add_space(2.0);
    ui.checkbox(&mut app.settings.normal_flip_green, t.flip_normal_green);
    ui.checkbox(&mut app.settings.process_metallic, t.convert_metallic);
    ui.checkbox(&mut app.settings.generate_missing_spec, t.generate_missing_spec);
    let rc_available = crate::resolve_rc_path(&app.preferences.rc_path).path.is_some();
    if rc_available {
        if ui
            .checkbox(&mut app.preferences.generate_dds, t.generate_dds)
            .changed()
        {
            app.save_preferences();
        }
    } else {
        app.preferences.generate_dds = false;
        ui.add_enabled_ui(false, |ui| {
            let mut off = false;
            ui.checkbox(&mut off, t.generate_dds);
        })
        .response
        .on_hover_text(t.rc_not_configured);
    }
    if ui
        .checkbox(&mut app.preferences.delete_tif_after_dds, t.delete_tif)
        .on_hover_text(t.delete_tif_hover)
        .changed()
    {
        app.save_preferences();
    }

    ui.add_space(4.0);
    egui::CollapsingHeader::new(
        RichText::new(t.advanced_heading).size(11.5).strong().color(theme::MUTED),
    )
    .id_salt("v2_tex_advanced")
    .show(ui, |ui| {
        widgets::section_label(ui, t.output_texture_types);
        Grid::new("v2_texture_types").num_columns(2).show(ui, |ui| {
            ui.checkbox(&mut app.settings.texture_types.diff, t.tt_diff);
            ui.checkbox(&mut app.settings.texture_types.spec, t.tt_spec);
            ui.end_row();
            ui.checkbox(&mut app.settings.texture_types.ddna, t.tt_ddna);
            ui.checkbox(&mut app.settings.texture_types.displ, t.tt_displ);
            ui.end_row();
            ui.checkbox(&mut app.settings.texture_types.emissive, t.tt_emissive);
            ui.checkbox(&mut app.settings.texture_types.sss, t.tt_sss);
            ui.end_row();
        });
        ui.add_space(4.0);
        ui.checkbox(&mut app.settings.normalize_height, t.normalize_height);
        ui.checkbox(&mut app.settings.dither, t.dither);
        ui.checkbox(
            &mut app.settings.generate_missing_emissive,
            t.generate_missing_emissive,
        );
        ui.checkbox(&mut app.settings.generate_missing_sss, t.generate_missing_sss);
        ui.checkbox(
            &mut app.settings.generate_sss_from_diffuse,
            t.generate_sss_from_diffuse,
        );
        ui.add_space(4.0);
        Grid::new("v2_tex_advanced_grid")
            .num_columns(2)
            .spacing([10.0, 5.0])
            .show(ui, |ui| {
                ui.label(t.arm_order_label);
                ComboBox::from_id_salt("v2_arm_order")
                    .selected_text(match app.settings.arm_order {
                        ArmOrder::Arm => "ARM",
                        ArmOrder::Orm => "ORM",
                        ArmOrder::Rma => "RMA",
                    })
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut app.settings.arm_order, ArmOrder::Arm, "ARM");
                        ui.selectable_value(&mut app.settings.arm_order, ArmOrder::Orm, "ORM");
                        ui.selectable_value(&mut app.settings.arm_order, ArmOrder::Rma, "RMA");
                    });
                ui.end_row();
                ui.label(t.height_normal_strength);
                ui.add(
                    egui::DragValue::new(&mut app.settings.normal_from_height_strength)
                        .speed(0.1)
                        .range(0.0..=100.0),
                );
                ui.end_row();
                ui.label(t.emissive_brightness_label);
                ui.add(
                    egui::DragValue::new(&mut app.settings.emissive_brightness)
                        .speed(0.05)
                        .range(0.0..=20.0),
                );
                ui.end_row();
                ui.label(t.sss_intensity_label);
                ui.add(
                    egui::DragValue::new(&mut app.settings.sss_intensity)
                        .speed(0.05)
                        .range(0.0..=20.0),
                );
                ui.end_row();
                ui.label(t.sss_contrast_label);
                ui.add(
                    egui::DragValue::new(&mut app.settings.sss_contrast)
                        .speed(0.05)
                        .range(0.0..=5.0),
                );
                ui.end_row();
            });
        ui.add_space(4.0);
        // "Metal Gate" is a proper feature name — untranslated per policy.
        ui.checkbox(&mut app.settings.metal_gate, "Metal Gate")
            .on_hover_text(t.metal_gate_hover);
        ui.add_enabled_ui(app.settings.metal_gate, |ui| {
            Grid::new("v2_metal_gate")
                .num_columns(2)
                .spacing([10.0, 5.0])
                .show(ui, |ui| {
                    ui.label(t.mg_metallic_cut);
                    ui.add(
                        egui::DragValue::new(&mut app.settings.metal_gate_metallic_cut)
                            .speed(0.01)
                            .range(0.0..=1.0),
                    );
                    ui.end_row();
                    ui.label(t.mg_spec_min);
                    ui.add(
                        egui::DragValue::new(&mut app.settings.metal_gate_spec_min)
                            .speed(0.01)
                            .range(0.0..=1.0),
                    );
                    ui.end_row();
                    ui.label(t.mg_gloss_cut);
                    ui.add(
                        egui::DragValue::new(&mut app.settings.metal_gate_gloss_cut)
                            .speed(0.01)
                            .range(0.0..=1.0),
                    );
                    ui.end_row();
                    ui.label(t.mg_transition);
                    ui.add(
                        egui::DragValue::new(&mut app.settings.metal_gate_transition)
                            .speed(0.01)
                            .range(0.0..=0.5),
                    );
                    ui.end_row();
                });
        });
    });
}

// ---- RC / DDS Export -------------------------------------------------------

/// RC.exe path field + resolution status, shared with the Models stack's
/// Export Options panel (both edit the same preference).
pub(super) fn rc_path_section(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    ui.label(
        RichText::new(t.rc_path_label)
            .size(theme::FONT_SMALL)
            .color(theme::MUTED),
    );
    let resolution = crate::resolve_rc_path(&app.preferences.rc_path);
    let invalid = resolution.configured_invalid || resolution.path.is_none();
    let stroke = if invalid {
        Stroke::new(1.5, theme::HAZARD)
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
                        TextEdit::singleline(&mut app.preferences.rc_path)
                            .desired_width((ui.available_width() - 74.0).max(100.0))
                            .hint_text(r"C:\CryEngine\Tools\rc\rc.exe"),
                    )
                    .changed();
            });
        browse = ui.button(t.browse).clicked();
    });
    if browse {
        match choose_rc_executable(&app.preferences.rc_path) {
            Ok(Some(path)) => {
                app.preferences.rc_path = path.to_string_lossy().into_owned();
                changed = true;
            }
            Ok(None) => {}
            Err(error) => app.status = error,
        }
    }
    if changed {
        app.save_preferences();
    }
    let resolution = crate::resolve_rc_path(&app.preferences.rc_path);
    if resolution.configured_invalid {
        ui.label(
            RichText::new(match (&resolution.path, resolution.source) {
                (Some(path), source) => {
                    fill(t.rc_invalid_using, &[source, &path.display().to_string()])
                }
                (None, _) => t.rc_not_configured_full.to_owned(),
            })
            .size(theme::FONT_SMALL)
            .color(theme::HAZARD),
        );
    } else if let Some(path) = &resolution.path {
        ui.label(
            RichText::new(fill(t.rc_using, &[resolution.source, &path.display().to_string()]))
                .size(theme::FONT_SMALL)
                .color(theme::MUTED2),
        );
    } else {
        ui.label(
            RichText::new(t.rc_not_configured_full)
                .size(theme::FONT_SMALL)
                .color(theme::HAZARD),
        );
    }
}

fn rc_body(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    rc_path_section(app, ui);

    // Adaptive pool progress while the running conversion is in its DDS phase.
    if let Some(process) = app.process.as_ref().filter(|process| process.dds_active) {
        ui.add_space(6.0);
        let fraction = if process.dds_total > 0 {
            process.dds_completed as f32 / process.dds_total as f32
        } else {
            0.0
        };
        ui.add(
            egui::ProgressBar::new(fraction)
                .desired_width(ui.available_width())
                .desired_height(7.0)
                .fill(theme::ACCENT),
        );
        ui.label(
            RichText::new(fill(
                t.dds_pool_line,
                &[
                    &process.dds_workers.to_string(),
                    &process.dds_completed.to_string(),
                    &process.dds_total.to_string(),
                    &process.dds_current,
                ],
            ))
            .size(theme::FONT_SMALL)
            .color(theme::MUTED2),
        );
    }
}
