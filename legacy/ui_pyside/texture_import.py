#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Texture import panel for the PySide6 UI."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.texture_manager import TextureManager


class TextureImportPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.texture_manager = TextureManager()
        self.all_textures = []
        self.group_panel = None
        self.preview_panel = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        import_button = QPushButton("Import Textures")
        import_button.clicked.connect(self.import_textures)
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_textures)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_selected)
        button_row.addWidget(import_button)
        button_row.addWidget(clear_button)
        button_row.addWidget(delete_button)
        layout.addLayout(button_row)

        list_box = QGroupBox("Imported Textures")
        list_layout = QVBoxLayout(list_box)
        self.texture_list = QListWidget()
        self.texture_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.texture_list.itemSelectionChanged.connect(self._on_texture_select)
        list_layout.addWidget(self.texture_list)
        layout.addWidget(list_box, 1)

        classify_box = QGroupBox("Classification Options")
        classify_layout = QHBoxLayout(classify_box)
        self.classification_combo = QComboBox()
        self.classification_combo.addItems(
            [
                "Diffuse",
                "Normal",
                "Specular",
                "Glossiness",
                "Roughness",
                "Displacement",
                "Metallic",
                "AO",
                "Alpha",
                "Emissive",
                "SSS",
                "ARM",
            ]
        )
        set_button = QPushButton("Set")
        set_button.clicked.connect(self._set_texture_type)
        classify_layout.addWidget(self.classification_combo)
        classify_layout.addWidget(set_button)
        layout.addWidget(classify_box)

    def set_group_panel(self, group_panel):
        self.group_panel = group_panel

    def set_preview_panel(self, preview_panel):
        self.preview_panel = preview_panel

    def load_suffix_settings(self):
        self.texture_manager = TextureManager()

    def import_textures(self, file_paths=None):
        if file_paths is False:
            file_paths = None

        if file_paths is None:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Texture Files",
                os.getcwd(),
                "Image files (*.jpg *.jpeg *.png *.tga *.tif *.tiff *.bmp *.hdr *.exr);;All files (*.*)",
            )
            if not file_paths:
                return []

        textures_added = []
        duplicates_skipped = 0
        existing_paths = {texture.get("path") for texture in self.all_textures if texture.get("path")}

        for path in file_paths:
            if path in existing_paths:
                duplicates_skipped += 1
                continue

            texture = self.texture_manager.add_texture(path)
            if texture is None:
                duplicates_skipped += 1
                continue

            textures_added.append(texture)
            self.all_textures.append(texture)
            self.texture_list.addItem(os.path.basename(path))
            existing_paths.add(path)

        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())

        if file_paths:
            message = f"Successfully imported {len(textures_added)} textures."
            if duplicates_skipped > 0:
                message += f"\nSkipped {duplicates_skipped} duplicate textures."
            QMessageBox.information(self, "Import Complete", message)

        return textures_added

    def clear_textures(self):
        if not self.all_textures:
            return
        if QMessageBox.question(self, "Confirm Clear", "Are you sure you want to clear all imported textures?") != QMessageBox.Yes:
            return
        self.texture_list.clear()
        self.all_textures = []
        self.texture_manager = TextureManager()
        if self.group_panel:
            self.group_panel.set_texture_groups([])

    def _on_texture_select(self):
        selected = self.texture_list.selectedIndexes()
        if not selected or not self.preview_panel:
            return
        index = selected[0].row()
        if 0 <= index < len(self.all_textures):
            self.preview_panel.set_current_texture(self.all_textures[index])

    def _set_texture_type(self):
        selected = sorted((index.row() for index in self.texture_list.selectedIndexes()), reverse=True)
        if not selected:
            QMessageBox.information(self, "Info", "No textures selected.")
            return

        new_type = self.classification_combo.currentText().lower()
        for index in selected:
            if 0 <= index < len(self.all_textures):
                self.all_textures[index]["type"] = new_type

        self.texture_manager = TextureManager()
        for texture in self.all_textures:
            self.texture_manager.add_texture(texture["path"], texture["type"])

        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())

    def _delete_selected(self):
        selected = sorted((index.row() for index in self.texture_list.selectedIndexes()), reverse=True)
        if not selected:
            QMessageBox.information(self, "Info", "No textures selected.")
            return

        if QMessageBox.question(self, "Confirm Delete", f"Delete {len(selected)} selected textures?") != QMessageBox.Yes:
            return

        deleted_paths = []
        for index in selected:
            if 0 <= index < len(self.all_textures):
                deleted_paths.append(self.all_textures[index]["path"])
                self.texture_list.takeItem(index)

        self.all_textures = [texture for texture in self.all_textures if texture["path"] not in deleted_paths]
        self.texture_manager = TextureManager()
        for texture in self.all_textures:
            self.texture_manager.add_texture(texture["path"], texture.get("type"))

        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())
