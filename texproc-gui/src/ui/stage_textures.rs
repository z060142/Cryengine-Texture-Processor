//! Textures stage (SPEC.md §6.2). Phase A stub — Phase B1 fills the preview,
//! HUD chips, caption pills and drop-zone empty state.

use eframe::egui;

pub fn draw(_app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    ui.centered_and_justified(|ui| {
        ui.weak("Phase B");
    });
}
