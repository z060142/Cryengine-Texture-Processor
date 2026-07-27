#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Albedo Processor

This module provides functionality for processing input textures to generate
albedo intermediate format (pure color without lighting information).
"""

import numpy as np
from PIL import Image
from utils.image_processing import ImageProcessor

class AlbedoProcessor:
    """
    Class for processing input textures to generate albedo intermediate format.
    """
    
    def __init__(self):
        """
        Initialize the albedo processor.
        """
        self.image_processor = ImageProcessor()
    
    def process_from_diffuse(self, diffuse_texture, ao_texture=None):
        """
        Generate albedo from diffuse texture, optionally using AO.
        
        Args:
            diffuse_texture: Diffuse texture object
            ao_texture: Optional AO texture object
            
        Returns:
            Generated albedo texture object or None if generation failed
        """
        # Load diffuse image if needed
        if "image" not in diffuse_texture:
            diffuse_texture = self.image_processor.load_image(diffuse_texture["path"])
            if diffuse_texture is None:
                return None
        
        # Simply use diffuse as albedo without applying AO
        # AO will be applied in diff_exporter if needed
        print("Using diffuse as albedo (without AO)")
        
        # Create a copy of the texture object
        albedo_texture = dict(diffuse_texture)
        albedo_texture["type"] = "albedo"
        albedo_texture["source"] = "from_diffuse"
        albedo_texture["diffuse_source"] = diffuse_texture
        
        return albedo_texture
    
    def process_from_basecolor(self, basecolor_texture):
        """
        Use basecolor texture as albedo (basecolor is already albedo).
        
        Args:
            basecolor_texture: Basecolor texture object
            
        Returns:
            Albedo texture object
        """
        print("Using basecolor as albedo")
        
        # Load basecolor image if needed
        if "image" not in basecolor_texture:
            basecolor_texture = self.image_processor.load_image(basecolor_texture["path"])
            if basecolor_texture is None:
                return None
        
        # Basecolor is already albedo, so just re-label it
        albedo_texture = dict(basecolor_texture)
        albedo_texture["type"] = "albedo"
        albedo_texture["source"] = "from_basecolor"
        albedo_texture["basecolor_source"] = basecolor_texture
        
        return albedo_texture
    
    def process_from_diffuse_and_metallic(self, diffuse_texture, metallic_texture):
        """
        Generate albedo from diffuse and metallic textures.
        Similar to refl.py logic for creating albedo.
        
        Args:
            diffuse_texture: Diffuse texture object
            metallic_texture: Metallic texture object
            
        Returns:
            Generated albedo texture object
        """
        print("Generating albedo from diffuse and metallic")
        
        # Load diffuse image if needed
        if "image" not in diffuse_texture:
            diffuse_texture = self.image_processor.load_image(diffuse_texture["path"])
            if diffuse_texture is None:
                return None
        
        # Load metallic image if needed
        if "image" not in metallic_texture:
            metallic_texture = self.image_processor.load_image(metallic_texture["path"])
            if metallic_texture is None:
                return None
        
        # Convert metallic to grayscale if not already
        metallic_gray = self.image_processor.convert_to_grayscale(metallic_texture)
        
        # Invert metallic (non-metal areas become white)
        inverted_metallic = self.image_processor.invert_image(metallic_gray)
        
        # Apply linear-burn compositing (like in refl.py)
        # This is essentially: max(0, diffuse + inverted_metallic - 1)
        # Which makes metallic areas darker in the albedo
        
        diffuse_img = diffuse_texture["image"]
        metallic_img = inverted_metallic["image"]
        
        # Convert to numpy arrays for processing
        diffuse_array = np.array(diffuse_img).astype(np.float32) / 255.0
        metallic_array = np.array(metallic_img).astype(np.float32) / 255.0
        
        # If metallic is single channel, expand to match diffuse dimensions
        if len(metallic_array.shape) == 2:
            metallic_array = np.expand_dims(metallic_array, axis=2)
            if diffuse_array.shape[2] == 3:
                metallic_array = np.repeat(metallic_array, 3, axis=2)
            elif diffuse_array.shape[2] == 4:
                metallic_array = np.repeat(metallic_array, 4, axis=2)
        
        # Apply linear burn formula: max(0, a + b - 1)
        result_array = np.maximum(0, diffuse_array + metallic_array - 1.0)
        
        # Convert back to 8-bit
        result_array = (result_array * 255.0).astype(np.uint8)
        
        # Create PIL image from array
        result_mode = diffuse_img.mode
        result_img = Image.fromarray(result_array, mode=result_mode)
        
        # Create result texture
        albedo_texture = {
            "path": f"{diffuse_texture.get('path', '')}_albedo",
            "image": result_img,
            "width": result_img.width,
            "height": result_img.height,
            "channels": len(result_img.getbands()),
            "mode": result_img.mode,
            "type": "albedo",
            "source": "generated_from_diffuse_metallic",
            "diffuse_source": diffuse_texture,
            "metallic_source": metallic_texture
        }
        
        return albedo_texture
    
    def check_is_albedo(self, texture):
        """
        Check if a texture is likely an albedo texture.
        
        Args:
            texture: Texture object to check
            
        Returns:
            True if likely albedo, False otherwise
        """
        # Check filename for albedo-related suffixes
        filename = texture.get("filename", "").lower()
        albedo_suffixes = ["_albedo", "_basecolor", "_color", "_c", "_diffuse"]
        
        for suffix in albedo_suffixes:
            if suffix in filename:
                return True
        
        # If we have the image data, could perform additional analysis here
        
        return False
