//! Visual tokens for the v2 UI, translated verbatim from the mockup CSS
//! (SPEC.md §1). theme.rs is the single source of truth — no other module may
//! hardcode a chrome color.

use eframe::egui::{self, Color32, CornerRadius, FontFamily, FontId, Margin, Stroke, TextStyle};

// ---- core palette -----------------------------------------------------------
pub const BG: Color32 = Color32::from_rgb(0x18, 0x1b, 0x21);
pub const STAGE: Color32 = Color32::from_rgb(0x10, 0x12, 0x16);
pub const PANEL: Color32 = Color32::from_rgb(0x22, 0x26, 0x2e);
pub const PANEL2: Color32 = Color32::from_rgb(0x29, 0x2e, 0x37);
pub const PANEL3: Color32 = Color32::from_rgb(0x2f, 0x35, 0x3f);
pub const BORDER: Color32 = Color32::from_rgb(0x36, 0x3c, 0x47);
pub const BORDER2: Color32 = Color32::from_rgb(0x43, 0x4b, 0x58);
pub const INK: Color32 = Color32::from_rgb(0xe6, 0xe9, 0xef);
pub const MUTED: Color32 = Color32::from_rgb(0x9a, 0xa3, 0xb2);
pub const MUTED2: Color32 = Color32::from_rgb(0x6c, 0x74, 0x80);
pub const ACCENT: Color32 = Color32::from_rgb(0x4d, 0x8d, 0xff);
pub const ACCENT2: Color32 = Color32::from_rgb(0x7c, 0x5c, 0xff);
pub const ACCENT_TEXT: Color32 = Color32::from_rgb(0x8f, 0xb6, 0xff);
pub const ACCENT_BORDER: Color32 = Color32::from_rgb(0x31, 0x50, 0x8c);
pub const OK: Color32 = Color32::from_rgb(0x41, 0xc0, 0x72);
pub const OK_BORDER: Color32 = Color32::from_rgb(0x2c, 0x4a, 0x37);
pub const WARN: Color32 = Color32::from_rgb(0xe2, 0xa1, 0x3c);
pub const WARN_BORDER: Color32 = Color32::from_rgb(0x5a, 0x46, 0x20);
pub const HAZARD: Color32 = Color32::from_rgb(0xe5, 0x56, 0x4c);

// Translucent "weak" fills, stored premultiplied so they can be `const`.
/// rgba(77,141,255,0.16)
pub const ACCENT_WEAK: Color32 = Color32::from_rgba_premultiplied(12, 23, 41, 41);
/// rgba(65,192,114,0.15)
pub const OK_WEAK: Color32 = Color32::from_rgba_premultiplied(10, 29, 17, 38);
/// rgba(226,161,60,0.15)
pub const WARN_WEAK: Color32 = Color32::from_rgba_premultiplied(34, 24, 9, 38);
/// Stage grid line: white at alpha ≈ 0x08.
pub const GRID: Color32 = Color32::from_rgba_premultiplied(8, 8, 8, 8);
/// HUD chip background: rgba(20,23,29,0.72).
#[allow(dead_code)] // Phase B: stage HUD chips (SPEC §6.2).
pub const HUD_BG: Color32 = Color32::from_rgba_premultiplied(14, 17, 21, 184);
/// Stagebar wash over the stage: rgba(24,27,33,0.7).
pub const STAGEBAR_BG: Color32 = Color32::from_rgba_premultiplied(17, 19, 23, 178);

// Chrome strip fills (mockup gradients flattened to their midpoint).
pub const TOPBAR_BG: Color32 = Color32::from_rgb(0x20, 0x24, 0x2c);
pub const RAIL_BG: Color32 = Color32::from_rgb(0x1b, 0x1e, 0x24);
pub const TIMELINE_BG: Color32 = Color32::from_rgb(0x19, 0x1c, 0x20);
pub const PRESETBAR_BG: Color32 = Color32::from_rgb(0x1d, 0x21, 0x2a);
pub const STAGEBAR_LINE: Color32 = Color32::from_rgb(0x23, 0x27, 0x2f);
/// Empty type-dot fill in group rows (mockup `.tdot`).
#[allow(dead_code)] // Phase B: Group Review type dots (SPEC §7).
pub const DOT_EMPTY: Color32 = Color32::from_rgb(0x3b, 0x41, 0x4c);
/// "linked: N maps" sub-line color (mockup `.gsub.link`).
#[allow(dead_code)] // Phase B: Group Review sub-line (SPEC §7).
pub const LINKED_TEXT: Color32 = Color32::from_rgb(0x6f, 0x8f, 0xbf);

// ---- sizes ------------------------------------------------------------------
pub const TOPBAR_H: f32 = 44.0;
pub const RAIL_W: f32 = 76.0;
pub const RAIL_BTN: f32 = 60.0;
pub const STACK_W: f32 = 344.0;
pub const STAGEBAR_H: f32 = 40.0;
pub const TIMELINE_H: f32 = 64.0;

// Corner radii (panel 8, controls 6, rail buttons 10, chips 14).
pub const RADIUS_PANEL: u8 = 8;
pub const RADIUS_CTRL: u8 = 6;
pub const RADIUS_RAIL: u8 = 10;
pub const RADIUS_CHIP: u8 = 14;

// ---- fonts ------------------------------------------------------------------
pub const FONT_BODY: f32 = 13.0;
pub const FONT_SMALL: f32 = 10.5;
pub const FONT_BUTTON: f32 = 12.0;
pub const FONT_PANEL_TITLE: f32 = 12.5;
pub const FONT_SECTION: f32 = 10.0;

/// Apply the dark v2 style to the whole context. Called once at startup.
pub fn apply_style(ctx: &egui::Context) {
    let mut style = (*ctx.style()).clone();
    style.text_styles.insert(
        TextStyle::Body,
        FontId::new(FONT_BODY, FontFamily::Proportional),
    );
    style.text_styles.insert(
        TextStyle::Small,
        FontId::new(FONT_SMALL, FontFamily::Proportional),
    );
    style.text_styles.insert(
        TextStyle::Button,
        FontId::new(FONT_BUTTON, FontFamily::Proportional),
    );
    style.text_styles.insert(
        TextStyle::Heading,
        FontId::new(15.0, FontFamily::Proportional),
    );
    style.spacing.button_padding = egui::vec2(10.0, 5.0);
    style.spacing.item_spacing = egui::vec2(7.0, 6.0);

    let visuals = &mut style.visuals;
    *visuals = egui::Visuals::dark();
    visuals.window_fill = PANEL;
    visuals.panel_fill = BG;
    visuals.faint_bg_color = PANEL2;
    visuals.extreme_bg_color = STAGE;
    visuals.window_stroke = Stroke::new(1.0, BORDER2);
    visuals.window_corner_radius = CornerRadius::same(RADIUS_RAIL);
    visuals.menu_corner_radius = CornerRadius::same(RADIUS_CTRL);
    visuals.hyperlink_color = ACCENT_TEXT;
    visuals.selection.bg_fill = ACCENT_WEAK;
    visuals.selection.stroke = Stroke::new(1.0, ACCENT_TEXT);
    visuals.warn_fg_color = WARN;
    visuals.error_fg_color = HAZARD;

    let widgets = &mut visuals.widgets;
    widgets.noninteractive.bg_fill = PANEL;
    widgets.noninteractive.weak_bg_fill = PANEL;
    widgets.noninteractive.bg_stroke = Stroke::new(1.0, BORDER);
    widgets.noninteractive.fg_stroke = Stroke::new(1.0, MUTED);
    widgets.noninteractive.corner_radius = CornerRadius::same(RADIUS_CTRL);
    widgets.inactive.bg_fill = PANEL2;
    widgets.inactive.weak_bg_fill = PANEL2;
    widgets.inactive.bg_stroke = Stroke::new(1.0, BORDER2);
    widgets.inactive.fg_stroke = Stroke::new(1.0, INK);
    widgets.inactive.corner_radius = CornerRadius::same(RADIUS_CTRL);
    widgets.hovered.bg_fill = PANEL3;
    widgets.hovered.weak_bg_fill = PANEL3;
    widgets.hovered.bg_stroke = Stroke::new(1.0, Color32::from_rgb(0x52, 0x5b, 0x6a));
    widgets.hovered.fg_stroke = Stroke::new(1.0, INK);
    widgets.hovered.corner_radius = CornerRadius::same(RADIUS_CTRL);
    widgets.active.bg_fill = PANEL3;
    widgets.active.weak_bg_fill = PANEL3;
    widgets.active.bg_stroke = Stroke::new(1.0, ACCENT);
    widgets.active.fg_stroke = Stroke::new(1.0, INK);
    widgets.active.corner_radius = CornerRadius::same(RADIUS_CTRL);
    widgets.open.bg_fill = PANEL2;
    widgets.open.weak_bg_fill = PANEL2;
    widgets.open.bg_stroke = Stroke::new(1.0, BORDER2);
    widgets.open.fg_stroke = Stroke::new(1.0, INK);
    widgets.open.corner_radius = CornerRadius::same(RADIUS_CTRL);

    ctx.set_style(style);
}

/// Body frame for a stack panel (PANEL fill, BORDER stroke, radius 8).
pub fn panel_frame() -> egui::Frame {
    egui::Frame::new()
        .fill(PANEL)
        .stroke(Stroke::new(1.0, BORDER))
        .corner_radius(CornerRadius::same(RADIUS_PANEL))
}

/// Central stage background frame (no margin — the stage paints its own grid).
pub fn stage_frame() -> egui::Frame {
    egui::Frame::new().fill(STAGE)
}

/// Card frame used by floating layers (popover, toast).
pub fn overlay_frame() -> egui::Frame {
    egui::Frame::new()
        .fill(PANEL)
        .stroke(Stroke::new(1.0, BORDER2))
        .corner_radius(CornerRadius::same(9))
        .inner_margin(Margin::same(12))
}
