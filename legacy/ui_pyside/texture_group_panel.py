#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Texture group panel for the PySide6 UI."""

import os

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TextureGroupPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.texture_groups = []
        self.preview_panel = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Detected Texture Groups")
        group_layout = QVBoxLayout(group_box)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Base Name", "Detected Textures", "Unknown Textures"])
        self.tree.itemSelectionChanged.connect(self._on_group_select)
        self.tree.itemDoubleClicked.connect(self._on_group_double_click)
        group_layout.addWidget(self.tree)
        layout.addWidget(group_box, 1)

        details_box = QGroupBox("Group Details")
        details_layout = QFormLayout(details_box)
        self.base_name_label = QLabel("")
        self.types_label = QLabel("")
        details_layout.addRow("Base Name:", self.base_name_label)
        details_layout.addRow("Texture Types:", self.types_label)
        layout.addWidget(details_box)

        unknown_box = QGroupBox("Unknown Textures")
        unknown_layout = QVBoxLayout(unknown_box)
        self.unknown_list = QListWidget()
        unknown_layout.addWidget(self.unknown_list)
        classify_row = QHBoxLayout()
        classify_row.addWidget(QLabel("Set Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            [
                "diffuse",
                "normal",
                "specular",
                "glossiness",
                "roughness",
                "displacement",
                "metallic",
                "ao",
                "alpha",
                "emissive",
                "sss",
                "arm",
            ]
        )
        classify_row.addWidget(self.type_combo)
        classify_button = QPushButton("Set Type")
        classify_button.clicked.connect(self._set_texture_type)
        classify_row.addWidget(classify_button)
        unknown_layout.addLayout(classify_row)
        layout.addWidget(unknown_box)

    def set_preview_panel(self, preview_panel):
        self.preview_panel = preview_panel

    def set_texture_groups(self, texture_groups):
        self.texture_groups = texture_groups or []
        self.tree.clear()

        for index, group in enumerate(self.texture_groups):
            if hasattr(group, "base_name"):
                base_name = group.base_name
                detected = []
                unknown_count = 0
                for texture_type, texture in group.textures.items():
                    if texture_type == "unknown":
                        unknown_count = len(texture) if isinstance(texture, list) else 0
                    elif texture is not None:
                        detected.append(texture_type)
            else:
                base_name = group.get("base_name", "")
                textures = group.get("textures", [])
                detected = [texture.get("type", "unknown") for texture in textures]
                unknown_count = sum(1 for texture in textures if texture.get("type") == "unknown")

            item = QTreeWidgetItem([base_name, ", ".join(detected), str(unknown_count)])
            item.setData(0, 256, index)
            self.tree.addTopLevelItem(item)

    def _selected_group(self):
        selected = self.tree.selectedItems()
        if not selected:
            return None
        index = selected[0].data(0, 256)
        if index is None or index < 0 or index >= len(self.texture_groups):
            return None
        return self.texture_groups[index]

    def _on_group_select(self):
        group = self._selected_group()
        if not group:
            return

        self.unknown_list.clear()
        if hasattr(group, "base_name"):
            self.base_name_label.setText(group.base_name)
            types = [
                texture_type
                for texture_type, texture in group.textures.items()
                if texture_type != "unknown" and texture is not None
            ]
            self.types_label.setText(", ".join(types))
            for texture in group.textures.get("unknown", []):
                self.unknown_list.addItem(os.path.basename(texture.get("path", "")))
        else:
            self.base_name_label.setText(group.get("base_name", ""))
            types = [texture.get("type", "unknown") for texture in group.get("textures", [])]
            self.types_label.setText(", ".join(types))

    def _on_group_double_click(self, item, column):
        group = self._selected_group()
        if not group or not self.preview_panel:
            return

        textures = []
        if hasattr(group, "textures"):
            for texture_type, texture in group.textures.items():
                if texture_type == "unknown":
                    textures.extend(texture)
                elif texture is not None:
                    textures.append(texture)
        else:
            textures = group.get("textures", [])

        self.preview_panel.set_textures(textures)

    def _set_texture_type(self):
        group = self._selected_group()
        selected_unknowns = self.unknown_list.selectedItems()
        if not group or not selected_unknowns or not hasattr(group, "textures"):
            QMessageBox.information(self, "Info", "No unknown texture selected.")
            return

        selected_index = self.unknown_list.row(selected_unknowns[0])
        unknowns = group.textures.get("unknown", [])
        if selected_index < 0 or selected_index >= len(unknowns):
            return

        texture = unknowns.pop(selected_index)
        new_type = self.type_combo.currentText()
        texture["type"] = new_type
        group.textures[new_type] = texture
        self.set_texture_groups(self.texture_groups)
