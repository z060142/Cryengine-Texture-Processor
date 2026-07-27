#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Glossiness Processor

This module provides functionality for processing input textures to generate
glossiness intermediate format (surface smoothness).
"""
import os
import subprocess
import shutil
# import tempfile # No longer needed here
# import atexit   # No longer needed here
from pathlib import Path
from utils.image_processing import ImageProcessor # Still needed for loading/PIL fallbacks if any

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


class GlossinessProcessor:
    """
    Class for processing input textures to generate glossiness intermediate format.
    """
    
    def __init__(self):
        """
        Initialize the glossiness processor.
        """
        self.image_processor = ImageProcessor() # Keep for loading images if needed by helpers

    def ensure_intermediate_glossiness(self, texture_group, settings):
        """
        Ensures a reliable intermediate glossiness file exists, creating it if necessary
        from glossiness, roughness (standalone or from ARM). Saves the result
        to a temporary file and returns the texture object with the path.
        
        Args:
            texture_group: The TextureGroup containing source textures and intermediates.
            settings: Dictionary of processing settings.
            
        Returns:
            A texture dictionary for the generated intermediate glossiness file, 
            containing the path, dimensions, etc., or None if failed.
        """
        print("\n--- Glossiness Processor: Ensuring Intermediate ---")

        if not TEMP_DIR:
            print("Error: Temporary directory not available.")
            return None

        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None

        source_path = None
        source_desc = ""
        invert_source = False

        # 1. Check for standalone glossiness (original first, then intermediate)
        gloss_orig = texture_group.textures.get("glossiness")
        if gloss_orig and gloss_orig.get("path") and os.path.exists(gloss_orig.get("path")):
            source_path = gloss_orig.get("path")
            source_desc = "original glossiness"
        else:
            gloss_inter = texture_group.intermediate.get("glossiness")
            if gloss_inter and gloss_inter.get("path") and os.path.exists(gloss_inter.get("path")):
                 source_path = gloss_inter.get("path")
                 source_desc = "intermediate glossiness"

        # 2. If no gloss, check for roughness (intermediate first - likely from ARM, then original)
        if not source_path:
            rough_inter = texture_group.intermediate.get("roughness")
            if rough_inter and rough_inter.get("path") and os.path.exists(rough_inter.get("path")):
                source_path = rough_inter.get("path")
                source_desc = "intermediate roughness (from ARM?)"
                invert_source = True
            else:
                rough_orig = texture_group.textures.get("roughness")
                if rough_orig and rough_orig.get("path") and os.path.exists(rough_orig.get("path")):
                    source_path = rough_orig.get("path")
                    source_desc = "original roughness"
                    invert_source = True
        
        # 3. Check for specular alpha (optional, could be added here if needed)
        # ...

        if not source_path:
            print("No suitable source found for glossiness intermediate.")
            # Optionally generate default here if required by workflow
            # return self.generate_default_glossiness(...) 
            return None
            
        print(f"Found source for glossiness intermediate: {source_desc} ({source_path})")
        if invert_source:
            print("Source requires inversion (Roughness -> Glossiness)")

        # Construct temporary output path
        base_filename = texture_group.base_name # Use group base name
        temp_filename = f"{base_filename}_gloss_intermediate_temp.tif"
        temp_output_path = TEMP_DIR / temp_filename

        # --- ImageMagick Command Construction ---
        command = [
            magick_path,
            str(source_path)
        ]
        
        # Apply resolution scaling if needed (important for consistency)
        output_resolution = settings.get("output_resolution", "original")
        if output_resolution != "original":
            try:
                target_size = int(output_resolution)
                command.extend(['-resize', f'{target_size}x{target_size}>'])
                print(f"Applying resize to {target_size}x{target_size} (max)")
            except ValueError:
                print(f"Invalid output resolution '{output_resolution}', skipping resize.")

        # Ensure grayscale, 8-bit depth
        command.extend(['-colorspace', 'gray', '-depth', '8'])

        # Invert if needed
        if invert_source:
            command.append('-negate')

        # Define output format and path
        command.extend([
            '-define', 'tiff:compression=lzw',
            str(temp_output_path)
        ])

        # --- Execute ImageMagick Command ---
        try:
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Successfully created intermediate glossiness: {temp_output_path}")

            # Create result texture object, BUT DO NOT LOAD THE IMAGE DATA
            # Only return the path and metadata.
            # Dimensions could be added later if needed, e.g., using `magick identify`.

            intermediate_gloss_texture = {
                "path": str(temp_output_path), # Path to the saved file
                # "image": None, # Explicitly DO NOT store image data
                # "width": 0, # Omit or get via identify later if needed
                # "height": 0, # Omit or get via identify later if needed
                "channels": 1,
                "mode": "L",
                "type": "glossiness", # Mark as glossiness type
                "source": f"processed_from_{source_desc}" 
            }
            print("--- Glossiness Processor: Finished ---")
            return intermediate_gloss_texture

        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for intermediate glossiness:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            print("--- Glossiness Processor: Failed ---")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during intermediate glossiness creation: {e}")
            print("--- Glossiness Processor: Failed ---")
            return None

    # Removing old methods now handled by ensure_intermediate_glossiness
    # def process_from_glossiness(self, gloss_texture): ...
    # def process_from_roughness(self, roughness_texture): ...

    # Keep process_from_specular and generate_default_glossiness as potential fallbacks
    # or if they are called directly elsewhere.

    def process_from_specular(self, specular_texture):
        """
        Extract glossiness information from a specular texture (if available). 
        NOTE: This method currently uses PIL and doesn't save an intermediate file.
              It might need refactoring if used in the main pipeline.
        
        Args:
            specular_texture: Specular texture object
            
        Returns:
            Extracted glossiness texture object or None if not applicable
        """
        print("Extracting glossiness from specular texture (using PIL)")
        
        # Load specular image if needed
        if "image" not in specular_texture:
            specular_texture = self.image_processor.load_image(specular_texture["path"])
            if specular_texture is None:
                return None
        
        # Check if specular has an alpha channel that might contain glossiness
        if specular_texture["image"].mode == "RGBA":
            # Extract alpha channel
            alpha_texture = self.image_processor.extract_channel(specular_texture, 3)
            
            if alpha_texture:
                alpha_texture["type"] = "glossiness"
                alpha_texture["source"] = "from_specular_alpha"
                alpha_texture["specular_source"] = specular_texture
                # TODO: Should this also save an intermediate file? Currently doesn't.
                return alpha_texture
        
        # If no alpha channel, we could analyze the specular image to estimate glossiness
        # For now, return None to indicate not applicable
        print("No glossiness information found in specular texture")
        return None
    
    def generate_default_glossiness(self, width=1024, height=1024, value=127):
        """
        Generate a default glossiness texture using PIL.
        NOTE: This method currently uses PIL and doesn't save an intermediate file.
              It might need refactoring if used in the main pipeline.
        
        Args:
            width: Width of the texture
            height: Height of the texture
            value: Glossiness value (0-255, higher = glossier)
            
        Returns:
            Default glossiness texture object
        """
        print(f"Generating default glossiness texture ({width}x{height}, value={value})")
        
        # Create a solid gray image
        from PIL import Image
        import numpy as np
        
        gray_array = np.ones((height, width), dtype=np.uint8) * value
        gray_image = Image.fromarray(gray_array, mode="L")
        
        # Create result texture
        glossiness_texture = {
            "path": "default_glossiness",
            "image": gray_image,
            "width": width,
            "height": height,
            "channels": 1,
            "mode": "L",
            "type": "glossiness",
            "source": "default"
        }
        
        return glossiness_texture
