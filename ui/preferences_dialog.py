#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Preferences Dialog

This module provides a dialog for setting application preferences.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from language.language_manager import get_text
from utils.config_manager import ConfigManager

class PreferencesDialog:
    """
    Dialog for setting application preferences.
    """
    
    def __init__(self, parent):
        """
        Initialize the preferences dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = False
        self.config_manager = ConfigManager()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(get_text("preferences.title", "Preferences"))
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        # Set minimum size
        self.dialog.minsize(500, 300)
        
        # Position dialog in center of parent
        self._center_window()
        
        # Create UI elements
        self._init_ui()
        
        # Wait for the dialog to close
        parent.wait_window(self.dialog)
    
    def _center_window(self):
        """
        Center the dialog on the parent window.
        """
        parent = self.parent
        
        # Get parent geometry
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        # Get dialog size
        width = 500
        height = 300
        
        # Calculate position
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        # Set geometry
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def _init_ui(self):
        """
        Initialize UI components.
        """
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # CryEngine Integration tab
        cry_frame = ttk.Frame(notebook, padding=10)
        notebook.add(cry_frame, text=get_text("preferences.cry_integration", "CryEngine Integration"))
        
        # RC.exe path
        ttk.Label(cry_frame, text=get_text("preferences.rc_exe", "RC.exe Path:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=10)
        
        # RC.exe path entry frame
        rc_frame = ttk.Frame(cry_frame)
        rc_frame.grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=10)
        
        # Get saved RC.exe path
        rc_path = self.config_manager.get("rc_exe_path", "")
        
        # RC.exe entry
        self.rc_path_var = tk.StringVar(value=rc_path)
        rc_entry = ttk.Entry(rc_frame, textvariable=self.rc_path_var, width=40)
        rc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Browse button
        browse_button = ttk.Button(
            rc_frame, 
            text=get_text("button.browse", "Browse..."), 
            command=self._select_rc_exe
        )
        browse_button.pack(side=tk.RIGHT)
        
        # Status label for RC.exe
        self.rc_status_var = tk.StringVar()
        self._update_rc_status()
        rc_status_label = ttk.Label(cry_frame, textvariable=self.rc_status_var, foreground="gray")
        rc_status_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(0, 10))
        
        # Connect RC path entry to update status
        self.rc_path_var.trace_add("write", lambda name, index, mode: self._update_rc_status())
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=(15, 5))
        
        # OK button
        ok_button = ttk.Button(
            button_frame, 
            text=get_text("button.ok", "OK"), 
            command=self._on_ok
        )
        ok_button.pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        cancel_button = ttk.Button(
            button_frame, 
            text=get_text("button.cancel", "Cancel"), 
            command=self.dialog.destroy
        )
        cancel_button.pack(side=tk.RIGHT, padx=5)
    
    def _select_rc_exe(self):
        """
        Open file dialog to select RC.exe file.
        """
        file_path = filedialog.askopenfilename(
            title=get_text("preferences.select_rc_exe", "Select RC.exe"),
            filetypes=[
                (get_text("file.exe", "Executable files"), "*.exe"),
                (get_text("file.all", "All files"), "*.*")
            ],
            initialdir=os.path.dirname(self.rc_path_var.get()) if self.rc_path_var.get() else None
        )
        
        if file_path:
            self.rc_path_var.set(file_path)
    
    def _update_rc_status(self):
        """
        Update the RC.exe status label.
        """
        rc_path = self.rc_path_var.get()
        
        if not rc_path:
            self.rc_status_var.set(get_text("preferences.rc_not_selected", "RC.exe not selected"))
        elif not os.path.exists(rc_path):
            self.rc_status_var.set(get_text("preferences.rc_not_found", "RC.exe file not found"))
        elif not os.path.isfile(rc_path):
            self.rc_status_var.set(get_text("preferences.rc_not_file", "Selected path is not a file"))
        elif not os.access(rc_path, os.X_OK):
            # Not always reliable on Windows, but try it
            self.rc_status_var.set(get_text("preferences.rc_not_executable", "Selected file is not executable"))
        elif not rc_path.lower().endswith(".exe"):
            self.rc_status_var.set(get_text("preferences.rc_not_exe", "Selected file is not an .exe file"))
        else:
            self.rc_status_var.set(get_text("preferences.rc_valid", "RC.exe path is valid"))
    
    def _on_ok(self):
        """
        Handle OK button click.
        """
        # Save preferences
        self.config_manager.set("rc_exe_path", self.rc_path_var.get())
        
        # Save to file
        self.config_manager.save_config()
        
        # Set result flag
        self.result = True
        
        # Close dialog
        self.dialog.destroy()
