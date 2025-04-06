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
        
        try:
            # Clear existing Blender scene objects
            self._clear_scene()
            
            # Load model based on file extension
            extension = os.path.splitext(file_path)[1].lower()
            if extension == ".fbx":
                self.bpy.ops.import_scene.fbx(filepath=file_path)
            elif extension == ".obj":
                self.bpy.ops.import_scene.obj(filepath=file_path)
            elif extension == ".dae":
                self.bpy.ops.wm.collada_import(filepath=file_path)
            elif extension == ".3ds":
                self.bpy.ops.import_scene.autodesk_3ds(filepath=file_path)
            elif extension == ".blend":
                self.bpy.ops.wm.open_mainfile(filepath=file_path)
            else:
                print(f"Unsupported format: {extension}")
                return self._create_dummy_model(file_path)
            
            # Create a model object with scene data
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
        """
        if not self.bpy:
            return
            
        # Select all objects
        self.bpy.ops.object.select_all(action='SELECT')
        # Delete selected objects
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
