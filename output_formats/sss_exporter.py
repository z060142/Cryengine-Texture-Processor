#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SSS Exporter

This module provides functionality for exporting _sss (subsurface scattering) textures for CryEngine.
"""

import os
import subprocess
import shutil
# Keep ImageProcessor import for generation fallback
from utils.image_processing import ImageProcessor 

class SSSExporter:
    """
    Class for exporting _sss (subsurface scattering) textures.
    """
    
    def __init__(self):
        """
        Initialize the SSS exporter.
        """
        self.image_processor = ImageProcessor()
    
    def export(self, texture_group, settings, output_dir):
        """
        Export an _sss texture for CryEngine.
        
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
        output_path = os.path.join(output_dir, f"{base_name}_sss.tif")

        # Find ImageMagick executable
        magick_path = shutil.which('magick')
        
        # --- Determine Input Path for existing SSS ---
        input_path = None
        source_desc = ""
        
        # Check original textures first for SSS
        original_sss = texture_group.textures.get("sss")
        if original_sss and original_sss.get("path") and os.path.exists(original_sss.get("path")):
            input_path = original_sss.get("path")
            source_desc = "original sss"
            
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

            # Apply intensity adjustment if needed
            # Using -evaluate multiply factor. Factor 1.0 is no change.
            intensity = settings.get("sss_intensity", 1.0) 
            if intensity != 1.0:
                 try:
                     intensity_factor = float(intensity)
                     # Clamp intensity factor to avoid extreme values, e.g., 0.1 to 3.0
                     intensity_factor = max(0.1, min(intensity_factor, 3.0)) 
                     command.extend(['-evaluate', 'multiply', str(intensity_factor)])
                     print(f"Applying intensity factor: {intensity_factor}")
                 except (ValueError, TypeError):
                     print(f"Invalid sss_intensity value '{intensity}', skipping adjustment.")

            # Core conversion and saving options
            # SSS can be color or grayscale. Preserve color, ensure 8-bit.
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
                print(f"Successfully exported _sss to {output_path}")
                return output_path
            except subprocess.CalledProcessError as e:
                print(f"Error executing ImageMagick for _sss:")
                print(f"Command: {' '.join(e.cmd)}")
                print(f"Return Code: {e.returncode}")
                print(f"STDOUT: {e.stdout}")
                print(f"STDERR: {e.stderr}")
                # Fall through to generation if enabled
            except Exception as e:
                print(f"An unexpected error occurred during _sss export via ImageMagick: {e}")
                # Fall through to generation if enabled
                
            # If ImageMagick failed or wasn't found, but we had an input path, 
            # we might want to log that before falling through to generation.
            print("ImageMagick processing failed or not available. Checking generation options.")

        # --- Fallback/Generation Logic (using PIL) ---
        
        # Check if we should generate SSS from diffuse/albedo
        if settings.get("generate_sss_from_diffuse", False):
            # Get albedo or diffuse texture
            albedo_texture = texture_group.intermediate.get("albedo")
            diffuse_texture = texture_group.textures.get("diffuse")
            
            source_texture = None
            if albedo_texture and "image" in albedo_texture:
                source_texture = albedo_texture
            elif diffuse_texture:
                if "image" not in diffuse_texture:
                    diffuse_texture = self.image_processor.load_image(diffuse_texture["path"])
                if diffuse_texture:
                    source_texture = diffuse_texture
            
            if source_texture:
                # Create SSS texture from diffuse/albedo
                # Typically, SSS is derived by desaturating and adjusting diffuse
                # Ensure necessary PIL modules are imported here
                from PIL import ImageEnhance, ImageOps, Image 
                
                print("Attempting to generate SSS from diffuse/albedo using PIL.")
                # Ensure ImageProcessor is initialized
                if not hasattr(self, 'image_processor'):
                    self.image_processor = ImageProcessor()
                    
                # Start with a copy of the source image
                image = source_texture["image"].copy()
                
                # Apply resolution scaling if needed
                output_resolution = settings.get("output_resolution", "original")
                if output_resolution != "original" and source_texture:
                    # Need to resize source texture first
                    source_texture = self.image_processor.resize_to_resolution(source_texture, output_resolution)
                    # Image will be updated
                    image = source_texture["image"].copy()
                
                # Desaturate (reduce to grayscale then add back some color)
                grayscale = image.convert("L")
                sss_image = ImageOps.colorize(
                    grayscale, 
                    (0, 0, 0),  # black
                    (255, 240, 240)  # slight reddish tint for skin
                )
                
                # Adjust contrast to control SSS intensity
                intensity = settings.get("sss_intensity", 0.8)
                enhancer = ImageEnhance.Contrast(sss_image)
                sss_image = enhancer.enhance(intensity)
                
                # Create SSS texture object
                sss_texture = {
                    "image": sss_image,
                    "width": sss_image.width,
                    "height": sss_image.height,
                    "channels": 3,
                    "mode": "RGB"
                }
                
                # Save SSS texture
                self.image_processor.save_image(sss_texture, output_path, "TIFF")
                print(f"Exported SSS texture generated from diffuse/albedo to {output_path}")
                
                # Return path to exported texture
                return output_path
                
        # Generate default SSS if setting is enabled
        elif settings.get("generate_missing_sss", False):
            # Create a basic SSS texture
            # Ensure necessary PIL modules are imported here
            from PIL import Image 
            import numpy as np
            
            print("Attempting to generate default SSS using PIL.")
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
            
            # Create a mild SSS effect (slight reddish color for skin-like materials)
            # Default SSS color (very subtle effect)
            color_value = 30  # Low intensity
            sss_array = np.ones((height, width, 3), dtype=np.uint8) * color_value
            # Make it slightly reddish (typical for skin)
            sss_array[:, :, 0] += 10  # More red
            sss_array[:, :, 1] -= 5   # Less green
            sss_array[:, :, 2] -= 5   # Less blue
            
            sss_image = Image.fromarray(sss_array, mode="RGB")
            
            # Create SSS texture object
            sss_texture = {
                "image": sss_image,
                "width": width,
                "height": height,
                "channels": 3,
                "mode": "RGB"
            }
            
            # Save SSS texture
            self.image_processor.save_image(sss_texture, output_path, "TIFF")
            print(f"Exported default SSS texture to {output_path}")
            
            # Return path to exported texture
            return output_path
            
        else:
            print(f"SSS texture not available and generation settings are disabled")
            return None
