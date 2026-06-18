#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Texture preview panel for the PySide6 UI."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFormLayout, QFrame, QLabel, QVBoxLayout, QWidget


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_texture = None
        self.current_pixmap = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info_frame = QFrame()
        info_layout = QFormLayout(info_frame)
        self.name_label = QLabel("")
        self.type_label = QLabel("")
        self.dimensions_label = QLabel("")
        info_layout.addRow("Texture:", self.name_label)
        info_layout.addRow("Type:", self.type_label)
        info_layout.addRow("Dimensions:", self.dimensions_label)
        layout.addWidget(info_frame)

        self.preview_label = QLabel("No texture selected")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(260)
        self.preview_label.setFrameShape(QFrame.StyledPanel)
        self.preview_label.setStyleSheet("background: #2b2b2b; color: #cfcfcf;")
        layout.addWidget(self.preview_label, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

    def set_textures(self, textures):
        self.set_current_texture(textures[0] if textures else None)

    def set_current_texture(self, texture):
        self.current_texture = texture
        self.current_pixmap = None

        if not texture:
            self.name_label.setText("")
            self.type_label.setText("")
            self.dimensions_label.setText("")
            self.preview_label.setText("No texture selected")
            self.preview_label.setPixmap(QPixmap())
            return

        texture_path = texture.get("path", "")
        self.name_label.setText(os.path.basename(texture_path))
        self.type_label.setText(texture.get("type", "Unknown"))

        pixmap = QPixmap(texture_path)
        if pixmap.isNull():
            self.dimensions_label.setText("Error loading image")
            self.preview_label.setText("Preview unavailable")
            return

        self.current_pixmap = pixmap
        self.dimensions_label.setText(f"{pixmap.width()} x {pixmap.height()}")
        self._update_pixmap()

    def _update_pixmap(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return

        target_size = self.preview_label.size()
        scaled = self.current_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)
