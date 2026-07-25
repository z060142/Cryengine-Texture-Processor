#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{collections::BTreeMap, path::PathBuf};

use eframe::egui::{
    self, Color32, ComboBox, Grid, RichText, ScrollArea, Stroke, TextEdit, ViewportBuilder,
};
use texproc_gui::{ReviewDocument, ASSIGNABLE_SOURCE_TYPES};

const APP_TITLE: &str = "CryEngine Texture Group Review";

fn main() -> eframe::Result {
    let initial_path = std::env::args_os().nth(1).map(PathBuf::from);
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_inner_size([1400.0, 850.0])
            .with_min_inner_size([900.0, 600.0]),
        ..Default::default()
    };
    eframe::run_native(
        APP_TITLE,
        options,
        Box::new(move |_context| Ok(Box::new(GroupReviewApp::new(initial_path)))),
    )
}

struct GroupReviewApp {
    document: Option<ReviewDocument>,
    path_text: String,
    status: String,
    assignment_choices: BTreeMap<String, String>,
}

impl GroupReviewApp {
    fn new(initial_path: Option<PathBuf>) -> Self {
        let path_text = initial_path
            .as_ref()
            .map(|path| path.to_string_lossy().into_owned())
            .unwrap_or_default();
        let mut app = Self {
            document: None,
            path_text,
            status: "Enter or drop a texproc scan groups JSON file.".to_owned(),
            assignment_choices: BTreeMap::new(),
        };
        if initial_path.is_some() {
            app.load();
        }
        app
    }

    fn load(&mut self) {
        let path = PathBuf::from(self.path_text.trim());
        match ReviewDocument::load(&path) {
            Ok(document) => {
                let groups = document.scan().groups.len();
                let unknown = document.unresolved_unknown_count();
                self.document = Some(document);
                self.assignment_choices.clear();
                self.status = format!("Loaded {groups} group(s), {unknown} unknown file(s).");
            }
            Err(error) => {
                self.document = None;
                self.assignment_choices.clear();
                self.status = error;
            }
        }
    }

    fn save(&mut self) {
        let Some(document) = &mut self.document else {
            self.status = "Nothing is loaded.".to_owned();
            return;
        };
        let requested_path = PathBuf::from(self.path_text.trim());
        let result = if requested_path == document.path() {
            document.save()
        } else {
            document.save_as(requested_path)
        };
        self.status = match result {
            Ok(()) => format!("Saved reviewed groups to {}.", document.path().display()),
            Err(error) => error,
        };
    }

    fn receive_dropped_file(&mut self, context: &egui::Context) {
        let dropped = context.input(|input| input.raw.dropped_files.clone());
        if let Some(path) = dropped.into_iter().find_map(|file| file.path) {
            self.path_text = path.to_string_lossy().into_owned();
            self.load();
        }
    }

    fn top_bar(&mut self, context: &egui::Context) {
        egui::TopBottomPanel::top("file_controls").show(context, |ui| {
            ui.add_space(6.0);
            ui.horizontal(|ui| {
                ui.label("Groups JSON");
                ui.add(
                    TextEdit::singleline(&mut self.path_text)
                        .desired_width(f32::INFINITY)
                        .hint_text(r"C:\path\to\groups.json"),
                );
            });
            ui.horizontal(|ui| {
                if ui.button("Load").clicked() {
                    self.load();
                }
                let save_label = if self.document.as_ref().is_some_and(ReviewDocument::is_dirty) {
                    "Save reviewed JSON *"
                } else {
                    "Save reviewed JSON"
                };
                if ui
                    .add_enabled(self.document.is_some(), egui::Button::new(save_label))
                    .clicked()
                {
                    self.save();
                }
                ui.separator();
                ui.label(&self.status);
                ui.separator();
                ui.weak("Tip: drag a groups JSON file into this window to load it.");
            });
            ui.add_space(6.0);
        });
    }

    fn document_view(&mut self, context: &egui::Context) {
        let Some(document) = &self.document else {
            egui::CentralPanel::default().show(context, |ui| {
                ui.centered_and_justified(|ui| {
                    ui.heading("Load a `texproc scan --out groups.json` file to begin.");
                });
            });
            return;
        };

        let group_count = document.scan().groups.len();
        let unknown_count = document.unresolved_unknown_count();
        let conflict_count = document.conflict_warning_count();
        egui::CentralPanel::default().show(context, |ui| {
            ui.horizontal(|ui| {
                ui.heading(format!("{group_count} groups"));
                ui.separator();
                let unknown_color = if unknown_count == 0 {
                    Color32::from_rgb(90, 180, 100)
                } else {
                    Color32::from_rgb(235, 180, 70)
                };
                ui.label(
                    RichText::new(format!("{unknown_count} unknown"))
                        .strong()
                        .color(unknown_color),
                );
                if conflict_count > 0 {
                    ui.separator();
                    ui.label(
                        RichText::new(format!("{conflict_count} DEF-19 conflict warning(s)"))
                            .strong()
                            .color(Color32::from_rgb(240, 110, 90)),
                    );
                }
            });
            ui.label(
                "Rows are groups; columns are process source-type slots. Unknown files appear in review rows below their group.",
            );
            ui.separator();

            ScrollArea::both()
                .auto_shrink([false, false])
                .show(ui, |ui| self.group_table(ui));
        });
    }

    fn group_table(&mut self, ui: &mut egui::Ui) {
        let Some(document) = &self.document else {
            return;
        };
        let groups = document.scan().groups.clone();
        let mut requested_assignment = None;

        Grid::new("group_slot_grid")
            .striped(true)
            .min_col_width(88.0)
            .show(ui, |ui| {
                ui.strong("Group");
                for source_type in ASSIGNABLE_SOURCE_TYPES {
                    ui.strong(source_type);
                }
                ui.strong("Unknown");
                ui.end_row();

                for (group_index, group) in groups.iter().enumerate() {
                    ui.strong(&group.base_name);
                    for source_type in ASSIGNABLE_SOURCE_TYPES {
                        match group.slots.get(source_type) {
                            Some(entry) => {
                                ui.label(&entry.filename).on_hover_text(&entry.path);
                            }
                            None => {
                                ui.weak("—");
                            }
                        }
                    }
                    let unknown_text = if group.unknown.is_empty() {
                        RichText::new("0").color(Color32::from_rgb(90, 180, 100))
                    } else {
                        RichText::new(group.unknown.len().to_string())
                            .strong()
                            .color(Color32::from_rgb(235, 180, 70))
                    };
                    ui.label(unknown_text);
                    ui.end_row();

                    if !group.unknown.is_empty()
                        || group
                            .diagnostics
                            .iter()
                            .any(|diagnostic| diagnostic.code == "DEF-19")
                    {
                        ui.end_row();
                        ui.vertical(|ui| {
                            ui.label(RichText::new("Review").strong());
                            for diagnostic in group
                                .diagnostics
                                .iter()
                                .filter(|diagnostic| diagnostic.code == "DEF-19")
                            {
                                ui.label(
                                    RichText::new(format!(
                                        "{}: {}",
                                        diagnostic.code, diagnostic.message
                                    ))
                                    .color(Color32::from_rgb(240, 110, 90)),
                                );
                            }
                            for (unknown_index, entry) in group.unknown.iter().enumerate() {
                                let key = format!("{group_index}\u{0}{}", entry.path);
                                let selected = self
                                    .assignment_choices
                                    .entry(key)
                                    .or_insert_with(|| ASSIGNABLE_SOURCE_TYPES[0].to_owned());
                                let occupant =
                                    group.slots.get(selected.as_str()).map(|item| &item.filename);
                                let conflict = occupant.is_some();
                                egui::Frame::new()
                                    .stroke(Stroke::new(
                                        if conflict { 2.0 } else { 1.0 },
                                        if conflict {
                                            Color32::from_rgb(240, 110, 90)
                                        } else {
                                            ui.visuals().widgets.noninteractive.bg_stroke.color
                                        },
                                    ))
                                    .inner_margin(6.0)
                                    .show(ui, |ui| {
                                        ui.horizontal(|ui| {
                                            ui.label(&entry.filename).on_hover_text(&entry.path);
                                            ComboBox::from_id_salt((
                                                "assign",
                                                group_index,
                                                unknown_index,
                                            ))
                                            .selected_text(selected.as_str())
                                            .show_ui(
                                                ui,
                                                |ui| {
                                                    for source_type in ASSIGNABLE_SOURCE_TYPES {
                                                        ui.selectable_value(
                                                            selected,
                                                            source_type.to_owned(),
                                                            source_type,
                                                        );
                                                    }
                                                },
                                            );
                                            if ui
                                                .add_enabled(
                                                    !conflict,
                                                    egui::Button::new("Assign"),
                                                )
                                                .clicked()
                                            {
                                                requested_assignment = Some((
                                                    group_index,
                                                    unknown_index,
                                                    selected.clone(),
                                                ));
                                            }
                                        });
                                        if let Some(filename) = occupant {
                                            ui.label(
                                                RichText::new(format!(
                                                    "DEF-19 conflict: target already contains {filename}"
                                                ))
                                                .color(Color32::from_rgb(240, 110, 90)),
                                            );
                                        }
                                    });
                            }
                        });
                        for _ in 0..ASSIGNABLE_SOURCE_TYPES.len() + 1 {
                            ui.label("");
                        }
                        ui.end_row();
                    }
                }
            });

        if let Some((group_index, unknown_index, source_type)) = requested_assignment {
            if let Some(document) = &mut self.document {
                self.status =
                    match document.assign_unknown(group_index, unknown_index, &source_type) {
                        Ok(()) => format!("Assigned unknown file to `{source_type}`."),
                        Err(error) => error,
                    };
            }
        }
    }
}

impl eframe::App for GroupReviewApp {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive_dropped_file(context);
        self.top_bar(context);
        self.document_view(context);
    }
}
