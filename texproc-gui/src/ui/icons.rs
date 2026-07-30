//! Hand-painted line icons translated from the mockup's 24×24 SVGs
//! (docs/ux-demos/r2-hybrid2-stage-evo.html). Approximated with segments,
//! polylines, circles and arcs — no icon-font dependency (SPEC.md §11).

use eframe::egui::{self, Color32, Pos2, Rect, Shape, Stroke, StrokeKind, Vec2};

use super::theme;

// Some variants land with the Phase B panel bodies (SPEC §11 icon set).
#[allow(dead_code)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Icon {
    Textures,
    Models,
    Proxy,
    Pbr,
    Help,
    Import,
    ListLines,
    Gear,
    Globe,
    Rc,
    Cube,
    Transform,
    Export,
    Check,
}

/// Paint `icon` centered in `rect` (icon art lives in a 24×24 unit box that is
/// scaled to the rect's short side).
pub fn draw(painter: &egui::Painter, rect: Rect, icon: Icon, color: Color32, stroke_width: f32) {
    let scale = rect.width().min(rect.height()) / 24.0;
    let origin = rect.center() - Vec2::splat(12.0 * scale);
    let p = move |x: f32, y: f32| Pos2::new(origin.x + x * scale, origin.y + y * scale);
    let stroke = Stroke::new(stroke_width, color);
    let line = |a: Pos2, b: Pos2| painter.line_segment([a, b], stroke);
    let poly = |points: Vec<Pos2>| {
        painter.add(Shape::line(points, stroke));
    };
    let closed = |points: Vec<Pos2>| {
        painter.add(Shape::closed_line(points, stroke));
    };
    match icon {
        Icon::Textures => {
            // rect 3,3 18×18 r2 + cross at x/y = 9.
            let frame = Rect::from_min_max(p(3.0, 3.0), p(21.0, 21.0));
            painter.rect_stroke(frame, 2.0 * scale, stroke, StrokeKind::Middle);
            line(p(3.0, 9.0), p(21.0, 9.0));
            line(p(9.0, 3.0), p(9.0, 21.0));
        }
        Icon::Models | Icon::Cube => {
            closed(hex(p));
            line(p(3.0, 7.0), p(12.0, 12.0));
            line(p(21.0, 7.0), p(12.0, 12.0));
            line(p(12.0, 12.0), p(12.0, 22.0));
        }
        Icon::Proxy => {
            // Dashed cube outline + core sphere.
            let mut points = hex(p);
            points.push(points[0]);
            painter.extend(Shape::dashed_line(
                &points,
                stroke,
                3.2 * scale,
                2.4 * scale,
            ));
            painter.circle_stroke(p(12.0, 12.0), 3.0 * scale, stroke);
        }
        Icon::Pbr => {
            painter.circle_stroke(p(12.0, 12.0), 9.0 * scale, stroke);
            // Left semicircle meridian + half equator (diffuse→PBR converter).
            poly(arc(p(12.0, 12.0), 9.0 * scale, 0.5, 1.5));
            line(p(3.0, 12.0), p(12.0, 12.0));
        }
        Icon::Globe => {
            painter.circle_stroke(p(12.0, 12.0), 9.0 * scale, stroke);
            poly(ellipse(p(12.0, 12.0), 4.5 * scale, 9.0 * scale));
            line(p(3.0, 12.0), p(21.0, 12.0));
        }
        Icon::Help => {
            painter.circle_stroke(p(12.0, 12.0), 9.0 * scale, stroke);
            // Question hook + stem + dot.
            let mut hook = arc(p(12.0, 9.5), 2.5 * scale, 1.0, 2.2);
            hook.push(p(12.0, 13.2));
            poly(hook);
            painter.circle_filled(p(12.0, 16.8), 1.0 * scale * stroke_width.max(1.0), color);
        }
        Icon::Import => {
            line(p(12.0, 3.0), p(12.0, 15.0));
            line(p(8.0, 11.0), p(12.0, 15.0));
            line(p(16.0, 11.0), p(12.0, 15.0));
            poly(vec![
                p(4.0, 17.0),
                p(4.0, 21.0),
                p(20.0, 21.0),
                p(20.0, 17.0),
            ]);
        }
        Icon::Export => {
            line(p(12.0, 15.0), p(12.0, 3.0));
            line(p(8.0, 7.0), p(12.0, 3.0));
            line(p(16.0, 7.0), p(12.0, 3.0));
            poly(vec![
                p(4.0, 17.0),
                p(4.0, 21.0),
                p(20.0, 21.0),
                p(20.0, 17.0),
            ]);
        }
        Icon::ListLines => {
            for y in [6.0, 12.0, 18.0] {
                line(p(8.0, y), p(21.0, y));
                painter.circle_filled(p(3.8, y), 1.1 * scale, color);
            }
        }
        Icon::Gear => {
            painter.circle_stroke(p(12.0, 12.0), 2.2 * scale, stroke);
            painter.circle_stroke(p(12.0, 12.0), 5.4 * scale, stroke);
            for k in 0..8 {
                let angle = k as f32 * std::f32::consts::FRAC_PI_4;
                let dir = Vec2::new(angle.cos(), angle.sin());
                let center = p(12.0, 12.0);
                line(center + dir * 5.4 * scale, center + dir * 8.6 * scale);
            }
        }
        Icon::Rc => {
            let top = Rect::from_min_max(p(4.0, 4.0), p(20.0, 10.0));
            let bottom = Rect::from_min_max(p(4.0, 14.0), p(20.0, 20.0));
            painter.rect_stroke(top, 1.5 * scale, stroke, StrokeKind::Middle);
            painter.rect_stroke(bottom, 1.5 * scale, stroke, StrokeKind::Middle);
            painter.circle_filled(p(7.5, 7.0), 1.0 * scale, color);
            painter.circle_filled(p(7.5, 17.0), 1.0 * scale, color);
        }
        Icon::Transform => {
            line(p(12.0, 2.0), p(12.0, 22.0));
            line(p(2.0, 12.0), p(22.0, 12.0));
            poly(vec![p(5.0, 9.0), p(2.0, 12.0), p(5.0, 15.0)]);
            poly(vec![p(19.0, 9.0), p(22.0, 12.0), p(19.0, 15.0)]);
            poly(vec![p(9.0, 5.0), p(12.0, 2.0), p(15.0, 5.0)]);
        }
        Icon::Check => {
            let frame = Rect::from_min_max(p(3.0, 3.0), p(21.0, 21.0));
            painter.rect_stroke(frame, 2.0 * scale, stroke, StrokeKind::Middle);
            poly(vec![p(8.0, 12.0), p(11.0, 15.0), p(20.0, 6.0)]);
        }
    }
}

/// The cube silhouette shared by Models / Cube / Proxy.
fn hex(p: impl Fn(f32, f32) -> Pos2) -> Vec<Pos2> {
    vec![
        p(12.0, 2.0),
        p(3.0, 7.0),
        p(3.0, 17.0),
        p(12.0, 22.0),
        p(21.0, 17.0),
        p(21.0, 7.0),
    ]
}

/// Circular arc as a polyline; angles are in half-turns (1.0 = 180°), screen
/// coordinates (y down), 0 pointing right.
fn arc(center: Pos2, radius: f32, start_half_turns: f32, end_half_turns: f32) -> Vec<Pos2> {
    let steps = 16;
    (0..=steps)
        .map(|i| {
            let t =
                start_half_turns + (end_half_turns - start_half_turns) * i as f32 / steps as f32;
            let angle = t * std::f32::consts::PI;
            Pos2::new(
                center.x + radius * angle.cos(),
                center.y + radius * angle.sin(),
            )
        })
        .collect()
}

/// Closed ellipse polyline (used for the globe meridian).
fn ellipse(center: Pos2, rx: f32, ry: f32) -> Vec<Pos2> {
    let steps = 24;
    let mut points: Vec<Pos2> = (0..=steps)
        .map(|i| {
            let angle = std::f32::consts::TAU * i as f32 / steps as f32;
            Pos2::new(center.x + rx * angle.cos(), center.y + ry * angle.sin())
        })
        .collect();
    points.push(points[0]);
    points
}

/// Square icon button with a hover backplate. Returns the click response.
#[allow(dead_code)] // Phase B: stagebar gadgets (SPEC §6.1).
pub fn icon_button(ui: &mut egui::Ui, icon: Icon, size: f32, color: Color32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(Vec2::splat(size), egui::Sense::click());
    let color = if response.hovered() {
        theme::INK
    } else {
        color
    };
    if response.hovered() {
        ui.painter().rect_filled(rect, 5.0, theme::PANEL2);
    }
    draw(ui.painter(), rect.shrink(size * 0.2), icon, color, 1.6);
    response
}
