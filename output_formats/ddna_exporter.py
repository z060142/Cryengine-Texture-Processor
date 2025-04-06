#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DDNA Exporter

This module provides functionality for exporting _ddna textures for CryEngine.
The _ddna format combines normal and gloss information in a single texture.
Similar to the logic in ddna.py.
"""

import os
import subprocess
import shutil
# from utils.image_processing import ImageProcessor # No longer needed for saving/combining
# from PIL import Image # No longer needed

class DDNAExporter:
    """
    Class for exporting _ddna textures.
    """
    
    # def __init__(self):
    #     """
    #     Initialize the DDNA exporter.
    #     """
    #     # self.image_processor = ImageProcessor() # No longer needed
    
    def export(self, texture_group, settings, output_dir):
        """
        Export a _ddna texture for CryEngine.
        
        Args:
            texture_group: TextureGroup object containing intermediate formats
            settings: Export settings dictionary
            output_dir: Directory to save the exported texture
            
        Returns:
            Path to the exported texture or None if export failed
        """
        # Get base name for output
        base_name = texture_group.base_name
        
        # Find ImageMagick executable
        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        # --- Determine Input Paths ---
        print("\n--- DDNA Exporter ---") 
        
        # Simplified path finding: Check intermediate first, then original
        def find_valid_path_simple(texture_type):
            """Finds a valid path, checking intermediate then original."""
            intermediate_tex = texture_group.intermediate.get(texture_type)
            if intermediate_tex and intermediate_tex.get("path") and os.path.exists(intermediate_tex.get("path")):
                print(f"  Using intermediate path for {texture_type}: {intermediate_tex.get('path')}")
                return intermediate_tex.get("path")
            
            original_tex = texture_group.textures.get(texture_type)
            if original_tex and original_tex.get("path") and os.path.exists(original_tex.get("path")):
                 print(f"  Using original path for {texture_type}: {original_tex.get('path')}")
                 return original_tex.get("path")
                 
            print(f"  Could not find valid path for {texture_type}.")
            return None

        # Find Normal Map Path
        normal_path = find_valid_path_simple("normal")
        if not normal_path:
            print(f"Normal texture path could not be found or is invalid. Cannot export DDNA.")
            return None
        print(f"Using Normal map: {normal_path}")

        # Find Intermediate Glossiness Path (should have been created by GlossinessProcessor)
        alpha_source_path = None
        gloss_intermediate = texture_group.intermediate.get("glossiness")
        if gloss_intermediate and gloss_intermediate.get("path") and os.path.exists(gloss_intermediate.get("path")):
            alpha_source_path = gloss_intermediate.get("path")
            print(f"Using Intermediate Glossiness map for alpha: {alpha_source_path}")
        else:
             print(f"Intermediate Glossiness map not found at path: {gloss_intermediate.get('path', 'N/A') if gloss_intermediate else 'N/A'}")

        # Check if we have a normal map path (redundant check, already done)
        if not normal_path:
            print(f"Normal texture path could not be found or is invalid.")
            return None
        # Determine output filename and log intent
        if alpha_source_path:
             print(f"  >>> Will export _ddna.tif") 
        else:
            print("Intermediate Glossiness map not found. Exporting _ddn (no alpha).")
            print(f"  >>> Will export _ddn.tif") 

        # Create output path (_ddna if alpha source exists, _ddn otherwise for now)
        output_filename = f"{base_name}_ddna.tif" if alpha_source_path else f"{base_name}_ddn.tif"
        output_path = os.path.join(output_dir, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # --- ImageMagick Command Construction ---
        command = [magick_path, str(normal_path)]

        # Apply resolution scaling (to normal map before combining)
        output_resolution = settings.get("output_resolution", "original")
        if output_resolution != "original":
            try:
                target_size = int(output_resolution)
                command.extend(['-resize', f'{target_size}x{target_size}>'])
                print(f"Applying resize to {target_size}x{target_size} (max) to normal map")
            except ValueError:
                print(f"Invalid output resolution '{output_resolution}', skipping resize.")
        
        # Ensure normal map is 8-bit RGB before potential alpha composition
        command.extend(['-depth', '8', '-type', 'TrueColor']) # Ensures RGB

        # Flip green channel if requested
        flip_green = settings.get("normal_flip_green", False)
        if flip_green:
            command.extend(['-channel', 'G', '-negate', '+channel'])
            print("Applying green channel flip to normal map")

        # Prepare alpha source command part if intermediate glossiness exists
        if alpha_source_path:
            # The source is already processed glossiness, just need path
            alpha_command_part = ['(', str(alpha_source_path)]
            
            # Apply matching resize if needed
            if output_resolution != "original":
                 try:
                    target_size = int(output_resolution)
                    alpha_command_part.extend(['-resize', f'{target_size}x{target_size}>'])
                    print(f"Applying resize to {target_size}x{target_size} (max) to intermediate glossiness")
                 except ValueError:
                    pass 

            # Ensure grayscale, 8-bit depth (should already be, but good practice)
            alpha_command_part.extend(['-colorspace', 'gray', '-depth', '8'])
            # DO NOT INVERT HERE - GlossinessProcessor already handled inversion if needed
            alpha_command_part.append(')')

            # Add alpha processing to main command
            command.extend(alpha_command_part)
            
            # Compose alpha channel
            command.extend([
                '-alpha', 'off',           # Ensure base image alpha is off before composing
                '-compose', 'CopyOpacity', # Use grayscale intensity of second image as alpha
                '-composite'               # Perform the composition
            ])
        # else: # Handle case where no gloss/rough is found - maybe create default alpha?
            # Example: Create a 50% gray alpha channel if needed
            # command.extend(['(', '-size', f'{width}x{height}', 'xc:gray50', ')']) # Needs width/height
            # command.extend(['-alpha', 'off', '-compose', 'CopyOpacity', '-composite'])
            # print("No gloss/roughness found, using default alpha (if implemented)")
            # For now, we just export _ddn without alpha if source is missing.

        # Final output options
        command.extend([
            '-define', 'tiff:compression=lzw',
            str(output_path)
        ])

        # --- Execute ImageMagick Command ---
        try:
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"ImageMagick STDOUT: {result.stdout}")
            print(f"ImageMagick STDERR: {result.stderr}")
            print(f"Successfully exported {output_filename} to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for {output_filename}:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during {output_filename} export: {e}")
            return None
