#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Image Processing Utilities

This module provides utility functions for image processing tasks using Pillow (PIL) library.
"""

from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageStat
import os
import numpy as np

class ImageProcessor:
    """
    Class providing image processing utility functions.
    """
    
    @staticmethod
    def load_image(file_path):
        """
        Load an image from a file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Loaded image object or None if loading failed
        """
        try:
            image = Image.open(file_path)
            
            # Return image data dictionary
            return {
                "path": file_path,
                "image": image,
                "width": image.width,
                "height": image.height,
                "channels": len(image.getbands()),
                "mode": image.mode,
                "filename": os.path.basename(file_path)
            }
        except Exception as e:
            print(f"Error loading image from {file_path}: {e}")
            return None
    
    @staticmethod
    def save_image(image_data, file_path, file_format="TIFF"):
        """
        Save an image to a file.
        
        Args:
            image_data: Image data dictionary containing 'image' key with PIL Image
            file_path: Path to save the image to
            file_format: Format to save the image in
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            image = image_data.get("image")
            if image is None:
                return False
                
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save image in specified format
            if file_format.lower() in ["tiff", "tif"]:
                image.save(file_path, "TIFF", compression="lzw")
            else:
                image.save(file_path, file_format)
                
            print(f"Saved image to {file_path}")
            return True
        except Exception as e:
            print(f"Error saving image to {file_path}: {e}")
            return False
    
    @staticmethod
    def resize_image(image_data, width, height, filter_type="LANCZOS"):
        """
        Resize an image.
        
        Args:
            image_data: Image data dictionary
            width: Target width
            height: Target height
            filter_type: Resampling filter type (NEAREST, BILINEAR, BICUBIC, LANCZOS)
            
        Returns:
            Resized image data dictionary
        """
        try:
            image = image_data.get("image")
            if image is None:
                return image_data
            
            # Map filter type string to PIL resampling filter
            filter_map = {
                "NEAREST": Image.NEAREST,
                "BILINEAR": Image.BILINEAR,
                "BICUBIC": Image.BICUBIC, 
                "LANCZOS": Image.LANCZOS
            }
            
            # Get filter
            resample_filter = filter_map.get(filter_type.upper(), Image.LANCZOS)
            
            # Resize image
            resized_image = image.resize((width, height), resample_filter)
            
            # Create new image data dictionary
            resized_data = dict(image_data)
            resized_data["image"] = resized_image
            resized_data["width"] = width
            resized_data["height"] = height
            
            return resized_data
        except Exception as e:
            print(f"Error resizing image: {e}")
            return image_data
    
    @staticmethod
    def resize_to_resolution(image_data, target_resolution):
        """
        Resize an image to a specific resolution while maintaining aspect ratio.
        If target_resolution is 'original', the image is returned unchanged.
        
        Args:
            image_data: Image data dictionary
            target_resolution: Target resolution ('original', '4096', '2048', '1024', '512')
            
        Returns:
            Resized image data dictionary
        """
        try:
            # If target is 'original', return unchanged
            if target_resolution == "original":
                return image_data
                
            image = image_data.get("image")
            if image is None:
                return image_data
                
            # Get target resolution as int
            try:
                target_size = int(target_resolution)
            except ValueError:
                # If resolution is not a number, return original
                return image_data
                
            # Get current dimensions
            width, height = image.size
            
            # Determine max dimension
            max_dimension = max(width, height)
            
            # If already smaller than target, return original
            if max_dimension <= target_size:
                return image_data
                
            # Calculate scale factor
            scale_factor = target_size / max_dimension
            
            # Calculate new dimensions
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Resize image
            return ImageProcessor.resize_image(image_data, new_width, new_height, "LANCZOS")
                
        except Exception as e:
            print(f"Error resizing to resolution: {e}")
            return image_data
    
    @staticmethod
    def flip_channel(image_data, channel_index):
        """
        Flip (invert) a specific channel in an image.
        
        Args:
            image_data: Image data dictionary
            channel_index: Channel to flip (0=R, 1=G, 2=B, 3=A)
            
        Returns:
            Image data dictionary with flipped channel
        """
        try:
            image = image_data.get("image")
            if image is None:
                return image_data
            
            # Ensure image has sufficient channels
            bands = list(image.split())
            if channel_index >= len(bands):
                print(f"Channel index {channel_index} out of range")
                return image_data
            
            # Invert the specified channel
            bands[channel_index] = ImageOps.invert(bands[channel_index])
            
            # Recombine channels
            if image.mode == "RGB":
                new_image = Image.merge("RGB", bands)
            elif image.mode == "RGBA":
                new_image = Image.merge("RGBA", bands)
            elif image.mode == "L":
                new_image = bands[0]
            else:
                # For other modes, convert to RGB first
                rgb_image = image.convert("RGB")
                rgb_bands = list(rgb_image.split())
                rgb_bands[channel_index] = ImageOps.invert(rgb_bands[channel_index])
                new_image = Image.merge("RGB", rgb_bands)
            
            # Create new image data dictionary
            result = dict(image_data)
            result["image"] = new_image
            
            return result
        except Exception as e:
            print(f"Error flipping channel: {e}")
            return image_data
    
    @staticmethod
    def split_channels(image_data):
        """
        Split an image into its constituent channels.
        
        Args:
            image_data: Image data dictionary
            
        Returns:
            List of image data dictionaries, one for each channel
        """
        try:
            image = image_data.get("image")
            if image is None:
                return []
            
            # Split image into individual channels
            bands = image.split()
            
            # Create image data dictionaries for each channel
            channel_names = ["red", "green", "blue", "alpha"]
            result = []
            
            for i, band in enumerate(bands):
                channel_name = channel_names[i] if i < len(channel_names) else f"channel_{i}"
                
                # Convert band to L mode (8-bit grayscale)
                if band.mode != "L":
                    band = band.convert("L")
                
                channel_data = {
                    "path": image_data.get("path", "") + f"_{channel_name}",
                    "image": band,
                    "width": band.width,
                    "height": band.height,
                    "channels": 1,
                    "mode": "L",
                    "channel_index": i,
                    "channel_name": channel_name,
                    "source": image_data
                }
                
                result.append(channel_data)
            
            return result
        except Exception as e:
            print(f"Error splitting channels: {e}")
            return []
    
    @staticmethod
    def combine_channels(channels, output_mode="RGB"):
        """
        Combine individual channels into a single image.
        
        Args:
            channels: List of image data dictionaries (one per channel)
            output_mode: Output mode (RGB, RGBA, etc.)
            
        Returns:
            Combined image data dictionary
        """
        try:
            # Extract PIL image from each channel data dictionary
            bands = []
            width = 0
            height = 0
            source_path = ""
            
            for channel_data in channels:
                image = channel_data.get("image")
                if image is None:
                    continue
                
                # If image is not in L mode, convert it
                if image.mode != "L":
                    image = image.convert("L")
                
                bands.append(image)
                
                # Get dimensions from first channel
                if width == 0 or height == 0:
                    width = image.width
                    height = image.height
                    source_path = channel_data.get("path", "")
            
            # Check if we have enough channels for the desired mode
            required_channels = {
                "L": 1,
                "LA": 2,
                "RGB": 3,
                "RGBA": 4
            }
            
            if len(bands) < required_channels.get(output_mode, 0):
                print(f"Not enough channels for {output_mode} mode")
                return None
            
            # If we have more channels than needed, truncate
            if len(bands) > required_channels.get(output_mode, 0):
                bands = bands[:required_channels.get(output_mode, len(bands))]
            
            # Combine channels
            combined_image = Image.merge(output_mode, bands)
            
            # Create result image data dictionary
            result = {
                "path": source_path + "_combined",
                "image": combined_image,
                "width": width,
                "height": height,
                "channels": len(output_mode),
                "mode": output_mode
            }
            
            return result
        except Exception as e:
            print(f"Error combining channels: {e}")
            return None
    
    @staticmethod
    def multiply_images(image_data1, image_data2):
        """
        Multiply two images together (per-pixel multiplication).
        
        Args:
            image_data1: First image data dictionary
            image_data2: Second image data dictionary
            
        Returns:
            Result of multiplication as image data dictionary
        """
        try:
            image1 = image_data1.get("image")
            image2 = image_data2.get("image")
            
            if image1 is None or image2 is None:
                return None
            
            # Ensure both images have the same size
            if image1.size != image2.size:
                # Resize the second image to match the first
                image2 = image2.resize(image1.size, Image.LANCZOS)
            
            # Multiply images
            result_image = ImageChops.multiply(image1, image2)
            
            # Create result image data dictionary
            result = {
                "path": image_data1.get("path", "") + "_multiplied",
                "image": result_image,
                "width": result_image.width,
                "height": result_image.height,
                "channels": len(result_image.getbands()),
                "mode": result_image.mode
            }
            
            return result
        except Exception as e:
            print(f"Error multiplying images: {e}")
            return None
    
    @staticmethod
    def invert_image(image_data):
        """
        Invert all channels of an image.
        
        Args:
            image_data: Image data dictionary
            
        Returns:
            Inverted image data dictionary
        """
        try:
            image = image_data.get("image")
            if image is None:
                return image_data
            
            # Invert image
            inverted_image = ImageOps.invert(image)
            
            # Create result image data dictionary
            result = dict(image_data)
            result["image"] = inverted_image
            result["path"] = image_data.get("path", "") + "_inverted"
            
            return result
        except Exception as e:
            print(f"Error inverting image: {e}")
            return image_data
    
    @staticmethod
    def convert_to_grayscale(image_data):
        """
        Convert an image to grayscale.
        
        Args:
            image_data: Image data dictionary
            
        Returns:
            Grayscale image data dictionary
        """
        try:
            image = image_data.get("image")
            if image is None:
                return image_data
            
            # Convert to grayscale
            grayscale_image = image.convert("L")
            
            # Create result image data dictionary
            result = dict(image_data)
            result["image"] = grayscale_image
            result["path"] = image_data.get("path", "") + "_grayscale"
            result["channels"] = 1
            result["mode"] = "L"
            
            return result
        except Exception as e:
            print(f"Error converting to grayscale: {e}")
            return image_data
    
    @staticmethod
    def apply_colorize(image_data, color_rgb):
        """
        Apply colorization to a grayscale image.
        
        Args:
            image_data: Image data dictionary (should be grayscale)
            color_rgb: Tuple of (R, G, B) values for colorization
            
        Returns:
            Colorized image data dictionary
        """
        try:
            image = image_data.get("image")
            if image is None:
                return image_data
            
            # Ensure image is in L mode
            if image.mode != "L":
                image = image.convert("L")
            
            # Colorize image
            colorized_image = ImageOps.colorize(image, (0, 0, 0), color_rgb)
            
            # Create result image data dictionary
            result = dict(image_data)
            result["image"] = colorized_image
            result["path"] = image_data.get("path", "") + "_colorized"
            result["channels"] = 3
            result["mode"] = "RGB"
            
            return result
        except Exception as e:
            print(f"Error colorizing image: {e}")
            return image_data
    
    @staticmethod
    def extract_channel(image_data, channel_index):
        """
        Extract a specific channel from an image.
        
        Args:
            image_data: Image data dictionary
            channel_index: Channel to extract (0=R, 1=G, 2=B, 3=A)
            
        Returns:
            Image data dictionary containing only the specified channel
        """
        try:
            image = image_data.get("image")
            if image is None:
                return None
            
            # Split image into channels
            bands = list(image.split())
            
            # Check if channel exists
            if channel_index >= len(bands):
                print(f"Channel index {channel_index} out of range")
                return None
            
            # Extract the specified channel
            channel = bands[channel_index]
            
            # Channel names for path extension
            channel_names = ["red", "green", "blue", "alpha"]
            channel_name = channel_names[channel_index] if channel_index < len(channel_names) else f"channel_{channel_index}"
            
            # Create result image data dictionary
            result = {
                "path": image_data.get("path", "") + f"_{channel_name}",
                "image": channel,
                "width": channel.width,
                "height": channel.height,
                "channels": 1,
                "mode": "L",
                "channel_index": channel_index,
                "channel_name": channel_name,
                "source": image_data
            }
            
            return result
        except Exception as e:
            print(f"Error extracting channel: {e}")
            return None
    
    @staticmethod
    def add_alpha_channel(image_data, alpha_data):
        """
        Add or replace alpha channel in an image.
        
        Args:
            image_data: Image data dictionary for base image
            alpha_data: Image data dictionary for alpha channel (or mask)
            
        Returns:
            Image with alpha channel added
        """
        try:
            base_image = image_data.get("image")
            alpha_image = alpha_data.get("image")
            
            if base_image is None or alpha_image is None:
                return image_data
            
            # Ensure base image is in RGB or RGBA mode
            if base_image.mode not in ["RGB", "RGBA"]:
                base_image = base_image.convert("RGB")
            
            # Ensure alpha is in grayscale
            if alpha_image.mode != "L":
                alpha_image = alpha_image.convert("L")
            
            # Resize alpha to match base image if needed
            if alpha_image.size != base_image.size:
                alpha_image = alpha_image.resize(base_image.size, Image.LANCZOS)
            
            # Convert base to RGBA if needed and set alpha
            if base_image.mode == "RGB":
                r, g, b = base_image.split()
                result_image = Image.merge("RGBA", (r, g, b, alpha_image))
            else:  # RGBA
                r, g, b, _ = base_image.split()
                result_image = Image.merge("RGBA", (r, g, b, alpha_image))
            
            # Create result image data dictionary
            result = dict(image_data)
            result["image"] = result_image
            result["path"] = image_data.get("path", "") + "_with_alpha"
            result["channels"] = 4
            result["mode"] = "RGBA"
            
            return result
        except Exception as e:
            print(f"Error adding alpha channel: {e}")
            return image_data
    
    @staticmethod
    def linear_burn(base_data, blend_data):
        """
        Apply linear burn blending mode.
        Formula: max(0, base + blend - 1)
        
        Args:
            base_data: Base image data dictionary
            blend_data: Blend image data dictionary
            
        Returns:
            Result of linear burn as image data dictionary
        """
        try:
            base_image = base_data.get("image")
            blend_image = blend_data.get("image")
            
            if base_image is None or blend_image is None:
                return None
            
            # Ensure both images have the same size
            if base_image.size != blend_image.size:
                blend_image = blend_image.resize(base_image.size, Image.LANCZOS)
            
            # Convert images to numpy arrays (0-1 float)
            base_array = np.array(base_image).astype(np.float32) / 255.0
            blend_array = np.array(blend_image).astype(np.float32) / 255.0
            
            # Apply linear burn formula
            result_array = np.maximum(0, base_array + blend_array - 1.0)
            
            # Convert back to 8-bit
            result_array = (result_array * 255.0).astype(np.uint8)
            
            # Create PIL image from array
            result_image = Image.fromarray(result_array)
            
            # Create result image data dictionary
            result = {
                "path": base_data.get("path", "") + "_linear_burn",
                "image": result_image,
                "width": result_image.width,
                "height": result_image.height,
                "channels": len(result_image.getbands()),
                "mode": result_image.mode
            }
            
            return result
        except Exception as e:
            print(f"Error applying linear burn: {e}")
            return None
    
    @staticmethod
    def generate_normal_from_height(height_data, strength=10.0):
        """
        Generate a normal map from a height/displacement map.
        
        Args:
            height_data: Height map image data dictionary
            strength: Strength of the effect (higher values = more pronounced normals)
            
        Returns:
            Normal map image data dictionary
        """
        try:
            height_image = height_data.get("image")
            if height_image is None:
                return None
            
            # Ensure image is grayscale
            if height_image.mode != "L":
                height_image = height_image.convert("L")
            
            # Convert to numpy array
            height_array = np.array(height_image).astype(np.float32) / 255.0
            
            # Create empty normal map array (RGB)
            normal_array = np.zeros((height_array.shape[0], height_array.shape[1], 3), dtype=np.float32)
            
            # Compute partial derivatives using Sobel operator
            dzdx = np.zeros_like(height_array)
            dzdy = np.zeros_like(height_array)
            
            # Sobel in X direction
            dzdx[:-1, :] = height_array[1:, :] - height_array[:-1, :]
            
            # Sobel in Y direction
            dzdy[:, :-1] = height_array[:, 1:] - height_array[:, :-1]
            
            # Normalize derivatives by strength
            dzdx = -dzdx * strength
            dzdy = -dzdy * strength
            
            # Compute normal vectors
            # Normal X component
            normal_array[:, :, 0] = dzdx
            
            # Normal Y component
            normal_array[:, :, 1] = dzdy
            
            # Normal Z component (always positive)
            normal_array[:, :, 2] = 1.0
            
            # Normalize vectors
            norm = np.sqrt(np.sum(normal_array**2, axis=2, keepdims=True))
            normal_array = normal_array / (norm + 1e-8)  # Avoid division by zero
            
            # Convert from [-1,1] to [0,1] range
            normal_array = normal_array * 0.5 + 0.5
            
            # Convert to 8-bit
            normal_array = (normal_array * 255.0).astype(np.uint8)
            
            # Create PIL image
            normal_image = Image.fromarray(normal_array, mode="RGB")
            
            # Create result image data dictionary
            result = {
                "path": height_data.get("path", "") + "_normal",
                "image": normal_image,
                "width": normal_image.width,
                "height": normal_image.height,
                "channels": 3,
                "mode": "RGB"
            }
            
            return result
        except Exception as e:
            print(f"Error generating normal map: {e}")
            return None
            
    @staticmethod
    def generate_thumbnail(image_path, output_path, size=(256, 256)):
        """
        Generate a thumbnail from an image file.
        
        Args:
            image_path: Path to the original image file
            output_path: Path to save the thumbnail to
            size: Thumbnail size as (width, height) tuple
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open the image
            image = Image.open(image_path)
            
            # Resize image to thumbnail size, keeping aspect ratio
            image.thumbnail(size, Image.LANCZOS)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save thumbnail
            image.save(output_path, "PNG")
            
            print(f"Generated thumbnail at {output_path}")
            return True
        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            return False
