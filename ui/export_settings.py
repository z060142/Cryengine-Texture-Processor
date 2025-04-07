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
# Import the new exporter function
from output_formats.mtl_exporter import export_mtl
# Import necessary components for data retrieval
# Assuming TextureManager is accessible via root.texture_import_panel
# Assuming ModelImportPanel is accessible via root.model_import_panel
from model_processing.texture_extractor import TextureExtractor # Needed to re-extract original paths if necessary

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
        Handler for Batch Process button. Exports textures first, then models (MTL).
        """
        print("Starting Batch Process...")
        settings = self.get_settings()
        texture_output_dir = settings.get("texture_output_directory")
        model_output_dir = settings.get("model_output_directory")

        # 1. Check if directories are set
        if not texture_output_dir:
             messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.error_no_texture_dir", "Texture output directory is not set."))
             return
        if not model_output_dir:
             messagebox.showwarning(get_text("export.warning", "Warning"), get_text("export.no_model_dir", "Please select a Model Output Directory first."))
             return

        # --- Ensure directories exist ---
        try:
            if not os.path.exists(texture_output_dir):
                print(f"Creating texture output directory: {texture_output_dir}")
                os.makedirs(texture_output_dir)
                self._update_texture_dir_status()
            if not os.path.exists(model_output_dir):
                 print(f"Creating model output directory: {model_output_dir}")
                 os.makedirs(model_output_dir)
                 self._update_model_dir_status()
        except Exception as e:
             messagebox.showerror(get_text("export.error", "Error"), f"Failed to create output directories: {e}")
             return

        # --- 2. Export Textures ---
        print("Batch Process: Exporting Textures...")
        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)

        texture_export_success = False # Flag to track success
        if main_window and hasattr(main_window, "start_batch_processing"):
            try:
                # Call the original function directly.
                # IMPORTANT: This function needs modification in main.py/core to accept and use settings['texture_output_directory']
                print("Batch Process: Calling main_window.start_batch_processing() for textures.")
                main_window.start_batch_processing() # Assuming it handles its own settings/paths for now
                texture_export_success = True
                print("Batch Process: Texture export call completed (assumed success).")
            except Exception as e:
                messagebox.showerror(get_text("export.error", "Error"), f"Failed during batch texture processing: {e}")
                import traceback
                traceback.print_exc()
                return # Stop batch if texture export fails
        else:
            messagebox.showerror(get_text("export.error", "Error"), "Texture processing function (start_batch_processing) not found in main application window.")
            return # Stop batch if function is missing

        if not texture_export_success:
            print("Batch Process: Halting due to texture export failure or cancellation.")
            return

        # --- 3. Export Models (MTL) ---
        print("Batch Process: Exporting Models (MTL)...")
        # Get panels and managers correctly via main_window
        model_import_panel = getattr(main_window, "model_import_panel", None)
        texture_manager = None
        if main_window and hasattr(main_window, "get_texture_manager"):
             texture_manager = main_window.get_texture_manager() # Correctly get manager instance

        if not model_import_panel or not hasattr(model_import_panel, "imported_models_info"):
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access model import panel data for batch process.")
             return
        if not texture_manager:
             # This check should now correctly use the retrieved manager instance
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access Texture Manager for batch MTL export.")
             return

        all_imported_models = model_import_panel.imported_models_info
        if not all_imported_models:
            print("Batch Process: No models imported, skipping model export.")
            mtl_exported_count = 0
            mtl_error_count = 0
        else:
            # --- Re-run the MTL export logic from _on_export_model ---
            # This is duplicated, consider refactoring into a helper method later
            texture_extractor = TextureExtractor()
            mtl_exported_count = 0
            mtl_error_count = 0
            mtl_error_messages = []

            for model_info in all_imported_models:
                model_obj = model_info.get("model_obj")
                model_filename = model_info.get("filename", "unknown_model")
                mtl_filename = f"{os.path.splitext(model_filename)[0]}.mtl"

                if not model_obj or model_obj.get("is_dummy"): continue

                materials_data_for_mtl = []
                try:
                    original_materials = model_obj.get("materials", [])
                    if not original_materials: continue

                    for orig_mat in original_materials:
                        mat_name = orig_mat.get('name', 'UnnamedMaterial')
                        processed_textures = {}
                        all_orig_refs = texture_extractor.extract(model_obj)
                        material_orig_refs = [ref for ref in all_orig_refs if ref.material_name == mat_name]

                        output_suffixes = {
                            "diffuse": "_diff.dds", "normal": "_ddna.dds", "specular": "_spec.dds",
                            "displacement": "_displ.dds", "emissive": "_emissive.dds", "opacity": "_opacity.dds"
                        }
                        base_name = None
                        for orig_ref in material_orig_refs:
                            if orig_ref.path and os.path.exists(orig_ref.path):
                                try:
                                    _, potential_base = texture_manager.classify_texture(orig_ref.path)
                                    if potential_base:
                                        base_name = potential_base
                                        break
                                except Exception: pass # Ignore classification errors here

                        if not base_name and material_orig_refs and material_orig_refs[0].path:
                             base_name = os.path.splitext(os.path.basename(material_orig_refs[0].path))[0]

                        if base_name:
                            for type_key, suffix in output_suffixes.items():
                                expected_filename = f"{base_name}{suffix}"
                                expected_path = os.path.join(texture_output_dir, expected_filename)
                                if os.path.exists(expected_path):
                                    processed_textures[type_key] = expected_path
                        else:
                             print(f"Batch Warning: Could not determine base name for material '{mat_name}'.")


                        materials_data_for_mtl.append({'name': mat_name, 'textures': processed_textures})

                except Exception as e:
                     mtl_error_messages.append(f"Batch Error processing material data for {model_filename}: {e}")
                     mtl_error_count += 1
                     continue

                if not materials_data_for_mtl: continue

                try:
                    success, result_path_or_msg = export_mtl(materials_data_for_mtl, model_output_dir, texture_output_dir, mtl_filename)
                    if success:
                        mtl_exported_count += 1
                    else:
                        mtl_error_count += 1
                        mtl_error_messages.append(f"{model_filename}: {result_path_or_msg}")
                except Exception as e:
                     mtl_error_count += 1
                     mtl_error_messages.append(f"Batch Unexpected error exporting MTL for {model_filename}: {e}")

            print(f"Batch Process: MTL Export finished. Exported: {mtl_exported_count}, Errors: {mtl_error_count}")

        # --- 4. Final Summary ---
        # Combine results from texture and model export if possible
        # For now, just show MTL summary
        summary_title = get_text("export.batch_process", "Batch Process")
        final_message = "Batch process finished.\n\n"
        # TODO: Get texture export status if possible
        final_message += f"MTL Files Exported: {mtl_exported_count}\n"
        final_message += f"MTL Export Errors: {mtl_error_count}"
        if mtl_error_count > 0:
             final_message += "\n\nErrors:\n" + "\n".join(mtl_error_messages)

        if mtl_error_count > 0:
             messagebox.showwarning(summary_title, final_message)
        else:
             messagebox.showinfo(summary_title, final_message)

    def _on_export_model(self):
        """
        Handler for Export Model button. Exports MTL files for ALL imported models.
        """
        settings = self.get_settings()
        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory") # Needed for finding processed textures

        if not model_output_dir:
             messagebox.showwarning(
                 get_text("export.warning", "Warning"),
                 get_text("export.no_model_dir", "Please select a Model Output Directory first.")
             )
             return

        # --- Get Managers and Model Data ---
        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)
        model_import_panel = getattr(main_window, "model_import_panel", None) # Access via main_window
        texture_manager = None
        if main_window and hasattr(main_window, "get_texture_manager"):
             texture_manager = main_window.get_texture_manager() # Use the getter method

        if not model_import_panel or not hasattr(model_import_panel, "imported_models_info"):
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access model import panel data.")
             return
        if not texture_manager:
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access Texture Manager.")
             return

        all_imported_models = model_import_panel.imported_models_info
        if not all_imported_models:
            messagebox.showinfo(get_text("export.info", "Info"), "No models have been imported yet.")
            return

        # --- Process Each Model ---
        texture_extractor = TextureExtractor() # To get original texture refs if needed
        exported_count = 0
        error_count = 0
        error_messages = []

        for model_info in all_imported_models:
            model_obj = model_info.get("model_obj")
            model_filename = model_info.get("filename", "unknown_model")
            mtl_filename = f"{os.path.splitext(model_filename)[0]}.mtl"

            if not model_obj or model_obj.get("is_dummy"):
                print(f"Skipping MTL export for failed/dummy model: {model_filename}")
                continue

            print(f"Processing model for MTL export: {model_filename}")

            # --- Build materials_data with PROCESSED texture paths ---
            materials_data_for_mtl = []
            try:
                # Option 1: Assume model_obj contains original material/texture info
                original_materials = model_obj.get("materials", [])
                if not original_materials:
                     print(f"Model {model_filename} has no materials. Skipping.")
                     continue

                for orig_mat in original_materials:
                    mat_name = orig_mat.get('name', 'UnnamedMaterial')
                    processed_textures = {} # Dict for {type: processed_path}

                    # Get original texture paths associated with this material
                    # This might require iterating through texture_refs extracted earlier
                    # or re-extracting specifically for this material.
                    # Let's assume we can get original paths per material.
                    # Example: orig_textures = get_original_textures_for_material(model_obj, mat_name)
                    # For simplicity, let's re-extract all textures and filter by material name
                    # (This might be inefficient for complex models)
                    all_orig_refs = texture_extractor.extract(model_obj)
                    material_orig_refs = [ref for ref in all_orig_refs if ref.material_name == mat_name]

                    # --- Find processed textures by checking expected output filenames (using UI output format) ---
                    output_format = settings.get("output_format", "tif") # Get format from settings
                    output_suffixes = {
                        "diffuse": f"_diff.{output_format}",
                        "normal": f"_ddna.{output_format}",
                        "specular": f"_spec.{output_format}",
                        "displacement": f"_displ.{output_format}",
                        "emissive": f"_emissive.{output_format}",
                        "opacity": f"_opacity.{output_format}", # Adjust if opacity has different suffix/format
                        "sss": f"_sss.{output_format}" # Added SSS
                    }

                    base_name = None
                    # Try to get base_name using classify_texture first
                    for orig_ref in material_orig_refs:
                        if orig_ref.path and os.path.exists(orig_ref.path):
                            try:
                                _, potential_base = texture_manager.classify_texture(orig_ref.path)
                                if potential_base:
                                    base_name = potential_base
                                    print(f"Determined base name '{base_name}' for material '{mat_name}' using texture '{orig_ref.path}'")
                                    break
                            except Exception as classify_error:
                                print(f"Could not classify {orig_ref.path} to get base name: {classify_error}")

                    # Fallback if classify didn't work
                    if not base_name and material_orig_refs:
                        first_tex_path = material_orig_refs[0].path
                        if first_tex_path:
                            filename_no_ext = os.path.splitext(os.path.basename(first_tex_path))[0]
                            # Slightly improved fallback: remove common suffixes if classify failed
                            common_suffixes_to_remove = ['_diff', '_color', '_albedo', '_n', '_normal', '_spec', '_specular', '_h', '_height', '_disp', '_e', '_emissive']
                            potential_base = filename_no_ext
                            for common_suffix in common_suffixes_to_remove:
                                if potential_base.lower().endswith(common_suffix):
                                    potential_base = potential_base[:-len(common_suffix)]
                                    break # Assume only one suffix needs removal
                            base_name = potential_base
                            print(f"Warning: Using fallback base name '{base_name}' for material '{mat_name}' derived from '{filename_no_ext}'")

                    if base_name:
                        print(f"Attempting to find textures for base name: '{base_name}' in '{texture_output_dir}'")
                        # Check for expected output files using the determined base name and output format
                        for type_key, suffix in output_suffixes.items():
                            expected_filename = f"{base_name}{suffix}"
                            expected_path = os.path.join(texture_output_dir, expected_filename)
                            print(f"  Checking for: {expected_path}") # Debug print
                            if os.path.exists(expected_path):
                                processed_textures[type_key] = expected_path
                                print(f"    Found!") # Debug print
                            # else:
                            #    print(f"    Not found.") # Debug print
                    else:
                        print(f"Warning: Could not determine base name for material '{mat_name}'. Cannot find processed textures.")

                    materials_data_for_mtl.append({
                        'name': mat_name,
                        'textures': processed_textures
                    })

            except Exception as e:
                 error_msg = f"Error processing material data for {model_filename}: {e}"
                 print(error_msg)
                 error_messages.append(error_msg)
                 error_count += 1
                 continue # Skip to next model

            # --- Call the MTL Exporter for this model ---
            if not materials_data_for_mtl:
                 print(f"No processable material data found for {model_filename} after checking textures. Skipping MTL export.")
                 continue

            print(f"Attempting to export MTL: {mtl_filename} to {model_output_dir}")
            try:
                success, result_path_or_msg = export_mtl(
                    materials_data_for_mtl,
                    model_output_dir,
                    texture_output_dir, # Pass texture dir for context
                    mtl_filename
                )
                if success:
                    exported_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"{model_filename}: {result_path_or_msg}")
            except Exception as e:
                 error_count += 1
                 error_msg = f"Unexpected error exporting MTL for {model_filename}: {e}"
                 print(error_msg)
                 error_messages.append(error_msg)
                 import traceback
                 traceback.print_exc()

        # --- Show Summary Message ---
        summary_title = get_text("export.export_model", "Export Model")
        if exported_count > 0 and error_count == 0:
            messagebox.showinfo(summary_title, f"Successfully exported {exported_count} MTL file(s).")
        elif exported_count > 0 and error_count > 0:
             messagebox.showwarning(summary_title, f"Exported {exported_count} MTL file(s) with {error_count} error(s):\n\n" + "\n".join(error_messages))
        elif exported_count == 0 and error_count > 0:
             messagebox.showerror(summary_title, f"Failed to export any MTL files. {error_count} error(s) occurred:\n\n" + "\n".join(error_messages))
        else: # No models processed or no errors but nothing exported
             messagebox.showinfo(summary_title, "No MTL files were exported (check if models have materials/textures).")


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
        # --- Restore original Batch Process logic ---
        # This button should now behave exactly like the original "Batch Process" button.
        # It calls start_batch_processing on the main window instance.
        print("Export Textures button clicked. Triggering main batch processing...")
        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)

        if main_window and hasattr(main_window, "start_batch_processing"):
            try:
                # Call the main batch processing function.
                # It should internally handle getting settings and the output directory.
                main_window.start_batch_processing()
            except Exception as e:
                messagebox.showerror(get_text("export.error", "Error"), f"Failed to start texture processing: {e}")
                import traceback
                traceback.print_exc()
        else:
            # This error message should now correctly indicate if the function is missing on MainWindow
            messagebox.showerror(get_text("export.error", "Error"), "Texture processing function (start_batch_processing) not found in main application window.")
