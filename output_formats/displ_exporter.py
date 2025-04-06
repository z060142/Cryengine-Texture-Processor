#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Displ Exporter

This module provides functionality for exporting _displ textures for CryEngine.
Similar to the logic in displ.py.
"""

import os
import subprocess
import shutil
# from utils.image_processing import ImageProcessor # No longer needed for saving

class DisplExporter:
    """
    Class for exporting _displ textures.
    """
    
    # def __init__(self):
    #     """
    #     Initialize the displ exporter.
    #     """
    #     # self.image_processor = ImageProcessor() # No longer needed
    
    def export(self, texture_group, settings, output_dir):
        """
        Export a _displ texture for CryEngine.
        
        Args:
            texture_group: TextureGroup object containing intermediate formats
            settings: Export settings dictionary
            output_dir: Directory to save the exported texture
            
        Returns:
            Path to the exported texture or None if export failed
        """
        # Get base name for output
        base_name = texture_group.base_name
        
        # Create output path
        output_path = os.path.join(output_dir, f"{base_name}_displ.tif")
        
        # Find ImageMagick executable
        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        # --- Determine Input Path ---
        input_path = None
        source_desc = ""

        # Prioritize intermediate height map
        height_intermediate = texture_group.intermediate.get("height")
        if height_intermediate and height_intermediate.get("path") and os.path.exists(height_intermediate.get("path")):
            input_path = height_intermediate.get("path")
            source_desc = "intermediate height"
        
        # Fallback to original displacement map if intermediate height failed or doesn't exist
        if not input_path:
            displacement_original = texture_group.textures.get("displacement")
            if displacement_original and displacement_original.get("path") and os.path.exists(displacement_original.get("path")):
                input_path = displacement_original.get("path")
                source_desc = "original displacement"

        # Fallback to original height map if displacement also failed
        if not input_path:
             height_original = texture_group.textures.get("height")
             if height_original and height_original.get("path") and os.path.exists(height_original.get("path")):
                 input_path = height_original.get("path")
                 source_desc = "original height"

        # Check if a valid path was found
        if not input_path:
            print(f"Could not find a valid source texture path for Height or Displacement.")
            # Optionally print available paths for debugging:
            # print(f"  Intermediate Height Path: {texture_group.intermediate.get('height', {}).get('path')}")
            # print(f"  Original Displacement Path: {texture_group.textures.get('displacement', {}).get('path')}")
            # print(f"  Original Height Path: {texture_group.textures.get('height', {}).get('path')}")
            return None
            
        print(f"Using {source_desc} texture: {input_path}")

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # --- ImageMagick Command Construction ---
        command = [
            magick_path,
            str(input_path)
        ]

        # Apply resolution scaling if needed (using ImageMagick)
        output_resolution = settings.get("output_resolution", "original")
        if output_resolution != "original":
            try:
                target_size = int(output_resolution)
                # Use ImageMagick's resize, maintaining aspect ratio, only downscaling '>'
                command.extend(['-resize', f'{target_size}x{target_size}>'])
                print(f"Applying resize to {target_size}x{target_size} (max)")
            except ValueError:
                print(f"Invalid output resolution '{output_resolution}', skipping resize.")

        # Apply normalization if requested (using ImageMagick)
        if settings.get("normalize_height", False):
            # Use -auto-level or -normalize depending on desired effect
            # -auto-level stretches the range, -normalize is similar but channel-independent
            command.extend(['-auto-level']) 
            print("Applying auto-level normalization")

        # Core conversion and saving options
        # Convert to grayscale, copy gray to alpha, ensure RGB channels exist
        command.extend([
            '-colorspace', 'gray',      # Ensure grayscale source
            '-depth', '8',              # Ensure 8-bit depth
            '-alpha', 'copy',           # Copy grayscale intensity to alpha channel
            '-channel', 'RGB',          # Ensure RGB channels exist (even if gray)
            '+channel',                 # Apply to all channels (including alpha)
            '-define', 'tiff:compression=lzw',
            str(output_path)
        ])
        print("Configured Displ export for RGBA (Gray copied to Alpha)")

        # --- Execute ImageMagick Command ---
        try:
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"ImageMagick STDOUT: {result.stdout}")
            print(f"ImageMagick STDERR: {result.stderr}")
            print(f"Successfully exported _displ to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for _displ:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during _displ export: {e}")
            return None
