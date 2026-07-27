#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Main PySide6 application window."""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
)
from PySide6.QtCore import Qt

from language.language_manager import change_language
from language.language_manager import get_instance as get_language_manager
from language.language_manager import get_text
from ui_pyside.export_settings import ExportSettingsPanel
from ui_pyside.model_import import ModelImportPanel
from ui_pyside.preview_panel import PreviewPanel
from ui_pyside.texture_group_panel import TextureGroupPanel
from ui_pyside.texture_import import TextureImportPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(get_text("app.title", "CryEngine Texture Processor"))
        self._init_ui()
        self._create_menu()
        self.setStatusBar(QStatusBar(self))
        self.update_status(get_text("app.ready", "Ready"))

    def _init_ui(self):
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        self.left_tabs = QTabWidget()
        self.texture_import_panel = TextureImportPanel()
        self.model_import_panel = ModelImportPanel()
        self.left_tabs.addTab(self.texture_import_panel, get_text("import.texture.title", "Texture Import"))
        self.left_tabs.addTab(self.model_import_panel, get_text("import.model.title", "Model Import"))
        main_splitter.addWidget(self.left_tabs)

        center_splitter = QSplitter(Qt.Vertical)
        self.preview_panel = PreviewPanel()
        self.texture_group_panel = TextureGroupPanel()
        center_splitter.addWidget(self.preview_panel)
        center_splitter.addWidget(self.texture_group_panel)
        main_splitter.addWidget(center_splitter)

        self.export_settings_panel = ExportSettingsPanel()
        main_splitter.addWidget(self.export_settings_panel)
        main_splitter.setSizes([320, 560, 360])

        self.texture_import_panel.set_group_panel(self.texture_group_panel)
        self.texture_import_panel.set_preview_panel(self.preview_panel)
        self.texture_group_panel.set_preview_panel(self.preview_panel)
        self.model_import_panel.set_texture_import_panel(self.texture_import_panel)

    def _create_menu(self):
        menu_bar = self.menuBar()
        menu_bar.clear()

        file_menu = menu_bar.addMenu(get_text("menu.file.title", "File"))
        import_textures = QAction(get_text("menu.file.import_textures", "Import Textures..."), self)
        import_textures.triggered.connect(self._import_textures)
        file_menu.addAction(import_textures)

        import_model = QAction(get_text("menu.file.import_model", "Import Model..."), self)
        import_model.triggered.connect(self._import_model)
        file_menu.addAction(import_model)
        file_menu.addSeparator()

        export_action = QAction(get_text("menu.file.export", "Export..."), self)
        export_action.triggered.connect(self._export)
        file_menu.addAction(export_action)
        file_menu.addSeparator()

        exit_action = QAction(get_text("menu.file.exit", "Exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu(get_text("menu.edit.title", "Edit"))
        language_menu = edit_menu.addMenu(get_text("menu.edit.language", "Language"))
        language_manager = get_language_manager()
        names = language_manager.get_language_display_names()
        for code in language_manager.get_available_languages():
            action = QAction(f"{names.get(code, code)} ({code})", self)
            action.setCheckable(True)
            action.setChecked(code == language_manager.get_current_language())
            action.triggered.connect(lambda checked=False, lang_code=code: self._change_language(lang_code))
            language_menu.addAction(action)

        help_menu = menu_bar.addMenu(get_text("menu.help.title", "Help"))
        about_action = QAction(get_text("menu.help.about", "About"), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _change_language(self, language_code):
        if not change_language(language_code):
            return
        self.setWindowTitle(get_text("app.title", "CryEngine Texture Processor"))
        self.left_tabs.setTabText(0, get_text("import.texture.title", "Texture Import"))
        self.left_tabs.setTabText(1, get_text("import.model.title", "Model Import"))
        self._create_menu()
        QMessageBox.information(
            self,
            get_text("language.title", "Language"),
            get_text(
                "language.changed",
                "Language changed to {0}. Some changes will take effect immediately, but for a complete update, please restart the application.",
            ).format(language_code),
        )

    def _import_textures(self):
        self.left_tabs.setCurrentIndex(0)
        self.texture_import_panel.import_textures()

    def _import_model(self):
        self.left_tabs.setCurrentIndex(1)
        self.model_import_panel.import_model()

    def _export(self):
        self.export_settings_panel.export_textures(
            self.texture_import_panel.texture_manager.get_all_groups()
        )

    def _show_about(self):
        QMessageBox.information(
            self,
            get_text("about.title", "About"),
            get_text(
                "about.content",
                "CryEngine Texture Processor\n\nA tool for processing textures for use in CryEngine.\n\nVersion: 0.1",
            ),
        )

    def update_status(self, message):
        self.statusBar().showMessage(message)

    def start_batch_processing(self, *args, **kwargs):
        QMessageBox.information(
            self,
            get_text("batch.title", "Batch Processing"),
            get_text("batch.not_configured", "Batch processing is not fully configured yet."),
        )

    def get_texture_manager(self):
        return self.texture_import_panel.texture_manager
