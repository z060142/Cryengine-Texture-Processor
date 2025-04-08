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
# Import ProgressDialog
# No longer need direct imports for MTL export logic here
# from output_formats.mtl_exporter import export_mtl 
# from model_processing.texture_extractor import TextureExtractor

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
            "texture_output_directory": "", # Renamed from output_directory
            "model_output_directory": "",   # Added for model export
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

        # --- Texture Output Directory ---
        texture_output_dir_frame = ttk.LabelFrame(main_frame, text=get_text("export.texture_output_directory", "Texture Output Directory"))
        texture_output_dir_frame.pack(fill=tk.X, padx=5, pady=5)

        texture_dir_frame = ttk.Frame(texture_output_dir_frame, padding=10)
        texture_dir_frame.pack(fill=tk.X, expand=True)

        self.texture_output_dir_var = tk.StringVar(value=self.settings["texture_output_directory"])
        texture_dir_entry = ttk.Entry(texture_dir_frame, textvariable=self.texture_output_dir_var, width=40)
        texture_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        texture_browse_button = ttk.Button(
            texture_dir_frame,
            text=get_text("button.browse", "Browse..."),
            command=self._select_texture_output_dir,
            width=15
        )
        texture_browse_button.pack(side=tk.LEFT)

        self.texture_dir_status_var = tk.StringVar(value="")
        texture_dir_status_label = ttk.Label(texture_dir_frame, textvariable=self.texture_dir_status_var, foreground="gray")
        texture_dir_status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self._update_texture_dir_status() # Initial status update

        # --- Model Output Directory ---
        model_output_dir_frame = ttk.LabelFrame(main_frame, text=get_text("export.model_output_directory", "Model Output Directory"))
        model_output_dir_frame.pack(fill=tk.X, padx=5, pady=5)

        model_dir_frame = ttk.Frame(model_output_dir_frame, padding=10)
        model_dir_frame.pack(fill=tk.X, expand=True)

        self.model_output_dir_var = tk.StringVar(value=self.settings["model_output_directory"])
        model_dir_entry = ttk.Entry(model_dir_frame, textvariable=self.model_output_dir_var, width=40)
        model_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        model_browse_button = ttk.Button(
            model_dir_frame,
            text=get_text("button.browse", "Browse..."),
            command=self._select_model_output_dir,
            width=15
        )
        model_browse_button.pack(side=tk.LEFT)

        self.model_dir_status_var = tk.StringVar(value="")
        model_dir_status_label = ttk.Label(model_dir_frame, textvariable=self.model_dir_status_var, foreground="gray")
        model_dir_status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self._update_model_dir_status() # Initial status update
        
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
        
        self.export_textures_button = ttk.Button( # Renamed variable
            action_frame,
            text=get_text("export.export_textures", "Export Textures"),
            command=lambda: self.export_textures(),
            width=20
        )
        self.export_textures_button.pack(side=tk.LEFT, padx=5)

        # Add Export Model button
        self.export_model_button = ttk.Button(
            action_frame,
            text=get_text("export.export_model", "Export Model"),
            command=self._on_export_model, # Connect to placeholder
            width=20
        )
        self.export_model_button.pack(side=tk.LEFT, padx=5)
        
        # Save settings button
        save_settings_button = ttk.Button(
            action_frame, 
            text=get_text("export.save_settings", "Save Settings"), 
            command=self._save_settings,
            width=15
        )
        save_settings_button.pack(side=tk.RIGHT, padx=5)

        # Connect output directory entries to update status
        self.texture_output_dir_var.trace_add("write", lambda *args: self._update_texture_dir_status())
        self.model_output_dir_var.trace_add("write", lambda *args: self._update_model_dir_status())

    def _update_texture_dir_status(self):
        """Update the texture output directory status label."""
        self._update_dir_status_generic(self.texture_output_dir_var, self.texture_dir_status_var)

    def _update_model_dir_status(self):
        """Update the model output directory status label."""
        self._update_dir_status_generic(self.model_output_dir_var, self.model_dir_status_var)

    def _update_dir_status_generic(self, dir_var, status_var):
        """Generic function to update directory status labels."""
        directory = dir_var.get()
        if not directory:
            status_var.set(get_text("export.no_directory_selected", "No directory selected. Will prompt when exporting."))
            return
        if os.path.exists(directory):
            if os.access(directory, os.W_OK):
                status_var.set(get_text("export.directory_valid", "Directory is valid and writable."))
            else:
                status_var.set(get_text("export.directory_not_writable", "Warning: Directory is not writable!"))
        else:
            status_var.set(get_text("export.directory_not_exist", "Directory does not exist. It will be created when exporting."))

    def _select_texture_output_dir(self):
        """Open file dialog to select texture output directory."""
        self._select_dir_generic(
            self.texture_output_dir_var,
            get_text("export.select_texture_directory", "Select Texture Output Directory"),
            self._update_texture_dir_status
        )

    def _select_model_output_dir(self):
        """Open file dialog to select model output directory."""
        self._select_dir_generic(
            self.model_output_dir_var,
            get_text("export.select_model_directory", "Select Model Output Directory"),
            self._update_model_dir_status
        )

    def _select_dir_generic(self, dir_var, title, update_callback):
        """Generic function to select a directory."""
        directory = filedialog.askdirectory(
            title=title,
            initialdir=dir_var.get() or os.getcwd()
        )
        if directory:
            dir_var.set(directory)
            update_callback()

    def _on_batch_process(self):
        """
        Handler for Batch Process button. Orchestrates texture export then model export.
        """
        print("Starting Batch Process...")
        settings = self.get_settings()
        texture_output_dir = settings.get("texture_output_directory")
        model_output_dir = settings.get("model_output_directory")

        # --- Pre-checks ---
        if not texture_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.error_no_texture_dir", "Texture output directory is not set."))
            return
        if not model_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.no_model_dir", "Please select a Model Output Directory first."))
            return

        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)
        if not main_window:
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access main application window.")
             return
        if not hasattr(main_window, "start_batch_processing") or not hasattr(main_window, "run_model_mtl_export"):
             messagebox.showerror(get_text("export.error", "Error"), "Required export functions not found in main application.")
             return

        # --- Ensure directories exist ---
        try:
            if not os.path.exists(texture_output_dir): os.makedirs(texture_output_dir)
            if not os.path.exists(model_output_dir): os.makedirs(model_output_dir)
            self._update_texture_dir_status()
            self._update_model_dir_status()
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"Failed to create output directories: {e}")
            return

        # --- Create Progress Dialog ---
        # Note: start_batch_processing and run_model_mtl_export now create their own dialogs internally.
        # We need to adapt this. Let's have this function manage ONE dialog for the whole batch.
        # This requires modifying start_batch_processing and run_model_mtl_export again
        # to ACCEPT an optional progress_dialog instance instead of creating one.

        # --- TEMPORARY WORKAROUND: Call functions sequentially, they'll show separate dialogs ---
        # This isn't ideal for UX but avoids further refactoring right now.
        # TODO: Refactor main.py functions to accept an existing ProgressDialog instance.

        # --- Stage 1: Export Textures ---
        print("Batch Process - Stage 1: Exporting Textures...")
        texture_export_success = False
        try:
            # This will show its own progress dialog
            texture_export_success = main_window.start_batch_processing(export_settings=settings)
            print(f"Batch Process: Texture export finished. Success: {texture_export_success}")
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"Failed during texture export stage: {e}")
            import traceback
            traceback.print_exc()
            return # Stop if texture stage fails critically

        if not texture_export_success:
            print("Batch Process: Halting because texture export failed or was cancelled.")
            # No need for message box here, start_batch_processing likely showed one
            return

        # --- Stage 2: Export Models (MTL) ---
        print("Batch Process - Stage 2: Exporting Models (MTL)...")
        mtl_exported_count = 0
        mtl_error_count = 0
        mtl_error_messages = []
        try:
            # This will show its own progress dialog (or just a message box if no models)
            # We don't pass a dialog here due to the temporary workaround.
            mtl_exported_count, mtl_error_count, mtl_error_messages = main_window.run_model_mtl_export(settings=settings)
            print(f"Batch Process: MTL export finished. Exported: {mtl_exported_count}, Errors: {mtl_error_count}")
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"Failed during model export stage: {e}")
            import traceback
            traceback.print_exc()
            # Continue to show summary even if this stage fails

        # --- Final Summary ---
        summary_title = get_text("export.batch_process", "Batch Process")
        final_message = "Batch process finished.\n\n"
        final_message += f"Texture Export Stage: {'Success' if texture_export_success else 'Failed/Cancelled'}\n"
        final_message += f"MTL Files Exported: {mtl_exported_count}\n"
        final_message += f"MTL Export Errors: {mtl_error_count}"

        if mtl_error_count > 0:
             final_message += "\n\nMTL Errors:\n" + "\n".join(mtl_error_messages)

        if not texture_export_success or mtl_error_count > 0:
             messagebox.showwarning(summary_title, final_message)
        else:
             messagebox.showinfo(summary_title, final_message)

    def _on_export_model(self):
        """
        Handler for Export Model button. Calls the dedicated MTL export function from main.py.
        """
        settings = self.get_settings()
        model_output_dir = settings.get("model_output_directory")

        if not model_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.no_model_dir", "Please select a Model Output Directory first."))
            return

        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)
        if not main_window or not hasattr(main_window, "run_model_mtl_export"):
             messagebox.showerror(get_text("export.error", "Error"), "Model export function not found in main application.")
             return

        # --- Ensure Model Output Directory Exists ---
        try:
            if not os.path.exists(model_output_dir):
                 print(f"Creating model output directory: {model_output_dir}")
                 os.makedirs(model_output_dir)
                 self._update_model_dir_status()
        except Exception as e:
             messagebox.showerror(get_text("export.error", "Error"), f"Failed to create model output directory: {e}")
             return

        # --- Call the Export Function (which handles its own progress/summary) ---
        print("Export Model button clicked. Calling run_model_mtl_export...")
        try:
            # This function now handles showing messages or its own progress dialog
            main_window.run_model_mtl_export(settings=settings)
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"An unexpected error occurred during model export: {e}")
            import traceback
            traceback.print_exc()

    def _save_settings(self):
        """
        Save current settings to configuration.
        """
        # Update settings from UI
        # Ensure these are read correctly before use
        self.settings["texture_output_directory"] = self.texture_output_dir_var.get()
        self.settings["model_output_directory"] = self.model_output_dir_var.get()
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
        self.settings["texture_output_directory"] = self.texture_output_dir_var.get()
        self.settings["model_output_directory"] = self.model_output_dir_var.get()
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
        self.texture_output_dir_var.set(self.settings["texture_output_directory"])
        self.model_output_dir_var.set(self.settings["model_output_directory"])
        self.diff_format_var.set(self.settings["diff_format"])
        self.normal_flip_var.set(self.settings["normal_flip_green"])
        self.spec_gen_var.set(self.settings["generate_missing_spec"])
        self.metallic_process_var.set(self.settings["process_metallic"])
        self.format_var.set(self.settings["output_format"])
        self.resolution_var.set(self.settings["output_resolution"])
        self.generate_dds_var.set(self.settings.get("generate_cry_dds", False))

        # Update directory statuses
        self._update_texture_dir_status()
        self._update_model_dir_status()
        
        # Update texture type checkboxes if available
        if "texture_types" in self.settings:
            for type_key, enabled in self.settings["texture_types"].items():
                if type_key in self.type_vars:
                    self.type_vars[type_key].set(enabled)
    
    def export_textures(self, texture_groups=None):
        """
        Export textures with current settings.
        
        Args:
            texture_groups: Ignored. Uses all groups from TextureManager.
        """
        # This button now ONLY triggers the texture processing part.
        print("Export Textures button clicked. Triggering texture processing...")
        settings = self.get_settings()
        texture_output_dir = settings.get("texture_output_directory")

        if not texture_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.error_no_texture_dir", "Texture output directory is not set."))
            return

        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)
        if not main_window or not hasattr(main_window, "start_batch_processing"):
             messagebox.showerror(get_text("export.error", "Error"), "Texture processing function not found in main application.")
             return

        # --- Ensure Texture Output Directory Exists ---
        try:
            if not os.path.exists(texture_output_dir):
                 print(f"Creating texture output directory: {texture_output_dir}")
                 os.makedirs(texture_output_dir)
                 self._update_texture_dir_status()
        except Exception as e:
             messagebox.showerror(get_text("export.error", "Error"), f"Failed to create texture output directory: {e}")
             return

        # --- Call the Texture Processing Function ---
        try:
            # Pass the settings so it uses the correct output dir etc.
            # This function handles its own progress dialog and completion message.
            main_window.start_batch_processing(export_settings=settings)
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"Failed to start texture processing: {e}")
            import traceback
            traceback.print_exc()
