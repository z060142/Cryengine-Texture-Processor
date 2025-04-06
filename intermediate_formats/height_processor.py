#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Height Processor

This module provides functionality for processing height/displacement maps.
"""

from utils.image_processing import ImageProcessor

class HeightProcessor:
    """
    Class for processing height/displacement maps.
    """
    
    def __init__(self):
        """
        Initialize the height processor.
        """
        self.image_processor = ImageProcessor()
    
    def process(self, height_texture):
        """
        Process a height/displacement map (convert to grayscale if needed).
        
        Args:
            height_texture: Height/displacement texture object
            
        Returns:
            Processed height texture object
        """
        print(f"Processing height/displacement map")
        
        # Load height image if needed
        if "image" not in height_texture:
            height_texture = self.image_processor.load_image(height_texture["path"])
            if height_texture is None:
                return None
        
        # Ensure height map is grayscale
        if height_texture["image"].mode != "L":
            height_texture = self.image_processor.convert_to_grayscale(height_texture)
        
        # Create result texture
        result = dict(height_texture)
        result["type"] = "height"
        result["source"] = "processed"
        
        return result
    
    def normalize_height(self, height_texture):
        """
        Normalize a height map to use the full 0-255 range.
        
        Args:
            height_texture: Height texture object
            
        Returns:
            Normalized height texture object
        """
        print(f"Normalizing height map")
        
        # Load height image if needed
        if "image" not in height_texture:
            height_texture = self.image_processor.load_image(height_texture["path"])
            if height_texture is None:
                return None
        
        # Ensure height map is grayscale
        if height_texture["image"].mode != "L":
            height_texture = self.image_processor.convert_to_grayscale(height_texture)
        
        # Normalize the image
        from PIL import ImageOps
        
        # Create a copy of the image to avoid modifying the original
        image = height_texture["image"].copy()
        
        # Apply normalization
        normalized_image = ImageOps.autocontrast(image, cutoff=0)
        
        # Create result texture
        result = dict(height_texture)
        result["image"] = normalized_image
        result["type"] = "height"
        result["source"] = "normalized"
        result["height_source"] = height_texture
        
        return result
    
    def invert_height(self, height_texture):
        """
        Invert a height map (flip values so white becomes black and vice versa).
        
        Args:
            height_texture: Height texture object
            
        Returns:
            Inverted height texture object
        """
        print(f"Inverting height map")
        
        # Load height image if needed
        if "image" not in height_texture:
            height_texture = self.image_processor.load_image(height_texture["path"])
            if height_texture is None:
                return None
        
        # Ensure height map is grayscale
        if height_texture["image"].mode != "L":
            height_texture = self.image_processor.convert_to_grayscale(height_texture)
        
        # Invert the image
        inverted_texture = self.image_processor.invert_image(height_texture)
        
        if inverted_texture:
            inverted_texture["type"] = "height"
            inverted_texture["source"] = "inverted"
            inverted_texture["height_source"] = height_texture
        
        return inverted_texture
    
    def adjust_height_levels(self, height_texture, black_point=0, white_point=255, gamma=1.0):
        """
        Adjust levels of a height map.
        
        Args:
            height_texture: Height texture object
            black_point: New black point (0-255)
            white_point: New white point (0-255)
            gamma: Gamma correction value
            
        Returns:
            Adjusted height texture object
        """
        print(f"Adjusting height map levels (black={black_point}, white={white_point}, gamma={gamma})")
        
        # Load height image if needed
        if "image" not in height_texture:
            height_texture = self.image_processor.load_image(height_texture["path"])
            if height_texture is None:
                return None
        
        # Ensure height map is grayscale
        if height_texture["image"].mode != "L":
            height_texture = self.image_processor.convert_to_grayscale(height_texture)
        
        # Apply levels adjustment
        import numpy as np
        from PIL import Image
        
        # Get image as array
        image = height_texture["image"]
        img_array = np.array(image).astype(np.float32)
        
        # Normalize to 0-1
        img_array = img_array / 255.0
        
        # Apply black and white point
        img_array = (img_array - black_point/255.0) / ((white_point - black_point)/255.0)
        img_array = np.clip(img_array, 0, 1)
        
        # Apply gamma
        if gamma != 1.0:
            img_array = np.power(img_array, 1.0/gamma)
        
        # Convert back to 8-bit
        img_array = (img_array * 255.0).astype(np.uint8)
        
        # Create new image
        adjusted_image = Image.fromarray(img_array, mode="L")
        
        # Create result texture
        result = dict(height_texture)
        result["image"] = adjusted_image
        result["type"] = "height"
        result["source"] = "adjusted_levels"
        result["height_source"] = height_texture
        result["levels_settings"] = {
            "black_point": black_point,
            "white_point": white_point,
            "gamma": gamma
        }
        
        return result
