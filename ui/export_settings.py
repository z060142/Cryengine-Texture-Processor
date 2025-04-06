#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Export Settings UI Component

This module provides UI components for configuring texture export settings
and output options for CryEngine compatibility.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from language.language_manager import get_text

class ExportSettingsPanel:
    """
    UI panel for configuring export settings.
    """
    
    def __init__(self, parent):
        """
        Initialize the export settings panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        
        # Default export settings
        self.settings = {
            "output_directory": "",
            "diff_format": "albedo",  # Options: 'albedo', 'diffuse_ao'
            "normal_flip_green": False,  # Whether to flip green channel for normal maps
            "generate_missing_spec": True,  # Whether to generate a default spec when missing
            "process_metallic": True,  # Whether to convert metallic to albedo+reflection
            "output_format": "tif",  # Output file format
            "output_resolution": "original"  # Output resolution
        }
        
        # Create frame
        self.frame = parent
        
        # Create UI elements
        self._init_ui()
    
    def _init_ui(self):
        """
        Initialize UI components and layout.
        """
        # Create main frame with padding
        main_frame = ttk.Frame(self.frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create output directory frame (as a separate and more prominent section)
        output_dir_frame = ttk.LabelFrame(main_frame, text=get_text("export.output_directory", "Output Directory"))
        output_dir_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Output directory selection
        dir_frame = ttk.Frame(output_dir_frame, padding=10)
        dir_frame.pack(fill=tk.X, expand=True)
        
        self.output_dir_var = tk.StringVar(value=self.settings["output_directory"])
        dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=40)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_button = ttk.Button(
            dir_frame, 
            text=get_text("button.browse", "Browse..."), 
            command=self._select_output_dir,
            width=15
        )
        browse_button.pack(side=tk.LEFT)
        
        # Add a label to show the directory status
        self.dir_status_var = tk.StringVar(value="")
        dir_status_label = ttk.Label(dir_frame, textvariable=self.dir_status_var, foreground="gray")
        dir_status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        # Update directory status
        self._update_dir_status()
        
        # Create settings frame
        settings_frame = ttk.LabelFrame(main_frame, text=get_text("export.settings", "Export Settings"))
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Settings content frame with padding
        settings_content = ttk.Frame(settings_frame, padding=10)
        settings_content.pack(fill=tk.X, expand=True)
        
        # Add CryEngine DDS checkbox
        self.generate_dds_var = tk.BooleanVar(value=self.settings.get("generate_cry_dds", False))
        dds_checkbutton = ttk.Checkbutton(
            settings_content,
            text=get_text("export.generate_cry_dds", "Generate CryEngine DDS"),
            variable=self.generate_dds_var
        )
        dds_checkbutton.grid(row=0, column=2, rowspan=1, sticky=tk.W, padx=5, pady=5)
        
        # Diff format
        ttk.Label(settings_content, text=get_text("export.diffuse_format", "Diffuse Format:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.diff_format_var = tk.StringVar(value=self.settings["diff_format"])
        diff_format_combo = ttk.Combobox(settings_content, textvariable=self.diff_format_var, width=15)
        diff_format_combo['values'] = ('albedo', 'diffuse_ao')
        diff_format_combo.current(0 if self.settings["diff_format"] == "albedo" else 1)
        diff_format_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Normal green channel flip
        self.normal_flip_var = tk.BooleanVar(value=self.settings["normal_flip_green"])
        normal_flip_check = ttk.Checkbutton(
            settings_content, 
            text=get_text("export.flip_normal", "Flip Normal Map Green Channel"), 
            variable=self.normal_flip_var
        )
        normal_flip_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Spec generation
        self.spec_gen_var = tk.BooleanVar(value=self.settings["generate_missing_spec"])
        spec_gen_check = ttk.Checkbutton(
            settings_content, 
            text=get_text("export.generate_spec", "Generate Missing Specular Maps"), 
            variable=self.spec_gen_var
        )
        spec_gen_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Metallic processing
        self.metallic_process_var = tk.BooleanVar(value=self.settings["process_metallic"])
        metallic_process_check = ttk.Checkbutton(
            settings_content, 
            text=get_text("export.process_metallic", "Convert Metallic to Albedo+Reflection"), 
            variable=self.metallic_process_var
        )
        metallic_process_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Output format
        ttk.Label(settings_content, text=get_text("export.output_format", "Output Format:")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.format_var = tk.StringVar(value=self.settings["output_format"])
        format_combo = ttk.Combobox(settings_content, textvariable=self.format_var, width=10)
        format_combo['values'] = ('tif', 'png', 'dds')
        format_combo.current(0)
        format_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Output resolution
        ttk.Label(settings_content, text=get_text("export.output_resolution", "Output Resolution:")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.resolution_var = tk.StringVar(value=self.settings["output_resolution"])
        resolution_combo = ttk.Combobox(settings_content, textvariable=self.resolution_var, width=15)
        resolution_combo['values'] = ('original', '4096', '2048', '1024', '512')
        resolution_combo.current(0)
        resolution_combo.grid(row=5, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Create texture types frame
        types_frame = ttk.LabelFrame(main_frame, text=get_text("export.texture_types", "Output Texture Types"))
        types_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Types content frame with padding
        types_content = ttk.Frame(types_frame, padding=10)
        types_content.pack(fill=tk.BOTH, expand=True)
        
        # Create texture type checkboxes
        self.type_vars = {}
        types = [
            ("diff", get_text("export.type_diff", "Diffuse (_diff)")),
            ("spec", get_text("export.type_spec", "Specular (_spec)")),
            ("ddna", get_text("export.type_ddna", "Normal & Gloss (_ddna)")),
            ("displ", get_text("export.type_displ", "Displacement (_displ)")),
            ("emissive", get_text("export.type_emissive", "Emissive (_emissive)")),
            ("sss", get_text("export.type_sss", "Subsurface Scattering (_sss)"))
        ]
        
        for i, (type_key, type_label) in enumerate(types):
            var = tk.BooleanVar(value=True)
            self.type_vars[type_key] = var
            
            checkbox = ttk.Checkbutton(
                types_content,
                text=type_label,
                variable=var
            )
            checkbox.grid(row=i // 3, column=i % 3, sticky=tk.W, padx=10, pady=5)
        
        # Create action buttons frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=10)
        
        # Batch process button
        self.batch_button = ttk.Button(
            action_frame, 
            text=get_text("export.batch_process", "Batch Process"), 
            command=self._on_batch_process,
            width=20
        )
        self.batch_button.pack(side=tk.LEFT, padx=5)
        
        self.export_button = ttk.Button(
            action_frame, 
            text=get_text("export.export_textures", "Export Textures"), 
            command=lambda: self.export_textures(),
            width=20
        )
        self.export_button.pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        save_settings_button = ttk.Button(
            action_frame, 
            text=get_text("export.save_settings", "Save Settings"), 
            command=self._save_settings,
            width=15
        )
        save_settings_button.pack(side=tk.RIGHT, padx=5)
        
        # Connect output directory entry to update status
        self.output_dir_var.trace_add("write", lambda name, index, mode: self._update_dir_status())
    
    def _update_dir_status(self):
        """
        Update the output directory status label.
        """
        directory = self.output_dir_var.get()
        
        if not directory:
            self.dir_status_var.set(get_text("export.no_directory_selected", "No directory selected. Will prompt when exporting."))
            return
            
        if os.path.exists(directory):
            if os.access(directory, os.W_OK):
                self.dir_status_var.set(get_text("export.directory_valid", "Directory is valid and writable."))
            else:
                self.dir_status_var.set(get_text("export.directory_not_writable", "Warning: Directory is not writable!"))
        else:
            self.dir_status_var.set(get_text("export.directory_not_exist", "Directory does not exist. It will be created when exporting."))
    
    def _select_output_dir(self):
        """
        Open file dialog to select output directory.
        """
        directory = filedialog.askdirectory(
            title=get_text("export.select_directory", "Select Output Directory"),
            initialdir=self.output_dir_var.get() or os.getcwd()
        )
        
        if directory:
            self.output_dir_var.set(directory)
            self._update_dir_status()
    
    def _on_batch_process(self):
        """
        Handler for batch process button.
        """
        # Check if the application has a batch processing function
        if hasattr(self.parent, "winfo_toplevel"):
            root = self.parent.winfo_toplevel()
            if hasattr(root, "start_batch_processing"):
                # Call the batch processing function
                root.start_batch_processing()
            else:
                # Get parent application (MainWindow) through root if available
                for attr in dir(root):
                    attr_value = getattr(root, attr)
                    if hasattr(attr_value, "start_batch_processing"):
                        attr_value.start_batch_processing()
                        break
                else:
                    messagebox.showinfo(
                        get_text("export.not_implemented", "Not Implemented"),
                        get_text("export.batch_not_available", "Batch processing is not available yet.")
                    )
    
    def _save_settings(self):
        """
        Save current settings to configuration.
        """
        # Update settings from UI
        self.settings["output_directory"] = self.output_dir_var.get()
        self.settings["diff_format"] = self.diff_format_var.get()
        self.settings["normal_flip_green"] = self.normal_flip_var.get()
        self.settings["generate_missing_spec"] = self.spec_gen_var.get()
        self.settings["process_metallic"] = self.metallic_process_var.get()
        self.settings["output_format"] = self.format_var.get()
        self.settings["output_resolution"] = self.resolution_var.get()
        self.settings["generate_cry_dds"] = self.generate_dds_var.get()
        
        # Show success message
        messagebox.showinfo(
            get_text("export.settings_saved_title", "Settings Saved"),
            get_text("export.settings_saved_message", "Export settings have been saved.")
        )
    
    def get_settings(self):
        """
        Get the current export settings.
        
        Returns:
            Dictionary containing export settings
        """
        # Update settings from UI
        self.settings["output_directory"] = self.output_dir_var.get()
        self.settings["diff_format"] = self.diff_format_var.get()
        self.settings["normal_flip_green"] = self.normal_flip_var.get()
        self.settings["generate_missing_spec"] = self.spec_gen_var.get()
        self.settings["process_metallic"] = self.metallic_process_var.get()
        self.settings["output_format"] = self.format_var.get()
        self.settings["output_resolution"] = self.resolution_var.get()
        self.settings["generate_cry_dds"] = self.generate_dds_var.get()
        
        # Add enabled texture types
        texture_types = {}
        for type_key, var in self.type_vars.items():
            texture_types[type_key] = var.get()
        self.settings["texture_types"] = texture_types
        
        return self.settings.copy()
    
    def set_settings(self, settings):
        """
        Set export settings.
        
        Args:
            settings: Dictionary containing export settings
        """
        # Update settings with provided values
        for key, value in settings.items():
            if key in self.settings:
                self.settings[key] = value
        
        # Update UI to reflect new settings
        self._update_ui_from_settings()
    
    def _update_ui_from_settings(self):
        """
        Update UI elements to reflect current settings.
        """
        self.output_dir_var.set(self.settings["output_directory"])
        self.diff_format_var.set(self.settings["diff_format"])
        self.normal_flip_var.set(self.settings["normal_flip_green"])
        self.spec_gen_var.set(self.settings["generate_missing_spec"])
        self.metallic_process_var.set(self.settings["process_metallic"])
        self.format_var.set(self.settings["output_format"])
        self.resolution_var.set(self.settings["output_resolution"])
        self.generate_dds_var.set(self.settings.get("generate_cry_dds", False))
        
        # Update directory status
        self._update_dir_status()
        
        # Update texture type checkboxes if available
        if "texture_types" in self.settings:
            for type_key, enabled in self.settings["texture_types"].items():
                if type_key in self.type_vars:
                    self.type_vars[type_key].set(enabled)
    
    def export_textures(self, texture_groups=None):
        """
        Export textures with current settings.
        
        Args:
            texture_groups: Optional list of texture groups to export
        """
        # Get current settings
        settings = self.get_settings()
        
        # Check if output directory is set
        if not settings["output_directory"]:
            # Prompt for output directory
            directory = filedialog.askdirectory(
                title=get_text("export.select_directory", "Select Output Directory"),
                initialdir=os.getcwd()
            )
            
            if not directory:
                return  # User cancelled
            
            settings["output_directory"] = directory
            self.output_dir_var.set(directory)
            self._update_dir_status()
        
        # Check if output directory exists
        if not os.path.exists(settings["output_directory"]):
            try:
                os.makedirs(settings["output_directory"])
                self._update_dir_status()
            except Exception as e:
                messagebox.showerror(
                    get_text("export.error", "Error"),
                    get_text("export.create_dir_error", "Failed to create output directory: {0}").format(str(e))
                )
                return
                
        # Debug information
        print(f"Export_textures called with {len(texture_groups) if texture_groups else 0} texture groups")
        
        # Check if we have texture groups to export
        if texture_groups is None or len(texture_groups) == 0:
            # Try to get texture groups from MainWindow if available
            if hasattr(self.parent, "winfo_toplevel"):
                root = self.parent.winfo_toplevel()
                if hasattr(root, "texture_import_panel") and hasattr(root.texture_import_panel, "texture_manager"):
                    texture_groups = root.texture_import_panel.texture_manager.get_all_groups()
                    print(f"Got {len(texture_groups)} texture groups from MainWindow")
            
            # If still no texture groups, show warning
            if texture_groups is None or len(texture_groups) == 0:
                messagebox.showwarning(
                    get_text("export.warning", "Warning"),
                    get_text("export.no_textures", "No texture groups to export.")
                )
                return
        
        # Debug information about texture groups
        for i, group in enumerate(texture_groups):
            if hasattr(group, 'base_name'):
                print(f"Group {i+1}: {group.base_name}")
            else:
                print(f"Group {i+1}: {group}")
        
        # In a real implementation, would process texture groups here
        # For now, just show a success message with some details
        enabled_types = [
            type_name for type_name, enabled in settings["texture_types"].items() 
            if enabled
        ]
        
        message = get_text("export.preview_message", "Would export {0} texture groups with the following settings:").format(len(texture_groups))
        message += "\n\n"
        message += get_text("export.preview_dir", "Output Directory: {0}").format(settings['output_directory']) + "\n"
        message += get_text("export.preview_diff", "Diffuse Format: {0}").format(settings['diff_format']) + "\n"
        message += get_text("export.preview_flip", "Flip Normal Green Channel: {0}").format(settings['normal_flip_green']) + "\n"
        message += get_text("export.preview_spec", "Generate Missing Specular: {0}").format(settings['generate_missing_spec']) + "\n"
        message += get_text("export.preview_metallic", "Convert Metallic to Albedo+Reflection: {0}").format(settings['process_metallic']) + "\n"
        message += get_text("export.preview_format", "Output Format: {0}").format(settings['output_format']) + "\n"
        message += get_text("export.preview_resolution", "Output Resolution: {0}").format(settings['output_resolution']) + "\n"
        message += get_text("export.preview_types", "Enabled Texture Types: {0}").format(', '.join(enabled_types))
        
        messagebox.showinfo(get_text("export.preview_title", "Export Preview"), message)
