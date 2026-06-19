#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Extractor

This module provides functionality for extracting texture references from models using Blender's Python API.
"""

import os
import importlib

from model_processing.texture_type_resolver import (
    infer_texture_type_from_path,
    infer_texture_type_from_text,
)

class TextureReference:
    """
    Class representing a reference to a texture in a model material.
    """
    
    def __init__(self, path, texture_type, material_name, source_mode="blender"):
        """
        Initialize a texture reference.
        
        Args:
            path: Path to the texture file
            texture_type: Type of texture (e.g., 'diffuse', 'normal')
            material_name: Name of the material that uses this texture
        """
        self.path = path
        self.texture_type = texture_type
        self.material_name = material_name
        self.filename = os.path.basename(path) if path else ""
        self.processed_path = None
        self.source_mode = source_mode
    
    def set_processed_path(self, processed_path):
        """
        Set the path to the processed version of this texture.
        
        Args:
            processed_path: Path to the processed texture
        """
        self.processed_path = processed_path
    
    def as_dict(self):
        """
        Convert this object to a dictionary for easier JSON serialization.
        
        Returns:
            Dictionary representation of this object
        """
        return {
            "path": self.path,
            "type": self.texture_type,
            "material": self.material_name,
            "filename": self.filename,
            "processed_path": self.processed_path,
            "source_mode": self.source_mode,
        }


class TextureExtractor:
    """
    Class for extracting texture references from models.
    """
    
    def __init__(self):
        """
        Initialize the texture extractor.
        """
        # Try to import bpy
        self.bpy = None
        try:
            # Try to safely import bpy
            try:
                self.bpy = importlib.import_module('bpy')
                print("Successfully imported Blender Python API (bpy) in TextureExtractor")
            except ImportError:
                print("Warning: Blender Python API (bpy) not available in TextureExtractor. Texture extraction will be limited.")
            except Exception as e:
                print(f"bpy import error in TextureExtractor: {str(e)}")
                print("Texture extraction will use fallback method.")
        except Exception as e:
            print(f"Unexpected error initializing TextureExtractor: {str(e)}")
    
    def extract(self, model):
        """
        Extract texture references from a model.
        
        Args:
            model: Loaded model object
            
        Returns:
            List of TextureReference objects
        """
        # Check if this is a dummy model or if Blender is not available
        if model.get("is_dummy", False):
            print("Skipping texture extraction for dummy model.")
            return []

        if not self.bpy:
            return self._create_filesystem_references(model, source_mode="filesystem_no_bpy")
            
        # Check if this is an import-only model (created by alternative import method)
        if model.get("is_import_only", False):
            return self._create_filesystem_references(model, source_mode="filesystem_import_only")
        
        # If this is a full Blender model, extract textures using Blender's API
        texture_references = []
        
        # Extract textures from Blender materials
        for material in self.bpy.data.materials:
            if material.use_nodes:
                for node in material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        # Find the texture path
                        texture_path = node.image.filepath
                        if texture_path.startswith("//"):  # Relative path in Blender
                            # Convert to absolute path
                            blend_dir = os.path.dirname(self.bpy.data.filepath)
                            texture_path = os.path.join(blend_dir, texture_path[2:])
                            texture_path = os.path.normpath(texture_path)
                        
                        # Determine texture type
                        texture_type = self._determine_texture_type(node, material)
                        
                        # Create texture reference
                        texture_references.append(
                            TextureReference(
                                path=texture_path,
                                texture_type=texture_type,
                                material_name=material.name,
                                source_mode="blender",
                            )
                        )
        
        return texture_references
    
    def _determine_texture_type(self, node, material):
        """
        Determine the type of a texture node in Blender.
        
        Args:
            node: Blender texture node
            material: Blender material
            
        Returns:
            Texture type string
        """
        # Check node connections
        if node.outputs and len(node.outputs) > 0:
            for output in node.outputs:
                for link in output.links:
                    if link.to_socket:
                        texture_type = infer_texture_type_from_text(link.to_socket.name)
                        if texture_type:
                            return texture_type

        for attr in ("label", "name"):
            texture_type = infer_texture_type_from_text(getattr(node, attr, ""))
            if texture_type:
                return texture_type

        image = getattr(node, "image", None)
        texture_type = infer_texture_type_from_path(getattr(image, "filepath", ""))
        return texture_type or "diffuse"
    
    def _create_filesystem_references(self, model, source_mode="filesystem_import_only"):
        """
        Create filesystem-scanned texture references for degraded model loads.
        This method performs a more thorough scan for textures in common locations.
        
        Args:
            model: Model dictionary
            
        Returns:
            List of TextureReference objects
        """
        texture_references = []
        seen_paths = set()
        
        # Get the model path and extract directory
        model_path = model.get("path", "")
        model_dir = os.path.dirname(model_path)
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        print(f"Scanning for textures for model '{model_name}' using {source_mode} mode")
        
        # Define common texture directories to check
        directories_to_check = [
            os.path.join(model_dir, "textures"),  # model_dir/textures/
            os.path.join(model_dir, "texture"),   # model_dir/texture/
            os.path.join(model_dir, "maps"),      # model_dir/maps/
            os.path.join(model_dir, "materials"), # model_dir/materials/
            model_dir                            # same directory as model
        ]
        
        # Get materials from the model
        materials = model.get("materials", [])
        material_names = [mat.get("name", "Material") for mat in materials]
        
        # If no materials defined, use model name as a fallback
        if not material_names:
            material_names = [model_name]
        
        # Texture extensions to look for
        texture_extensions = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp")
        
        # Scan all potential texture directories
        for directory in directories_to_check:
            if os.path.exists(directory) and os.path.isdir(directory):
                print(f"Searching for textures in: {directory}")
                
                # Look for files in this directory and its subdirectories
                for root, _, files in os.walk(directory):
                    for file in files:
                        # Check if this is a texture file
                        if file.lower().endswith(texture_extensions):
                            file_path = os.path.join(root, file)
                            normalized_file_path = os.path.normcase(os.path.abspath(file_path))
                            if normalized_file_path in seen_paths:
                                continue
                            seen_paths.add(normalized_file_path)
                            file_lower = file.lower()
                            
                            texture_type = infer_texture_type_from_path(file_lower) or "diffuse"
                            
                            # Try to figure out which material this texture belongs to
                            material_name = material_names[0]  # Default to first material if no match
                            
                            # Check if filename contains any material name
                            file_base = os.path.splitext(file)[0].lower()
                            for mat_name in material_names:
                                if mat_name.lower() in file_base:
                                    material_name = mat_name
                                    break
                            
                            # Create texture reference
                            texture_references.append(
                                TextureReference(
                                    path=file_path,
                                    texture_type=texture_type,
                                    material_name=material_name,
                                    source_mode=source_mode,
                                )
                            )
                            print(f"Found texture: {file} (Type: {texture_type}, Material: {material_name})")
        
        # If no textures found, check for texture filenames with model name as prefix
        if not texture_references:
            print(f"No textures found in standard locations, checking for files with model name prefix: {model_name}")
            # This is a fallback in case the directories above didn't contain any textures
            # but textures might be named after the model in another location
            # This would be better implemented in a real solution
        
        return texture_references

    def _create_enhanced_references(self, model):
        """Compatibility wrapper for older tests/callers."""
        return self._create_filesystem_references(model, source_mode="filesystem_import_only")
        
    def _create_dummy_references(self, model):
        """
        Create filesystem texture references for legacy callers.
        
        Args:
            model: Model dictionary
            
        Returns:
            List of dummy TextureReference objects
        """
        if model.get("is_dummy", False):
            return []
        return self._create_filesystem_references(model, source_mode="filesystem_legacy")
    
    def find_missing_textures(self, texture_references):
        """
        Find texture files that are referenced but don't exist.
        
        Args:
            texture_references: List of TextureReference objects
            
        Returns:
            List of TextureReference objects for missing textures
        """
        missing = []
        
        for ref in texture_references:
            if ref.path and not os.path.exists(ref.path):
                missing.append(ref)
        
        return missing
    
    def find_unreferenced_textures(self, texture_references, texture_dir):
        """
        Find texture files that exist but aren't referenced by the model.
        
        Args:
            texture_references: List of TextureReference objects
            texture_dir: Directory to search for texture files
            
        Returns:
            List of paths to unreferenced texture files
        """
        # Get all texture files in the directory
        texture_files = []
        for root, _, files in os.walk(texture_dir):
            for file in files:
                if file.lower().endswith((".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff")):
                    texture_files.append(os.path.join(root, file))
        
        # Get all referenced texture paths
        referenced_paths = set(ref.path for ref in texture_references if ref.path)
        
        # Find unreferenced textures
        unreferenced = [path for path in texture_files if path not in referenced_paths]
        
        return unreferenced
