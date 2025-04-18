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
from ui.progress_dialog import ProgressDialog
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
            "output_resolution": "original",  # Output resolution
            "delete_after_export": {
                "tif": False,
                "fbx": False,
                "json": True
            }
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
        
        # Create texture export settings frame
        settings_frame = ttk.LabelFrame(main_frame, text=get_text("export.settings", "Texture Export Settings"))
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Settings content frame with padding
        settings_content = ttk.Frame(settings_frame, padding=10)
        settings_content.pack(fill=tk.X, expand=True)
        
        # Add CryEngine DDS checkbox
        self.generate_dds_var = tk.BooleanVar(value=self.settings.get("generate_cry_dds", False))
        dds_checkbutton = ttk.Checkbutton(
            settings_content,
            text=get_text("export.generate_cry_dds", "Generate CryEngine DDS"),
            variable=self.generate_dds_var,
            command=self._update_tif_delete_state
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
        types_frame.pack(fill=tk.X, padx=5, pady=5)
        
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
        
        # Create model export settings frame
        model_settings_frame = ttk.LabelFrame(main_frame, text=get_text("export.model_settings", "Model Export Settings"))
        model_settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Model settings content frame with padding
        model_settings_content = ttk.Frame(model_settings_frame, padding=10)
        model_settings_content.pack(fill=tk.X, expand=True)
        
        # Model export settings options would go here
        # For now, we'll just add a placeholder label
        model_settings_label = ttk.Label(model_settings_content, text=get_text("export.model_settings_note", "Model export settings will be added here."))
        model_settings_label.pack(padx=5, pady=5)
        
        # Create miscellaneous settings frame
        misc_frame = ttk.LabelFrame(main_frame, text=get_text("export.misc_settings", "Miscellaneous Settings"))
        misc_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Misc settings content frame with padding
        misc_content = ttk.Frame(misc_frame, padding=10)
        misc_content.pack(fill=tk.X, expand=True)
        
        # Add "Delete after export" checkboxes
        delete_label = ttk.Label(misc_content, text=get_text("export.delete_after_export", "Delete after export:"))
        delete_label.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        # TIF deletion checkbox
        self.delete_tif_var = tk.BooleanVar(value=False)
        self.delete_tif_check = ttk.Checkbutton(
            misc_content,
            text="TIF",
            variable=self.delete_tif_var
        )
        self.delete_tif_check.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # FBX deletion checkbox
        self.delete_fbx_var = tk.BooleanVar(value=False)
        delete_fbx_check = ttk.Checkbutton(
            misc_content,
            text="FBX",
            variable=self.delete_fbx_var
        )
        delete_fbx_check.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        
        # JSON deletion checkbox (default checked)
        self.delete_json_var = tk.BooleanVar(value=True)
        delete_json_check = ttk.Checkbutton(
            misc_content,
            text="JSON",
            variable=self.delete_json_var
        )
        delete_json_check.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
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
        
        # Set initial state of TIF deletion checkbox
        self._update_tif_delete_state()

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
    
    def _update_tif_delete_state(self):
        """Update the TIF deletion checkbox state based on DDS generation state."""
        if hasattr(self, 'delete_tif_check') and hasattr(self, 'generate_dds_var'):
            # Enable TIF deletion only when DDS generation is checked
            dds_enabled = self.generate_dds_var.get()
            if dds_enabled:
                self.delete_tif_check.config(state="normal")
            else:
                # When DDS is not checked, disable TIF deletion and uncheck it
                self.delete_tif_check.config(state="disabled")
                self.delete_tif_var.set(False)

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
        現在會執行完整的導出工作流程，包括紋理導出、MTL文件生成，以及FBX文件導出。
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
        if not hasattr(main_window, "start_batch_processing") or not hasattr(main_window, "run_model_mtl_export") or not hasattr(main_window, "run_model_fbx_export"):
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
            
        # --- 記錄導出前目錄中的檔案 ---
        existing_texture_files = set()
        existing_model_files = set()
        
        # 記錄現有的TIF檔案
        if os.path.exists(texture_output_dir):
            for filename in os.listdir(texture_output_dir):
                if filename.lower().endswith(".tif"):
                    existing_texture_files.add(filename)
        
        # 記錄現有的FBX和JSON檔案
        if os.path.exists(model_output_dir):
            for filename in os.listdir(model_output_dir):
                if filename.lower().endswith(".fbx") or filename.lower().endswith(".json"):
                    existing_model_files.add(filename)

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
            messagebox.showerror(get_text("export.error", "Error"), f"Failed during MTL export stage: {e}")
            import traceback
            traceback.print_exc()
            # Continue to show summary even if this stage fails
        
        # --- Stage 3: Export Models (FBX) ---
        print("Batch Process - Stage 3: Exporting Models (FBX)...")
        fbx_exported_count = 0
        fbx_error_count = 0
        fbx_error_messages = []
        try:
            # This will show its own progress dialog
            fbx_exported_count, fbx_error_count, fbx_error_messages = main_window.run_model_fbx_export(settings=settings)
            print(f"Batch Process: FBX export finished. Exported: {fbx_exported_count}, Errors: {fbx_error_count}")
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), f"Failed during FBX export stage: {e}")
            import traceback
            traceback.print_exc()
            # Continue to show summary even if this stage fails

        # --- Final Summary ---
        summary_title = get_text("export.batch_process", "Batch Process")
        final_message = "Batch process finished.\n\n"
        final_message += f"Texture Export: {'Success' if texture_export_success else 'Failed/Cancelled'}\n"
        final_message += f"MTL Files Exported: {mtl_exported_count}\n"
        final_message += f"FBX Files Exported: {fbx_exported_count}\n"
        final_message += f"MTL Export Errors: {mtl_error_count}\n"
        final_message += f"FBX Export Errors: {fbx_error_count}"

        # 整合所有錯誤訊息
        all_errors = []
        if mtl_error_count > 0:
            all_errors.extend([f"MTL: {msg}" for msg in mtl_error_messages[:5]])
            if len(mtl_error_messages) > 5:
                all_errors.append(f"... and {len(mtl_error_messages) - 5} more MTL errors")
                
        if fbx_error_count > 0:
            all_errors.extend([f"FBX: {msg}" for msg in fbx_error_messages[:5]])
            if len(fbx_error_messages) > 5:
                all_errors.append(f"... and {len(fbx_error_messages) - 5} more FBX errors")
                
        if all_errors:
            final_message += "\n\nErrors:\n" + "\n".join(all_errors)

        if not texture_export_success or mtl_error_count > 0 or fbx_error_count > 0:
            messagebox.showwarning(summary_title, final_message)
        else:
            messagebox.showinfo(summary_title, final_message)
            
        # --- 找出本次操作生成的新檔案 ---
        new_texture_files = set()
        new_model_files = set()
        
        # 檢查新生成的TIF檔案
        if os.path.exists(texture_output_dir):
            for filename in os.listdir(texture_output_dir):
                if filename.lower().endswith(".tif") and filename not in existing_texture_files:
                    new_texture_files.add(filename)
        
        # 檢查新生成的FBX和JSON檔案
        if os.path.exists(model_output_dir):
            for filename in os.listdir(model_output_dir):
                if filename.lower().endswith((".fbx", ".json")) and filename not in existing_model_files:
                    new_model_files.add(filename)
                    
        print(f"Found {len(new_texture_files)} new TIF files and {len(new_model_files)} new model files")
        
        # 設置臨時屬性，將本次生成的檔案傳遞給清理函數
        self._new_generated_files = {
            "texture": new_texture_files,
            "model": new_model_files
        }
        
        # 如果設置了刪除選項，處理最終的文件清理
        self._process_post_export_cleanup(settings)

    def _on_export_model(self):
        """
        Handler for Export Model button. Calls the MTL and FBX export functions from main.py.
        Exports both MTL materials and FBX models with correctly configured shader nodes.
        """
        settings = self.get_settings()
        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory")

        # Validation checks
        if not model_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), 
                                  get_text("export.no_model_dir", "Please select a Model Output Directory first."))
            return
            
        if not texture_output_dir:
            messagebox.showwarning(get_text("export.warning", "Warning"), 
                                  get_text("export.no_texture_dir", "Please select a Texture Output Directory first."))
            return

        # Get main window reference
        root = self.parent.winfo_toplevel()
        main_window = getattr(root, "main_window", None)
        if not main_window:
            messagebox.showerror(get_text("export.error", "Error"), "Cannot access main application window.")
            return
            
        # Check for required export functions
        if not hasattr(main_window, "run_model_mtl_export") or not hasattr(main_window, "run_model_fbx_export"):
            messagebox.showerror(get_text("export.error", "Error"), 
                                "Required model export functions not found in main application.")
            return

        # --- Ensure Model Output Directory Exists ---
        try:
            if not os.path.exists(model_output_dir):
                print(f"Creating model output directory: {model_output_dir}")
                os.makedirs(model_output_dir)
                self._update_model_dir_status()
        except Exception as e:
            messagebox.showerror(get_text("export.error", "Error"), 
                                f"Failed to create model output directory: {e}")
            return
            
        # --- 記錄導出前目錄中的檔案 ---
        existing_model_files = set()
        
        # 記錄現有的FBX和JSON檔案
        if os.path.exists(model_output_dir):
            for filename in os.listdir(model_output_dir):
                if filename.lower().endswith((".fbx", ".json")):
                    existing_model_files.add(filename)

        # --- Create Progress Dialog ---
        progress_dialog = ProgressDialog(
            root,
            title=get_text("export.model_export_title", "Exporting Models..."),
            allow_cancel=True
        )

        # --- Export MTL files first ---
        print("Starting model export process...")
        print("Step 1: Exporting MTL files...")
        try:
            mtl_exported, mtl_errors, mtl_error_msgs = main_window.run_model_mtl_export(
                settings=settings, 
                progress_dialog=progress_dialog
            )
        except Exception as e:
            progress_dialog.close()
            messagebox.showerror(get_text("export.error", "Error"), 
                                f"An unexpected error occurred during MTL export: {e}")
            import traceback
            traceback.print_exc()
            return

        # Check if user cancelled during MTL export
        if progress_dialog.is_cancelled():
            progress_dialog.close()
            messagebox.showinfo(get_text("export.cancelled", "Export Cancelled"), 
                               get_text("export.process_cancelled", "Export process was cancelled."))
            return

        # --- Now export FBX models ---
        print("Step 2: Exporting FBX models with updated materials...")
        try:
            fbx_exported, fbx_errors, fbx_error_msgs = main_window.run_model_fbx_export(
                settings=settings, 
                progress_dialog=progress_dialog
            )
        except Exception as e:
            progress_dialog.close()
            messagebox.showerror(get_text("export.error", "Error"), 
                                f"An unexpected error occurred during FBX export: {e}")
            import traceback
            traceback.print_exc()
            return

        # Close progress dialog
        progress_dialog.close()

        # --- Display Summary Results ---
        total_exported = mtl_exported + fbx_exported
        total_errors = mtl_errors + fbx_errors
        
        # --- 找出本次操作生成的新檔案 ---
        new_model_files = set()
        
        # 檢查新生成的FBX和JSON檔案
        if os.path.exists(model_output_dir):
            for filename in os.listdir(model_output_dir):
                if filename.lower().endswith((".fbx", ".json")) and filename not in existing_model_files:
                    new_model_files.add(filename)
                    
        print(f"Found {len(new_model_files)} new model files")
        
        # 只有当有錯誤時才顯示訊息如
        if total_errors > 0:
            summary_title = get_text("export.export_complete", "Export Complete")
            summary_message = get_text("export.summary", "Export Summary:") + "\n\n"
            summary_message += get_text("export.mtl_files", "MTL Files:") + f" {mtl_exported}" + "\n"
            summary_message += get_text("export.fbx_models", "FBX Models:") + f" {fbx_exported}" + "\n"
            summary_message += "\n" + get_text("export.errors", "Errors:") + f" {total_errors}" + "\n"
            
            if mtl_error_msgs:
                summary_message += "\n" + get_text("export.mtl_errors", "MTL Errors:") + "\n"
                # Limit to first 5 errors to avoid very large message boxes
                for msg in mtl_error_msgs[:5]:
                    summary_message += f"- {msg}\n"
                if len(mtl_error_msgs) > 5:
                    summary_message += f"  (+ {len(mtl_error_msgs) - 5} more errors)\n"
                    
            if fbx_error_msgs:
                summary_message += "\n" + get_text("export.fbx_errors", "FBX Errors:") + "\n"
                # Limit to first 5 errors
                for msg in fbx_error_msgs[:5]:
                    summary_message += f"- {msg}\n"
                if len(fbx_error_msgs) > 5:
                    summary_message += f"  (+ {len(fbx_error_msgs) - 5} more errors)\n"
                    
            # 只有当有錯誤時才顯示訊息如
            messagebox.showwarning(summary_title, summary_message)
            
        # 設置臨時屬性，將本次生成的檔案傳遞給清理函數
        self._new_generated_files = {
            "texture": set(),  # 沒有生成新的紋理檔案
            "model": new_model_files
        }
        
        # 如果設置了刪除選項，處理最終的文件清理
        self._process_post_export_cleanup(settings)

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
        
        # Update delete after export settings
        if not "delete_after_export" in self.settings:
            self.settings["delete_after_export"] = {}
        self.settings["delete_after_export"]["tif"] = self.delete_tif_var.get()
        self.settings["delete_after_export"]["fbx"] = self.delete_fbx_var.get()
        self.settings["delete_after_export"]["json"] = self.delete_json_var.get()
        
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
        
        # Update delete after export settings if available
        if "delete_after_export" in self.settings:
            delete_settings = self.settings["delete_after_export"]
            if "tif" in delete_settings:
                self.delete_tif_var.set(delete_settings["tif"])
            if "fbx" in delete_settings:
                self.delete_fbx_var.set(delete_settings["fbx"])
            if "json" in delete_settings:
                self.delete_json_var.set(delete_settings["json"])
        
        # Update TIF deletion checkbox state
        self._update_tif_delete_state()

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

        # --- 記錄導出前目錄中的檔案 ---
        existing_texture_files = set()
        
        # 記錄現有的TIF檔案
        if os.path.exists(texture_output_dir):
            for filename in os.listdir(texture_output_dir):
                if filename.lower().endswith(".tif"):
                    existing_texture_files.add(filename)

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
            return
            
        # --- 找出本次操作生成的新檔案 ---
        new_texture_files = set()
        
        # 檢查新生成的TIF檔案
        if os.path.exists(texture_output_dir):
            for filename in os.listdir(texture_output_dir):
                if filename.lower().endswith(".tif") and filename not in existing_texture_files:
                    new_texture_files.add(filename)
                    
        print(f"Found {len(new_texture_files)} new TIF files")
        
        # 設置臨時屬性，將本次生成的檔案傳遞給清理函數
        self._new_generated_files = {
            "texture": new_texture_files,
            "model": set()  # 沒有生成新的模型檔案
        }
        
        # 如果設置了刪除選項，處理最終的文件清理
        self._process_post_export_cleanup(settings)
            
    def _process_post_export_cleanup(self, settings):
        """
        處理導出後的文件清理，根據設置中的刪除選項刪除相應文件。
        只刪除本次操作生成的檔案，不會影響之前已存在的檔案。
        
        Args:
            settings (dict): 導出設置字典
        """
        # 目錄路徑
        texture_output_dir = settings.get("texture_output_directory")
        model_output_dir = settings.get("model_output_directory")
        
        # 確保刪除設置存在
        if not "delete_after_export" in settings:
            return
            
        # 確保我們知道哪些是新生成的檔案
        if not hasattr(self, "_new_generated_files"):
            print("No new generated files to clean up")
            return
            
        delete_settings = settings["delete_after_export"]
        new_files = self._new_generated_files
        
        # 累計刪除列表
        deleted_files = []
        failed_files = []
        
        # 處理TIF刪除 - 只刪除新生成的TIF檔案
        if delete_settings.get("tif", False) and settings.get("generate_cry_dds", False):
            for filename in new_files.get("texture", set()):
                if filename.lower().endswith(".tif"):
                    try:
                        file_path = os.path.join(texture_output_dir, filename)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files.append(f"TIF: {filename}")
                    except Exception as e:
                        failed_files.append(f"TIF: {filename} - {str(e)}")
                        print(f"Error deleting TIF file {filename}: {e}")
        
        # 處理FBX刪除 - 只刪除新生成的FBX檔案
        if delete_settings.get("fbx", False):
            for filename in new_files.get("model", set()):
                if filename.lower().endswith(".fbx"):
                    try:
                        file_path = os.path.join(model_output_dir, filename)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files.append(f"FBX: {filename}")
                    except Exception as e:
                        failed_files.append(f"FBX: {filename} - {str(e)}")
                        print(f"Error deleting FBX file {filename}: {e}")
        
        # 處理JSON刪除 - 只刪除新生成的JSON檔案
        if delete_settings.get("json", True):  # JSON預設刪除
            for filename in new_files.get("model", set()):
                if filename.lower().endswith(".json"):
                    try:
                        file_path = os.path.join(model_output_dir, filename)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            deleted_files.append(f"JSON: {filename}")
                    except Exception as e:
                        failed_files.append(f"JSON: {filename} - {str(e)}")
                        print(f"Error deleting JSON file {filename}: {e}")
        
        # 清理臨時屬性
        if hasattr(self, "_new_generated_files"):
            delattr(self, "_new_generated_files")
        
        # 顯示儀要的刪除結果消息
        if deleted_files:
            total_deleted = len(deleted_files)
            message = f"已成功刪除 {total_deleted} 個文件"
            
            # 當有太多文件時，只顯示前幾個
            if len(deleted_files) > 5:
                files_preview = "\n".join(deleted_files[:5])
                message += f"\n\n包括: {files_preview}\n... 及其他 {len(deleted_files) - 5} 個文件"
            else:
                message += "\n\n" + "\n".join(deleted_files)
                
            # 顯示失敗的刪除
            if failed_files:
                message += f"\n\n有 {len(failed_files)} 個文件無法刪除:\n"
                if len(failed_files) > 3:
                    message += "\n".join(failed_files[:3])
                    message += f"\n... 及其他 {len(failed_files) - 3} 個文件"
                else:
                    message += "\n".join(failed_files)
                    
            print(message)
            # 刪除顯示清理結果的訊息對話框
