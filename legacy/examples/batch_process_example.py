#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch Process Example

This script demonstrates how to use the batch processing functionality
to convert a directory of textures to CryEngine format.
"""

import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.texture_manager import TextureManager
from core.batch_processor import BatchProcessor
from ui.progress_dialog import ProgressDialog

def select_directory(title, initial_dir=None):
    """
    Show directory selection dialog.
    
    Args:
        title: Dialog title
        initial_dir: Initial directory
        
    Returns:
        Selected directory or empty string if cancelled
    """
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    directory = filedialog.askdirectory(
        title=title,
        initialdir=initial_dir
    )
    
    root.destroy()
    return directory

def message_box(title, message):
    """
    Show message box.
    
    Args:
        title: Message box title
        message: Message text
    """
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    messagebox.showinfo(title, message)
    
    root.destroy()

def main():
    """
    Main function to demonstrate batch processing.
    """
    print("CryEngine Texture Processor - Batch Processing Example")
    print("-----------------------------------------------------")
    
    # Create texture manager
    texture_manager = TextureManager()
    
    # Select input directory
    print("Select input directory containing textures...")
    input_dir = select_directory("Select Input Directory")
    if not input_dir:
        print("No input directory selected. Exiting.")
        return
    
    print(f"Input directory: {input_dir}")
    
    # Select output directory
    print("Select output directory for processed textures...")
    output_dir = select_directory("Select Output Directory", input_dir)
    if not output_dir:
        print("No output directory selected. Exiting.")
        return
    
    print(f"Output directory: {output_dir}")
    
    # Import textures
    print("Importing textures...")
    texture_count = 0
    for root, _, files in os.walk(input_dir):
        for file in files:
            # Check if file has a supported extension
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.tga', '.bmp')):
                file_path = os.path.join(root, file)
                texture_manager.add_texture(file_path)
                texture_count += 1
    
    print(f"Imported {texture_count} textures.")
    
    # Get texture groups
    groups = texture_manager.get_all_groups()
    print(f"Found {len(groups)} texture groups.")
    
    if len(groups) == 0:
        message_box("No Textures Found", "No valid texture groups found in the selected directory.")
        return
    
    # Print texture groups
    for i, group in enumerate(groups):
        print(f"Group {i+1}: {group.base_name}")
        for texture_type, texture in group.textures.items():
            if texture_type == "unknown":
                unknown_count = len(texture) if isinstance(texture, list) else 0
                if unknown_count > 0:
                    print(f"  {texture_type}: {unknown_count} textures")
            elif texture is not None:
                print(f"  {texture_type}: {os.path.basename(texture.get('path', 'N/A'))}")
    
    # Configure processing settings
    settings = {
        "diff_format": "albedo",         # Use albedo for diff
        "normal_flip_green": False,      # Don't flip green channel in normal maps
        "generate_missing_spec": True,   # Generate default spec if missing
        "process_metallic": True,        # Process metallic textures to reflection
        "normal_from_height_strength": 10.0,  # Strength for normal maps generated from height
        "normalize_height": True         # Normalize height maps
    }
    
    # Create batch processor
    batch_processor = BatchProcessor(texture_manager)
    batch_processor.set_output_dir(output_dir)
    batch_processor.set_settings(settings)
    
    # Create and show progress dialog
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    # Progress dialog callback
    def progress_callback(progress, current, status):
        progress_dialog.update_progress(progress, current, status)
        
        # Update window title with progress percentage
        progress_pct = int(progress * 100)
        progress_dialog.dialog.title(f"Processing... ({progress_pct}%)")
    
    # Cancel callback
    def cancel_callback():
        batch_processor.cancel()
    
    # Create progress dialog
    progress_dialog = ProgressDialog(root, "Processing Textures")
    progress_dialog.set_cancel_callback(cancel_callback)
    
    # Set progress callback
    batch_processor.set_progress_callback(progress_callback)
    
    # Start processing
    batch_processor.process_all_groups()
    
    # Wait for processing to complete
    while batch_processor.is_processing():
        root.update()
        time.sleep(0.1)
    
    # Show completion
    if progress_dialog.is_cancelled():
        progress_dialog.show_completion(False, True)
        message_box("Processing Cancelled", "Texture processing was cancelled.")
    else:
        progress_dialog.show_completion(True, True)
        message_box("Processing Complete", f"Processed {len(groups)} texture groups successfully.")
    
    # Wait for dialog to close
    while progress_dialog.dialog.winfo_exists():
        try:
            root.update()
            time.sleep(0.1)
        except tk.TclError:
            break  # Dialog was closed
    
    root.destroy()

if __name__ == "__main__":
    main()
