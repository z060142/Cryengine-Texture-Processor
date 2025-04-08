#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Extractor

This module provides functionality for extracting texture references from models using Blender's Python API.
"""

import os
import importlib

class TextureReference:
    """
    Class representing a reference to a texture in a model material.
    """
    
    def __init__(self, path, texture_type, material_name):
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
            "processed_path": self.processed_path
        }


class TextureExtractor:
    """
    Class for extracting texture references from models.
    """
    
    def __init__(self):
        """
        Initialize the texture extractor.
        """
        # Mapping from Blender texture types to our texture types
        self.texture_type_map = {
            "Base Color": "diffuse",
            "Diffuse": "diffuse",
            "Diffuse Color": "diffuse",
            "Normal": "normal",
            "Normal Map": "normal",
            "Specular": "specular",
            "Specular Color": "specular",
            "Roughness": "roughness",
            "Glossiness": "glossiness",
            "Glossy": "glossiness",
            "Glossy BSDF": "glossiness",
            "Metallic": "metallic",
            "Emission": "emissive",
            "Emission Color": "emissive",
            "Alpha": "alpha",
            "Opacity": "alpha",
            "Ambient Occlusion": "ao",
            "AO": "ao",
            "Height": "displacement",
            "Displacement": "displacement",
            "Bump": "displacement"
        }
        
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
        if not self.bpy or model.get("is_dummy", False):
            # Create dummy texture references if bpy is not available or model is a dummy
            return self._create_dummy_references(model)
            
        # Check if this is an import-only model (created by alternative import method)
        if model.get("is_import_only", False):
            # Use the enhanced dummy reference creation that scans directories
            return self._create_enhanced_references(model)
        
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
                                material_name=material.name
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
        texture_type = "diffuse"  # Default to diffuse
        
        # Check node connections
        if node.outputs and len(node.outputs) > 0:
            for output in node.outputs:
                for link in output.links:
                    if link.to_socket:
                        socket_name = link.to_socket.name
                        if socket_name in self.texture_type_map:
                            return self.texture_type_map[socket_name]
                        
                        # Check some common socket names
                        socket_name_lower = socket_name.lower()
                        if "color" in socket_name_lower or "albedo" in socket_name_lower:
                            return "diffuse"
                        elif "normal" in socket_name_lower:
                            return "normal"
                        elif "specular" in socket_name_lower:
                            return "specular"
                        elif "rough" in socket_name_lower:
                            return "roughness"
                        elif "gloss" in socket_name_lower or "glossy" in socket_name_lower:
                            return "glossiness"
                        elif "metal" in socket_name_lower:
                            return "metallic"
                        elif "emission" in socket_name_lower or "emissive" in socket_name_lower:
                            return "emissive"
                        elif "alpha" in socket_name_lower or "opacity" in socket_name_lower:
                            return "alpha"
                        elif "ao" in socket_name_lower or "ambient" in socket_name_lower or "occlusion" in socket_name_lower:
                            return "ao"
                        elif "height" in socket_name_lower or "displace" in socket_name_lower or "bump" in socket_name_lower:
                            return "displacement"
        
        # Check node name
        node_name = node.name.lower()
        if "color" in node_name or "albedo" in node_name or "diffuse" in node_name:
            return "diffuse"
        elif "normal" in node_name:
            return "normal"
        elif "specular" in node_name:
            return "specular"
        elif "rough" in node_name:
            return "roughness"
        elif "gloss" in node_name or "glossy" in node_name:
            return "glossiness"
        elif "metal" in node_name:
            return "metallic"
        elif "emission" in node_name or "emissive" in node_name:
            return "emissive"
        elif "alpha" in node_name or "opacity" in node_name:
            return "alpha"
        elif "ao" in node_name or "ambient" in node_name or "occlusion" in node_name:
            return "ao"
        elif "height" in node_name or "displace" in node_name or "bump" in node_name:
            return "displacement"
        
        return texture_type
    
    def _create_enhanced_references(self, model):
        """
        Create enhanced texture references for import-only models.
        This method performs a more thorough scan for textures in common locations.
        
        Args:
            model: Model dictionary with is_import_only=True
            
        Returns:
            List of TextureReference objects
        """
        texture_references = []
        
        # Get the model path and extract directory
        model_path = model.get("path", "")
        model_dir = os.path.dirname(model_path)
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        
        print(f"Scanning for textures for import-only model: {model_name}")
        
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
        
        # Mapping of filename patterns to texture types
        # The order matters for priority
        pattern_to_type = {
            "normal": ["_normal", "_norm", "_n", "_nrm", "_ddn", "_ddna", "_nor", "_nor_dx", "_nor_gl"],
            "diffuse": ["_diffuse", "_diff", "_albedo", "_color", "_col", "_d", "_basecolor"],
            "specular": ["_specular", "_spec", "_s", "reflection", "_refl"],
            "glossiness": ["_glossiness", "_gloss", "_glossy", "_g", "_smoothness"],
            "roughness": ["_roughness", "_rough", "_r"],
            "displacement": ["_displacement", "_disp", "_height", "_bump", "_h", "_displ"],
            "metallic": ["_metallic", "_metal", "_m", "_metalness"],
            "ao": ["_ao", "_ambient", "_occlusion"],
            "alpha": ["_alpha", "_opacity", "_transparency", "_a"],
            "emissive": ["_emissive", "_emission", "_glow", "_e"],
            "sss": ["_sss", "_subsurface"]
        }
        
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
                            file_lower = file.lower()
                            
                            # Determine texture type from filename
                            texture_type = "diffuse"  # Default if no pattern matches
                            
                            # Check each pattern for a match
                            for typ, patterns in pattern_to_type.items():
                                if any(pattern in file_lower for pattern in patterns):
                                    texture_type = typ
                                    break
                            
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
                                    material_name=material_name
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
        
    def _create_dummy_references(self, model):
        """
        Create dummy texture references when bpy is not available or model is dummy.
        
        Args:
            model: Model dictionary
            
        Returns:
            List of dummy TextureReference objects
        """
        texture_references = []
        
        # Parse model path to get base directory
        model_dir = os.path.dirname(model.get("path", ""))
        
        # Check if a textures folder exists in the same directory as the model
        textures_dir = os.path.join(model_dir, "textures")
        if os.path.exists(textures_dir) and os.path.isdir(textures_dir):
            # Look for common texture file patterns
            for root, _, files in os.walk(textures_dir):
                for file in files:
                    if file.lower().endswith((".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp")):
                        file_path = os.path.join(root, file)
                        file_lower = file.lower()
                        
                        # Try to determine texture type from filename
                        texture_type = "diffuse"  # Default
                        if "_normal" in file_lower or "_n" in file_lower or "_nrm" in file_lower:
                            texture_type = "normal"
                        elif "_spec" in file_lower or "_s" in file_lower:
                            texture_type = "specular"
                        elif "_rough" in file_lower or "_r" in file_lower:
                            texture_type = "roughness"
                        elif "_gloss" in file_lower or "_glossy" in file_lower or "_g" in file_lower:
                            texture_type = "glossiness"
                        elif "_metal" in file_lower or "_m" in file_lower:
                            texture_type = "metallic"
                        elif "_emission" in file_lower or "_e" in file_lower or "_emissive" in file_lower:
                            texture_type = "emissive"
                        elif "_alpha" in file_lower or "_a" in file_lower or "_opacity" in file_lower:
                            texture_type = "alpha"
                        elif "_ao" in file_lower or "_ambient" in file_lower or "_occlusion" in file_lower:
                            texture_type = "ao"
                        elif "_height" in file_lower or "_h" in file_lower or "_disp" in file_lower or "_displacement" in file_lower:
                            texture_type = "displacement"
                        
                        # Create texture reference
                        texture_references.append(
                            TextureReference(
                                path=file_path,
                                texture_type=texture_type,
                                material_name="Material"  # Generic material name
                            )
                        )
        
        return texture_references
    
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
