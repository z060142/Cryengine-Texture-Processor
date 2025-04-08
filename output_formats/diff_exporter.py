#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diff Exporter

This module provides functionality for exporting _diff textures for CryEngine.
Similar to the logic in diff_opacity.py.
"""

import os
import subprocess
import shutil
# Keep ImageProcessor import for fallback/helper methods if needed later
import numpy as np # Needed for _darker_color_blend fallback
from PIL import Image, ImageChops # Needed for _darker_color_blend fallback

class DiffExporter:
    """
    Class for exporting _diff textures.
    """
    
    # def __init__(self):
    #     """
    #     Initialize the diff exporter.
    #     """
    #     # Keep ImageProcessor instance for potential fallback in _darker_color_blend
    #     self.image_processor = ImageProcessor() 
    
    def export(self, texture_group, settings, output_dir):
        """
        Export a _diff texture for CryEngine.
        
        Args:
            texture_group: TextureGroup object containing intermediate formats
            settings: Export settings dictionary
            output_dir: Directory to save the exported texture
            
        Returns:
            Path to the exported texture or None if export failed
        """
        # Determine diff format based on settings
        diff_format = settings.get("diff_format", "albedo")
        
        # Get base name for output
        base_name = texture_group.base_name
        
        # Create output path
        output_path = os.path.join(output_dir, f"{base_name}_diff.tif")

        # Find ImageMagick executable
        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        # --- Determine Input Paths ---
        def find_valid_path(texture_type):
            """Helper to find a valid path, checking intermediate then original."""
            intermediate_tex = texture_group.intermediate.get(texture_type)
            if intermediate_tex and intermediate_tex.get("path") and os.path.exists(intermediate_tex.get("path")):
                return intermediate_tex.get("path"), f"intermediate {texture_type}"
            
            original_tex = texture_group.textures.get(texture_type)
            if original_tex and original_tex.get("path") and os.path.exists(original_tex.get("path")):
                return original_tex.get("path"), f"original {texture_type}"
                
            return None, None

        albedo_path, albedo_desc = find_valid_path("albedo")
        if not albedo_path:
             albedo_path, albedo_desc = find_valid_path("diffuse") # Fallback to diffuse if albedo not found

        ao_path, ao_desc = find_valid_path("ao")
        alpha_path, alpha_desc = find_valid_path("alpha") # Check for separate alpha map

        if not albedo_path:
            print(f"Albedo/Diffuse texture path could not be found or is invalid.")
            return None
        print(f"Using {albedo_desc} texture: {albedo_path}")
        if ao_path: print(f"Using {ao_desc} texture: {ao_path}")
        if alpha_path: print(f"Using {alpha_desc} texture: {alpha_path}")

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # --- ImageMagick Command Construction ---
        command = [magick_path]
        
        # Base image (Albedo/Diffuse)
        command.append(str(albedo_path))

        # Apply resolution scaling (applied before AO/Alpha operations)
        output_resolution = settings.get("output_resolution", "original")
        resize_applied = False
        if output_resolution != "original":
            try:
                target_size = int(output_resolution)
                command.extend(['-resize', f'{target_size}x{target_size}>'])
                print(f"Applying resize to {target_size}x{target_size} (max) to base image")
                resize_applied = True
            except ValueError:
                print(f"Invalid output resolution '{output_resolution}', skipping resize.")

        # Handle AO multiplication if format is diffuse_ao and AO exists
        if diff_format == "diffuse_ao" and ao_path:
            print("Applying AO multiplication.")
            ao_command_part = ['(', str(ao_path)]
            # Apply matching resize to AO if base was resized
            if resize_applied:
                 try:
                    target_size = int(output_resolution)
                    ao_command_part.extend(['-resize', f'{target_size}x{target_size}>'])
                    print(f"Applying resize to {target_size}x{target_size} (max) to AO map")
                 except ValueError:
                    pass # Ignore invalid resolution for AO resize
            
            # Ensure AO is grayscale and apply Darken blend mode
            ao_command_part.extend(['-colorspace', 'gray', '-depth', '8', ')'])
            command.extend(ao_command_part)
            print("Applying AO using Darken blend mode.") # Log change
            command.extend(['-compose', 'Darken', '-composite']) # Using Darken blend mode

        # Handle Alpha channel if alpha map exists
        if alpha_path:
            print("Applying Alpha channel.")
            alpha_command_part = ['(', str(alpha_path)]
            # Apply matching resize to Alpha if base was resized
            if resize_applied:
                 try:
                    target_size = int(output_resolution)
                    alpha_command_part.extend(['-resize', f'{target_size}x{target_size}>'])
                    print(f"Applying resize to {target_size}x{target_size} (max) to Alpha map")
                 except ValueError:
                    pass # Ignore invalid resolution for Alpha resize
            
            # Ensure Alpha is grayscale and copy to alpha channel
            alpha_command_part.extend(['-colorspace', 'gray', '-depth', '8', ')'])
            command.extend(alpha_command_part)
            command.extend(['-alpha', 'off', '-compose', 'CopyOpacity', '-composite'])

        # Final output options (ensure 8-bit depth)
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
            print(f"Successfully exported _diff to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for _diff:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during _diff export: {e}")
            return None
    
    def _darker_color_blend(self, base_texture, blend_texture):
        """
        Apply Darker Color blend mode between two textures.
        Darker Color takes the RGB value from the darkest of the two textures at each pixel.
        
        Args:
            base_texture: Base texture object (albedo)
            blend_texture: Blend texture object (AO)
            
        Returns:
            Result texture object
        """
        try:
            base_img = base_texture["image"]
            blend_img = blend_texture["image"]
            
            # Ensure blend image is grayscale
            if blend_img.mode != "L":
                blend_img = blend_img.convert("L")
            
            # Convert grayscale AO to match base image mode
            if base_img.mode == "RGB":
                blend_img_rgb = Image.merge("RGB", [blend_img, blend_img, blend_img])
            elif base_img.mode == "RGBA":
                blend_img_rgb = Image.merge("RGB", [blend_img, blend_img, blend_img])
                # We'll need to restore alpha later
                base_alpha = base_img.split()[3]
            else:
                # For other modes, convert both to RGB
                base_img = base_img.convert("RGB")
                blend_img_rgb = Image.merge("RGB", [blend_img, blend_img, blend_img])
            
            # Resize blend to match base if needed
            if blend_img_rgb.size != base_img.size:
                blend_img_rgb = blend_img_rgb.resize(base_img.size, Image.LANCZOS)
            
            # Convert to numpy arrays for Darker Color blend
            base_array = np.array(base_img)
            blend_array = np.array(blend_img_rgb)
            
            # Darker Color blend: take the darker of the two textures for each pixel
            # First calculate luminance for each pixel in both textures
            if len(base_array.shape) > 2:
                base_luminance = 0.299 * base_array[:,:,0] + 0.587 * base_array[:,:,1] + 0.114 * base_array[:,:,2]
                blend_luminance = 0.299 * blend_array[:,:,0] + 0.587 * blend_array[:,:,1] + 0.114 * blend_array[:,:,2]
                
                # Create a mask where base is darker
                mask = base_luminance <= blend_luminance
                
                # Initialize result array with blend array
                result_array = blend_array.copy()
                
                # For each channel, use values from base where mask is True
                for c in range(min(base_array.shape[2], blend_array.shape[2])):
                    result_array[:,:,c] = np.where(mask, base_array[:,:,c], blend_array[:,:,c])
                
                # Restore alpha channel if needed
                if base_img.mode == "RGBA":
                    # Get alpha as array
                    alpha_array = np.array(base_alpha)
                    
                    # Add alpha channel
                    if len(result_array.shape) == 3 and result_array.shape[2] == 3:
                        # Create new array with alpha
                        rgba_array = np.zeros((result_array.shape[0], result_array.shape[1], 4), dtype=result_array.dtype)
                        rgba_array[:,:,:3] = result_array
                        rgba_array[:,:,3] = alpha_array
                        result_array = rgba_array
            else:
                # Grayscale case
                result_array = np.minimum(base_array, blend_array)
            
            # Convert back to PIL image
            result_img = Image.fromarray(result_array, mode=base_img.mode)
            
            # Create result texture
            result_texture = {
                "path": f"{base_texture.get('path', '')}_with_ao",
                "image": result_img,
                "width": result_img.width,
                "height": result_img.height,
                "channels": len(result_img.getbands()),
                "mode": result_img.mode,
                "type": "diff",
                "source": "albedo_with_ao"
            }
            
            return result_texture
            
        except Exception as e:
            print(f"Error applying Darker Color blend: {e}")
            return base_texture  # Fall back to base texture on error
