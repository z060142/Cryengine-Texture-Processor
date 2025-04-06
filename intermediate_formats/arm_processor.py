#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ARM Texture Processor

This module provides functionality for processing ARM textures, which contain
Ambient Occlusion (R channel), Roughness (G channel), and Metallic (B channel)
information in a single texture.
"""
import os
import subprocess
import shutil
# import tempfile # No longer needed here
# import atexit   # No longer needed here
from pathlib import Path
from utils.image_processing import ImageProcessor

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


class ARMProcessor:
    """
    Class for processing ARM textures.
    """
    
    def __init__(self):
        """
        Initialize the ARM processor.
        """
        self.image_processor = ImageProcessor()
    
    def process(self, arm_texture):
        """
        Process an ARM texture and extract individual channels.
        
        Args:
            arm_texture: ARM texture object
            
        Returns:
            Dictionary containing separated AO, Roughness, and Metallic textures
        """
        print(f"Processing ARM texture to extract AO, Roughness, and Metallic channels")
        
        # Load ARM image if needed
        if "image" not in arm_texture:
            arm_texture = self.image_processor.load_image(arm_texture["path"])
            if arm_texture is None:
                return None
        
        # Extract AO from R channel (and save intermediate)
        ao_texture = self._extract_and_save_channel(arm_texture, 0, "ao", "r")
        
        # Extract Roughness from G channel (and save intermediate)
        roughness_texture = self._extract_and_save_channel(arm_texture, 1, "roughness", "g")
        
        # Extract Metallic from B channel (and save intermediate)
        metallic_texture = self._extract_and_save_channel(arm_texture, 2, "metallic", "b")
        
        # Return all extracted textures (containing paths to saved intermediates)
        return {
            "ao": ao_texture,
            "roughness": roughness_texture,
            "metallic": metallic_texture,
            "source": arm_texture
        }
    
    def _extract_ao(self, arm_texture):
        """
        Extract AO from the red channel of an ARM texture.
        
        Args:
            arm_texture: ARM texture object
            
        Returns:
            Extracted AO texture object
        """
        print(f"Extracting AO from R channel")
        
        # Extract the red channel (index 0)
        ao_texture = self.image_processor.extract_channel(arm_texture, 0)
        # This method is now replaced by _extract_and_save_channel
        pass
    
    def _extract_roughness(self, arm_texture):
        """
        Extract Roughness from the green channel of an ARM texture.
        
        Args:
            arm_texture: ARM texture object
            
        Returns:
            Extracted Roughness texture object
        """
        print(f"Extracting Roughness from G channel")
        
        # Extract the green channel (index 1)
        roughness_texture = self.image_processor.extract_channel(arm_texture, 1)
        # This method is now replaced by _extract_and_save_channel
        pass 
    
    def _extract_metallic(self, arm_texture):
        """
        Extract Metallic from the blue channel of an ARM texture.
        
        Args:
            arm_texture: ARM texture object
            
        Returns:
            Extracted Metallic texture object
        """
        print(f"Extracting Metallic from B channel")
        
        # Extract the blue channel (index 2)
        metallic_texture = self.image_processor.extract_channel(arm_texture, 2)
        # This method is now replaced by _extract_and_save_channel
        pass
        
    def _extract_and_save_channel(self, source_texture_obj, channel_index, output_type, channel_name):
        """
        Extracts a channel using ImageMagick and saves it to a temporary file.
        Updates the path in the returned texture object.
        """
        print(f"Extracting {output_type} from channel {channel_name.upper()}")
        
        source_path = source_texture_obj.get("path")
        if not source_path or not os.path.exists(source_path):
            print(f"Error: Source path for {output_type} extraction not found: {source_path}")
            return None
            
        if not TEMP_DIR:
            print("Error: Temporary directory not available for saving intermediate.")
            return None

        magick_path = shutil.which('magick')
        if not magick_path:
            print("Error: ImageMagick 'magick' command not found in PATH.")
            return None # Cannot save intermediate without ImageMagick

        # Construct temporary output path
        base_filename = Path(source_path).stem
        temp_filename = f"{base_filename}_{output_type}_temp.tif"
        temp_output_path = TEMP_DIR / temp_filename

        # ImageMagick command to extract channel and save
        command = [
            magick_path,
            str(source_path),
            '-channel', channel_name.upper(), # R, G, or B
            '-separate', '+channel',          # Extract the channel
            '-depth', '8',                     # Ensure 8-bit grayscale
            '-define', 'tiff:compression=lzw', # Use LZW compression
            str(temp_output_path)
        ]

        try:
            print(f"Executing: {' '.join(command)}")
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            # print(f"ImageMagick STDOUT: {result.stdout}") # Usually empty on success
            # print(f"ImageMagick STDERR: {result.stderr}") # Can contain warnings
            print(f"Successfully saved intermediate {output_type} to {temp_output_path}")

            # Create a new texture object for the intermediate file
            # We use PIL here just to get dimensions easily, could use identify too
            try:
                 intermediate_img_data = self.image_processor.load_image(str(temp_output_path))
                 if not intermediate_img_data:
                      raise ValueError("Failed to load saved intermediate image")
            except Exception as pil_e:
                 print(f"Warning: Could not load intermediate {output_type} with PIL: {pil_e}. Using default info.")
                 intermediate_img_data = {"width": 0, "height": 0, "channels": 1, "mode": "L"}


            intermediate_texture = {
                "path": str(temp_output_path), # CRITICAL: Path to the saved file
                "image": intermediate_img_data.get("image"), # Keep image in memory if loaded
                "width": intermediate_img_data.get("width"),
                "height": intermediate_img_data.get("height"),
                "channels": 1,
                "mode": "L",
                "type": output_type,
                "source": "extracted_from_arm",
                "arm_source": source_texture_obj,
                "channel": channel_name
            }
            return intermediate_texture

        except subprocess.CalledProcessError as e:
            print(f"Error executing ImageMagick for {output_type} extraction:")
            print(f"Command: {' '.join(e.cmd)}")
            print(f"Return Code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during {output_type} extraction/saving: {e}")
            return None
    
    def convert_roughness_to_glossiness(self, roughness_texture):
        """
        Convert a roughness texture to glossiness by inverting it.
        
        Args:
            roughness_texture: Roughness texture object
            
        Returns:
            Glossiness texture object
        """
        print(f"Converting roughness to glossiness by inverting")
        
        # Load roughness image if needed
        if "image" not in roughness_texture:
            roughness_texture = self.image_processor.load_image(roughness_texture["path"])
            if roughness_texture is None:
                return None
        
        # Invert the roughness to get glossiness
        glossiness_texture = self.image_processor.invert_image(roughness_texture)
        
        if glossiness_texture:
            glossiness_texture["type"] = "glossiness"
            glossiness_texture["source"] = "converted_from_roughness"
            glossiness_texture["roughness_source"] = roughness_texture
        
        return glossiness_texture
