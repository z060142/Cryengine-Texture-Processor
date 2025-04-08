#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Normal Map Processor

This module provides functionality for processing normal maps, including
conversion between different formats (DirectX/OpenGL).
"""

from utils.image_processing import ImageProcessor
from PIL import ImageStat

class NormalProcessor:
    """
    Class for processing normal maps.
    """
    
    def __init__(self):
        """
        Initialize the normal map processor.
        """
        self.image_processor = ImageProcessor()
    
    def process(self, normal_texture, is_directx=True):
        """
        Process a normal map, converting between formats if needed.
        
        Args:
            normal_texture: Normal map texture object
            is_directx: Whether the input normal map is in DirectX format
            
        Returns:
            Processed normal map texture object
        """
        print(f"Processing normal map (input format: {'DirectX' if is_directx else 'OpenGL'})")
        
        # Load normal map image if needed
        if "image" not in normal_texture:
            normal_texture = self.image_processor.load_image(normal_texture["path"])
            if normal_texture is None:
                return None
        
        # If already in DirectX format, just return it
        if is_directx:
            result = dict(normal_texture)
            result["type"] = "normal"
            result["source"] = "processed"
            result["format"] = "directx"
            return result
        
        # If in OpenGL format, flip green channel to convert to DirectX
        else:
            # Flip G channel (index 1)
            converted_texture = self.image_processor.flip_channel(normal_texture, 1)
            
            if converted_texture:
                converted_texture["type"] = "normal"
                converted_texture["source"] = "converted_opengl_to_directx"
                converted_texture["input_source"] = normal_texture
                converted_texture["format"] = "directx"
                return converted_texture
        
        return None
    
    def flip_green_channel(self, normal_texture):
        """
        Flip the green channel of a normal map (converts between DirectX and OpenGL).
        
        Args:
            normal_texture: Normal map texture object
            
        Returns:
            Normal map texture object with flipped green channel
        """
        print("Flipping green channel of normal map")
        
        # Load normal map image if needed
        if "image" not in normal_texture:
            normal_texture = self.image_processor.load_image(normal_texture["path"])
            if normal_texture is None:
                return None
        
        # Flip G channel (index 1)
        flipped_texture = self.image_processor.flip_channel(normal_texture, 1)
        
        if flipped_texture:
            flipped_texture["type"] = "normal"
            flipped_texture["source"] = "flipped_green"
            flipped_texture["input_source"] = normal_texture
            flipped_texture["format"] = "directx" if normal_texture.get("format") == "opengl" else "opengl"
            return flipped_texture
        
        return None
    
    def generate_from_height(self, height_texture, strength=10.0):
        """
        Generate a normal map from a height/displacement map.
        
        Args:
            height_texture: Height map texture object
            strength: Strength of the generated normals
            
        Returns:
            Generated normal map texture object
        """
        print(f"Generating normal map from height map (strength: {strength})")
        
        # Load height map image if needed
        if "image" not in height_texture:
            height_texture = self.image_processor.load_image(height_texture["path"])
            if height_texture is None:
                return None
        
        # Generate normal map
        normal_texture = self.image_processor.generate_normal_from_height(height_texture, strength)
        
        if normal_texture:
            normal_texture["type"] = "normal"
            normal_texture["source"] = "generated_from_height"
            normal_texture["height_source"] = height_texture
            normal_texture["strength"] = strength
            normal_texture["format"] = "directx"
            return normal_texture
        
        return None
    
    def determine_format(self, normal_texture):
        """
        Determine if a normal map is in DirectX or OpenGL format.
        
        Args:
            normal_texture: Normal map texture object
            
        Returns:
            "directx" or "opengl" string
        """
        # First check filename for hints
        filename = normal_texture.get("filename", "").lower()
        
        if "opengl" in filename or "gl" in filename:
            return "opengl"
        elif "directx" in filename or "dx" in filename:
            return "directx"
        
        # If no hint in filename, try to analyze the image
        if "image" not in normal_texture:
            normal_texture = self.image_processor.load_image(normal_texture["path"])
            if normal_texture is None:
                return "directx"  # Default to DirectX as it's more common
        
        image = normal_texture.get("image")
        if image:
            # Get channels
            channels = list(image.split())
            if len(channels) < 3:
                return "directx"  # Not enough channels for analysis
            
            # Get stats for green channel
            g_stats = ImageStat.Stat(channels[1])
            g_mean = g_stats.mean[0]
            
            # In DirectX normal maps, green channel tends to have mean > 128
            # In OpenGL normal maps, green channel tends to have mean < 128
            if g_mean < 120:
                return "opengl"
            else:
                return "directx"
        
        # Default to DirectX if analysis failed
        return "directx"
