#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export settings panel for the PySide6 UI."""

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from language.language_manager import get_text
from ui_pyside.progress_dialog import ProgressDialog

RC_OUTPUT_FORMAT_OPTIONS = ("tif",)


def _normalize_output_format(value):
    value = str(value or "tif").strip().lower()
    return value if value in RC_OUTPUT_FORMAT_OPTIONS else "tif"


class ExportSettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = {
            "texture_output_directory": "",
            "model_output_directory": "",
            "diff_format": "albedo",
            "normal_flip_green": False,
            "generate_missing_spec": True,
            "process_metallic": True,
            "output_format": "tif",
            "output_resolution": "original",
            "delete_after_export": {
                "tif": False,
                "fbx": False,
                "json": True,
            },
        }
        self._new_generated_files = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        texture_dir_box = QGroupBox(get_text("export.texture_output_directory", "Texture Output Directory"))
        texture_dir_layout = QVBoxLayout(texture_dir_box)
        texture_dir_row = QHBoxLayout()
        self.texture_output_dir_edit = QLineEdit()
        self.texture_output_dir_edit.textChanged.connect(self._update_texture_dir_status)
        texture_browse = QPushButton(get_text("button.browse", "Browse..."))
        texture_browse.clicked.connect(self._select_texture_output_dir)
        texture_dir_row.addWidget(self.texture_output_dir_edit)
        texture_dir_row.addWidget(texture_browse)
        self.texture_dir_status_label = QLabel("")
        texture_dir_layout.addLayout(texture_dir_row)
        texture_dir_layout.addWidget(self.texture_dir_status_label)
        layout.addWidget(texture_dir_box)

        model_dir_box = QGroupBox(get_text("export.model_output_directory", "Model Output Directory"))
        model_dir_layout = QVBoxLayout(model_dir_box)
        model_dir_row = QHBoxLayout()
        self.model_output_dir_edit = QLineEdit()
        self.model_output_dir_edit.textChanged.connect(self._update_model_dir_status)
        model_browse = QPushButton(get_text("button.browse", "Browse..."))
        model_browse.clicked.connect(self._select_model_output_dir)
        model_dir_row.addWidget(self.model_output_dir_edit)
        model_dir_row.addWidget(model_browse)
        self.model_dir_status_label = QLabel("")
        model_dir_layout.addLayout(model_dir_row)
        model_dir_layout.addWidget(self.model_dir_status_label)
        layout.addWidget(model_dir_box)

        settings_box = QGroupBox(get_text("export.settings", "Texture Export Settings"))
        form = QFormLayout(settings_box)
        self.generate_dds_check = QCheckBox(get_text("export.generate_cry_dds", "Generate CryEngine DDS"))
        self.generate_dds_check.toggled.connect(self._update_tif_delete_state)
        form.addRow(self.generate_dds_check)

        self.diff_format_combo = QComboBox()
        self.diff_format_combo.addItems(["albedo", "diffuse_ao"])
        form.addRow(get_text("export.diffuse_format", "Diffuse Format:"), self.diff_format_combo)

        self.normal_flip_check = QCheckBox(get_text("export.flip_normal", "Flip Normal Map Green Channel"))
        form.addRow(self.normal_flip_check)
        self.spec_gen_check = QCheckBox(get_text("export.generate_spec", "Generate Missing Specular Maps"))
        self.spec_gen_check.setChecked(True)
        form.addRow(self.spec_gen_check)
        self.metallic_process_check = QCheckBox(
            get_text("export.process_metallic", "Convert Metallic to Albedo+Reflection")
        )
        self.metallic_process_check.setChecked(True)
        form.addRow(self.metallic_process_check)

        self.format_combo = QComboBox()
        self.format_combo.addItems(list(RC_OUTPUT_FORMAT_OPTIONS))
        form.addRow(get_text("export.output_format", "Output Format:"), self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["original", "4096", "2048", "1024", "512"])
        form.addRow(get_text("export.output_resolution", "Output Resolution:"), self.resolution_combo)
        layout.addWidget(settings_box)

        types_box = QGroupBox(get_text("export.texture_types", "Output Texture Types"))
        types_layout = QHBoxLayout(types_box)
        self.type_checks = {}
        for type_key, label in [
            ("diff", get_text("export.type_diff", "Diffuse (_diff)")),
            ("spec", get_text("export.type_spec", "Specular (_spec)")),
            ("ddna", get_text("export.type_ddna", "Normal & Gloss (_ddna)")),
            ("displ", get_text("export.type_displ", "Displacement (_displ)")),
            ("emissive", get_text("export.type_emissive", "Emissive (_em)")),
            ("sss", get_text("export.type_sss", "Subsurface Scattering (_sss)")),
        ]:
            check = QCheckBox(label)
            check.setChecked(True)
            self.type_checks[type_key] = check
            types_layout.addWidget(check)
        layout.addWidget(types_box)

        misc_box = QGroupBox(get_text("export.misc_settings", "Miscellaneous Settings"))
        misc_layout = QHBoxLayout(misc_box)
        misc_layout.addWidget(QLabel(get_text("export.delete_after_export", "Delete after export:")))
        self.delete_tif_check = QCheckBox("TIF")
        self.delete_fbx_check = QCheckBox("FBX")
        self.delete_json_check = QCheckBox("JSON")
        self.delete_json_check.setChecked(True)
        misc_layout.addWidget(self.delete_tif_check)
        misc_layout.addWidget(self.delete_fbx_check)
        misc_layout.addWidget(self.delete_json_check)
        misc_layout.addStretch(1)
        layout.addWidget(misc_box)

        button_row = QHBoxLayout()
        batch_button = QPushButton(get_text("export.batch_process", "Batch Process"))
        batch_button.clicked.connect(self._on_batch_process)
        export_textures_button = QPushButton(get_text("export.export_textures", "Export Textures"))
        export_textures_button.clicked.connect(self.export_textures)
        export_model_button = QPushButton(get_text("export.export_model", "Export Model"))
        export_model_button.clicked.connect(self._on_export_model)
        save_button = QPushButton(get_text("export.save_settings", "Save Settings"))
        save_button.clicked.connect(self._save_settings)
        button_row.addWidget(batch_button)
        button_row.addWidget(export_textures_button)
        button_row.addWidget(export_model_button)
        button_row.addStretch(1)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self._update_tif_delete_state()
        self.update_directory_statuses()

    def _select_texture_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            get_text("export.select_texture_directory", "Select Texture Output Directory"),
            self.texture_output_dir_edit.text() or os.getcwd(),
        )
        if directory:
            self.texture_output_dir_edit.setText(directory)

    def _select_model_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            get_text("export.select_model_directory", "Select Model Output Directory"),
            self.model_output_dir_edit.text() or os.getcwd(),
        )
        if directory:
            self.model_output_dir_edit.setText(directory)

    def _update_dir_status(self, directory, label):
        if not directory:
            label.setText(get_text("export.no_directory_selected", "No directory selected. Will prompt when exporting."))
        elif os.path.exists(directory):
            if os.access(directory, os.W_OK):
                label.setText(get_text("export.directory_valid", "Directory is valid and writable."))
            else:
                label.setText(get_text("export.directory_not_writable", "Warning: Directory is not writable!"))
        else:
            label.setText(get_text("export.directory_not_exist", "Directory does not exist. It will be created when exporting."))

    def _update_texture_dir_status(self):
        self._update_dir_status(self.texture_output_dir_edit.text(), self.texture_dir_status_label)

    def _update_model_dir_status(self):
        self._update_dir_status(self.model_output_dir_edit.text(), self.model_dir_status_label)

    def update_directory_statuses(self):
        self._update_texture_dir_status()
        self._update_model_dir_status()

    def _update_tif_delete_state(self):
        enabled = self.generate_dds_check.isChecked()
        self.delete_tif_check.setEnabled(enabled)
        if not enabled:
            self.delete_tif_check.setChecked(False)

    def _main_window(self):
        window = self.window()
        return window if window and hasattr(window, "start_batch_processing") else None

    def _ensure_dirs(self, texture=False, model=False):
        settings = self.get_settings()
        try:
            if texture and settings.get("texture_output_directory"):
                os.makedirs(settings["texture_output_directory"], exist_ok=True)
            if model and settings.get("model_output_directory"):
                os.makedirs(settings["model_output_directory"], exist_ok=True)
            self.update_directory_statuses()
            return True
        except Exception as e:
            QMessageBox.critical(self, get_text("export.error", "Error"), f"Failed to create output directories: {e}")
            return False

    def _on_batch_process(self):
        settings = self.get_settings()
        if not settings.get("texture_output_directory"):
            QMessageBox.warning(self, get_text("export.warning", "Warning"), "Texture output directory is not set.")
            return
        if not settings.get("model_output_directory"):
            QMessageBox.warning(self, get_text("export.warning", "Warning"), "Model output directory is not set.")
            return
        main_window = self._main_window()
        if not main_window:
            QMessageBox.critical(self, get_text("export.error", "Error"), "Cannot access main application window.")
            return
        if not self._ensure_dirs(texture=True, model=True):
            return

        existing_texture_files = self._snapshot_files(settings["texture_output_directory"], (".tif",))
        existing_model_files = self._snapshot_files(settings["model_output_directory"], (".fbx", ".json"))

        texture_export_ok = main_window.start_batch_processing(export_settings=settings)
        if not texture_export_ok:
            self._new_generated_files = {
                "texture": self._new_files(settings["texture_output_directory"], (".tif",), existing_texture_files),
                "model": set(),
            }
            self._process_post_export_cleanup(settings)
            self._show_export_summary(0, 0, 1, ["Texture export failed; model export was skipped."])
            return

        progress = ProgressDialog(self, title=get_text("export.model_export_title", "Exporting Models..."))
        mtl_exported, mtl_errors, mtl_msgs = main_window.run_model_mtl_export(settings, progress)
        if not progress.is_cancelled():
            fbx_exported, fbx_errors, fbx_msgs = main_window.run_model_fbx_export(settings, progress)
        else:
            fbx_exported, fbx_errors, fbx_msgs = 0, 0, []
        progress.close()

        self._new_generated_files = {
            "texture": self._new_files(settings["texture_output_directory"], (".tif",), existing_texture_files),
            "model": self._new_files(settings["model_output_directory"], (".fbx", ".json"), existing_model_files),
        }
        self._process_post_export_cleanup(settings)
        self._show_export_summary(mtl_exported, fbx_exported, mtl_errors + fbx_errors, mtl_msgs + fbx_msgs)

    def _on_export_model(self):
        settings = self.get_settings()
        if not settings.get("model_output_directory") or not settings.get("texture_output_directory"):
            QMessageBox.warning(self, get_text("export.warning", "Warning"), "Texture and model output directories are required.")
            return
        main_window = self._main_window()
        if not main_window or not self._ensure_dirs(model=True):
            return

        existing_model_files = self._snapshot_files(settings["model_output_directory"], (".fbx", ".json"))
        progress = ProgressDialog(self, title=get_text("export.model_export_title", "Exporting Models..."))
        mtl_exported, mtl_errors, mtl_msgs = main_window.run_model_mtl_export(settings, progress)
        if not progress.is_cancelled():
            fbx_exported, fbx_errors, fbx_msgs = main_window.run_model_fbx_export(settings, progress)
        else:
            fbx_exported, fbx_errors, fbx_msgs = 0, 0, []
        progress.close()

        self._new_generated_files = {
            "texture": set(),
            "model": self._new_files(settings["model_output_directory"], (".fbx", ".json"), existing_model_files),
        }
        self._process_post_export_cleanup(settings)
        self._show_export_summary(mtl_exported, fbx_exported, mtl_errors + fbx_errors, mtl_msgs + fbx_msgs)

    def export_textures(self, texture_groups=None):
        if texture_groups is False:
            texture_groups = None

        settings = self.get_settings()
        if not settings.get("texture_output_directory"):
            QMessageBox.warning(self, get_text("export.warning", "Warning"), "Texture output directory is not set.")
            return
        main_window = self._main_window()
        if not main_window or not self._ensure_dirs(texture=True):
            return
        existing_files = self._snapshot_files(settings["texture_output_directory"], (".tif",))
        texture_export_ok = main_window.start_batch_processing(texture_groups=texture_groups, export_settings=settings)
        if not texture_export_ok:
            self._new_generated_files = {
                "texture": self._new_files(settings["texture_output_directory"], (".tif",), existing_files),
                "model": set(),
            }
            self._process_post_export_cleanup(settings)
            return

        self._new_generated_files = {
            "texture": self._new_files(settings["texture_output_directory"], (".tif",), existing_files),
            "model": set(),
        }
        self._process_post_export_cleanup(settings)

    def _snapshot_files(self, directory, suffixes):
        if not directory or not os.path.exists(directory):
            return set()
        return {name for name in os.listdir(directory) if name.lower().endswith(suffixes)}

    def _new_files(self, directory, suffixes, existing):
        if not directory or not os.path.exists(directory):
            return set()
        return {
            name
            for name in os.listdir(directory)
            if name.lower().endswith(suffixes) and name not in existing
        }

    def _show_export_summary(self, mtl_exported, fbx_exported, total_errors, messages):
        if total_errors <= 0:
            return
        message = f"MTL Files: {mtl_exported}\nFBX Models: {fbx_exported}\nErrors: {total_errors}"
        if messages:
            message += "\n\n" + "\n".join(f"- {item}" for item in messages[:8])
        QMessageBox.warning(self, get_text("export.export_complete", "Export Complete"), message)

    def _process_post_export_cleanup(self, settings):
        if not self._new_generated_files:
            return

        delete_settings = settings.get("delete_after_export", {})
        for filename in self._new_generated_files.get("texture", set()):
            if delete_settings.get("tif", False) and settings.get("generate_cry_dds", False):
                self._try_remove(os.path.join(settings.get("texture_output_directory", ""), filename))

        for filename in self._new_generated_files.get("model", set()):
            if filename.lower().endswith(".fbx") and delete_settings.get("fbx", False):
                self._try_remove(os.path.join(settings.get("model_output_directory", ""), filename))
            if filename.lower().endswith(".json") and delete_settings.get("json", True):
                self._try_remove(os.path.join(settings.get("model_output_directory", ""), filename))

        self._new_generated_files = None

    def _try_remove(self, path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error deleting file {path}: {e}")

    def _save_settings(self):
        self.get_settings()
        QMessageBox.information(
            self,
            get_text("export.settings_saved_title", "Settings Saved"),
            get_text("export.settings_saved_message", "Export settings have been saved."),
        )

    def get_settings(self):
        self.settings["texture_output_directory"] = self.texture_output_dir_edit.text()
        self.settings["model_output_directory"] = self.model_output_dir_edit.text()
        self.settings["diff_format"] = self.diff_format_combo.currentText()
        self.settings["normal_flip_green"] = self.normal_flip_check.isChecked()
        self.settings["generate_missing_spec"] = self.spec_gen_check.isChecked()
        self.settings["process_metallic"] = self.metallic_process_check.isChecked()
        self.settings["output_format"] = _normalize_output_format(self.format_combo.currentText())
        self.settings["output_resolution"] = self.resolution_combo.currentText()
        self.settings["generate_cry_dds"] = self.generate_dds_check.isChecked()
        self.settings["delete_after_export"] = {
            "tif": self.delete_tif_check.isChecked(),
            "fbx": self.delete_fbx_check.isChecked(),
            "json": self.delete_json_check.isChecked(),
        }
        self.settings["texture_types"] = {
            key: check.isChecked() for key, check in self.type_checks.items()
        }
        return self.settings.copy()

    def set_settings(self, settings):
        self.settings.update({key: value for key, value in settings.items() if key in self.settings})
        self.settings["output_format"] = _normalize_output_format(self.settings.get("output_format", "tif"))
        self.texture_output_dir_edit.setText(self.settings.get("texture_output_directory", ""))
        self.model_output_dir_edit.setText(self.settings.get("model_output_directory", ""))
        self.diff_format_combo.setCurrentText(self.settings.get("diff_format", "albedo"))
        self.normal_flip_check.setChecked(self.settings.get("normal_flip_green", False))
        self.spec_gen_check.setChecked(self.settings.get("generate_missing_spec", True))
        self.metallic_process_check.setChecked(self.settings.get("process_metallic", True))
        self.format_combo.setCurrentText(_normalize_output_format(self.settings.get("output_format", "tif")))
        self.resolution_combo.setCurrentText(self.settings.get("output_resolution", "original"))
        self.generate_dds_check.setChecked(self.settings.get("generate_cry_dds", False))
        delete_settings = self.settings.get("delete_after_export", {})
        self.delete_tif_check.setChecked(delete_settings.get("tif", False))
        self.delete_fbx_check.setChecked(delete_settings.get("fbx", False))
        self.delete_json_check.setChecked(delete_settings.get("json", True))
        for key, enabled in self.settings.get("texture_types", {}).items():
            if key in self.type_checks:
                self.type_checks[key].setChecked(enabled)
        self._update_tif_delete_state()
        self.update_directory_statuses()
