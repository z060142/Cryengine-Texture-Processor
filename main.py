#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CryEngine Texture Processor - Main Entry Point

This module serves as the entry point for the CryEngine Texture Processor application.
It initializes the UI and connects it to the core processing components.
"""

import os
import sys
import time # Import the time module
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ui.main_window import MainWindow
from ui.progress_dialog import ProgressDialog
from language.language_manager import get_instance as get_language_manager
from language.language_manager import get_text
from utils.config_manager import ConfigManager
import traceback # Needed for error reporting
from core.batch_processor import BatchProcessor
from utils.dds_processor import DDSProcessor
from model_processing.texture_extractor import TextureExtractor # Needed for MTL export
from output_formats.mtl_exporter import export_mtl # Needed for MTL export

def main():
    """
    Main function to initialize and run the application.
    """
    # Configure garbage collection for better memory management
    import gc
    gc.enable()
    
    # Add signal handlers for clean shutdown
    import signal
    import atexit
    
    def cleanup():
        print("Performing cleanup...")
        gc.collect()
    
    def signal_handler(sig, frame):
        print("\nCleaning up and shutting down...")
        cleanup()
        sys.exit(0)
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination
    except (AttributeError, ValueError):
        # SIGTERM might not be available on Windows or signal already handled
        pass
    
    # Configure NumPy warnings
    try:
        import numpy as np
        np.seterr(all='warn')  # Set NumPy to warn instead of raise exceptions
        print(f"NumPy version: {np.__version__}")
    except ImportError:
        print("NumPy not available - some functionality may be limited")
    except Exception as e:
        print(f"Error configuring NumPy: {e}")
    
    # Load configuration
    config_manager = ConfigManager()
    
    # Initialize language system
    language_manager = get_language_manager()
    
    # Load saved language preference
    saved_language = config_manager.get("language", "EN")
    if saved_language and saved_language != language_manager.get_current_language():
        language_manager.load_language(saved_language)
    
    # Create Tkinter root window
    root = tk.Tk()
    root.title(get_text("app.title", "CryEngine Texture Processor"))
    
    # Set window size
    window_width = 1200
    window_height = 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Center window
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Set minimum size
    root.minsize(800, 600)
    
    # Add icon if available
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass  # Ignore icon errors
    
    # Create and initialize main window
    app = MainWindow(root)

    # Define batch processing function (now accepts optional settings)
    def start_batch_processing(texture_groups=None, export_settings=None):
        """
        Starts the batch processing for textures.

        Args:
            texture_groups (list, optional): List of TextureGroup objects to process.
                                            If None, uses all groups from TextureManager.
            export_settings (dict, optional): Dictionary of export settings.
                                             If None, retrieves settings from the UI panel.
        """
        print(f"start_batch_processing called with {len(texture_groups) if texture_groups else 'all'} groups and {'provided' if export_settings else 'no'} settings.")

        # Use the texture manager from texture import panel
        texture_manager = app.texture_import_panel.texture_manager
        if not texture_manager:
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access Texture Manager.")
             return

        # Create batch processor using this texture manager
        batch_processor = BatchProcessor(texture_manager)

        # Get texture groups if not provided
        if texture_groups is None:
            texture_groups = texture_manager.get_all_groups()
            print(f"Retrieved {len(texture_groups)} groups from TextureManager.")

        # Get export settings if not provided, otherwise use the provided ones
        settings = export_settings if export_settings is not None else app.export_settings_panel.get_settings()
        print(f"Using settings: {settings}")

        # Get output directory - PRIORITIZE provided settings, then UI, then prompt
        output_dir = settings.get("texture_output_directory", "") # Use the correct key
        print(f"Output directory from settings: '{output_dir}'")

        if not output_dir:
             # If not in provided settings (or settings were None), check UI panel directly
             output_dir = app.export_settings_panel.texture_output_dir_var.get()
             print(f"Output directory from UI variable: '{output_dir}'")
             if not output_dir:
                 # Only prompt if BOTH provided settings AND UI field are empty
                 print("Output directory is empty, prompting user...")
                 output_dir = filedialog.askdirectory(
                     title=get_text("export.select_texture_directory", "Select Texture Output Directory"), # Use correct text key
                     initialdir=os.getcwd()
                 )
                 if not output_dir:
                     print("User cancelled directory selection.")
                     return  # Cancelled

                 # If user selected a directory via prompt, update the UI and settings
                 print(f"User selected directory: {output_dir}")
                 settings["texture_output_directory"] = output_dir
                 app.export_settings_panel.set_settings(settings) # Update panel to reflect selection
             else:
                 # If directory was found in UI var but not settings dict, update settings dict
                 settings["texture_output_directory"] = output_dir

        # Ensure the final output_dir is used (and exists)
        final_output_dir = settings.get("texture_output_directory")
        if not final_output_dir:
             messagebox.showerror(get_text("export.error", "Error"), "Output directory could not be determined.")
             return
        
        # Check if the final output directory exists and create if needed
        if not os.path.exists(final_output_dir):
            try:
                print(f"Creating output directory: {final_output_dir}")
                os.makedirs(final_output_dir)
                # Update UI status if possible (might need a reference back)
                if hasattr(app.export_settings_panel, "_update_texture_dir_status"):
                     app.export_settings_panel._update_texture_dir_status()
            except Exception as e:
                 messagebox.showerror(
                     get_text("export.error", "Error"),
                     get_text("export.create_texture_dir_error", "Failed to create texture output directory: {0}").format(str(e)) # Use correct text key
                 )
                 return

        # Set batch processor settings using the final determined settings and directory
        batch_processor.set_output_dir(final_output_dir)
        batch_processor.set_settings(settings) # Pass the potentially updated settings
        
        # Check if we have texture groups to process
        if len(texture_groups) == 0:
            messagebox.showwarning(
                get_text("export.warning", "Warning"),
                get_text("export.no_textures", "No texture groups to process.")
            )
            return
        
        # Debug output - show how many groups we have
        print(f"Processing {len(texture_groups)} texture groups")
        for i, group in enumerate(texture_groups):
            print(f"Group {i+1}: {group.base_name}")
            for texture_type, texture in group.textures.items():
                if texture_type == "unknown":
                    unknown_count = len(texture) if isinstance(texture, list) else 0
                    if unknown_count > 0:
                        print(f"  {texture_type}: {unknown_count} textures")
                elif texture is not None:
                    print(f"  {texture_type}: {os.path.basename(texture.get('path', 'N/A'))}")
        
        # Update status
        app.update_status(get_text("status.preparing", "Preparing for batch processing..."))
        
        # Create progress dialog
        progress_dialog = ProgressDialog(
            root,
            get_text("progress.processing", "Processing Textures")
        )
        
        # Set callbacks
        # Updated progress_callback to handle the new signature from BatchProcessor
        def progress_callback(progress, stage_text, current_task, status):
            # Update the stage text in the dialog
            if hasattr(progress_dialog, 'update_stage'): # Check if method exists
                 progress_dialog.update_stage(stage_text)
            # Update the regular progress elements
            progress_dialog.update_progress(progress, current_task, status)
            
            # Update application status bar with the current task
            if current_task:
                app.update_status(current_task)
        
        def cancel_callback():
            batch_processor.cancel()
            app.update_status(get_text("status.cancelling", "Cancelling..."))
            # Ensure the dialog reflects cancellation immediately if possible
            if progress_dialog:
                 progress_dialog.update_progress(progress_dialog.progress_var.get() / 100.0, "Cancelling...", "")
        
        progress_dialog.set_cancel_callback(cancel_callback)
        batch_processor.set_progress_callback(progress_callback)
        
        # Start processing
        batch_processor.process_all_groups()
        
        # --- Refactored Monitoring Logic ---
        # This function now returns True for success, False for failure/cancel
        processing_successful = True # Assume success initially

        # Monitor processing thread
        while batch_processor.is_processing():
            # Check for cancellation via dialog
            if progress_dialog.is_cancelled():
                 batch_processor.cancel() # Ensure processor knows
                 processing_successful = False
                 break
            root.update() # Keep UI responsive
            time.sleep(0.1) # Wait a bit

        # Check final status after loop exits
        if progress_dialog.is_cancelled():
            processing_successful = False
            progress_dialog.show_completion(False, True) # Show cancelled state
            app.update_status(get_text("status.processing_cancelled", "Processing cancelled"))
        elif batch_processor.cancel_flag: # Check processor flag too
             processing_successful = False
             progress_dialog.show_completion(False, True) # Show cancelled state
             app.update_status(get_text("status.processing_cancelled", "Processing cancelled"))
        else:
            # Processing finished (not cancelled), now check for DDS
            if settings.get("generate_cry_dds", False):
                # Get generated TIF files
                tif_files = []
                for group in texture_groups:
                    for output_type, output_path in group.output.items():
                        if output_path and output_path.lower().endswith(".tif"):
                            tif_files.append(output_path)
                
                if tif_files and settings.get("output_format", "tif").lower() == "tif":
                    # --- DDS Processing Stage ---
                    dds_stage_text = "Post-Process: Generating DDS"
                    app.update_status(get_text("status.generating_dds", "Generating DDS files..."))
                    # Update dialog for DDS stage
                    if hasattr(progress_dialog, 'update_stage'):
                         progress_dialog.update_stage(dds_stage_text)
                    progress_dialog.update_progress(0.0, get_text("progress.generating_dds", "Generating CryEngine DDS files"), "") # Reset progress for DDS

                    dds_processor = DDSProcessor()
                    
                    # DDS Progress Callback (simpler, only updates progress/current/status)
                    def dds_progress_callback(progress, current, status):
                         progress_dialog.update_progress(progress, current, status)
                         if current: app.update_status(current)

                    dds_processor.set_progress_callback(dds_progress_callback)
                    dds_processor.process_tif_files(tif_files)
                    
                    # Monitor DDS processing
                    while dds_processor.is_processing():
                         if progress_dialog.is_cancelled(): # Allow cancelling DDS too
                             dds_processor.cancel()
                             processing_successful = False
                             break
                         root.update()
                         time.sleep(0.1)

                    if progress_dialog.is_cancelled() or dds_processor.cancel_flag:
                         processing_successful = False
                         progress_dialog.show_completion(False, True)
                         app.update_status(get_text("status.dds_cancelled", "DDS generation cancelled"))
                    else:
                         # DDS completed successfully
                         progress_dialog.show_completion(True, True)
                         app.update_status(get_text("status.processing_complete", f"Processing complete. Processed {len(texture_groups)} groups, generated DDS."))
                else:
                    # No TIF files or output format not TIF, DDS skipped
                    progress_dialog.show_completion(True, True)
                    app.update_status(get_text("status.processing_complete", f"Processing complete. Processed {len(texture_groups)} groups."))
            else:
                # No DDS generation needed, just show completion
                progress_dialog.show_completion(True, True)
                app.update_status(get_text("status.processing_complete", f"Processing complete. Processed {len(texture_groups)} groups."))

        # Return the final success status
        return processing_successful
    
    # --- New Function for FBX Export ---
    def run_model_fbx_export(settings, progress_dialog=None):
        """
        Exports FBX files with properly configured materials for all imported models.
        Removes original shader nodes and creates new ones with diff and ddna textures.
        每個模型導出時會單獨處理，確保每個FBX文件只包含一個模型。
        
        Args:
            settings (dict): Export settings dictionary.
            progress_dialog (ProgressDialog, optional): Dialog to update.
            
        Returns:
            tuple: (exported_count, error_count, error_messages)
        """
        from model_processing.fbx_exporter import FbxExporter
        from model_processing.model_loader import ModelLoader  # 引入ModelLoader以重新加載模型
        
        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory")
        texture_rel_dir = "textures"  # Relative directory path for textures
        
        # --- Get Managers and Model Data ---
        model_import_panel = getattr(app, "model_import_panel", None)
        texture_manager = getattr(app, "texture_import_panel", None).texture_manager if hasattr(app, "texture_import_panel") else None
        
        if not model_import_panel or not hasattr(model_import_panel, "imported_models_info"):
            messagebox.showerror(get_text("export.error", "Error"), "Cannot access model import panel data.")
            return 0, 1, ["Cannot access model import panel data."]
        if not texture_manager:
            messagebox.showerror(get_text("export.error", "Error"), "Cannot access Texture Manager.")
            return 0, 1, ["Cannot access Texture Manager."]
            
        all_imported_models = model_import_panel.imported_models_info
        if not all_imported_models:
            messagebox.showinfo(get_text("export.info", "Info"), "No models have been imported yet.")
            return 0, 0, []
        
        # 創建模型加載器和FBX導出器
        model_loader = ModelLoader()
        fbx_exporter = FbxExporter()
        
        # 檢查初始化是否成功
        if not fbx_exporter.initialized or not model_loader.bpy:
            error_msg = "FBX exporter or model loader could not be initialized. Blender Python API (bpy) is not available."
            print(f"ERROR: {error_msg}")
            print("This usually means that either:")
            print("1. Blender is not installed on this system, or")
            print("2. The Python environment doesn't have access to the Blender Python modules")
            print("3. There might be a version incompatibility between Python and Blender")
            
            messagebox.showerror(
                get_text("export.error", "Error"), 
                error_msg + "\n\nPlease ensure Blender is installed and the Python environment has access to bpy."
            )
            return 0, 1, ["Blender Python API (bpy) is not available. Cannot export FBX."]
            
        # --- Process Each Model ---
        texture_extractor = TextureExtractor()
        exported_count = 0
        error_count = 0
        error_messages = []
        total_models = len(all_imported_models)
        
        # Update progress dialog if provided
        if progress_dialog:
            if hasattr(progress_dialog, 'update_stage'):
                progress_dialog.update_stage("Exporting Models (FBX)")
            progress_dialog.update_progress(0.0, "Starting FBX export...", f"Found {total_models} models")
            
        for i, model_info in enumerate(all_imported_models):
            # Check for cancellation
            if progress_dialog and progress_dialog.is_cancelled():
                error_messages.append("FBX export cancelled by user.")
                error_count += (total_models - i)  # Count remaining as errors/skipped
                break
                
            model_path = model_info.get("path", "")
            model_filename = model_info.get("filename", "unknown_model")
            base_filename = os.path.splitext(model_filename)[0]
            fbx_filename = f"{base_filename}.fbx"
            fbx_output_path = os.path.join(model_output_dir, fbx_filename)
            
            # Update progress
            current_progress = (i + 1) / total_models
            if progress_dialog:
                progress_dialog.update_progress(
                    current_progress, 
                    f"Processing: {model_filename}", 
                    f"Model {i+1} of {total_models}"
                )
                root.update()  # Keep UI responsive
            
            # 檢查路徑是否有效
            if not model_path or not os.path.exists(model_path):
                print(f"Skipping FBX export - invalid model path: {model_path}")
                error_count += 1
                error_messages.append(f"Invalid model path: {model_path}")
                continue
            
            # 跳過不能處理的模型類型
            if model_info.get("is_dummy", False):
                print(f"Skipping FBX export for dummy model: {model_filename}")
                continue
            
            if model_info.get("is_import_only", False):
                print(f"Skipping FBX export for import-only model: {model_filename}")
                print(f"This model was loaded with the alternative import method for texture extraction only.")
                continue
            
            print(f"Processing model for FBX export: {model_filename}")
            
            # 清除場景並重新加載當前模型
            try:
                print(f"Clearing scene and loading model: {model_filename}")
                # 使用 model_loader 的 _clear_scene 方法清除場景
                model_loader._clear_scene()  
                
                # 重新加載當前模型
                reloaded_model = model_loader.load(model_path)
                
                if not reloaded_model or reloaded_model.get("is_dummy", False):
                    print(f"Failed to reload model: {model_filename}")
                    error_count += 1
                    error_messages.append(f"Failed to reload model: {model_filename}")
                    continue
                
                print(f"Successfully reloaded model: {model_filename}")
                
                # 確保模型輸出目錄中的紋理子目錄存在
                model_texture_dir = os.path.join(model_output_dir, texture_rel_dir)
                os.makedirs(model_texture_dir, exist_ok=True)
                
                # 處理材質和導出FBX
                materials_texture_data = {}
                
                # 獲取所有材質
                original_materials = reloaded_model.get("materials", [])
                if not original_materials:
                    print(f"Model {model_filename} has no materials. Skipping.")
                    continue
                
                # 提取紋理引用
                all_orig_refs = texture_extractor.extract(reloaded_model)
                
                # 處理每個材質
                for orig_mat in original_materials:
                    mat_name = orig_mat.get('name', 'UnnamedMaterial')
                    # 跳過默認Blender材質
                    if mat_name in ["Material", "Dots Stroke"]:
                        continue
                    
                    # 獲取該材質的紋理引用
                    material_orig_refs = [ref for ref in all_orig_refs if ref.material_name == mat_name]
                    
                    # 確定用於查找已處理紋理的基本名稱
                    output_format = settings.get("output_format", "tif")
                    base_name = None
                    
                    # 嘗試從紋理管理器獲取基本名稱
                    for orig_ref in material_orig_refs:
                        if orig_ref.path and os.path.exists(orig_ref.path):
                            try:
                                _, potential_base = texture_manager.classify_texture(orig_ref.path)
                                if potential_base:
                                    base_name = potential_base
                                    break
                            except Exception:
                                pass
                    
                    # 如果無法獲取基本名稱，使用回退方法
                    if not base_name and material_orig_refs and material_orig_refs[0].path:
                        filename_no_ext = os.path.splitext(os.path.basename(material_orig_refs[0].path))[0]
                        common_suffixes = ['_diff', '_color', '_albedo', '_n', '_normal', '_spec', '_specular']
                        potential_base = filename_no_ext
                        for common_suffix in common_suffixes:
                            if potential_base.lower().endswith(common_suffix):
                                potential_base = potential_base[:-len(common_suffix)]
                                break
                        base_name = potential_base
                    
                    # 如果沒有基本名稱，跳過該材質
                    if not base_name:
                        print(f"Warning: Could not determine base name for material '{mat_name}'.")
                        continue
                    
                    # 查找已處理的紋理
                    texture_data = {}
                    
                    # 查找diff紋理
                    diff_path = os.path.join(texture_output_dir, f"{base_name}_diff.{output_format}")
                    if os.path.exists(diff_path):
                        texture_data['diff'] = diff_path
                    
                    # 查找ddna紋理
                    ddna_path = os.path.join(texture_output_dir, f"{base_name}_ddna.{output_format}")
                    if os.path.exists(ddna_path):
                        texture_data['ddna'] = ddna_path
                    
                    # 如果找到了有效的紋理數據，則存儲該材質的紋理數據
                    if texture_data:
                        materials_texture_data[mat_name] = texture_data
                
                # 如果沒有有效的材質紋理數據，跳過導出
                if not materials_texture_data:
                    print(f"No processed textures found for model {model_filename}. Skipping FBX export.")
                    continue
                
                print(f"Found texture data for {len(materials_texture_data)} materials in {model_filename}")
                
                # 調用FBX導出器導出模型
                print(f"Calling fbx_exporter.export for {model_filename}")
                print(f"- Output path: {fbx_output_path}")
                print(f"- Texture directory: {texture_rel_dir}")
                print(f"- Materials data: {list(materials_texture_data.keys())}")
                
                result = fbx_exporter.export(
                    reloaded_model,
                    fbx_output_path,
                    texture_dir=texture_rel_dir,
                    texture_data=materials_texture_data
                )
                
                if result:
                    exported_count += 1
                    print(f"Successfully exported FBX: {fbx_output_path}")
                else:
                    error_count += 1
                    error_msg = f"Failed to export FBX for {model_filename}"
                    error_messages.append(error_msg)
                    print(error_msg)
                
            except Exception as e:
                error_count += 1
                error_msg = f"Unexpected error exporting FBX for {model_filename}: {e}"
                print(error_msg)
                traceback.print_exc()
                error_messages.append(error_msg)
        
        # 最終進度更新
        if progress_dialog:
            final_progress = 1.0 if not progress_dialog.is_cancelled() else current_progress
            final_message = "FBX export complete" if not progress_dialog.is_cancelled() else "FBX export cancelled"
            progress_dialog.update_progress(
                final_progress, 
                final_message, 
                f"Exported: {exported_count}, Errors: {error_count}"
            )
        
        return exported_count, error_count, error_messages
        
    # --- New Function for Model (MTL) Export ---
    def run_model_mtl_export(settings, progress_dialog=None):
        """
        Exports MTL files for all imported models based on provided settings.
        Updates the provided progress dialog if available.
        每個模型導出時會單獨處理，確保每個MTL文件只包含一個模型的材質信息。

        Args:
            settings (dict): Export settings dictionary.
            progress_dialog (ProgressDialog, optional): Dialog to update.

        Returns:
            tuple: (exported_count, error_count, error_messages)
        """
        from model_processing.model_loader import ModelLoader  # 引入ModelLoader以重新加載模型
        
        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory") # Needed for finding processed textures

        # --- Get Managers and Model Data (Access via app instance) ---
        model_import_panel = getattr(app, "model_import_panel", None)
        texture_manager = getattr(app, "texture_import_panel", None).texture_manager if hasattr(app, "texture_import_panel") else None

        if not model_import_panel or not hasattr(model_import_panel, "imported_models_info"):
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access model import panel data.")
             return 0, 1, ["Cannot access model import panel data."]
        if not texture_manager:
             messagebox.showerror(get_text("export.error", "Error"), "Cannot access Texture Manager.")
             return 0, 1, ["Cannot access Texture Manager."]

        all_imported_models = model_import_panel.imported_models_info
        if not all_imported_models:
            messagebox.showinfo(get_text("export.info", "Info"), "No models have been imported yet.")
            return 0, 0, []
            
        # 創建模型加載器
        model_loader = ModelLoader()
        if not model_loader.bpy:
            print("Warning: Blender Python API not available, but continuing with MTL export as it doesn't require BPY.")

        # --- Process Each Model ---
        texture_extractor = TextureExtractor()
        exported_count = 0
        error_count = 0
        error_messages = []
        total_models = len(all_imported_models)

        # Update progress dialog if provided
        if progress_dialog:
             if hasattr(progress_dialog, 'update_stage'):
                 progress_dialog.update_stage("Exporting Models (MTL)")
             progress_dialog.update_progress(0.0, "Starting MTL export...", f"Found {total_models} models")

        for i, model_info in enumerate(all_imported_models):
            # Check for cancellation
            if progress_dialog and progress_dialog.is_cancelled():
                 error_messages.append("MTL export cancelled by user.")
                 error_count += (total_models - i) # Count remaining as errors/skipped
                 break

            model_path = model_info.get("path", "")
            model_filename = model_info.get("filename", "unknown_model")
            mtl_filename = f"{os.path.splitext(model_filename)[0]}.mtl"

            # Update progress
            current_progress = (i + 1) / total_models
            if progress_dialog:
                 progress_dialog.update_progress(current_progress, f"Processing: {model_filename}", f"Model {i+1} of {total_models}")
                 root.update() # Keep UI responsive
                 
            # 檢查路徑是否有效
            if not model_path or not os.path.exists(model_path):
                print(f"Skipping MTL export - invalid model path: {model_path}")
                error_count += 1
                error_messages.append(f"Invalid model path: {model_path}")
                continue

            # 跳過不能處理的模型類型
            if model_info.get("is_dummy", False) or model_info.get("is_import_only", False):
                print(f"Skipping MTL export for failed/dummy/import-only model: {model_filename}")
                continue
                
            # MTL導出不需要完整的Blender場景，所以不必重新加載模型
            # 但我們需要准備只將當前一個模型的材質加入MTL文件
            print(f"Processing model for MTL export: {model_filename}")
            model_obj = model_info.get("model_obj")
            if not model_obj:
                print(f"Warning: No model object data available for {model_filename}, trying to extract materials from path")
                continue

            # 為當前模型初始化材質數據列表            
            materials_data_for_mtl = []
            try:
                original_materials = model_obj.get("materials", [])
                if not original_materials:
                     print(f"Model {model_filename} has no materials. Skipping.")
                     continue

                # 自已存在的模型數據提取所有材質信息
                for orig_mat in original_materials:
                    mat_name = orig_mat.get('name', 'UnnamedMaterial')
                    # 如果需要，遍過默認Blender材質
                    if mat_name in ["Material", "Dots Stroke"]: 
                        continue

                    processed_textures = {}
                    # 只提取該模型的紋理引用
                    all_orig_refs = texture_extractor.extract(model_obj)
                    material_orig_refs = [ref for ref in all_orig_refs if ref.material_name == mat_name]

                    output_format = settings.get("output_format", "tif")
                    output_suffixes = {
                        "diffuse": f"_diff.{output_format}", "normal": f"_ddna.{output_format}",
                        "specular": f"_spec.{output_format}", "displacement": f"_displ.{output_format}",
                        "emissive": f"_emissive.{output_format}", "opacity": f"_opacity.{output_format}",
                        "sss": f"_sss.{output_format}"
                    }
                    base_name = None
                    for orig_ref in material_orig_refs:
                        if orig_ref.path and os.path.exists(orig_ref.path):
                            try:
                                _, potential_base = texture_manager.classify_texture(orig_ref.path)
                                if potential_base:
                                    base_name = potential_base
                                    break
                            except Exception: pass

                    if not base_name and material_orig_refs and material_orig_refs[0].path:
                         filename_no_ext = os.path.splitext(os.path.basename(material_orig_refs[0].path))[0]
                         common_suffixes_to_remove = ['_diff', '_color', '_albedo', '_n', '_normal', '_spec', '_specular', '_h', '_height', '_disp', '_e', '_emissive']
                         potential_base = filename_no_ext
                         for common_suffix in common_suffixes_to_remove:
                             if potential_base.lower().endswith(common_suffix):
                                 potential_base = potential_base[:-len(common_suffix)]
                                 break
                         base_name = potential_base

                    if base_name:
                        for type_key, suffix in output_suffixes.items():
                            expected_filename = f"{base_name}{suffix}"
                            expected_path = os.path.join(texture_output_dir, expected_filename)
                            if os.path.exists(expected_path):
                                processed_textures[type_key] = expected_path
                    else:
                        print(f"Warning: Could not determine base name for material '{mat_name}'.")

                    materials_data_for_mtl.append({'name': mat_name, 'textures': processed_textures})

            except Exception as e:
                 error_msg = f"Error processing material data for {model_filename}: {e}"
                 print(error_msg)
                 traceback.print_exc()
                 error_messages.append(error_msg)
                 error_count += 1
                 continue

            if not materials_data_for_mtl:
                 print(f"No processable material data found for {model_filename}. Skipping MTL export.")
                 continue

            print(f"Attempting to export MTL: {mtl_filename} to {model_output_dir}")
            try:
                success, result_path_or_msg = export_mtl(materials_data_for_mtl, model_output_dir, texture_output_dir, mtl_filename)
                if success:
                    exported_count += 1
                    print(f"Successfully exported MTL: {result_path_or_msg}")
                else:
                    error_count += 1
                    error_messages.append(f"{model_filename}: {result_path_or_msg}")
                    print(f"Failed to export MTL: {result_path_or_msg}")
            except Exception as e:
                 error_count += 1
                 error_msg = f"Unexpected error exporting MTL for {model_filename}: {e}"
                 print(error_msg)
                 traceback.print_exc()
                 error_messages.append(error_msg)

        # Final progress update
        if progress_dialog:
             final_progress = 1.0 if not progress_dialog.is_cancelled() else current_progress
             final_message = "MTL export complete" if not progress_dialog.is_cancelled() else "MTL export cancelled"
             progress_dialog.update_progress(final_progress, final_message, f"Exported: {exported_count}, Errors: {error_count}")
             # Don't close the dialog here, let the caller handle it

        return exported_count, error_count, error_messages

    # Assign the functions to the main window instance
    app.start_batch_processing = start_batch_processing
    app.run_model_mtl_export = run_model_mtl_export
    app.run_model_fbx_export = run_model_fbx_export

    # Run application event loop
    try:
        root.mainloop()
    finally:
        # Perform cleanup when application exits
        print("Application closing, performing final cleanup...")
        # Force garbage collection
        import gc
        gc.collect()
        # Release any other resources if needed
        # ...
        print("Cleanup completed")

if __name__ == "__main__":
    main()
