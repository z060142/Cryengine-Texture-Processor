#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;

use eframe::egui::{
    self, Color32, ComboBox, Grid, RichText, ScrollArea, TextEdit, ViewportBuilder,
};
use texproc::ScanGroup;
use texproc_gui::{ReviewDocument, ASSIGNABLE_SOURCE_TYPES};

const APP_TITLE: &str = "CryEngine Texture Group Review";

fn main() -> eframe::Result {
    let initial_path = std::env::args_os().nth(1).map(PathBuf::from);
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_inner_size([1180.0, 760.0])
            .with_min_inner_size([860.0, 560.0]),
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
    search_text: String,
    review_only: bool,
    selected_group: Option<usize>,
    selected_unknown: Option<usize>,
    assignment_type: String,
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
            search_text: String::new(),
            review_only: false,
            selected_group: None,
            selected_unknown: None,
            assignment_type: ASSIGNABLE_SOURCE_TYPES[0].to_owned(),
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
                self.selected_group = document
                    .scan()
                    .groups
                    .iter()
                    .position(|group| !group.unknown.is_empty())
                    .or((groups > 0).then_some(0));
                self.selected_unknown = self.selected_group.and_then(|index| {
                    (!document.scan().groups[index].unknown.is_empty()).then_some(0)
                });
                self.review_only = unknown > 0;
                self.search_text.clear();
                self.document = Some(document);
                self.status = format!("Loaded {groups} group(s), {unknown} unknown file(s).");
            }
            Err(error) => {
                self.document = None;
                self.selected_group = None;
                self.selected_unknown = None;
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
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                ui.heading("Texture Group Review");
                if let Some(document) = &self.document {
                    ui.separator();
                    let unknown = document.unresolved_unknown_count();
                    if unknown == 0 {
                        ui.label(
                            RichText::new("Review complete")
                                .strong()
                                .color(Color32::from_rgb(80, 170, 100)),
                        );
                    } else {
                        ui.label(
                            RichText::new(format!("{unknown} unknown remaining"))
                                .strong()
                                .color(Color32::from_rgb(220, 160, 55)),
                        );
                    }
                }
            });
            ui.add_space(3.0);
            ui.horizontal(|ui| {
                ui.label("Groups JSON");
                ui.add(
                    TextEdit::singleline(&mut self.path_text)
                        .desired_width(ui.available_width() - 205.0)
                        .hint_text(r"C:\path\to\groups.json"),
                );
                if ui.button("Load").clicked() {
                    self.load();
                }
                let save_label = if self.document.as_ref().is_some_and(ReviewDocument::is_dirty) {
                    "Save JSON *"
                } else {
                    "Save JSON"
                };
                if ui
                    .add_enabled(self.document.is_some(), egui::Button::new(save_label))
                    .clicked()
                {
                    self.save();
                }
            });
            ui.horizontal(|ui| {
                ui.label(RichText::new(&self.status).small());
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.weak("Drop a groups JSON anywhere in the window to open it.");
                });
            });
            ui.add_space(6.0);
        });
    }

    fn empty_view(&mut self, context: &egui::Context) {
        egui::CentralPanel::default().show(context, |ui| {
            ui.centered_and_justified(|ui| {
                ui.vertical_centered(|ui| {
                    ui.heading("No texture groups loaded");
                    ui.add_space(8.0);
                    ui.label("Open a JSON produced by `texproc scan --out groups.json`.");
                    ui.label("You can also drag the file into this window.");
                });
            });
        });
    }

    fn document_view(&mut self, context: &egui::Context) {
        if self.document.is_none() {
            self.empty_view(context);
            return;
        }

        self.group_browser(context);
        self.group_details(context);
    }

    fn group_browser(&mut self, context: &egui::Context) {
        let groups = self
            .document
            .as_ref()
            .map(|document| document.scan().groups.clone())
            .unwrap_or_default();
        let query = self.search_text.trim().to_lowercase();

        egui::SidePanel::left("group_browser")
            .resizable(true)
            .default_width(500.0)
            .min_width(360.0)
            .max_width(680.0)
            .show(context, |ui| {
                ui.add_space(8.0);
                ui.horizontal(|ui| {
                    ui.heading("Detected Texture Groups");
                    ui.weak(format!("({})", groups.len()));
                });
                ui.add_space(4.0);
                ui.horizontal(|ui| {
                    ui.add(
                        TextEdit::singleline(&mut self.search_text)
                            .desired_width(ui.available_width() - 155.0)
                            .hint_text("Search groups or filenames"),
                    );
                    ui.checkbox(&mut self.review_only, "Needs review");
                });
                ui.add_space(8.0);

                Grid::new("group_headers")
                    .num_columns(3)
                    .spacing([12.0, 4.0])
                    .show(ui, |ui| {
                        ui.add_sized(
                            [145.0, 18.0],
                            egui::Label::new(RichText::new("Base Name").strong()),
                        );
                        ui.add_sized(
                            [235.0, 18.0],
                            egui::Label::new(RichText::new("Detected Textures").strong()),
                        );
                        ui.add_sized(
                            [70.0, 18.0],
                            egui::Label::new(RichText::new("Unknown").strong()),
                        );
                        ui.end_row();
                    });
                ui.separator();

                let mut visible_count = 0;
                ScrollArea::vertical()
                    .auto_shrink([false, false])
                    .show(ui, |ui| {
                        Grid::new("group_rows")
                            .num_columns(3)
                            .striped(true)
                            .spacing([12.0, 6.0])
                            .show(ui, |ui| {
                                for (index, group) in groups.iter().enumerate() {
                                    if self.review_only && group.unknown.is_empty() {
                                        continue;
                                    }
                                    if !query.is_empty() && !group_matches(group, &query) {
                                        continue;
                                    }
                                    visible_count += 1;
                                    let selected = self.selected_group == Some(index);
                                    let response = ui.add_sized(
                                        [145.0, 24.0],
                                        egui::Button::selectable(selected, &group.base_name),
                                    );
                                    if response.clicked() {
                                        self.selected_group = Some(index);
                                        self.selected_unknown =
                                            (!group.unknown.is_empty()).then_some(0);
                                        self.assignment_type =
                                            ASSIGNABLE_SOURCE_TYPES[0].to_owned();
                                    }

                                    let detected = detected_type_summary(group);
                                    ui.add_sized(
                                        [235.0, 24.0],
                                        egui::Label::new(detected).truncate(),
                                    )
                                    .on_hover_text(detected_file_summary(group));

                                    let unknown = group.unknown.len();
                                    let text = if unknown == 0 {
                                        RichText::new("—").weak()
                                    } else {
                                        RichText::new(unknown.to_string())
                                            .strong()
                                            .color(Color32::from_rgb(220, 160, 55))
                                    };
                                    ui.add_sized([70.0, 24.0], egui::Label::new(text));
                                    ui.end_row();
                                }
                            });
                    });

                if visible_count == 0 {
                    ui.add_space(16.0);
                    ui.vertical_centered(|ui| {
                        ui.weak("No groups match the current filter.");
                    });
                }
            });
    }

    fn group_details(&mut self, context: &egui::Context) {
        let group = self
            .selected_group
            .and_then(|index| {
                self.document
                    .as_ref()
                    .and_then(|document| document.scan().groups.get(index))
            })
            .cloned();

        egui::CentralPanel::default().show(context, |ui| {
            ui.add_space(8.0);
            let Some(group) = group else {
                ui.centered_and_justified(|ui| {
                    ui.weak("Select a texture group to inspect it.");
                });
                return;
            };

            ScrollArea::vertical()
                .auto_shrink([false, false])
                .show(ui, |ui| {
                    self.group_details_contents(ui, &group);
                });
        });
    }

    fn group_details_contents(&mut self, ui: &mut egui::Ui, group: &ScanGroup) {
        ui.horizontal(|ui| {
            ui.heading(&group.base_name);
            ui.separator();
            ui.label(format!("{} detected", group.slots.len()));
            ui.separator();
            let unknown_text = if group.unknown.is_empty() {
                RichText::new("No unknown textures").color(Color32::from_rgb(80, 170, 100))
            } else {
                RichText::new(format!("{} unknown", group.unknown.len()))
                    .strong()
                    .color(Color32::from_rgb(220, 160, 55))
            };
            ui.label(unknown_text);
        });
        ui.add_space(8.0);

        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong("Group Details");
            ui.add_space(6.0);
            Grid::new("selected_group_details")
                .num_columns(2)
                .spacing([18.0, 6.0])
                .show(ui, |ui| {
                    ui.label("Base Name:");
                    ui.strong(&group.base_name);
                    ui.end_row();
                    ui.label("Texture Types:");
                    ui.label(detected_type_summary(group));
                    ui.end_row();
                });

            if !group.slots.is_empty() {
                ui.add_space(8.0);
                ui.separator();
                ui.add_space(4.0);
                Grid::new("detected_texture_files")
                    .num_columns(2)
                    .striped(true)
                    .spacing([16.0, 5.0])
                    .show(ui, |ui| {
                        for source_type in ASSIGNABLE_SOURCE_TYPES {
                            if let Some(entry) = group.slots.get(source_type) {
                                ui.add_sized(
                                    [95.0, 20.0],
                                    egui::Label::new(RichText::new(source_type).strong()),
                                );
                                ui.label(&entry.filename).on_hover_text(&entry.path);
                                ui.end_row();
                            }
                        }
                    });
            }

            for diagnostic in group
                .diagnostics
                .iter()
                .filter(|diagnostic| diagnostic.code == "DEF-19")
            {
                ui.add_space(6.0);
                ui.label(
                    RichText::new(format!("{}: {}", diagnostic.code, diagnostic.message))
                        .color(Color32::from_rgb(220, 85, 70)),
                );
            }
        });

        ui.add_space(12.0);
        ui.group(|ui| {
            ui.set_width(ui.available_width());
            ui.strong("Unknown Textures");
            ui.add_space(6.0);

            if group.unknown.is_empty() {
                ui.label(
                    RichText::new("All textures in this group have a source type.")
                        .color(Color32::from_rgb(80, 170, 100)),
                );
                return;
            }

            ui.label("Select one file, choose its source type, then apply the assignment.");
            ui.add_space(6.0);
            for (index, entry) in group.unknown.iter().enumerate() {
                let selected = self.selected_unknown == Some(index);
                if ui
                    .add_sized(
                        [ui.available_width(), 28.0],
                        egui::Button::selectable(selected, &entry.filename),
                    )
                    .on_hover_text(&entry.path)
                    .clicked()
                {
                    self.selected_unknown = Some(index);
                }
            }

            ui.add_space(10.0);
            ui.separator();
            ui.add_space(8.0);
            let occupant = group
                .slots
                .get(self.assignment_type.as_str())
                .map(|entry| entry.filename.as_str());
            let can_assign = self.selected_unknown.is_some() && occupant.is_none();
            let mut requested_assignment = false;

            ui.horizontal(|ui| {
                ui.label("Set Type:");
                ComboBox::from_id_salt("selected_unknown_type")
                    .selected_text(&self.assignment_type)
                    .width(145.0)
                    .show_ui(ui, |ui| {
                        for source_type in ASSIGNABLE_SOURCE_TYPES {
                            ui.selectable_value(
                                &mut self.assignment_type,
                                source_type.to_owned(),
                                source_type,
                            );
                        }
                    });
                if ui
                    .add_enabled(can_assign, egui::Button::new("Set Type"))
                    .clicked()
                {
                    requested_assignment = true;
                }
            });

            if let Some(filename) = occupant {
                ui.add_space(5.0);
                ui.label(
                    RichText::new(format!(
                        "DEF-19 conflict: `{}` already contains {filename}. Choose an empty type.",
                        self.assignment_type
                    ))
                    .strong()
                    .color(Color32::from_rgb(220, 85, 70)),
                );
            } else if self.selected_unknown.is_none() {
                ui.add_space(5.0);
                ui.weak("Select an unknown texture before assigning a type.");
            }

            if requested_assignment {
                self.assign_selected_unknown();
            }
        });
    }

    fn assign_selected_unknown(&mut self) {
        let (Some(group_index), Some(unknown_index), Some(document)) = (
            self.selected_group,
            self.selected_unknown,
            &mut self.document,
        ) else {
            self.status = "Select a group and an unknown texture first.".to_owned();
            return;
        };

        self.status = match document.assign_unknown(
            group_index,
            unknown_index,
            self.assignment_type.as_str(),
        ) {
            Ok(()) => {
                let remaining = document.scan().groups[group_index].unknown.len();
                if remaining == 0 && self.review_only {
                    self.selected_group = document
                        .scan()
                        .groups
                        .iter()
                        .position(|group| !group.unknown.is_empty());
                    self.selected_unknown = self.selected_group.map(|_| 0);
                } else {
                    self.selected_unknown =
                        (remaining > 0).then_some(unknown_index.min(remaining - 1));
                }
                format!("Assigned unknown texture to `{}`.", self.assignment_type)
            }
            Err(error) => error,
        };
    }
}

impl eframe::App for GroupReviewApp {
    fn update(&mut self, context: &egui::Context, _frame: &mut eframe::Frame) {
        self.receive_dropped_file(context);
        self.top_bar(context);
        self.document_view(context);
    }
}

fn group_matches(group: &ScanGroup, query: &str) -> bool {
    group.base_name.to_lowercase().contains(query)
        || group
            .slots
            .values()
            .chain(group.unknown.iter())
            .any(|entry| entry.filename.to_lowercase().contains(query))
}

fn detected_type_summary(group: &ScanGroup) -> String {
    let types = ASSIGNABLE_SOURCE_TYPES
        .iter()
        .filter(|source_type| group.slots.contains_key(**source_type))
        .copied()
        .collect::<Vec<_>>();
    if types.is_empty() {
        "—".to_owned()
    } else {
        types.join(", ")
    }
}

fn detected_file_summary(group: &ScanGroup) -> String {
    ASSIGNABLE_SOURCE_TYPES
        .iter()
        .filter_map(|source_type| {
            group
                .slots
                .get(*source_type)
                .map(|entry| format!("{source_type}: {}", entry.filename))
        })
        .collect::<Vec<_>>()
        .join("\n")
}
