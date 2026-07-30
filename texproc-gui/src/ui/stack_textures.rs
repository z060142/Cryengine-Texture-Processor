//! Textures parameter stack (SPEC.md §7). Phase A draws the four collapsible
//! panel shells so preset/memory machinery is live; Phase B1 fills the bodies.

use eframe::egui;

use super::icons::Icon;
use super::widgets;
use super::UiMode;

/// (panel id, title, icon). Titles are technical terms (T-018: untranslated);
/// Phase B may move them to i18n if translated variants are ruled.
const PANELS: [(&str, &str, Icon); 4] = [
    ("tex.import", "Import", Icon::Import),
    ("tex.groups", "Group Review", Icon::ListLines),
    ("tex.convert", "Conversion Settings", Icon::Gear),
    ("tex.rc", "RC / DDS Export", Icon::Rc),
];

pub fn draw(app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    let t = app.t();
    let mode = UiMode::Textures;
    for (id, title, icon) in PANELS {
        let open = app.ui.is_open(mode, id);
        let response = widgets::collapsible_panel(
            ui,
            id,
            title,
            icon,
            open,
            0,
            None,
            t.reset_to_defaults,
            |ui| {
                ui.weak("Phase B");
            },
        );
        if response.toggled {
            app.ui.toggle_panel(mode, id);
        }
    }
}
