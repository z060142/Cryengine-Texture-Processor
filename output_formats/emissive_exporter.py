#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Emissive Exporter

This module provides functionality for exporting _emissive textures for CryEngine.
"""

import os
import subprocess
import shutil
# Keep ImageProcessor import for generation fallback
from utils.image_processing import ImageProcessor 

class EmissiveExporter:
    """
    Class for exporting _emissive textures.
    """
    
    def __init__(self):
        """
        Initialize the emissive exporter.
        """
        self.image_processor = ImageProcessor()
    
    def export(self, texture_group, settings, output_dir):
        """
        Export an _emissive texture for CryEngine.
        
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
        output_path = os.path.join(output_dir, f"{base_name}_emissive.tif")

        # Find ImageMagick executable
        magick_path = shutil.which('magick')

        # --- Determine Input Path for existing Emissive ---
        input_path = None
        source_desc = ""
        
        # Check original textures for emissive
        original_emissive = texture_group.textures.get("emissive")
        if original_emissive and original_emissive.get("path") and os.path.exists(original_emissive.get("path")):
            input_path = original_emissive.get("path")
            source_desc = "original emissive"
            
        # Try ImageMagick path if input found and magick exists
        if input_path and magick_path:
            print(f"Using {source_desc} texture: {input_path}")
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # --- ImageMagick Command Construction ---
            command = [
                magick_path,
                str(input_path)
            ]

            # Apply resolution scaling if needed
            output_resolution = settings.get("output_resolution", "original")
            if output_resolution != "original":
                try:
                    target_size = int(output_resolution)
                    command.extend(['-resize', f'{target_size}x{target_size}>'])
                    print(f"Applying resize to {target_size}x{target_size} (max)")
                except ValueError:
                    print(f"Invalid output resolution '{output_resolution}', skipping resize.")

            # Apply brightness adjustment if needed
            # Using -evaluate multiply factor. Factor 1.0 is no change.
            brightness = settings.get("emissive_brightness", 1.0) 
            if brightness != 1.0:
                 try:
                     brightness_factor = float(brightness)
                     # Clamp factor to avoid extreme values, e.g., 0.1 to 5.0
                     brightness_factor = max(0.1, min(brightness_factor, 5.0)) 
                     command.extend(['-evaluate', 'multiply', str(brightness_factor)])
                     print(f"Applying brightness factor: {brightness_factor}")
                 except (ValueError, TypeError):
                     print(f"Invalid emissive_brightness value '{brightness}', skipping adjustment.")

            # Core conversion and saving options
            # Emissive can be color or grayscale. Preserve color, ensure 8-bit.
            command.extend([
                '-depth', '8', 
                '-define', 'tiff:compression=lzw',
                str(output_path)
            ])

            # --- Execute ImageMagick Command ---
            try:
                print(f"Executing: {' '.join(command)}")
                result = subprocess.run(command, check=True, capture_output=True, text=True)
                print(f"ImageMagick STDOUT: {result.stdout}")
                print(f"ImageMagick STDERR: {result.stderr}")
                print(f"Successfully exported _emissive to {output_path}")
                return output_path
            except subprocess.CalledProcessError as e:
                print(f"Error executing ImageMagick for _emissive:")
                print(f"Command: {' '.join(e.cmd)}")
                print(f"Return Code: {e.returncode}")
                print(f"STDOUT: {e.stdout}")
                print(f"STDERR: {e.stderr}")
                # Fall through to generation if enabled
            except Exception as e:
                print(f"An unexpected error occurred during _emissive export via ImageMagick: {e}")
                # Fall through to generation if enabled
                
            print("ImageMagick processing failed or not available. Checking generation options.")

        # --- Fallback/Generation Logic (using PIL) ---
        
        # No valid input path found or ImageMagick failed
        if settings.get("generate_missing_emissive", False):
                # Create a black emissive texture (indicating no emission)
                # Ensure necessary PIL modules are imported here
                from PIL import Image 
                import numpy as np
                
                print("Attempting to generate default (black) emissive using PIL.")
                # Ensure ImageProcessor is initialized
                if not hasattr(self, 'image_processor'):
                     self.image_processor = ImageProcessor()

                # Determine size from other textures (using PIL via ImageProcessor)
                width = 1024
                height = 1024
                
                if texture_group.intermediate.get("albedo") and "image" in texture_group.intermediate.get("albedo"):
                    width = texture_group.intermediate.get("albedo")["image"].width
                    height = texture_group.intermediate.get("albedo")["image"].height
                elif texture_group.textures.get("diffuse") and "image" in texture_group.textures.get("diffuse"):
                    width = texture_group.textures.get("diffuse")["image"].width
                    height = texture_group.textures.get("diffuse")["image"].height
                
                # Apply resolution scaling if needed
                output_resolution = settings.get("output_resolution", "original")
                if output_resolution != "original":
                    try:
                        target_size = int(output_resolution)
                        max_dimension = max(width, height)
                        if max_dimension > target_size:  # Only downscale, don't upscale
                            scale_factor = target_size / max_dimension
                            width = int(width * scale_factor)
                            height = int(height * scale_factor)
                    except ValueError:
                        # If resolution is not a number, use original dimensions
                        pass
                
                # Create black image (no emission)
                black_array = np.zeros((height, width, 3), dtype=np.uint8)
                black_image = Image.fromarray(black_array, mode="RGB")
                
                # Create emissive texture object
                emissive_texture = {
                    "image": black_image,
                    "width": width,
                    "height": height,
                    "channels": 3,
                    "mode": "RGB"
                }
                
                # Save emissive texture
                self.image_processor.save_image(emissive_texture, output_path, "TIFF")
                print(f"Exported default (black) emissive texture to {output_path}")
                
                # Return path to exported texture
                return output_path
        else: # <--- Corrected indentation for line 180
            print(f"Emissive texture not available and generate_missing_emissive is disabled")
            return None
