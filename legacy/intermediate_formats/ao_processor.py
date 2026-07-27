#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ambient Occlusion Processor

This module provides functionality for processing ambient occlusion (AO) maps.
"""

from utils.image_processing import ImageProcessor

class AOProcessor:
    """
    Class for processing ambient occlusion maps.
    """
    
    def __init__(self):
        """
        Initialize the AO processor.
        """
        self.image_processor = ImageProcessor()
    
    def process(self, ao_texture):
        """
        Process an ambient occlusion map (convert to grayscale if needed).
        
        Args:
            ao_texture: AO texture object
            
        Returns:
            Processed AO texture object
        """
        print("Processing ambient occlusion map")
        
        # Load AO image if needed
        if "image" not in ao_texture:
            ao_texture = self.image_processor.load_image(ao_texture["path"])
            if ao_texture is None:
                return None
        
        # Ensure AO map is grayscale
        if ao_texture["image"].mode != "L":
            ao_texture = self.image_processor.convert_to_grayscale(ao_texture)
        
        # Create result texture
        result = dict(ao_texture)
        result["type"] = "ao"
        result["source"] = "processed"
        
        return result
    
    def adjust_ao_strength(self, ao_texture, strength=1.0):
        """
        Adjust the strength of an ambient occlusion map.
        
        Args:
            ao_texture: AO texture object
            strength: Strength adjustment (0.0-2.0, where 1.0 is unchanged)
            
        Returns:
            Adjusted AO texture object
        """
        print(f"Adjusting ambient occlusion strength to {strength}")
        
        # Load AO image if needed
        if "image" not in ao_texture:
            ao_texture = self.image_processor.load_image(ao_texture["path"])
            if ao_texture is None:
                return None
        
        # Ensure AO map is grayscale
        if ao_texture["image"].mode != "L":
            ao_texture = self.image_processor.convert_to_grayscale(ao_texture)
        
        # Apply strength adjustment
        import numpy as np
        from PIL import Image
        
        # Get image as array
        image = ao_texture["image"]
        img_array = np.array(image).astype(np.float32)
        
        # Normalize to 0-1
        img_array = img_array / 255.0
        
        # Apply power function to adjust strength
        if strength >= 1.0:
            # When strength > 1, darker areas get even darker
            power = strength
        else:
            # When strength < 1, reduce contrast
            power = strength * 2  # Scale to make effect more noticeable
        
        img_array = np.power(img_array, power)
        
        # Ensure values stay in 0-1 range
        img_array = np.clip(img_array, 0, 1)
        
        # Convert back to 8-bit
        img_array = (img_array * 255.0).astype(np.uint8)
        
        # Create new image
        adjusted_image = Image.fromarray(img_array, mode="L")
        
        # Create result texture
        result = dict(ao_texture)
        result["image"] = adjusted_image
        result["type"] = "ao"
        result["source"] = "adjusted_strength"
        result["ao_source"] = ao_texture
        result["strength"] = strength
        
        return result
    
    def invert_ao(self, ao_texture):
        """
        Invert an ambient occlusion map.
        
        Args:
            ao_texture: AO texture object
            
        Returns:
            Inverted AO texture object
        """
        print("Inverting ambient occlusion map")
        
        # Load AO image if needed
        if "image" not in ao_texture:
            ao_texture = self.image_processor.load_image(ao_texture["path"])
            if ao_texture is None:
                return None
        
        # Ensure AO map is grayscale
        if ao_texture["image"].mode != "L":
            ao_texture = self.image_processor.convert_to_grayscale(ao_texture)
        
        # Invert the image
        inverted_texture = self.image_processor.invert_image(ao_texture)
        
        if inverted_texture:
            inverted_texture["type"] = "ao"
            inverted_texture["source"] = "inverted"
            inverted_texture["ao_source"] = ao_texture
        
        return inverted_texture
    
    def generate_default_ao(self, width=1024, height=1024, value=255):
        """
        Generate a default ambient occlusion texture (flat white by default).
        
        Args:
            width: Width of the texture
            height: Height of the texture
            value: AO value (0-255, higher = less occlusion)
            
        Returns:
            Default AO texture object
        """
        print(f"Generating default ambient occlusion texture ({width}x{height}, value={value})")
        
        # Create a solid gray image
        from PIL import Image
        import numpy as np
        
        # Default is white (no occlusion)
        gray_array = np.ones((height, width), dtype=np.uint8) * value
        gray_image = Image.fromarray(gray_array, mode="L")
        
        # Create result texture
        ao_texture = {
            "path": "default_ao",
            "image": gray_image,
            "width": width,
            "height": height,
            "channels": 1,
            "mode": "L",
            "type": "ao",
            "source": "default"
        }
        
        return ao_texture
