#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Material Manager

This module provides functionality for managing materials, including
creation, updating, and conversion to CryEngine format.
"""

class Material:
    """
    Class representing a material with its properties and texture maps.
    """
    
    def __init__(self, name):
        """
        Initialize a material.
        
        Args:
            name: Name of the material
        """
        self.name = name
        
        # Basic material properties
        self.properties = {
            "diffuse_color": (1.0, 1.0, 1.0),
            "specular_color": (1.0, 1.0, 1.0),
            "specular_factor": 0.5,
            "specular_glossiness": 10.0,
            "opacity": 1.0,
            "emissive_color": (0.0, 0.0, 0.0),
            "emissive_factor": 0.0
        }
        
        # Texture maps
        self.textures = {
            "diffuse": None,
            "normal": None,
            "specular": None,
            "glossiness": None,
            "displacement": None,
            "emissive": None,
            "sss": None
        }
    
    def set_property(self, property_name, value):
        """
        Set a material property.
        
        Args:
            property_name: Name of the property
            value: Value to set
        """
        if property_name in self.properties:
            self.properties[property_name] = value
    
    def set_texture(self, texture_type, path):
        """
        Set a texture map.
        
        Args:
            texture_type: Type of texture map
            path: Path to the texture file
        """
        if texture_type in self.textures:
            self.textures[texture_type] = path
    
    def get_cryengine_textures(self):
        """
        Get textures mapped to CryEngine format.
        
        Returns:
            Dictionary mapping CryEngine texture slots to texture paths
        """
        cryengine_textures = {
            "diff": self.textures.get("diffuse"),
            "spec": self.textures.get("specular"),
            "ddna": None,  # Will be generated from normal and glossiness
            "displ": self.textures.get("displacement"),
            "emissive": self.textures.get("emissive"),
            "sss": self.textures.get("sss")
        }
        
        return cryengine_textures


class MaterialManager:
    """
    Class for managing materials and converting them to CryEngine format.
    """
    
    def __init__(self):
        """
        Initialize the material manager.
        """
        self.materials = {}
    
    def create_material(self, name):
        """
        Create a new material.
        
        Args:
            name: Name of the material
            
        Returns:
            The created material
        """
        material = Material(name)
        self.materials[name] = material
        return material
    
    def get_material(self, name):
        """
        Get a material by name.
        
        Args:
            name: Name of the material
            
        Returns:
            The material or None if not found
        """
        return self.materials.get(name)
    
    def convert_to_cryengine(self, material_name, texture_group):
        """
        Convert a material to CryEngine format using a texture group.
        
        Args:
            material_name: Name of the material to convert
            texture_group: TextureGroup containing processed textures
            
        Returns:
            The updated material or None if material not found
        """
        material = self.get_material(material_name)
        if not material:
            return None
        
        # Update material properties for CryEngine
        # These would be adjusted based on CryEngine material requirements
        
        # Update texture paths with processed textures
        if texture_group.output.get("diff"):
            material.set_texture("diffuse", texture_group.output["diff"])
        
        if texture_group.output.get("spec"):
            material.set_texture("specular", texture_group.output["spec"])
        
        if texture_group.output.get("ddna"):
            # In CryEngine, normal and gloss are combined in ddna
            # This would need special handling in the actual implementation
            pass
        
        if texture_group.output.get("displ"):
            material.set_texture("displacement", texture_group.output["displ"])
        
        if texture_group.output.get("emissive"):
            material.set_texture("emissive", texture_group.output["emissive"])
        
        if texture_group.output.get("sss"):
            material.set_texture("sss", texture_group.output["sss"])
        
        return material
    
    def apply_to_model(self, model, texture_groups):
        """
        Apply materials to a model using processed texture groups.
        
        Args:
            model: Model object to update
            texture_groups: List of TextureGroup objects with processed textures
            
        Returns:
            Updated model object
        """
        # This is a placeholder for the actual implementation
        # In reality, this would match model materials with texture groups
        # and update the model's materials
        
        # Example pseudocode:
        # for material_name in model.materials:
        #     # Find matching texture group
        #     group = self._find_matching_group(material_name, texture_groups)
        #     if group:
        #         # Convert material to CryEngine format
        #         self.convert_to_cryengine(material_name, group)
        
        return model
    
    def _find_matching_group(self, material_name, texture_groups):
        """
        Find a texture group that matches a material name.
        
        Args:
            material_name: Name of the material
            texture_groups: List of TextureGroup objects
            
        Returns:
            Matching TextureGroup or None if no match found
        """
        # This is a placeholder for the actual implementation
        # In reality, this would use more sophisticated matching logic
        
        for group in texture_groups:
            # Simple string matching (would be more complex in real implementation)
            if material_name.lower() in group.base_name.lower():
                return group
        
        return None
