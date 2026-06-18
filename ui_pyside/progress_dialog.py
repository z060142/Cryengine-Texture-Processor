#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PySide6 progress dialog compatible with the legacy progress API."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
)

from language.language_manager import get_text


class _ProgressValue:
    def __init__(self):
        self._value = 0.0

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class ProgressDialog(QDialog):
    def __init__(self, parent, title=None, allow_cancel=True):
        super().__init__(parent)
        self.cancelled = False
        self.cancel_callback = None
        self.progress_var = _ProgressValue()

        self.setWindowTitle(title or get_text("progress.title", "Processing..."))
        self.setModal(True)
        self.setMinimumSize(420, 170)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.current_label = QLabel(get_text("progress.preparing", "Preparing..."))
        self.current_label.setWordWrap(True)
        layout.addWidget(self.current_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_button = QPushButton(get_text("button.cancel", "Cancel"))
        self.cancel_button.clicked.connect(self._on_cancel)
        self.close_button = QPushButton(get_text("button.close", "Close"))
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(False)
        self.close_button.hide()

        if allow_cancel:
            button_row.addWidget(self.cancel_button)
        else:
            self.cancel_button.hide()
            self.close_button.show()
            button_row.addWidget(self.close_button)

        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)
        self.show()

    def update_stage(self, stage_text):
        self.stage_label.setText(stage_text or "")
        self.repaint()

    def update_progress(self, progress, current=None, status=None):
        progress_percent = max(0.0, min(100.0, float(progress) * 100.0))
        self.progress_var.set(progress_percent)
        self.progress_bar.setValue(int(progress_percent))
        if current is not None:
            self.current_label.setText(current)
        if status is not None:
            self.status_label.setText(status)
        self.repaint()

    def set_cancel_callback(self, callback):
        self.cancel_callback = callback

    def _on_cancel(self):
        self.cancelled = True
        if self.cancel_callback:
            self.cancel_callback()
        self.cancel_button.setEnabled(False)

    def closeEvent(self, event):
        if not self.is_complete():
            self._on_cancel()
            event.ignore()
        else:
            event.accept()

    def show_completion(self, success=True, allow_close=True):
        self.progress_var.set(100.0)
        self.progress_bar.setValue(100)
        self.current_label.setText(
            get_text("progress.complete", "Operation complete")
            if success
            else get_text("progress.failed", "Operation failed")
        )
        self.cancel_button.hide()
        if allow_close:
            self.close_button.setEnabled(True)
            self.close_button.show()
        self.repaint()

    def is_complete(self):
        return self.progress_var.get() >= 99.9

    def is_cancelled(self):
        return self.cancelled
