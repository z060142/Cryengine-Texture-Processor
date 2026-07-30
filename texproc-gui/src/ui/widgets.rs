//! Shared v2 components (SPEC.md §4/§5/§9/§10). Phase B panel code depends on
//! these signatures — change them only with a matching spec update.

use std::hash::{Hash, Hasher};
use std::time::{Duration, Instant};

use eframe::egui::{
    self, Align, Align2, Color32, CornerRadius, FontId, Id, Layout, Margin, Pos2, Rect, RichText,
    Sense, Shape, Stroke, StrokeKind, TextEdit, Ui, UiBuilder, Vec2,
};

use super::icons::{self, Icon};
use super::theme;

/// Chip styling for panel pcounts / pills: plain, warning-hot, or accent-new.
#[allow(dead_code)] // Phase B: panels start passing pcounts (SPEC §5).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PcountStyle {
    Normal,
    Hot,
    New,
}

impl PcountStyle {
    /// (text, fill, border)
    fn colors(self) -> (Color32, Color32, Color32) {
        match self {
            PcountStyle::Normal => (theme::MUTED2, theme::STAGE, theme::BORDER),
            PcountStyle::Hot => (theme::WARN, theme::WARN_WEAK, theme::WARN_BORDER),
            PcountStyle::New => (theme::ACCENT_TEXT, theme::ACCENT_WEAK, theme::ACCENT_BORDER),
        }
    }
}

/// Result of drawing one collapsible panel for a frame.
pub struct PanelResponse {
    #[allow(dead_code)] // API contract; Phase B callers read it.
    pub open: bool,
    pub toggled: bool,
    pub reset_clicked: bool,
}

/// Mockup-style collapsible panel: chevron + icon + title header (whole header
/// clickable), optional ●N modified badge with hover-revealed reset button,
/// optional right-aligned pcount chip, body only when open.
#[allow(clippy::too_many_arguments)]
pub fn collapsible_panel(
    ui: &mut Ui,
    id: &str,
    title: &str,
    icon: Icon,
    open: bool,
    modified_count: usize,
    pcount: Option<(&str, PcountStyle)>,
    reset_label: &str,
    body: impl FnOnce(&mut Ui),
) -> PanelResponse {
    let mut result = PanelResponse {
        open,
        toggled: false,
        reset_clicked: false,
    };
    let panel_id = Id::new(("v2_panel", id));
    theme::panel_frame().show(ui, |ui| {
        ui.spacing_mut().item_spacing.y = 0.0;
        let width = ui.available_width();
        let header_h = 38.0;
        let (rect, header) = ui.allocate_exact_size(Vec2::new(width, header_h), Sense::click());
        if header.clicked() {
            result.toggled = true;
        }
        let painter = ui.painter().clone();
        if open || header.hovered() {
            let radius = theme::RADIUS_PANEL.saturating_sub(1);
            let corner = CornerRadius {
                nw: radius,
                ne: radius,
                sw: if open { 0 } else { radius },
                se: if open { 0 } else { radius },
            };
            painter.rect_filled(rect, corner, theme::PANEL2);
        }
        // Chevron (▶ collapsed / ▼ open) as a small filled triangle.
        let center = Pos2::new(rect.left() + 16.0, rect.center().y);
        let ch = 3.6;
        let points = if open {
            vec![
                Pos2::new(center.x - ch, center.y - ch * 0.7),
                Pos2::new(center.x + ch, center.y - ch * 0.7),
                Pos2::new(center.x, center.y + ch),
            ]
        } else {
            vec![
                Pos2::new(center.x - ch * 0.7, center.y - ch),
                Pos2::new(center.x + ch, center.y),
                Pos2::new(center.x - ch * 0.7, center.y + ch),
            ]
        };
        painter.add(Shape::convex_polygon(points, theme::MUTED2, Stroke::NONE));
        // 15px icon.
        let icon_rect = Rect::from_center_size(
            Pos2::new(rect.left() + 33.0, rect.center().y),
            Vec2::splat(15.0),
        );
        icons::draw(&painter, icon_rect, icon, theme::MUTED, 1.5);
        // Title.
        let title_rect = painter.text(
            Pos2::new(rect.left() + 47.0, rect.center().y),
            Align2::LEFT_CENTER,
            title,
            FontId::proportional(theme::FONT_PANEL_TITLE),
            theme::INK,
        );
        // Right-aligned pcount chip.
        if let Some((text, style)) = pcount {
            let (fg, bg, border) = style.colors();
            let galley = painter.layout_no_wrap(text.to_owned(), FontId::proportional(10.0), fg);
            let chip_size = galley.size() + Vec2::new(14.0, 5.0);
            let chip_rect = Rect::from_min_size(
                Pos2::new(
                    rect.right() - 10.0 - chip_size.x,
                    rect.center().y - chip_size.y / 2.0,
                ),
                chip_size,
            );
            painter.rect(
                chip_rect,
                CornerRadius::same(9),
                bg,
                Stroke::new(1.0, border),
                StrokeKind::Inside,
            );
            painter.galley(chip_rect.min + Vec2::new(7.0, 2.5), galley, fg);
        }
        // ●N modified badge (hover reveals the reset button).
        if modified_count > 0 {
            let text = format!("● {modified_count}");
            let galley = painter.layout_no_wrap(text, FontId::proportional(10.0), theme::WARN);
            let badge_size = galley.size() + Vec2::new(14.0, 4.0);
            let badge_rect = Rect::from_min_size(
                Pos2::new(
                    title_rect.right() + 8.0,
                    rect.center().y - badge_size.y / 2.0,
                ),
                badge_size,
            );
            painter.rect(
                badge_rect,
                CornerRadius::same(9),
                theme::WARN_WEAK,
                Stroke::new(1.0, theme::WARN_BORDER),
                StrokeKind::Inside,
            );
            painter.galley(badge_rect.min + Vec2::new(7.0, 2.0), galley, theme::WARN);
            if modified_badge_reset(ui, panel_id, badge_rect, reset_label) {
                result.reset_clicked = true;
            }
        }
        if open {
            painter.hline(
                rect.left()..=rect.right(),
                rect.bottom(),
                Stroke::new(1.0, theme::BORDER),
            );
            egui::Frame::new()
                .inner_margin(Margin::symmetric(12, 11))
                .show(ui, |ui| {
                    ui.spacing_mut().item_spacing.y = 6.0;
                    ui.set_min_width(width - 24.0);
                    body(ui);
                });
        }
    });
    ui.add_space(9.0);
    result
}

/// Hover machinery for the ●N badge: while the badge (or the revealed button)
/// is hovered, float a "Reset to defaults" button right under it. Returns true
/// when that button is clicked.
fn modified_badge_reset(ui: &mut Ui, panel_id: Id, badge_rect: Rect, reset_label: &str) -> bool {
    let hover = ui.interact(badge_rect, panel_id.with("modbadge"), Sense::hover());
    let open_id = panel_id.with("reset_open");
    let mut open = ui
        .data(|data| data.get_temp::<bool>(open_id))
        .unwrap_or(false);
    if hover.hovered() {
        open = true;
    }
    let mut clicked = false;
    if open {
        let area = egui::Area::new(panel_id.with("reset_area"))
            .order(egui::Order::Foreground)
            .fixed_pos(Pos2::new(badge_rect.right(), badge_rect.bottom() + 4.0))
            .pivot(Align2::RIGHT_TOP)
            .show(ui.ctx(), |ui| {
                egui::Frame::new()
                    .fill(theme::PANEL3)
                    .stroke(Stroke::new(1.0, theme::BORDER2))
                    .corner_radius(CornerRadius::same(6))
                    .inner_margin(Margin::symmetric(8, 5))
                    .show(ui, |ui| {
                        ui.add(
                            egui::Button::new(
                                RichText::new(reset_label).size(10.0).color(theme::INK),
                            )
                            .frame(false),
                        )
                        .clicked()
                    })
                    .inner
            });
        clicked = area.inner;
        let pointer_over = ui.ctx().pointer_hover_pos().is_some_and(|pos| {
            badge_rect.expand(6.0).contains(pos) || area.response.rect.expand(6.0).contains(pos)
        });
        if clicked || !pointer_over {
            open = false;
        }
    }
    ui.data_mut(|data| data.insert_temp(open_id, open));
    clicked
}

/// Workspace preset row buttons. Returns the clicked preset id
/// ("minimal" / "review" / "export" / "custom"). The WORKSPACE label is drawn
/// by the caller (layout owns the strip).
pub fn preset_bar(
    ui: &mut Ui,
    active: &str,
    custom_dirty: bool,
    labels: [&str; 4],
) -> Option<&'static str> {
    const IDS: [&str; 4] = ["minimal", "review", "export", "custom"];
    let mut clicked = None;
    ui.horizontal(|ui| {
        ui.spacing_mut().item_spacing.x = 6.0;
        for (index, id) in IDS.iter().enumerate() {
            let on = active == *id;
            let is_custom = *id == "custom";
            let (fg, bg, border) = if on && is_custom && custom_dirty {
                (theme::WARN, theme::WARN_WEAK, theme::WARN_BORDER)
            } else if on {
                (theme::ACCENT_TEXT, theme::ACCENT_WEAK, theme::ACCENT_BORDER)
            } else {
                (theme::MUTED, theme::PANEL2, theme::BORDER)
            };
            let mut text = labels[index].to_owned();
            if is_custom {
                // Trailing room for the painted state dot.
                text.push_str("   ");
            }
            let button = ui.add(
                egui::Button::new(RichText::new(text).size(11.5).color(fg))
                    .fill(bg)
                    .stroke(Stroke::new(1.0, border)),
            );
            if is_custom {
                let dot_color = if custom_dirty {
                    theme::WARN
                } else {
                    theme::MUTED2
                };
                ui.painter().circle_filled(
                    Pos2::new(button.rect.right() - 10.0, button.rect.center().y),
                    3.0,
                    dot_color,
                );
            }
            if button.clicked() {
                clicked = Some(IDS[index]);
            }
        }
    });
    clicked
}

/// 60×60 rail button per SPEC §4: 24px icon + 10px label, optional green
/// memdot (top-right) and pcount badge; disabled = muted, no hover reaction.
pub fn rail_button(
    ui: &mut Ui,
    icon: Icon,
    label: &str,
    active: bool,
    enabled: bool,
    memdot: bool,
    pcount: Option<usize>,
) -> egui::Response {
    let sense = if enabled {
        Sense::click()
    } else {
        Sense::hover()
    };
    let (rect, response) = ui.allocate_exact_size(Vec2::splat(theme::RAIL_BTN), sense);
    let painter = ui.painter().clone();
    let hovered = enabled && response.hovered();
    if active {
        painter.rect(
            rect,
            CornerRadius::same(theme::RADIUS_RAIL),
            theme::ACCENT_WEAK,
            Stroke::new(1.0, theme::ACCENT_BORDER),
            StrokeKind::Inside,
        );
    } else if hovered {
        painter.rect_filled(rect, CornerRadius::same(theme::RADIUS_RAIL), theme::PANEL2);
    }
    let color = if !enabled {
        theme::MUTED2.linear_multiply(0.4)
    } else if active {
        theme::ACCENT_TEXT
    } else if hovered {
        theme::INK
    } else {
        theme::MUTED
    };
    let icon_rect = Rect::from_center_size(
        Pos2::new(rect.center().x, rect.top() + 23.0),
        Vec2::splat(22.0),
    );
    icons::draw(&painter, icon_rect, icon, color, 1.7);
    painter.text(
        Pos2::new(rect.center().x, rect.bottom() - 12.0),
        Align2::CENTER_CENTER,
        label,
        FontId::proportional(10.0),
        color,
    );
    let pcount = pcount.filter(|count| *count > 0);
    if let Some(count) = pcount {
        let galley = painter.layout_no_wrap(
            count.to_string(),
            FontId::proportional(9.0),
            theme::ACCENT_TEXT,
        );
        let size = galley.size() + Vec2::new(8.0, 2.0);
        let chip = Rect::from_min_size(
            Pos2::new(rect.right() - size.x - 4.0, rect.top() + 4.0),
            size,
        );
        painter.rect(
            chip,
            CornerRadius::same(7),
            theme::ACCENT_WEAK,
            Stroke::new(1.0, theme::ACCENT_BORDER),
            StrokeKind::Inside,
        );
        painter.galley(chip.min + Vec2::new(4.0, 1.0), galley, theme::ACCENT_TEXT);
    }
    if memdot {
        // Sits at top-right, nudged left when the pcount badge occupies it.
        let x = if pcount.is_some() {
            rect.left() + 9.0
        } else {
            rect.right() - 9.0
        };
        painter.circle(
            Pos2::new(x, rect.top() + 9.0),
            3.0,
            theme::OK,
            Stroke::new(2.0, theme::RAIL_BG),
        );
    }
    response
}

/// Translucent HUD chip for stage overlays (group name, dimensions, …).
#[allow(dead_code)] // Phase B: stage HUD (SPEC §6.2).
pub fn hud_chip(ui: &mut Ui, text: impl Into<RichText>) {
    egui::Frame::new()
        .fill(theme::HUD_BG)
        .stroke(Stroke::new(1.0, theme::BORDER))
        .corner_radius(CornerRadius::same(theme::RADIUS_CTRL))
        .inner_margin(Margin::symmetric(9, 3))
        .show(ui, |ui| {
            ui.label(text.into().size(theme::FONT_SMALL).color(theme::MUTED));
        });
}

/// Small rounded pill (map badges, status chips).
#[allow(dead_code)] // Phase B: caption pills (SPEC §6.2).
pub fn pill(ui: &mut Ui, text: impl Into<String>, style: PcountStyle) {
    let (fg, bg, border) = style.colors();
    let galley =
        ui.painter()
            .layout_no_wrap(text.into(), FontId::proportional(theme::FONT_SMALL), fg);
    let size = galley.size() + Vec2::new(18.0, 6.0);
    let (rect, _) = ui.allocate_exact_size(size, Sense::hover());
    ui.painter().rect(
        rect,
        CornerRadius::same(theme::RADIUS_CHIP.min((size.y / 2.0) as u8)),
        bg,
        Stroke::new(1.0, border),
        StrokeKind::Inside,
    );
    ui.painter()
        .galley(rect.min + Vec2::new(9.0, 3.0), galley, fg);
}

/// 10px uppercase MUTED2 section label.
pub fn section_label(ui: &mut Ui, text: &str) {
    ui.label(
        RichText::new(text.to_uppercase())
            .size(theme::FONT_SECTION)
            .strong()
            .color(theme::MUTED2),
    );
}

/// A single-line path field with a trailing `Browse…` button (restyled port of
/// the v1 helper). Returns `(text_changed, browse_clicked)`.
#[allow(dead_code)] // Phase B: panel path fields (SPEC §7/§8).
pub fn path_row(
    ui: &mut Ui,
    salt: &str,
    value: &mut String,
    hint: &str,
    browse_label: &str,
) -> (bool, bool) {
    let mut changed = false;
    let mut browse = false;
    ui.push_id(salt, |ui| {
        ui.horizontal(|ui| {
            changed = ui
                .add(
                    TextEdit::singleline(value)
                        .desired_width((ui.available_width() - 74.0).max(120.0))
                        .hint_text(hint),
                )
                .changed();
            browse = ui.button(browse_label).clicked();
        });
    });
    (changed, browse)
}

/// Group/model list row (mockup `.grow`): 26px gradient swatch, strong name,
/// sub-line, optional trailing content, whole row clickable.
#[allow(dead_code)] // Phase B: group/model lists (SPEC §7/§8).
#[allow(clippy::too_many_arguments)]
pub fn grow_row(
    ui: &mut Ui,
    salt: impl Hash,
    selected: bool,
    warn: bool,
    swatch_key: &str,
    name: &str,
    sub: &str,
    sub_color: Color32,
    trailing: impl FnOnce(&mut Ui),
) -> egui::Response {
    let height = 40.0;
    let (rect, response) =
        ui.allocate_exact_size(Vec2::new(ui.available_width(), height), Sense::click());
    let _ = &salt; // stable ids come from allocation order; salt kept for Phase B reuse
    let painter = ui.painter().clone();
    let (fill, stroke) = if selected {
        (theme::ACCENT_WEAK, Stroke::new(1.0, theme::ACCENT_BORDER))
    } else if warn {
        (Color32::TRANSPARENT, Stroke::new(1.0, theme::WARN_BORDER))
    } else if response.hovered() {
        (theme::PANEL2, Stroke::new(1.0, theme::BORDER))
    } else {
        (Color32::TRANSPARENT, Stroke::NONE)
    };
    painter.rect(
        rect,
        CornerRadius::same(theme::RADIUS_CTRL),
        fill,
        stroke,
        StrokeKind::Inside,
    );
    // Swatch.
    let swatch = Rect::from_min_size(
        Pos2::new(rect.left() + 8.0, rect.center().y - 13.0),
        Vec2::splat(26.0),
    );
    paint_swatch(&painter, swatch, swatch_key);
    // Name + sub-line, truncated against the trailing reserve.
    let text_left = swatch.right() + 9.0;
    let trailing_w = 104.0;
    let max_w = (rect.right() - trailing_w - text_left).max(40.0);
    let name_galley = truncated_galley(ui, name, FontId::proportional(11.5), theme::INK, max_w);
    painter.galley(
        Pos2::new(text_left, rect.top() + 6.0),
        name_galley,
        theme::INK,
    );
    let sub_galley = truncated_galley(ui, sub, FontId::proportional(10.0), sub_color, max_w);
    painter.galley(
        Pos2::new(text_left, rect.top() + 21.0),
        sub_galley,
        sub_color,
    );
    // Trailing content (type dots, badges, …).
    let trail_rect = Rect::from_min_max(
        Pos2::new(rect.right() - trailing_w, rect.top()),
        Pos2::new(rect.right() - 8.0, rect.bottom()),
    );
    let mut child = ui.new_child(
        UiBuilder::new()
            .max_rect(trail_rect)
            .layout(Layout::right_to_left(Align::Center)),
    );
    trailing(&mut child);
    response
}

/// One-line galley truncated with an ellipsis at `max_width`.
fn truncated_galley(
    ui: &Ui,
    text: &str,
    font: FontId,
    color: Color32,
    max_width: f32,
) -> std::sync::Arc<egui::Galley> {
    let mut job = egui::text::LayoutJob::simple_singleline(text.to_owned(), font, color);
    job.wrap = egui::text::TextWrapping::truncate_at_width(max_width);
    ui.painter().layout_job(job)
}

/// Stable two-color diagonal gradient for a group/model swatch key.
#[allow(dead_code)] // Phase B: list swatches (SPEC §7/§8).
pub fn swatch_colors(key: &str) -> (Color32, Color32) {
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    key.hash(&mut hasher);
    let hash = hasher.finish();
    let hue = (hash % 360) as f32;
    (
        hsl_color(hue, 0.45, 0.42),
        hsl_color((hue + 42.0) % 360.0, 0.5, 0.56),
    )
}

/// Paint the 26px gradient swatch (4-vertex mesh → smooth diagonal blend).
fn paint_swatch(painter: &egui::Painter, rect: Rect, key: &str) {
    let (a, b) = swatch_colors(key);
    let mut mesh = egui::Mesh::default();
    let base = mesh.vertices.len() as u32;
    for (pos, color) in [
        (rect.left_top(), a),
        (rect.right_top(), a),
        (rect.right_bottom(), b),
        (rect.left_bottom(), b),
    ] {
        mesh.colored_vertex(pos, color);
    }
    mesh.add_triangle(base, base + 1, base + 2);
    mesh.add_triangle(base, base + 2, base + 3);
    painter.add(Shape::mesh(mesh));
    painter.rect_stroke(
        rect,
        3.0,
        Stroke::new(1.0, Color32::from_black_alpha(70)),
        StrokeKind::Inside,
    );
}

fn hsl_color(h: f32, s: f32, l: f32) -> Color32 {
    let c = (1.0 - (2.0 * l - 1.0).abs()) * s;
    let hp = h / 60.0;
    let x = c * (1.0 - (hp % 2.0 - 1.0).abs());
    let (r, g, b) = match hp as u32 {
        0 => (c, x, 0.0),
        1 => (x, c, 0.0),
        2 => (0.0, c, x),
        3 => (0.0, x, c),
        4 => (x, 0.0, c),
        _ => (c, 0.0, x),
    };
    let m = l - c / 2.0;
    Color32::from_rgb(
        ((r + m) * 255.0) as u8,
        ((g + m) * 255.0) as u8,
        ((b + m) * 255.0) as u8,
    )
}

/// Solid ACCENT primary action button.
#[allow(dead_code)] // Phase B: panel primary actions (SPEC §7/§8).
pub fn primary_button(ui: &mut Ui, text: impl Into<String>) -> egui::Response {
    ui.add(
        egui::Button::new(
            RichText::new(text.into())
                .size(12.5)
                .strong()
                .color(Color32::WHITE),
        )
        .fill(theme::ACCENT)
        .stroke(Stroke::new(1.0, theme::ACCENT)),
    )
}

/// Full-width primary block button (Export CE Model style).
#[allow(dead_code)] // Phase B: Export CE Model block button (SPEC §8).
pub fn block_button(ui: &mut Ui, text: impl Into<String>) -> egui::Response {
    ui.add(
        egui::Button::new(
            RichText::new(text.into())
                .size(12.5)
                .strong()
                .color(Color32::WHITE),
        )
        .fill(theme::ACCENT)
        .stroke(Stroke::new(1.0, theme::ACCENT))
        .min_size(Vec2::new(ui.available_width(), 34.0)),
    )
}

// ---- toasts -----------------------------------------------------------------

/// Transient bottom-right notification (3s auto-dismiss).
pub struct Toast {
    pub title: String,
    pub subtitle: String,
    pub error: bool,
    pub created: Instant,
}

impl Toast {
    pub fn new(title: impl Into<String>, subtitle: impl Into<String>, error: bool) -> Self {
        Self {
            title: title.into(),
            subtitle: subtitle.into(),
            error,
            created: Instant::now(),
        }
    }
}

/// Draw and expire toasts: bottom-right, 78px above the window bottom (14px
/// above the timeline), OK/HAZARD left border.
pub fn toast_overlay(ctx: &egui::Context, toasts: &mut Vec<Toast>) {
    toasts.retain(|toast| toast.created.elapsed() < Duration::from_secs(3));
    if toasts.is_empty() {
        return;
    }
    // Keep repainting so expiry happens without user input.
    ctx.request_repaint_after(Duration::from_millis(120));
    egui::Area::new(Id::new("v2_toast_overlay"))
        .anchor(
            Align2::RIGHT_BOTTOM,
            Vec2::new(-18.0, -(theme::TIMELINE_H + 14.0)),
        )
        .order(egui::Order::Foreground)
        .interactable(false)
        .show(ctx, |ui| {
            for toast in toasts.iter() {
                let accent = if toast.error {
                    theme::HAZARD
                } else {
                    theme::OK
                };
                let weak = if toast.error {
                    theme::WARN_WEAK
                } else {
                    theme::OK_WEAK
                };
                let response = theme::overlay_frame().show(ui, |ui| {
                    ui.set_min_width(260.0);
                    ui.horizontal(|ui| {
                        let (icon_rect, _) =
                            ui.allocate_exact_size(Vec2::splat(24.0), Sense::hover());
                        ui.painter().circle_filled(icon_rect.center(), 12.0, weak);
                        ui.painter().text(
                            icon_rect.center(),
                            Align2::CENTER_CENTER,
                            if toast.error { "✗" } else { "✓" },
                            FontId::proportional(12.0),
                            accent,
                        );
                        ui.vertical(|ui| {
                            ui.label(RichText::new(&toast.title).size(12.5).strong());
                            ui.label(
                                RichText::new(&toast.subtitle)
                                    .size(11.0)
                                    .color(theme::MUTED),
                            );
                        });
                    });
                });
                let rect = response.response.rect;
                ui.painter().rect_filled(
                    Rect::from_min_max(rect.min, Pos2::new(rect.min.x + 3.0, rect.max.y)),
                    CornerRadius {
                        nw: 9,
                        sw: 9,
                        ne: 0,
                        se: 0,
                    },
                    accent,
                );
                ui.add_space(8.0);
            }
        });
}

// ---- timeline task chips ----------------------------------------------------

#[allow(dead_code)] // Phase B/C: capsules gain Done/Failed transitions (SPEC §9).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TaskState {
    Running,
    Done,
    Failed,
}

/// One session task capsule in the bottom timeline.
pub struct TaskCard {
    pub id: u64,
    pub title: String,
    pub subtitle: String,
    pub state: TaskState,
    pub progress: Option<f32>,
}

pub struct TaskChipResponse {
    pub clicked: bool,
    pub cancel_clicked: bool,
}

/// Draw one task capsule; clicking a running chip re-opens its modal, the ✕
/// (when `cancellable`) requests cancellation.
pub fn task_chip(ui: &mut Ui, card: &TaskCard, cancellable: bool) -> TaskChipResponse {
    let mut out = TaskChipResponse {
        clicked: false,
        cancel_clicked: false,
    };
    let border = match card.state {
        TaskState::Running => theme::ACCENT_BORDER,
        TaskState::Done => theme::OK_BORDER,
        TaskState::Failed => theme::WARN_BORDER,
    };
    let inner = egui::Frame::new()
        .fill(theme::PANEL)
        .stroke(Stroke::new(1.0, border))
        .corner_radius(CornerRadius::same(theme::RADIUS_PANEL))
        .inner_margin(Margin::symmetric(11, 6))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                let (icon_rect, _) = ui.allocate_exact_size(Vec2::splat(20.0), Sense::hover());
                match card.state {
                    TaskState::Running => {
                        ui.painter().rect_filled(icon_rect, 5.0, theme::ACCENT_WEAK);
                        ui.put(icon_rect, egui::Spinner::new().size(12.0));
                    }
                    TaskState::Done => {
                        ui.painter().rect_filled(icon_rect, 5.0, theme::OK_WEAK);
                        ui.painter().text(
                            icon_rect.center(),
                            Align2::CENTER_CENTER,
                            "✓",
                            FontId::proportional(11.0),
                            theme::OK,
                        );
                    }
                    TaskState::Failed => {
                        ui.painter().rect_filled(icon_rect, 5.0, theme::WARN_WEAK);
                        ui.painter().text(
                            icon_rect.center(),
                            Align2::CENTER_CENTER,
                            "✗",
                            FontId::proportional(11.0),
                            theme::HAZARD,
                        );
                    }
                }
                ui.vertical(|ui| {
                    ui.spacing_mut().item_spacing.y = 1.0;
                    ui.label(RichText::new(&card.title).size(11.0).strong());
                    let sub_color = match card.state {
                        TaskState::Running => theme::ACCENT_TEXT,
                        TaskState::Done => theme::OK,
                        TaskState::Failed => theme::HAZARD,
                    };
                    ui.label(RichText::new(&card.subtitle).size(9.5).color(sub_color));
                });
                if card.state == TaskState::Running {
                    if let Some(progress) = card.progress {
                        ui.add(
                            egui::ProgressBar::new(progress)
                                .desired_width(60.0)
                                .desired_height(4.0)
                                .fill(theme::ACCENT),
                        );
                    }
                    if cancellable
                        && ui
                            .add(
                                egui::Button::new(
                                    RichText::new("✕").size(11.0).color(theme::MUTED),
                                )
                                .frame(false),
                            )
                            .clicked()
                    {
                        out.cancel_clicked = true;
                    }
                }
            });
        });
    let response = ui.interact(
        inner.response.rect,
        Id::new(("v2_task_chip", card.id)),
        Sense::click(),
    );
    if response.clicked() && !out.cancel_clicked {
        out.clicked = true;
    }
    out
}
