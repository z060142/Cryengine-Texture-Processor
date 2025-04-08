#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Suffix Settings Dialog

This module provides a dialog for configuring texture type suffix settings.
"""

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox

class SuffixSettingsDialog:
    """
    Dialog for configuring texture type suffix settings.
    """
    
    def __init__(self, parent):
        """
        Initialize the suffix settings dialog.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.settings = {}
        self.result = False
        
        # Load current settings
        self._load_settings()
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Texture Suffix Settings")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create UI elements
        self._init_ui()
        
        # Wait for dialog to close
        parent.wait_window(self.dialog)
    
    def _init_ui(self):
        """
        Initialize UI components and layout.
        """
        # Create main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create instruction label
        instruction = ttk.Label(
            main_frame, 
            text="Configure suffixes for each texture type. Separate multiple suffixes with commas.",
            wraplength=550
        )
        instruction.pack(fill=tk.X, pady=(0, 10))
        
        # Create scrollable frame for suffix entries
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create entry fields for each texture type
        self.entries = {}
        row = 0
        
        # Define texture types and default suffixes
        texture_types = [
            ("diffuse", "Diffuse/Albedo"),
            ("normal", "Normal Maps"),
            ("specular", "Specular Maps"),
            ("glossiness", "Glossiness Maps"),
            ("roughness", "Roughness Maps"),
            ("displacement", "Displacement/Height Maps"),
            ("metallic", "Metallic Maps"),
            ("ao", "Ambient Occlusion Maps"),
            ("alpha", "Alpha/Transparency Maps"),
            ("emissive", "Emissive/Glow Maps"),
            ("sss", "Subsurface Scattering Maps"),
            ("removable_suffixes", "Removable Suffixes (dx, gl, etc.)")
        ]
        
        # Create entry for each texture type
        for type_key, type_label in texture_types:
            ttk.Label(scrollable_frame, text=f"{type_label}:").grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=5
            )
            
            entry = ttk.Entry(scrollable_frame, width=50)
            entry.grid(row=row, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
            
            # Set current value
            if type_key in self.settings:
                entry.insert(0, ", ".join(self.settings[type_key]))
            
            self.entries[type_key] = entry
            row += 1
        
        # Create button frame
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create buttons
        save_button = ttk.Button(button_frame, text="Save", command=self._save_settings)
        save_button.pack(side=tk.RIGHT, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # Set focus to first entry
        list(self.entries.values())[0].focus_set()
    
    def _load_settings(self):
        """
        Load suffix settings from file.
        """
        settings_file = self._get_settings_file()
        
        # Default settings
        default_settings = {
            "diffuse": ["diff", "diffuse", "albedo", "basecolor", "color", "col", "_d"],
            "normal": ["normal", "nrm", "norm", "_n"],
            "specular": ["spec", "specular", "_s"],
            "glossiness": ["gloss", "glossy", "glossiness", "smoothness", "_g"],
            "roughness": ["rough", "roughness", "_r"],
            "displacement": ["disp", "displacement", "height", "bump", "_h"],
            "metallic": ["metal", "metallic", "metalness", "_m"],
            "ao": ["ao", "ambient", "occlusion"],
            "alpha": ["alpha", "opacity", "transparency", "_a"],
            "emissive": ["emissive", "emission", "glow", "_e"],
            "sss": ["sss", "subsurface"],
            "removable_suffixes": ["2k", "4k", "8k", "dx", "gl", "directx", "opengl"]
        }
        
        # Try to load settings from file
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    self.settings = json.load(f)
            else:
                self.settings = default_settings
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load suffix settings: {e}")
            self.settings = default_settings
    
    def _save_settings(self):
        """
        Save suffix settings to file.
        """
        settings_file = self._get_settings_file()
        
        # Collect settings from entries
        new_settings = {}
        for type_key, entry in self.entries.items():
            # Get suffixes from entry, split by comma, and strip whitespace
            suffixes = [suffix.strip() for suffix in entry.get().split(",") if suffix.strip()]
            new_settings[type_key] = suffixes
        
        # Save settings to file
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(settings_file), exist_ok=True)
            
            # Write settings to file
            with open(settings_file, 'w') as f:
                json.dump(new_settings, f, indent=4)
            
            self.settings = new_settings
            self.result = True
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save suffix settings: {e}")
    
    def _get_settings_file(self):
        """
        Get the path to the suffix settings file.
        
        Returns:
            Path to the suffix settings file (in project root directory)
        """
        # Use __file__ to locate the project root directory
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # ui/ directory
        project_root = os.path.dirname(current_file_dir)  # Go up one level
        return os.path.join(project_root, "suffix_settings.json")  # No leading dot for better visibility in file explorers
