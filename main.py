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
    
    # Define batch processing function
    def start_batch_processing():
        # Use the texture manager from texture import panel
        # This ensures we're using the same manager that has the imported textures
        texture_manager = app.texture_import_panel.texture_manager
        
        # Create batch processor using this texture manager
        batch_processor = BatchProcessor(texture_manager)
        
        # Get texture groups directly from the texture manager
        texture_groups = texture_manager.get_all_groups()
        
        # Get export settings
        settings = app.export_settings_panel.get_settings()
        
        # Get output directory
        output_dir = settings.get("output_directory", "")
        if not output_dir:
            # Ask for output directory
            output_dir = filedialog.askdirectory(
                title=get_text("export.select_directory", "Select Output Directory"),
                initialdir=os.getcwd()
            )
            if not output_dir:
                return  # Cancelled
            
            # Save output directory in settings
            settings["output_directory"] = output_dir
            app.export_settings_panel.set_settings(settings)
        
        # Check if output directory exists
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror(
                    get_text("export.error", "Error"),
                    get_text("export.create_dir_error", "Failed to create output directory: {0}").format(str(e))
                )
                return
        
        # Set batch processor settings
        batch_processor.set_output_dir(output_dir)
        batch_processor.set_settings(settings)
        
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
    
    # Override the start_batch_processing method in app
    app.start_batch_processing = start_batch_processing
    
    # Now also update the export_textures method to use the same texture manager
    original_export_textures = app.export_settings_panel.export_textures
    
    def updated_export_textures(texture_groups=None):
        if texture_groups is None:
            # Use the texture groups from the texture import panel's texture manager
            texture_groups = app.texture_import_panel.texture_manager.get_all_groups()
        return original_export_textures(texture_groups)
    
    app.export_settings_panel.export_textures = updated_export_textures
    
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
