#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Reflection Processor

This module provides functionality for processing input textures to generate
reflection intermediate format (specular reflection properties).
"""
import os
import subprocess
import shutil
# import tempfile # No longer needed here
# import atexit   # No longer needed here
from pathlib import Path
from utils.image_processing import ImageProcessor # Keep for loading/fallbacks
import numpy as np # Needed for generate_default_reflection
from PIL import Image # Needed for generate_default_reflection

# --- Temporary Directory Path Definition ---
# Define the path, but don't create or manage cleanup here.
# Cleanup is handled by the calling process (e.g., BatchProcessor).
try:
    TEMP_DIR_BASE = Path(__file__).parent.parent / ".texproc_temp"
    # Get the PID to construct the specific temp dir path used by this process run
    TEMP_DIR = TEMP_DIR_BASE / str(os.getpid())
    # print(f"Using temporary directory path: {TEMP_DIR}") # Optional: for debugging
except Exception as e:
    print(f"Error defining temporary directory path: {e}. Intermediate file saving might fail.")
    TEMP_DIR = None
# --- End Temporary Directory Path Definition ---


class ReflectionProcessor:
    """
    Class for processing input textures to generate reflection intermediate format.
    """
    
    def __init__(self):
        """
        Initialize the reflection processor.
        """
        self.image_processor = ImageProcessor()
    
    def process_from_specular(self, specular_texture, gloss_texture=None):
        """
        Generate reflection format from specular texture, optionally using glossiness.
        
        Args:
            specular_texture: Specular texture object
            gloss_texture: Optional glossiness texture object
            
        Returns:
            Generated reflection texture object
        """
        print(f"Generating reflection from specular")
        
        # Load specular image if needed
        if "image" not in specular_texture:
            specular_texture = self.image_processor.load_image(specular_texture["path"])
            if specular_texture is None:
                return None
        
        # Create a copy of the texture object
        reflection_texture = dict(specular_texture)
        reflection_texture["type"] = "reflection"
        reflection_texture["source"] = "from_specular"
        reflection_texture["specular_source"] = specular_texture
        
        # If glossiness is available, we could combine them here if needed
        if gloss_texture:
            print(f"Including glossiness information in reflection")
            
            # In an actual implementation, we might process the combination somehow
            reflection_texture["gloss_source"] = gloss_texture
        
        return reflection_texture
    
    def process_from_metallic(self, metallic_texture, diffuse_texture):
        """
        Generate reflection format from metallic and diffuse textures.
        Follows the logic: Reflection = lerp(DefaultGray, Diffuse, Metallic)
        
        Args:
            metallic_texture: Metallic texture object (might just contain path)
            diffuse_texture: Diffuse texture object (might just contain path)
            
        Returns:
            Generated reflection texture object (with path to saved intermediate)
        """
        print(f"Generating reflection intermediate from metallic and diffuse textures")

        if not TEMP_DIR:
            print("Error: Temporary directory not available.")
            return None

        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        # --- Get Valid Input Paths ---
        metallic_path = metallic_texture.get("path")
        diffuse_path = diffuse_texture.get("path")

        if not metallic_path or not os.path.exists(metallic_path):
             print(f"Metallic texture path not found or invalid: {metallic_path}")
             return None
        if not diffuse_path or not os.path.exists(diffuse_path):
             print(f"Diffuse texture path not found or invalid: {diffuse_path}")
             return None
             
        print(f"Using Metallic: {metallic_path}")
        print(f"Using Diffuse: {diffuse_path}")

        # --- Determine Output Size (using identify) ---
        width, height = 1024, 1024 # Default
        try:
            cmd = [magick_path, 'identify', '-format', '%w %h', str(metallic_path)]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            w_str, h_str = result.stdout.split()
            width, height = int(w_str), int(h_str)
            print(f"Determined size from metallic map: {width}x{height}")
        except Exception as e:
            print(f"Warning: Could not get size from metallic map using identify: {e}. Using default {width}x{height}.")

        # Construct temporary output path
        # Use diffuse name as base, as reflection relates more closely to final color
        base_filename = Path(diffuse_path).stem 
        temp_filename = f"{base_filename}_refl_intermediate_temp.tif"
        temp_output_path = TEMP_DIR / temp_filename

        # --- ImageMagick Command Construction ---
        # Logic: Create base gray, composite diffuse on top using metallic as mask
        gray_value_rgb = "rgb(62,62,62)" # Default non-metal reflection
        
        command = [
            magick_path,
            # 1. Create base gray canvas
            '-size', f'{width}x{height}', f'xc:{gray_value_rgb}', 
            # 2. Load diffuse, ensure size matches
            '(', str(diffuse_path), '-resize', f'{width}x{height}!', ')', 
            # 3. Load metallic, ensure grayscale, 8bit, size matches
            '(', str(metallic_path), '-resize', f'{width}x{height}!', '-colorspace', 'gray', '-depth', '8', ')',
            # 4. Composite: Use metallic as mask to blend diffuse over gray
            '-compose', 'Over', '-composite', 
            # 5. Final output options
            '-depth', '8',
            '-define', 'tiff:compression=lzw',
            str(temp_output_path)
        ]
        
        # --- Execute ImageMagick Command ---
        try:
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Successfully created intermediate reflection: {temp_output_path}")

            # Create result texture object
            intermediate_refl_texture = {
                "path": str(temp_output_path), # Path to the saved file
                "width": width, # Use determined width
                "height": height, # Use determined height
                "channels": 3, # Result is RGB
                "mode": "RGB",
                "type": "reflection", 
                "source": "generated_from_metallic_diffuse",
                "metallic_source": metallic_texture, # Keep original refs if needed
                "diffuse_source": diffuse_texture
            }
            return intermediate_refl_texture

        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for intermediate reflection:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during intermediate reflection creation: {e}")
            return None
    
    def generate_default_reflection(self, width=1024, height=1024):
        """
        Generate a default reflection texture (mid-gray).
        
        Args:
            width: Width of the texture
            height: Height of the texture
            
        Returns:
            Default reflection texture object
        """
        print(f"Generating default reflection texture ({width}x{height})")
        
        # Create a solid gray image
        gray_value = 62  # Default gray for reflections
        gray_array = np.ones((height, width, 3), dtype=np.uint8) * gray_value
        gray_image = Image.fromarray(gray_array, mode="RGB")
        
        # Create result texture
        reflection_texture = {
            "path": "default_reflection",
            "image": gray_image,
            "width": width,
            "height": height,
            "channels": 3,
            "mode": "RGB",
            "type": "reflection",
            "source": "default"
        }
        
        return reflection_texture
