#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CryEngine Texture Processor - Main Entry Point

This module serves as the entry point for the CryEngine Texture Processor application.
It initializes the UI and connects it to the core processing components.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ui.main_window import MainWindow
from ui.progress_dialog import ProgressDialog
from language.language_manager import get_instance as get_language_manager
from language.language_manager import get_text
from utils.config_manager import ConfigManager
from core.batch_processor import BatchProcessor
from core.texture_manager import TextureManager
from utils.dds_processor import DDSProcessor

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
        def progress_callback(progress, current, status):
            progress_dialog.update_progress(progress, current, status)
            
            # Update application status bar
            if current:
                app.update_status(current)
        
        def cancel_callback():
            batch_processor.cancel()
            app.update_status(get_text("status.cancelling", "Cancelling..."))
        
        progress_dialog.set_cancel_callback(cancel_callback)
        batch_processor.set_progress_callback(progress_callback)
        
        # Start processing
        batch_processor.process_all_groups()
        
        # Monitor processing thread
        def check_processing():
            if batch_processor.is_processing():
                # Check again in 100ms
                root.after(100, check_processing)
            else:
                # Processing complete or cancelled
                if progress_dialog.is_cancelled():
                    progress_dialog.show_completion(False, True)
                    app.update_status(get_text("status.processing_cancelled", "Processing cancelled"))
                else:
                    # Check if we need to generate DDS files
                    if settings.get("generate_cry_dds", False):
                        # Get generated TIF files
                        tif_files = []
                        for group in texture_groups:
                            for output_type, output_path in group.output.items():
                                if output_path and output_path.lower().endswith(".tif"):
                                    tif_files.append(output_path)
                        
                        # If we have TIF files and the output format is TIF, generate DDS files
                        if tif_files and settings.get("output_format", "tif").lower() == "tif":
                            # Update status
                            app.update_status(get_text("status.generating_dds", "Generating DDS files..."))
                            progress_dialog.update_progress(0.0, get_text("progress.generating_dds", "Generating CryEngine DDS files"), "")
                            
                            # Create DDS processor
                            dds_processor = DDSProcessor()
                            
                            # Set progress callback
                            dds_processor.set_progress_callback(progress_callback)
                            
                            # Start DDS processing
                            dds_processor.process_tif_files(tif_files)
                            
                            # Monitor DDS processing
                            def check_dds_processing():
                                if dds_processor.is_processing():
                                    # Check again in 100ms
                                    root.after(100, check_dds_processing)
                                else:
                                    # DDS processing complete
                                    progress_dialog.show_completion(True, True)
                                    app.update_status(get_text("status.processing_complete", 
                                        f"Processing complete. Processed {len(texture_groups)} texture groups."))
                            
                            # Start monitoring DDS processing
                            check_dds_processing()
                        else:
                            # No TIF files or output format is not TIF, just show completion
                            progress_dialog.show_completion(True, True)
                            app.update_status(get_text("status.processing_complete", 
                                f"Processing complete. Processed {len(texture_groups)} texture groups."))
                    else:
                        # No DDS generation needed, just show completion
                        progress_dialog.show_completion(True, True)
                        app.update_status(get_text("status.processing_complete", 
                            f"Processing complete. Processed {len(texture_groups)} texture groups."))
        
        # Start monitoring
        check_processing()
    
    # Assign the updated batch processing function to the main window instance
    # This allows ui/export_settings.py to call it via root.main_window.start_batch_processing()
    app.start_batch_processing = start_batch_processing
    
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
