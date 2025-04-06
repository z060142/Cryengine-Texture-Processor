#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spec Exporter

This module provides functionality for exporting _spec textures for CryEngine.
Similar to the logic in spec.py.
"""

import os
import subprocess
import shutil
# from utils.image_processing import ImageProcessor # No longer needed for saving

class SpecExporter:
    """
    Class for exporting _spec textures.
    """
    
    # def __init__(self):
    #     """
    #     Initialize the spec exporter.
    #     """
    #     # self.image_processor = ImageProcessor() # No longer needed
    
    def export(self, texture_group, settings, output_dir):
        """
        Export a _spec texture for CryEngine.
        
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
        output_path = os.path.join(output_dir, f"{base_name}_spec.tif")
        
        # Find ImageMagick executable
        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        # --- Determine Input Path ---
        input_path = None
        source_desc = ""

        def find_valid_path(texture_type):
            """Helper to find a valid path, checking intermediate then original."""
            intermediate_tex = texture_group.intermediate.get(texture_type)
            if intermediate_tex and intermediate_tex.get("path") and os.path.exists(intermediate_tex.get("path")):
                return intermediate_tex.get("path"), f"intermediate {texture_type}"
            
            original_tex = texture_group.textures.get(texture_type)
            if original_tex and original_tex.get("path") and os.path.exists(original_tex.get("path")):
                return original_tex.get("path"), f"original {texture_type}"
                
            return None, None

        # Prioritize reflection, then specular
        input_path, source_desc = find_valid_path("reflection")
        if not input_path:
            input_path, source_desc = find_valid_path("specular")

        # Check if a valid path was found
        if input_path:
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

            # Core conversion and saving options
            # Specular maps can be color or grayscale. We'll preserve color if present,
            # but ensure 8-bit depth for consistency. If it's grayscale, IM handles it.
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
                print(f"Successfully exported _spec to {output_path}")
                return output_path
            except subprocess.CalledProcessError as e:
                print(f"Error executing ImageMagick for _spec:")
                print(f"Command: {' '.join(e.cmd)}")
                print(f"Return Code: {e.returncode}")
                print(f"STDOUT: {e.stdout}")
                print(f"STDERR: {e.stderr}")
                # Fall through to default generation if enabled
            except Exception as e:
                print(f"An unexpected error occurred during _spec export: {e}")
                # Fall through to default generation if enabled

        # If no input path or ImageMagick failed, and default generation is enabled:
        if settings.get("generate_missing_spec", True):
            print(f"Source texture not found or processing failed. Generating default _spec.")
            # Note: _generate_default_spec still uses PIL. This might need refactoring
            # to use ImageMagick as well for full consistency if PIL causes issues here too.
            # For now, we keep the existing PIL-based default generation.
            # We need ImageProcessor for default generation
            from utils.image_processing import ImageProcessor 
            self.image_processor = ImageProcessor() # Instantiate if needed
            return self._generate_default_spec(texture_group, output_path, settings)
        else:
            print(f"Reflection/Specular not available or processing failed, and generate_missing_spec is disabled. Cannot export _spec.")
            return None
    
    def _generate_default_spec(self, texture_group, output_path, settings):
        """
        Generate a default spec texture based on diffuse if available.
        
        Args:
            texture_group: TextureGroup object
            output_path: Path to save the spec texture
            settings: Export settings dictionary
            
        Returns:
            Path to the exported texture or None if export failed
        """
        # This function still uses PIL. If default generation also causes issues,
        # it should be refactored to use ImageMagick's 'xc:' color generator.
        # Example: magick -size {width}x{height} xc:"rgb(62,62,62)" -depth 8 ... output_path
        
        print(f"Generating default _spec texture using PIL")
        
        # We need ImageProcessor for default generation if self.image_processor wasn't init'd
        if not hasattr(self, 'image_processor'):
             from utils.image_processing import ImageProcessor 
             self.image_processor = ImageProcessor()

        # Get base size from albedo or diffuse if available (using paths now)
        width = 1024
        height = 1024
        base_size_source = None

        def get_image_size(texture_type):
             path = None
             intermediate_tex = texture_group.intermediate.get(texture_type)
             if intermediate_tex and intermediate_tex.get("path") and os.path.exists(intermediate_tex.get("path")):
                 path = intermediate_tex.get("path")
             else:
                 original_tex = texture_group.textures.get(texture_type)
                 if original_tex and original_tex.get("path") and os.path.exists(original_tex.get("path")):
                     path = original_tex.get("path")
             
             if path:
                 try:
                     # Use ImageMagick identify to get size without loading full image via PIL
                     magick_path = shutil.which('magick')
                     if magick_path:
                         cmd = [magick_path, 'identify', '-format', '%w %h', str(path)]
                         result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                         w_str, h_str = result.stdout.split()
                         return int(w_str), int(h_str), path
                 except Exception as e:
                     print(f"Could not get size using ImageMagick identify for {path}: {e}. Falling back.")
                 # Fallback to PIL if identify fails
                 try:
                     from PIL import Image
                     with Image.open(path) as img:
                         return img.width, img.height, path
                 except Exception as e:
                     print(f"Could not get size using PIL for {path}: {e}")
             return None, None, None

        width, height, base_size_source = get_image_size("albedo")
        if not base_size_source:
             width, height, base_size_source = get_image_size("diffuse")
        
        if base_size_source:
             print(f"Using size from {base_size_source} for default spec.")
        else:
             width, height = 1024, 1024 # Default if no source found
             print(f"Could not determine size from albedo/diffuse, using default {width}x{height}.")

        # Apply output resolution if specified
        output_resolution = settings.get("output_resolution", "original")
        if output_resolution != "original":
            try:
                target_size = int(output_resolution)
                # Calculate aspect ratio
                max_dimension = max(width, height)
                if max_dimension > target_size: # Only downscale
                    scale_factor = target_size / max_dimension
                    width = int(width * scale_factor)
                    height = int(height * scale_factor)
                    print(f"Applying resize to {width}x{height} for default spec.")
            except ValueError:
                # If resolution is not a number, use original
                pass
        
        # Create default gray spec texture (rgb 62,62,62) using PIL
        from PIL import Image
        import numpy as np
        
        # Default gray value for spec (mid-range reflection)
        gray_value = 62
        spec_array = np.ones((height, width, 3), dtype=np.uint8) * gray_value
        spec_image = Image.fromarray(spec_array, mode="RGB")
        
        # Create spec texture object
        spec_texture = {
            "image": spec_image,
            "width": width,
            "height": height,
            "channels": 3,
            "mode": "RGB"
        }
        
        # Save spec texture using PIL's save method via ImageProcessor
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if self.image_processor.save_image(spec_texture, output_path, "TIFF"):
            print(f"Exported default _spec to {output_path}")
            return output_path
        else:
            print(f"Failed to save default _spec texture.")
            return None
