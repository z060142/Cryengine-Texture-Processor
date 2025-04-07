#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Manager

This module provides functionality for managing textures, including
classification, grouping, and processing.
"""

import os
import re
from .name_parser import TextureNameParser

class TextureGroup:
    """
    Class representing a group of related textures that form a complete material.
    """
    
    def __init__(self, base_name):
        """
        Initialize a texture group.
        
        Args:
            base_name: Base name for the texture group
        """
        self.base_name = base_name
        self.textures = {
            "diffuse": None,
            "normal": None,
            "specular": None,
            "glossiness": None,
            "roughness": None,
            "displacement": None,
            "metallic": None,
            "ao": None,
            "alpha": None,
            "emissive": None,
            "sss": None,
            "arm": None,      # Combined AO, Roughness, Metallic texture
            "unknown": []    # List for unknown textures that need classification
        }
        
        # Intermediate formats
        self.intermediate = {
            "albedo": None,
            "reflection": None,
            "normal": None,
            "glossiness": None,
            "height": None,
            "ao": None
        }
        
        # Output formats
        self.output = {
            "diff": None,
            "spec": None,
            "ddna": None,
            "displ": None,
            "emissive": None,
            "sss": None
        }
    
    def add_texture(self, texture_type, texture):
        """
        Add a texture to the group.
        
        Args:
            texture_type: Type of texture (e.g., 'diffuse', 'normal')
            texture: Texture object
        """
        if texture_type == "unknown":
            # For unknown type, add to the list of unknown textures
            self.textures["unknown"].append(texture)
        elif texture_type in self.textures:
            self.textures[texture_type] = texture
    
    def has_texture(self, texture_type):
        """
        Check if the group has a specific texture type.
        
        Args:
            texture_type: Type of texture to check
            
        Returns:
            True if present, False otherwise
        """
        return texture_type in self.textures and self.textures[texture_type] is not None
    
    def get_missing_textures(self):
        """
        Get a list of missing texture types.
        
        Returns:
            List of texture types that are missing from this group
        """
        return [t_type for t_type, texture in self.textures.items() if texture is None]
    
    def generate_intermediate_formats(self, settings=None):
        """
        Generate intermediate texture formats from input textures.
        
        Args:
            settings: Dictionary of processing settings
            
        Returns:
            Dictionary of generated intermediate formats
        """
        # This is a placeholder for the actual implementation
        # In reality, this would use the appropriate processors to generate intermediates
        
        # Process ARM texture if available (extract AO, Roughness, Metallic)
        if self.has_texture("arm"):
            # Example pseudocode:
            # arm_processor = ARMProcessor()
            # result = arm_processor.process(self.textures["arm"])
            # self.textures["ao"] = result["ao"]
            # self.textures["roughness"] = result["roughness"]
            # self.textures["metallic"] = result["metallic"]
            pass
        
        # Process standard textures
        # Example pseudocode:
        # if self.has_texture("diffuse"):
        #     self.intermediate["albedo"] = albedo_processor.process(self.textures["diffuse"])
        
        # Process metallic texture based on settings
        if settings and "process_metallic" in settings and settings["process_metallic"] and self.has_texture("metallic"):
            # Example pseudocode:
            # Convert metallic + diffuse to albedo + reflection as in refl.py
            pass
        
        return self.intermediate
    
    def generate_output_formats(self, settings):
        """
        Generate CryEngine output formats from intermediate formats.
        
        Args:
            settings: Export settings dictionary
            
        Returns:
            Dictionary of generated output formats
        """
        # This is a placeholder for the actual implementation
        # In reality, this would use the appropriate exporters to generate outputs
        
        # Example pseudocode:
        # self.output["diff"] = diff_exporter.export(self.intermediate, settings)
        
        return self.output


class TextureManager:
    """
    Class for managing texture classification, grouping, and processing.
    """
    
    def __init__(self):
        """
        Initialize the texture manager.
        """
        self.texture_groups = []
        self.name_parser = TextureNameParser()
        self.all_texture_paths = set() # Keep track of all added texture paths to avoid duplicates
        self.settings = {
            "process_metallic": True  # Whether to convert metallic to albedo+reflection
        }
    
    def classify_texture(self, file_path):
        """
        Classify a texture by its type based on filename.
        
        Args:
            file_path: Path to the texture file
            
        Returns:
            Tuple of (texture_type, base_name)
        """
        return self.name_parser.parse(file_path)
    
    def add_texture(self, file_path, texture_type=None):
        """
        Add a texture to the manager and classify it.
        
        Args:
            file_path: Path to the texture file
            texture_type: Optional texture type override
            
        Returns:
            The added texture object, or None if the texture path already exists.
        """
        # --- Check for duplicates based on absolute path ---
        abs_file_path = os.path.abspath(file_path)
        if abs_file_path in self.all_texture_paths:
            print(f"Texture already managed: {file_path}")
            return None # Indicate duplicate
        # --- End Check ---

        # Create texture object (simplified for placeholder)
        texture = {
            "path": file_path, # Store original path for reference if needed
            "abs_path": abs_file_path, # Store absolute path for reliable checking
            "filename": os.path.basename(file_path)
        }
        
        # Classify texture if type is not provided
        if texture_type is None:
            texture_type, base_name = self.classify_texture(file_path)
        else:
            # Use provided type but still need to parse base name
            _, base_name = self.classify_texture(file_path)
            
        texture["type"] = texture_type
        texture["base_name"] = base_name
        
        # Mark if it's unknown
        texture["is_unknown"] = (texture_type == "unknown")
        
        # Find or create appropriate group
        group = self._find_or_create_group(base_name)
        group.add_texture(texture_type, texture)

        # Add the absolute path to the set of managed paths
        self.all_texture_paths.add(abs_file_path)
        
        return texture
    
    def _find_or_create_group(self, base_name):
        """
        Find a texture group by base name or create a new one.
        
        Args:
            base_name: Base name to search for
            
        Returns:
            TextureGroup instance
        """
        # Search for existing group
        for group in self.texture_groups:
            if group.base_name == base_name:
                return group
        
        # Create new group if not found
        new_group = TextureGroup(base_name)
        self.texture_groups.append(new_group)
        return new_group
    
    def generate_intermediate_formats(self):
        """
        Generate intermediate formats for all texture groups.
        """
        for group in self.texture_groups:
            group.generate_intermediate_formats(self.settings)
    
    def generate_output_formats(self, settings):
        """
        Generate output formats for all texture groups.
        
        Args:
            settings: Export settings dictionary
        """
        # Update internal settings from export settings if needed
        if "process_metallic" in settings:
            self.settings["process_metallic"] = settings["process_metallic"]
        
        # Generate intermediate formats for all groups
        self.generate_intermediate_formats()
        
        # Generate output formats for all groups
        for group in self.texture_groups:
            group.generate_output_formats(settings)
            
    def update_texture_type(self, texture, new_type):
        """
        Update the type of a texture (especially for reclassifying unknown textures).
        
        Args:
            texture: Texture object to update
            new_type: New texture type
            
        Returns:
            True if successful, False otherwise
        """
        if not texture:
            return False
            
        old_type = texture.get("type")
        if old_type == new_type:
            return True  # No change needed
            
        # Update texture type
        texture["type"] = new_type
        texture["is_unknown"] = False
        
        # Find the group containing this texture
        for group in self.texture_groups:
            # If it was unknown, remove from unknown list and add to specified type
            if old_type == "unknown" and texture in group.textures["unknown"]:
                group.textures["unknown"].remove(texture)
                group.add_texture(new_type, texture)
                return True
                
            # If it was another type, need to handle the replacement
            # (In a real implementation, would need to find the texture and move it)
        
        return False
    
    def get_all_groups(self):
        """
        Get all texture groups.
        
        Returns:
            List of all texture groups
        """
        # For compatibility with code expecting TextureGroup objects
        # We need to make sure the texture groups are properly instantiated
        for i, group in enumerate(self.texture_groups):
            # If it's a dictionary, convert it to a TextureGroup object
            if isinstance(group, dict):
                texture_group = TextureGroup(group.get("base_name", f"Group{i}"))
                
                # Copy textures from dictionary to the TextureGroup object
                for texture in group.get("textures", []):
                    texture_type = texture.get("type", "unknown")
                    texture_group.add_texture(texture_type, texture)
                
                # Replace dictionary with TextureGroup object
                self.texture_groups[i] = texture_group
                
        return self.texture_groups
