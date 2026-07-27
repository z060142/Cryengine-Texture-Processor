#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Analyzer

This module provides functionality for analyzing textures to determine their type.
"""

from PIL import Image, ImageStat
import os
import numpy as np

class TextureAnalyzer:
    """
    Class for analyzing textures to determine their type.
    """
    
    @staticmethod
    def analyze_texture_type(image_path):
        """
        Analyze a texture to determine its likely type.
        
        Args:
            image_path: Path to the texture file
            
        Returns:
            Tuple of (texture_type, confidence) where confidence is 0.0-1.0
        """
        try:
            # Open the image
            image = Image.open(image_path)
            
            # Check if the filename already contains type hints
            filename = os.path.basename(image_path).lower()
            type_from_filename = TextureAnalyzer._check_filename_for_type(filename)
            if type_from_filename:
                return type_from_filename, 0.9
            
            # Ensure image is in RGB or RGBA mode for analysis
            if image.mode not in ["RGB", "RGBA"]:
                image = image.convert("RGB")
            
            # Split into channels
            channels = list(image.split())
            
            # Calculate statistics for each channel
            stats = []
            for channel in channels[:3]:  # Only analyze RGB channels
                channel_stats = ImageStat.Stat(channel)
                stats.append({
                    "mean": channel_stats.mean[0],
                    "stddev": channel_stats.stddev[0],
                    "min": min(channel_stats.extrema[0]),
                    "max": max(channel_stats.extrema[0])
                })
            
            # Normal map detection
            if TextureAnalyzer._is_normal_map(stats):
                return "normal", 0.8
            
            # Grayscale texture analysis
            if TextureAnalyzer._is_grayscale(stats):
                # Determine which type of grayscale map
                return TextureAnalyzer._determine_grayscale_type(stats, image)
            
            # Analyze color properties for diffuse/albedo textures
            if TextureAnalyzer._is_likely_diffuse(stats):
                return "diffuse", 0.7
            
            # Check for emissive textures
            if TextureAnalyzer._is_emissive(stats):
                return "emissive", 0.6
            
            # Default to diffuse with low confidence
            return "diffuse", 0.3
            
        except Exception as e:
            print(f"Error analyzing texture {image_path}: {e}")
            return "unknown", 0.0
    
    @staticmethod
    def _check_filename_for_type(filename):
        """
        Check if the filename contains hints about the texture type.
        
        Args:
            filename: Base filename
            
        Returns:
            Detected type or None
        """
        # Check for common suffixes
        if any(suffix in filename for suffix in ["_normal", "_norm", "_n", "_nrm"]):
            return "normal"
        
        if any(suffix in filename for suffix in ["_diffuse", "_diff", "_d", "_albedo", "_basecolor", "_color", "_c"]):
            return "diffuse"
        
        if any(suffix in filename for suffix in ["_specular", "_spec", "_s", "_reflection", "_refl"]):
            return "specular"
        
        if any(suffix in filename for suffix in ["_glossiness", "_gloss", "_g"]):
            return "glossiness"
        
        if any(suffix in filename for suffix in ["_roughness", "_rough", "_r"]):
            return "roughness"
        
        if any(suffix in filename for suffix in ["_displacement", "_displ", "_disp", "_height", "_h"]):
            return "displacement"
        
        if any(suffix in filename for suffix in ["_metallic", "_metal", "_m"]):
            return "metallic"
        
        if any(suffix in filename for suffix in ["_ao", "_ambient", "_occlusion"]):
            return "ao"
        
        if any(suffix in filename for suffix in ["_opacity", "_alpha", "_mask"]):
            return "alpha"
        
        if any(suffix in filename for suffix in ["_emissive", "_emit", "_e"]):
            return "emissive"
        
        if any(suffix in filename for suffix in ["_arm"]):
            return "arm"
        
        return None
    
    @staticmethod
    def _is_normal_map(stats):
        """
        Determine if a texture is likely a normal map based on channel statistics.
        
        Args:
            stats: List of channel statistics
            
        Returns:
            True if likely a normal map, False otherwise
        """
        # Normal maps have:
        # - Red channel centered around 128
        # - Green channel centered around 128
        # - Blue channel typically higher (especially in DirectX normal maps)
        
        if (abs(stats[0]["mean"] - 128) < 30 and
            abs(stats[1]["mean"] - 128) < 30 and
            stats[2]["mean"] > 180):
            return True
        
        # Alternative check for OpenGL normal maps
        if (abs(stats[0]["mean"] - 128) < 30 and
            abs(stats[1]["mean"] - 128) < 30 and
            abs(stats[2]["mean"] - 128) < 30 and
            abs(stats[0]["mean"] - stats[1]["mean"]) < 20 and
            abs(stats[0]["mean"] - stats[2]["mean"]) < 20):
            return True
        
        return False
    
    @staticmethod
    def _is_grayscale(stats):
        """
        Determine if a texture is effectively grayscale (even if stored as RGB).
        
        Args:
            stats: List of channel statistics
            
        Returns:
            True if grayscale, False otherwise
        """
        # Check if all channels have similar mean values
        mean_r = stats[0]["mean"]
        mean_g = stats[1]["mean"]
        mean_b = stats[2]["mean"]
        
        # Calculate maximum difference between any two channels
        max_diff = max(abs(mean_r - mean_g), abs(mean_r - mean_b), abs(mean_g - mean_b))
        
        # If the maximum difference is small, it's likely grayscale
        return max_diff < 15
    
    @staticmethod
    def _determine_grayscale_type(stats, image):
        """
        Determine the specific type of a grayscale texture.
        
        Args:
            stats: List of channel statistics
            image: PIL Image object
            
        Returns:
            Tuple of (type, confidence)
        """
        mean_value = stats[0]["mean"]
        stddev_value = stats[0]["stddev"]
        min_value = stats[0]["min"]
        max_value = stats[0]["max"]
        
        # Calculate histogram to analyze distribution
        hist = image.convert("L").histogram()
        
        # Calculate histogram entropy and bimodality
        total_pixels = sum(hist)
        if total_pixels == 0:
            total_pixels = 1  # Avoid division by zero
            
        # Normalize histogram
        hist_norm = [h / total_pixels for h in hist]
        
        # Calculate entropy (measure of information content)
        entropy = 0
        for h in hist_norm:
            if h > 0:
                entropy -= h * np.log2(h)
        
        # Calculate bimodality coefficient
        bimodality = TextureAnalyzer._calculate_bimodality(hist_norm)
        
        # Displacement/height maps often have a wide range of values
        # and moderate to high entropy
        if max_value - min_value > 150 and entropy > 5.0:
            return "displacement", 0.7
        
        # Metallic maps often have clear distinction between metal/non-metal areas
        # resulting in higher bimodality
        if bimodality > 0.6 and stddev_value > 60:
            return "metallic", 0.7
        
        # Glossiness maps typically have higher mean values
        if mean_value > 150:
            return "glossiness", 0.7
        
        # Roughness maps typically have lower mean values
        if mean_value < 100:
            return "roughness", 0.7
        
        # AO maps typically have mid-range mean values with good contrast
        if 100 <= mean_value <= 180 and stddev_value > 30:
            return "ao", 0.6
        
        # Default to height/displacement as a best guess
        return "displacement", 0.5
    
    @staticmethod
    def _calculate_bimodality(hist):
        """
        Calculate bimodality coefficient of a histogram.
        
        Args:
            hist: Normalized histogram
            
        Returns:
            Bimodality coefficient (0-1, higher means more bimodal)
        """
        # Calculate mean
        mean = sum(i * h for i, h in enumerate(hist))
        
        # Calculate variance
        variance = sum(((i - mean) ** 2) * h for i, h in enumerate(hist))
        if variance == 0:
            return 0  # Avoid division by zero
        
        # Calculate skewness
        skewness = sum(((i - mean) ** 3) * h for i, h in enumerate(hist)) / (variance ** 1.5)
        
        # Calculate kurtosis
        kurtosis = sum(((i - mean) ** 4) * h for i, h in enumerate(hist)) / (variance ** 2)
        
        # Calculate bimodality coefficient
        bimodality = (skewness ** 2 + 1) / kurtosis
        
        # Normalize to 0-1 range (empirical values)
        normalized_bimodality = min(1.0, max(0.0, bimodality / 3.0))
        
        return normalized_bimodality
    
    @staticmethod
    def _is_likely_diffuse(stats):
        """
        Determine if a texture is likely a diffuse/albedo texture.
        
        Args:
            stats: List of channel statistics
            
        Returns:
            True if likely diffuse, False otherwise
        """
        # Diffuse textures typically have:
        # - Good color variation
        # - Medium to high standard deviation in all channels
        # - Relatively balanced channels (unless strongly tinted)
        
        # Check for reasonable color variation
        avg_stddev = (stats[0]["stddev"] + stats[1]["stddev"] + stats[2]["stddev"]) / 3
        
        # Diffuse textures usually have reasonable standard deviation
        if avg_stddev < 15:
            return False  # Too uniform for diffuse
        
        # Check channel imbalance (for textures with strong color tints)
        max_mean = max(stats[0]["mean"], stats[1]["mean"], stats[2]["mean"])
        min_mean = min(stats[0]["mean"], stats[1]["mean"], stats[2]["mean"])
        
        # Extreme channel imbalance might indicate special texture types
        if max_mean > 200 and min_mean < 50 and max_mean - min_mean > 180:
            return False
        
        return True
    
    @staticmethod
    def _is_emissive(stats):
        """
        Determine if a texture is likely an emissive texture.
        
        Args:
            stats: List of channel statistics
            
        Returns:
            True if likely emissive, False otherwise
        """
        # Emissive textures typically have:
        # - Some very bright areas
        # - Some very dark areas
        # - High contrast
        
        # Check for bright colors
        max_brightness = max(stats[0]["max"], stats[1]["max"], stats[2]["max"])
        
        # Check for dark areas
        min_brightness = min(stats[0]["min"], stats[1]["min"], stats[2]["min"])
        
        # Check standard deviation (contrast)
        max_stddev = max(stats[0]["stddev"], stats[1]["stddev"], stats[2]["stddev"])
        
        # Emissive typically has high brightness, dark areas, and high contrast
        if max_brightness > 220 and min_brightness < 30 and max_stddev > 60:
            return True
        
        return False
