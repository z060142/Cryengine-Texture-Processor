//! Models stage (SPEC.md §6.3). Phase A stub — Phase B2 fills the material
//! slot workspace, details, diagnostics and axis caption.

use eframe::egui;

pub fn draw(_app: &mut crate::WorkflowApp, ui: &mut egui::Ui) {
    ui.centered_and_justified(|ui| {
        ui.weak("Phase B");
    });
}
