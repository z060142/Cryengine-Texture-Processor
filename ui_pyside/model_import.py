#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Model import panel for the PySide6 UI."""

import os

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from language.language_manager import get_text
from model_processing.model_loader import ModelLoader
from model_processing.texture_extractor import TextureExtractor
from ui_pyside.progress_dialog import ProgressDialog


class ModelImportPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.imported_models_info = []
        self.model_loader = ModelLoader()
        self.texture_extractor = TextureExtractor()
        self.texture_import_panel = None
        self.currently_selected_model_textures = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        import_button = QPushButton(get_text("model_import.import_button", "Import Model(s)"))
        import_button.clicked.connect(self.import_model)
        button_row.addWidget(import_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        models_box = QGroupBox(get_text("model_import.imported_models", "Imported Models"))
        models_layout = QVBoxLayout(models_box)
        self.models_list = QListWidget()
        self.models_list.itemSelectionChanged.connect(self._on_model_select)
        models_layout.addWidget(self.models_list)
        layout.addWidget(models_box)

        info_box = QGroupBox(get_text("model_import.selected_info", "Selected Model Information"))
        info_layout = QFormLayout(info_box)
        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.materials_label = QLabel("0")
        self.textures_label = QLabel("0")
        info_layout.addRow(get_text("model_import.path_label", "Path:"), self.path_label)
        info_layout.addRow(get_text("model_import.materials_label", "Materials:"), self.materials_label)
        info_layout.addRow(get_text("model_import.textures_label", "Textures:"), self.textures_label)
        layout.addWidget(info_box)

        textures_box = QGroupBox(get_text("model_import.extracted_textures", "Extracted Textures"))
        textures_layout = QVBoxLayout(textures_box)
        self.texture_table = QTableWidget(0, 3)
        self.texture_table.setHorizontalHeaderLabels(
            [
                get_text("model_import.col_material", "Material"),
                get_text("model_import.col_type", "Type"),
                get_text("model_import.col_path", "Path"),
            ]
        )
        self.texture_table.horizontalHeader().setStretchLastSection(True)
        textures_layout.addWidget(self.texture_table)
        layout.addWidget(textures_box, 1)

        action_row = QHBoxLayout()
        self.add_to_processing_button = QPushButton(get_text("model_import.add_button", "Add to Processing"))
        self.add_to_processing_button.clicked.connect(self._add_to_processing)
        self.add_to_processing_button.setEnabled(False)
        action_row.addWidget(self.add_to_processing_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

    def set_texture_import_panel(self, panel):
        self.texture_import_panel = panel

    def import_model(self, initial_file_paths=None):
        if initial_file_paths is False:
            initial_file_paths = None

        if initial_file_paths is None:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                get_text("model_import.dialog_title", "Select Model Files"),
                os.getcwd(),
                "3D model files (*.fbx *.obj *.dae *.3ds *.blend);;All files (*.*)",
            )
            if not file_paths:
                return
        else:
            file_paths = list(initial_file_paths)

        self.imported_models_info.clear()
        self.models_list.clear()
        self._populate_table([])

        progress_dialog = ProgressDialog(
            self,
            title=get_text("model_import.progress_title", "Importing Models..."),
            allow_cancel=True,
        )

        all_texture_paths = []
        success_count = 0
        error_count = 0

        for index, file_path in enumerate(file_paths):
            if progress_dialog.is_cancelled():
                break

            filename = os.path.basename(file_path)
            progress_dialog.update_progress(
                (index + 1) / len(file_paths),
                get_text("model_import.progress_loading", "Loading: {filename}").format(filename=filename),
                get_text("model_import.progress_status", "Model {current}/{total}").format(
                    current=index + 1,
                    total=len(file_paths),
                ),
            )

            model_info = {
                "path": file_path,
                "filename": filename,
                "materials": 0,
                "model_obj": None,
                "extracted_textures": [],
            }

            try:
                model = self.model_loader.load(file_path)
                if model and not model.get("is_dummy", False):
                    model_info["model_obj"] = model
                    model_info["materials"] = len(model.get("materials", []))
                    refs = self.texture_extractor.extract(model)
                    textures = self._get_accurate_texture_info(refs)
                    model_info["extracted_textures"] = textures
                    all_texture_paths.extend(
                        texture["path"]
                        for texture in textures
                        if texture.get("path") and os.path.exists(texture["path"])
                    )
                    success_count += 1
                else:
                    model_info["filename"] += get_text("model_import.load_failed_suffix", " (Load Failed)")
                    error_count += 1
            except Exception as e:
                print(f"Error importing model {file_path}: {e}")
                model_info["filename"] += get_text("model_import.load_error_suffix", " (Error)")
                error_count += 1

            self.imported_models_info.append(model_info)

        progress_dialog.show_completion(True, True)
        progress_dialog.close()
        self._update_model_list_display()

        if all_texture_paths and self.texture_import_panel:
            self.texture_import_panel.import_textures(sorted(set(all_texture_paths)))

        QMessageBox.information(
            self,
            get_text("model_import.summary_title", "Multi-Import Complete"),
            get_text(
                "model_import.summary_finished",
                "Finished importing {total} models.\nSuccessfully loaded: {success}\nErrors: {errors}",
            ).format(total=len(file_paths), success=success_count, errors=error_count),
        )

    def _get_accurate_texture_info(self, texture_refs):
        accurate_textures = []
        texture_manager = None
        if self.texture_import_panel and hasattr(self.texture_import_panel, "texture_manager"):
            texture_manager = self.texture_import_panel.texture_manager

        for ref in texture_refs:
            accurate_type = ref.texture_type
            base_name = "Unknown"
            abs_path = None

            if ref.path:
                if os.path.isabs(ref.path):
                    abs_path = ref.path
                elif getattr(self.model_loader, "last_loaded_dir", None):
                    candidate = os.path.join(self.model_loader.last_loaded_dir, ref.path)
                    if os.path.exists(candidate):
                        abs_path = os.path.normpath(candidate)

            if texture_manager and abs_path and os.path.exists(abs_path):
                try:
                    accurate_type, base_name = texture_manager.classify_texture(abs_path)
                except Exception as e:
                    print(f"Warning: Could not classify {abs_path}: {e}")
            elif abs_path:
                base_name = os.path.splitext(os.path.basename(abs_path))[0]
            else:
                accurate_type = "Missing"
                base_name = os.path.splitext(ref.filename)[0] if ref.filename else "Unknown"

            accurate_textures.append(
                {
                    "path": abs_path,
                    "type": accurate_type,
                    "material": ref.material_name,
                    "filename": ref.filename,
                    "processed_path": ref.processed_path,
                    "base_name": base_name,
                }
            )

        return accurate_textures

    def _update_model_list_display(self):
        self.models_list.clear()
        for model_info in self.imported_models_info:
            self.models_list.addItem(model_info.get("filename", "Unknown Model"))
        if self.imported_models_info:
            self.models_list.setCurrentRow(0)

    def _on_model_select(self):
        row = self.models_list.currentRow()
        if row < 0 or row >= len(self.imported_models_info):
            self.path_label.setText("")
            self.materials_label.setText("0")
            self.textures_label.setText("0")
            self._populate_table([])
            self.currently_selected_model_textures = []
            self.add_to_processing_button.setEnabled(False)
            return

        model_info = self.imported_models_info[row]
        textures = model_info.get("extracted_textures", [])
        self.path_label.setText(model_info.get("path", ""))
        self.materials_label.setText(str(model_info.get("materials", 0)))
        self.textures_label.setText(str(len(textures)))
        self.currently_selected_model_textures = textures
        self._populate_table(textures)
        self.add_to_processing_button.setEnabled(
            any(texture.get("path") and os.path.exists(texture["path"]) for texture in textures)
        )

    def _populate_table(self, textures):
        self.texture_table.setRowCount(0)
        for texture in textures:
            row = self.texture_table.rowCount()
            self.texture_table.insertRow(row)
            self.texture_table.setItem(row, 0, QTableWidgetItem(texture.get("material", "Unknown")))
            self.texture_table.setItem(row, 1, QTableWidgetItem(texture.get("type", "Unknown")))
            self.texture_table.setItem(row, 2, QTableWidgetItem(texture.get("path") or texture.get("filename", "N/A")))

    def _add_to_processing(self):
        paths = [
            texture["path"]
            for texture in self.currently_selected_model_textures
            if texture.get("path") and os.path.exists(texture["path"])
        ]
        if not paths:
            QMessageBox.warning(self, get_text("error.title", "Error"), "No valid texture files found.")
            return
        if not self.texture_import_panel:
            QMessageBox.warning(self, get_text("error.title", "Error"), "Texture import panel not available.")
            return
        self.texture_import_panel.import_textures(paths)
