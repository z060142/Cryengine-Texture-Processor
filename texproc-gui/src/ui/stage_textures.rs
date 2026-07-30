//! Textures stage (SPEC.md §6.2): the existing texture preview as the central
//! viewport — HUD chips, fitted image with caption pills, and the drop-zone /
//! select-a-group empty states.

use eframe::egui::{
    self, Align, Align2, Color32, FontId, Layout, Pos2, Rect, RichText, Sense, Stroke, UiBuilder,
    Vec2,
};

use texproc_gui::ASSIGNABLE_SOURCE_TYPES;

use crate::i18n::fill;

use super::theme;
use super::widgets::{self, PcountStyle};

pub fn draw(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let rect = ui.available_rect_before_wrap();

    // Selected group drives the HUD + caption (cloned so the immutable borrow
    // does not pin `app` while widgets run).
    let group = app
        .texture
        .selected_group
        .zip(app.texture.document.as_ref())
        .and_then(|(index, document)| document.scan().groups.get(index))
        .cloned();

    if app.texture.document.is_none() {
        drop_zone(ui, rect, t.drop_hint, t.groups_empty);
        return;
    }

    let available = rect.size();
    if let Some(texture) = app.preview.texture.clone() {
        let source = texture.size_vec2();
        // Mockup proportions: the board occupies roughly half the stage.
        let cap = (available.y * 0.62).min(available.x * 0.55).max(160.0);
        let max = Vec2::splat(cap);
        let scale = (max.x / source.x).min(max.y / source.y).min(1.0);
        let size = source * scale;
        ui.scope_builder(
            UiBuilder::new()
                .max_rect(rect)
                .layout(Layout::top_down(Align::Center)),
            |ui| {
                let pad = ((available.y - size.y - 52.0) / 2.0).max(8.0);
                ui.add_space(pad);
                let image = ui.add(egui::Image::new(&texture).fit_to_exact_size(size));
                // Mockup tileboard treatment: rounded corners + faint 1px edge.
                ui.painter().rect_stroke(
                    image.rect,
                    6.0,
                    Stroke::new(1.0, Color32::from_white_alpha(18)),
                    egui::StrokeKind::Outside,
                );
                ui.add_space(14.0);
                caption_row(ui, app, group.as_ref(), available.x);
            },
        );
    } else if let Some(error) = &app.preview.error {
        ui.scope_builder(
            UiBuilder::new()
                .max_rect(rect)
                .layout(Layout::centered_and_justified(egui::Direction::TopDown)),
            |ui| {
                ui.label(
                    RichText::new(fill(t.preview_unavailable, &[error])).color(theme::HAZARD),
                );
            },
        );
    } else {
        ui.scope_builder(
            UiBuilder::new()
                .max_rect(rect)
                .layout(Layout::centered_and_justified(egui::Direction::TopDown)),
            |ui| {
                ui.label(RichText::new(t.select_group_preview).color(theme::MUTED2));
            },
        );
    }

    // HUD chips (top-left, drawn last so they overlay the image).
    let hud_rect = Rect::from_min_size(
        rect.min + Vec2::new(16.0, 14.0),
        Vec2::new(300.0, rect.height() - 28.0),
    );
    let mut hud = ui.new_child(
        UiBuilder::new()
            .max_rect(hud_rect)
            .layout(Layout::top_down(Align::LEFT)),
    );
    hud.spacing_mut().item_spacing.y = 4.0;
    if let Some(group) = &group {
        widgets::hud_chip(&mut hud, RichText::new(&group.base_name).strong());
    }
    if let Some(path) = app
        .preview
        .loaded_path
        .as_ref()
        .or(app.preview.requested_path.as_ref())
    {
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or_default();
        let text = if app.preview.source_type.is_empty() {
            name.to_owned()
        } else {
            format!("{name} · {}", app.preview.source_type)
        };
        widgets::hud_chip(&mut hud, text);
    }
    if let Some((width, height)) = app.preview.dimensions {
        widgets::hud_chip(&mut hud, format!("{width} × {height}"));
    }
    if app.preview.receiver.is_some() {
        hud.spinner();
    }
}

/// Caption under the image (mockup `.matcaption`): base name + one pill per
/// filled slot + a WARN pill for unresolved unknowns. Centered by measuring
/// the content first (egui has no reliable center main-align for rows).
fn caption_row(
    ui: &mut egui::Ui,
    app: &crate::WorkflowApp,
    group: Option<&texproc::ScanGroup>,
    width: f32,
) {
    let t = app.t();
    let Some(group) = group else {
        return;
    };
    let name_font = FontId::proportional(12.0);
    let pill_font = FontId::proportional(theme::FONT_SMALL);
    let measure = |text: &str, font: &FontId| {
        ui.painter()
            .layout_no_wrap(text.to_owned(), font.clone(), theme::INK)
            .size()
            .x
    };
    let spacing = 6.0;
    let mut total = measure(&group.base_name, &name_font);
    let mut pills: Vec<(String, PcountStyle)> = Vec::new();
    for source_type in ASSIGNABLE_SOURCE_TYPES {
        if group.slots.contains_key(source_type) {
            pills.push(((*source_type).to_owned(), PcountStyle::Normal));
        }
    }
    if !group.unknown.is_empty() {
        pills.push((
            fill(t.unknown_badge, &[&group.unknown.len().to_string()]),
            PcountStyle::Hot,
        ));
    }
    for (text, _) in &pills {
        total += spacing + measure(text, &pill_font) + 18.0;
    }
    ui.allocate_ui_with_layout(
        Vec2::new(width, 26.0),
        Layout::left_to_right(Align::Center),
        |ui| {
            ui.spacing_mut().item_spacing.x = spacing;
            ui.add_space(((width - total) / 2.0).max(0.0));
            ui.label(
                RichText::new(&group.base_name)
                    .size(12.0)
                    .strong()
                    .color(theme::INK),
            );
            for (text, style) in pills {
                widgets::pill(ui, text, style);
            }
        },
    );
}

/// Empty-state drop zone: centered dashed rounded frame with the drop hint.
fn drop_zone(ui: &mut egui::Ui, rect: Rect, headline: &str, sub: &str) {
    let zone = Rect::from_center_size(rect.center(), Vec2::new(430.0, 150.0));
    let painter = ui.painter();
    dashed_rect(painter, zone.shrink(0.5), theme::BORDER2, 9.0, 7.0);
    painter.text(
        zone.center() - Vec2::new(0.0, 14.0),
        Align2::CENTER_CENTER,
        headline,
        FontId::proportional(13.0),
        theme::MUTED,
    );
    painter.text(
        zone.center() + Vec2::new(0.0, 14.0),
        Align2::CENTER_CENTER,
        sub,
        FontId::proportional(theme::FONT_SMALL),
        theme::MUTED2,
    );
    // Keep the area allocated so the stage does not collapse.
    ui.allocate_rect(rect, Sense::hover());
}

/// egui strokes have no dash pattern; approximate one segment at a time.
fn dashed_rect(painter: &egui::Painter, rect: Rect, color: Color32, dash: f32, gap: f32) {
    let stroke = Stroke::new(1.5, color);
    let edges = [
        (rect.left_top(), rect.right_top()),
        (rect.right_top(), rect.right_bottom()),
        (rect.right_bottom(), rect.left_bottom()),
        (rect.left_bottom(), rect.left_top()),
    ];
    for (from, to) in edges {
        let length = from.distance(to);
        let direction = (to - from) / length;
        let mut travelled = 0.0;
        while travelled < length {
            let end = (travelled + dash).min(length);
            painter.line_segment(
                [
                    Pos2::new(from.x + direction.x * travelled, from.y + direction.y * travelled),
                    Pos2::new(from.x + direction.x * end, from.y + direction.y * end),
                ],
                stroke,
            );
            travelled = end + gap;
        }
    }
}
