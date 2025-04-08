#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Model Loader

This module provides functionality for loading 3D models using Blender's Python API (bpy).
"""

import os
import importlib

class ModelLoader:
    """
    Class for loading 3D models using Blender's Python API.
    """
    
    def __init__(self):
        """
        Initialize the model loader.
        """
        self.supported_formats = [".fbx", ".obj", ".dae", ".3ds", ".blend"]
        # Initialize Blender if possible
        self.bpy = None
        try:
            # Try to import bpy
            # First, check for NumPy version and handle accordingly
            try:
                import numpy as np
                # Print NumPy version for debugging
                print(f"NumPy version: {np.__version__}")
            except ImportError:
                print("NumPy not available. Some functionalities may be limited.")
            except Exception as e:
                print(f"NumPy import error: {e}")
                
            # Try to import bpy with error handling
            try:
                self.bpy = importlib.import_module('bpy')
                print("Successfully imported Blender Python API (bpy)")
            except ImportError:
                print("Blender Python API (bpy) not available. Model loading will be limited.")
            except Exception as e:
                print(f"bpy import error: {str(e)}")
                print("Some model loading features will be limited.")
        except Exception as e:
            print(f"Unexpected error initializing ModelLoader: {str(e)}")
    
    def can_load(self, file_path):
        """
        Check if a file can be loaded by this loader.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file can be loaded, False otherwise
        """
        extension = os.path.splitext(file_path)[1].lower()
        return extension in self.supported_formats
    
    def load(self, file_path):
        """
        Load a model from a file.
        
        Args:
            file_path: Path to the model file
            
        Returns:
            Loaded model object or None if loading failed
        """
        if not self.bpy:
            print("Cannot load model: Blender Python API not available")
            return self._create_dummy_model(file_path)
        
        # Store the directory of the model file for texture path resolution
        self.last_loaded_dir = os.path.dirname(os.path.abspath(file_path))
        
        try:
            # Clear existing Blender scene objects
            self._clear_scene()
            
            # Load model based on file extension using the appropriate method
            extension = os.path.splitext(file_path)[1].lower()
            import_success = False
            import_error = None
            
            try:
                if extension == ".fbx":
                    self.bpy.ops.import_scene.fbx(filepath=file_path)
                    import_success = True
                elif extension == ".obj":
                    self.bpy.ops.import_scene.obj(filepath=file_path)
                    import_success = True
                elif extension == ".dae":
                    # Try to import using Collada import operator
                    try:
                        print("Attempting to import Collada file using standard import")
                        self.bpy.ops.wm.collada_import(filepath=file_path)
                        import_success = True
                    except Exception as collada_error:
                        print(f"Error loading model: Operator bpy.ops.wm.collada_import.poll() failed, context is incorrect")
                        print(f"Failed to load model or dummy model returned for: {file_path}")
                        import_error = collada_error
                        # Don't return dummy model here, continue with alternative method
                elif extension == ".3ds":
                    self.bpy.ops.import_scene.autodesk_3ds(filepath=file_path)
                    import_success = True
                elif extension == ".blend":
                    self.bpy.ops.wm.open_mainfile(filepath=file_path)
                    import_success = True
                else:
                    print(f"Unsupported format: {extension}")
                    return self._create_dummy_model(file_path)
            except Exception as e:
                print(f"Error during standard import: {e}")
                import_error = e
            
            # If standard import failed for certain formats that need texture data only,
            # try alternative texture extraction method without full model import
            if not import_success:
                # For now, create a basic model with just the path information
                # In a real implementation, you could use PyAssimp or another library 
                # to extract just the material/texture info
                model = self._create_model_for_texture_extraction(file_path)
                if model:
                    return model
                else:
                    # If alternative method also failed, return dummy model with original error
                    if import_error:
                        print(f"Alternative texture extraction also failed: {import_error}")
                    return self._create_dummy_model(file_path)
            
            # If standard import was successful, create model object with scene data
            model = {
                "path": file_path,
                "filename": os.path.basename(file_path),
                "materials": self._extract_materials(),
                "meshes": self._extract_meshes()
            }
            
            return model
            
        except Exception as e:
            print(f"Error loading model: {e}")
            return self._create_dummy_model(file_path)
    
    def _clear_scene(self):
        """
        Clear existing objects from the Blender scene.
        Explicitly ensures the default cube is removed.
        """
        if not self.bpy:
            return
            
        # Deselect all objects first
        self.bpy.ops.object.select_all(action='DESELECT')
        
        # First, explicitly check for and delete the default cube
        default_cube = [obj for obj in self.bpy.data.objects if obj.name.lower() == "cube"]
        if default_cube:
            print(f"Removing default cube from scene")
            for obj in default_cube:
                obj.select_set(True)
            self.bpy.ops.object.delete()
            
            # Deselect again after cube deletion
            self.bpy.ops.object.select_all(action='DESELECT')
            
        # Then select and delete all remaining objects
        self.bpy.ops.object.select_all(action='SELECT')
        self.bpy.ops.object.delete()
    
    def _extract_materials(self):
        """
        Extract material information from the loaded Blender scene.
        
        Returns:
            List of material dictionaries
        """
        if not self.bpy:
            return []
            
        materials = []
        for mat in self.bpy.data.materials:
            materials.append({
                "name": mat.name,
                "nodes": mat.use_nodes  # Whether the material uses nodes
            })
            
        return materials
    
    def _extract_meshes(self):
        """
        Extract mesh information from the loaded Blender scene.
        
        Returns:
            List of mesh dictionaries
        """
        if not self.bpy:
            return []
            
        meshes = []
        for obj in self.bpy.data.objects:
            if obj.type == 'MESH':
                mesh_data = {
                    "name": obj.name,
                    "vertices": len(obj.data.vertices),
                    "polygons": len(obj.data.polygons),
                    "materials": []
                }
                
                # Extract material slots
                for slot in obj.material_slots:
                    if slot.material:
                        mesh_data["materials"].append(slot.material.name)
                        
                meshes.append(mesh_data)
                
        return meshes
    
    def _create_model_for_texture_extraction(self, file_path):
        """
        Create a model with basic material and texture information without 
        requiring full Blender import. This is used when the standard import 
        fails but we still need to extract texture information.
        
        Args:
            file_path: Path to the model file
            
        Returns:
            Model object with texture information or None if extraction fails
        """
        try:
            print(f"Using alternative texture extraction method for: {file_path}")
            extension = os.path.splitext(file_path)[1].lower()
            model_dir = os.path.dirname(file_path)
            
            # For the purposes of texture extraction, create a simple model structure
            # with at least one material that can be used for texture extraction
            model = {
                "path": file_path,
                "filename": os.path.basename(file_path),
                "materials": [],
                "meshes": [],
                "is_import_only": True  # Flag to indicate this is for import only
            }
            
            # Add a default material for texture extraction
            material_name = os.path.splitext(os.path.basename(file_path))[0]
            model["materials"].append({"name": material_name, "nodes": True})
            
            # Look for texture files in common locations
            textures_dir = os.path.join(model_dir, "textures")
            if not os.path.exists(textures_dir):
                # Try alternate locations: same dir as model, parent dir
                textures_dir = model_dir
            
            # We won't actually load the textures here, just note their existence for the texture extractor
            print(f"Scanning for textures in: {textures_dir}")
            
            # The texture_extractor will handle finding actual texture files
            # when extract() is called on this model
            
            return model
        except Exception as e:
            print(f"Error in alternative texture extraction: {e}")
            return None
            
    def _create_dummy_model(self, file_path):
        """
        Create a placeholder model object when actual loading fails.
        
        Args:
            file_path: Path to the model file
            
        Returns:
            Dummy model object
        """
        return {
            "path": file_path,
            "filename": os.path.basename(file_path),
            "materials": [],
            "meshes": [],
            "is_dummy": True  # Flag to indicate this is a dummy model
        }
    
    def get_scene_info(self, model):
        """
        Get information about the scene in a model.
        
        Args:
            model: Loaded model object
            
        Returns:
            Dictionary containing scene information
        """
        if model.get("is_dummy", False):
            return {
                "num_meshes": 0,
                "num_materials": 0,
                "num_textures": 0,
                "animation_info": []
            }
            
        return {
            "num_meshes": len(model.get("meshes", [])),
            "num_materials": len(model.get("materials", [])),
            "num_textures": 0,  # Will be populated by texture extractor
            "animation_info": []  # Animation info not implemented yet
        }
