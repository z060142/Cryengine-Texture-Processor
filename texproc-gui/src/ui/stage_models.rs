//! Models stage (SPEC.md §6.3): the material-slot workspace as the central
//! document — HUD chips, slots table with per-row and bulk physicalize,
//! material details, slot diagnostics, and the axis caption overlay.

use eframe::egui::{
    self, Align, Align2, ComboBox, FontId, Grid, Layout, Margin, Pos2, Rect, RichText, ScrollArea,
    UiBuilder,
};

use converter::rc_policy::resolve_physicalize;
use texproc_gui::axes_parallel;

use crate::i18n::fill;

use super::theme;
use super::widgets;

pub fn draw(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let rect = ui.available_rect_before_wrap();
    let Some(index) = app.selected_entry_index() else {
        ui.scope_builder(
            UiBuilder::new()
                .max_rect(rect)
                .layout(Layout::centered_and_justified(egui::Direction::TopDown)),
            |ui| {
                let hint = if app.model.entries.is_empty() {
                    t.add_fbx_left
                } else {
                    t.select_single_model_left
                };
                ui.label(RichText::new(hint).color(theme::MUTED2));
            },
        );
        return;
    };

    let manifest_configured = !app.preferences.manifest_path.trim().is_empty();
    let modifiers = ui.input(|input| input.modifiers);
    // Take the entry's mutable working state out so `review` can be borrowed
    // for the whole render without a self.model conflict (v1 pattern).
    let mut phys = std::mem::take(&mut app.model.entries[index].physicalize_overrides);
    let mut selected_material = app.model.entries[index].selected_material;
    let mut selected_materials = std::mem::take(&mut app.model.entries[index].selected_materials);
    let mut selection_anchor = app.model.entries[index].material_selection_anchor;
    let mut bulk = std::mem::take(&mut app.model.entries[index].bulk_physicalize);
    {
        let review = &app.model.entries[index].review;
        let file_name = review
            .path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("FBX")
            .to_owned();

        let content_w = (rect.width() - 48.0).min(880.0);
        let pad = ((rect.width() - content_w) / 2.0).max(16.0);
        let inner = Rect::from_min_max(
            Pos2::new(rect.left() + pad, rect.top() + 14.0),
            Pos2::new(rect.left() + pad + content_w, rect.bottom() - 34.0),
        );
        let mut content = ui.new_child(
            UiBuilder::new()
                .max_rect(inner)
                .layout(Layout::top_down(Align::LEFT)),
        );
        // HUD chip row.
        content.horizontal(|ui| {
            ui.spacing_mut().item_spacing.x = 5.0;
            widgets::hud_chip(ui, RichText::new(&file_name).strong());
            widgets::hud_chip(
                ui,
                format!(
                    "{} · {}",
                    fill(t.material_slots_count, &[&review.material_slots.len().to_string()]),
                    fill(t.diagnostics_count, &[&review.diagnostics.len().to_string()]),
                ),
            );
        });
        content.add_space(8.0);

        ScrollArea::vertical()
            .id_salt("mdl_stage_scroll")
            .auto_shrink([false, false])
            .show(&mut content, |ui| {
                // ---- Material Slots card ----
                theme::panel_frame()
                    .inner_margin(Margin::same(12))
                    .show(ui, |ui| {
                        ui.set_width(ui.available_width() - 4.0);
                        ui.label(RichText::new(t.rc_material_slots).strong());
                        ui.label(
                            RichText::new(t.multi_select_fbx_hint)
                                .size(theme::FONT_SMALL)
                                .color(theme::MUTED2),
                        );
                        let selected_count = selected_materials.len();
                        if selected_count > 0 {
                            ui.horizontal(|ui| {
                                ComboBox::from_id_salt("v2_bulk_physicalize")
                                    .selected_text(&bulk)
                                    .show_ui(ui, |ui| {
                                        for value in crate::PHYSICALIZE_VALUES {
                                            ui.selectable_value(&mut bulk, value.to_owned(), value);
                                        }
                                    });
                                if ui
                                    .button(fill(
                                        t.set_physicalize_btn,
                                        &[&selected_count.to_string()],
                                    ))
                                    .clicked()
                                {
                                    let names: Vec<&str> = review
                                        .material_slots
                                        .iter()
                                        .map(|slot| slot.name.as_str())
                                        .collect();
                                    crate::apply_bulk_physicalize(
                                        &mut phys,
                                        &names,
                                        &selected_materials,
                                        &bulk,
                                    );
                                }
                            });
                        }
                        ui.add_space(4.0);
                        Grid::new("v2_model_materials")
                            .num_columns(6)
                            .striped(true)
                            .spacing([14.0, 5.0])
                            .show(ui, |ui| {
                                // "FBX" / "Physicalize" are proper terms — untranslated.
                                for header in [
                                    "FBX",
                                    t.col_sub,
                                    t.col_material,
                                    "Physicalize",
                                    t.col_polygons,
                                    t.col_textures,
                                ] {
                                    ui.label(
                                        RichText::new(header)
                                            .size(theme::FONT_SECTION)
                                            .strong()
                                            .color(theme::MUTED2),
                                    );
                                }
                                ui.end_row();
                                for (row, slot) in review.material_slots.iter().enumerate() {
                                    let selected = selected_materials.contains(&row);
                                    if ui
                                        .selectable_label(
                                            selected,
                                            slot.fbx_material_id
                                                .and_then(|id| id.checked_sub(1))
                                                .map_or_else(
                                                    || "—".to_owned(),
                                                    |value| value.to_string(),
                                                ),
                                        )
                                        .clicked()
                                    {
                                        crate::apply_click_selection(
                                            &mut selected_materials,
                                            &mut selection_anchor,
                                            row,
                                            modifiers.ctrl,
                                            modifiers.shift,
                                        );
                                        selected_material = Some(row);
                                    }
                                    ui.label(slot.sub_index.to_string());
                                    ui.label(&slot.name);
                                    let default_value = if manifest_configured {
                                        resolve_physicalize(
                                            slot.physicalize
                                                .as_deref()
                                                .map(|value| ("physicalize", value)),
                                            &slot.name,
                                        )
                                        .value
                                        .as_str()
                                        .to_owned()
                                    } else {
                                        crate::DEFAULT_PHYSICALIZE.to_owned()
                                    };
                                    let mut physicalize = phys
                                        .get(&slot.name)
                                        .cloned()
                                        .unwrap_or_else(|| default_value.clone());
                                    ComboBox::from_id_salt(("v2_physicalize", row))
                                        .selected_text(&physicalize)
                                        .show_ui(ui, |ui| {
                                            for value in crate::PHYSICALIZE_VALUES {
                                                ui.selectable_value(
                                                    &mut physicalize,
                                                    value.to_owned(),
                                                    value,
                                                );
                                            }
                                        });
                                    if manifest_configured && physicalize == default_value {
                                        phys.remove(&slot.name);
                                    } else {
                                        phys.insert(slot.name.clone(), physicalize);
                                    }
                                    let assignment =
                                        slot.source_order.and_then(|source_order| {
                                            review.assignments.iter().find(|assignment| {
                                                assignment.source_order == source_order
                                            })
                                        });
                                    ui.label(
                                        assignment
                                            .and_then(|assignment| assignment.polygon_count)
                                            .unwrap_or(0)
                                            .to_string(),
                                    );
                                    let textures = slot
                                        .source_order
                                        .and_then(|source_order| {
                                            review.model.materials.get(source_order)
                                        })
                                        .map_or(0, |material| material.textures.len());
                                    ui.label(textures.to_string());
                                    ui.end_row();
                                }
                            });
                    });
                ui.add_space(9.0);

                // ---- Material Details card ----
                if let Some(selected) = selected_material {
                    if let Some(slot) = review.material_slots.get(selected) {
                        theme::panel_frame()
                            .inner_margin(Margin::same(12))
                            .show(ui, |ui| {
                                ui.set_width(ui.available_width() - 4.0);
                                ui.label(
                                    RichText::new(fill(t.material_details, &[&slot.name]))
                                        .strong(),
                                );
                                ui.label(
                                    RichText::new(fill(
                                        t.assignment_source,
                                        &[slot
                                            .assignment_reason
                                            .as_deref()
                                            .unwrap_or("slot projection")],
                                    ))
                                    .size(theme::FONT_SMALL)
                                    .color(theme::MUTED2),
                                );
                                if let Some(material) = slot.source_order.and_then(|source_order| {
                                    review.model.materials.get(source_order)
                                }) {
                                    if material.textures.is_empty() {
                                        ui.label(
                                            RichText::new(t.no_texture_references)
                                                .color(theme::MUTED2),
                                        );
                                    }
                                    for texture in &material.textures {
                                        ui.horizontal_wrapped(|ui| {
                                            ui.label(
                                                RichText::new(&texture.shader_prop).strong(),
                                            );
                                            ui.label(
                                                RichText::new(if texture.embedded {
                                                    fill(
                                                        t.embedded_texture,
                                                        &[
                                                            &texture.filename,
                                                            &texture.content_size.to_string(),
                                                        ],
                                                    )
                                                } else {
                                                    texture.absolute_filename.clone()
                                                })
                                                .color(theme::MUTED),
                                            );
                                        });
                                    }
                                }
                            });
                        ui.add_space(9.0);
                    }
                }

                // ---- Diagnostics card ----
                theme::panel_frame()
                    .inner_margin(Margin::same(12))
                    .show(ui, |ui| {
                        ui.set_width(ui.available_width() - 4.0);
                        ui.label(RichText::new(t.material_slot_diagnostics).strong());
                        if review.diagnostics.is_empty() {
                            ui.label(
                                RichText::new(t.no_material_diagnostics).color(theme::OK),
                            );
                        }
                        for diagnostic in &review.diagnostics {
                            ui.label(
                                RichText::new(format!(
                                    "[{}] {} · {}",
                                    diagnostic.severity, diagnostic.material, diagnostic.message
                                ))
                                .size(11.5)
                                .color(theme::MUTED),
                            );
                        }
                    });
                ui.add_space(6.0);
            });

        // Axis caption overlay (mockup .axisgz), bottom-left of the stage.
        let conversion = &app.model.entries[index].conversion;
        let overridden = conversion.forward != conversion.detected_forward
            || conversion.up != conversion.detected_up;
        let parallel = axes_parallel(&conversion.forward, &conversion.up);
        let axis_color = if parallel {
            theme::HAZARD
        } else if overridden {
            theme::WARN
        } else {
            theme::OK
        };
        let painter = ui.painter();
        let base = Pos2::new(rect.left() + 20.0, rect.bottom() - 16.0);
        let font = FontId::proportional(11.0);
        let lead = painter.text(
            base,
            Align2::LEFT_CENTER,
            format!("Forward {} · Up {}", conversion.forward, conversion.up),
            font.clone(),
            axis_color,
        );
        painter.text(
            Pos2::new(lead.right() + 8.0, base.y),
            Align2::LEFT_CENTER,
            fill(
                t.axis_footer,
                &[
                    &format!("{}", app.preferences.conversion_scale),
                    &app.preferences.conversion_unit,
                ],
            ),
            font,
            theme::MUTED2,
        );
    }
    let entry = &mut app.model.entries[index];
    entry.physicalize_overrides = phys;
    entry.selected_material = selected_material;
    entry.selected_materials = selected_materials;
    entry.material_selection_anchor = selection_anchor;
    entry.bulk_physicalize = bulk;
}
