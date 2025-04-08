#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FBX Exporter

This module provides functionality for exporting models to FBX format using Blender's Python API.
"""

import os
import sys
import traceback
from pathlib import Path

class FbxExporter:
    """
    Class for exporting models to FBX format.
    """
    
    def __init__(self):
        """
        Initialize the FBX exporter.
        """
        self.bpy = None
        self.initialized = False
        
        try:
            # Try to import bpy
            import bpy
            self.bpy = bpy
            self.initialized = True
            print(f"Successfully imported bpy (Blender Python API) version {bpy.app.version_string}")
            
            # Delete default cube when initializing
            self._delete_default_cube()
                
        except ImportError as e:
            print(f"WARNING: bpy (Blender Python API) is not available: {e}")
            print("FBX export functionality will be limited.")
            print("Please ensure Blender is installed and the Python environment has access to bpy.")
        except Exception as e:
            print(f"ERROR initializing FBX exporter: {e}")
            import traceback
            traceback.print_exc()
            
    def _delete_default_cube(self):
        """
        Delete the default cube that is created in new Blender scenes.
        This ensures a clean scene for imported models.
        """
        if not self.initialized:
            return
            
        bpy = self.bpy
        
        # Find objects named "Cube" and delete them
        default_objects = [obj for obj in bpy.data.objects if obj.name.lower() == "cube"]
        
        if default_objects:
            print(f"Deleting {len(default_objects)} default cube object(s) from the scene")
            
            # Select all default objects
            for obj in bpy.context.selected_objects:
                obj.select_set(False)  # Deselect everything first
                
            for obj in default_objects:
                obj.select_set(True)  # Select the default object
                
            # Delete selected objects
            bpy.ops.object.delete()
        else:
            print("No default cube found in the scene")
    
    def export(self, model, output_path, texture_dir=None, texture_data=None):
        """
        Export a model to FBX format.
        
        Args:
            model: Model object to export
            output_path: Path to save the FBX file
            texture_dir: Directory where textures are saved, relative to model
            texture_data: Dictionary mapping texture types to their absolute paths
                          e.g. {'diff': 'path/to/diff.dds', 'ddna': 'path/to/ddna.dds'}
            
        Returns:
            Path to the exported FBX file or None if export failed
        """
        if not self.initialized:
            print("Error: bpy (Blender Python API) is not available. Cannot export FBX.")
            return None
            
        if not model:
            print("Error: No model provided for FBX export.")
            return None
            
        # Check if this is an import-only model (not suitable for export)
        if model.get("is_import_only", False):
            print("Warning: Cannot export an import-only model to FBX.")
            print("This model was loaded with the alternative import method for texture extraction only.")
            return None
            
        # Check if this is a dummy model
        if model.get("is_dummy", False):
            print("Warning: Cannot export a dummy model to FBX.")
            return None
        
        try:
            print(f"Exporting model to {output_path}")
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # *** Setup materials with relative paths for export ***
            # Assuming texture_dir is the absolute path where textures will be saved
            absolute_texture_dir = texture_dir if texture_dir else os.path.join(os.path.dirname(output_path), 'textures') # Default guess if not provided
            absolute_output_path = os.path.abspath(output_path)

            # Pass texture_data to the setup function
            self._setup_materials_for_export(absolute_output_path, absolute_texture_dir, texture_data)

            # Export FBX with relative paths for textures
            try:
                print(f"Executing Blender export_scene.fbx operation...")
                
                # Check if export_scene.fbx is available
                if not hasattr(self.bpy.ops, 'export_scene') or not hasattr(self.bpy.ops.export_scene, 'fbx'):
                    print(f"ERROR: FBX export operator not available in this Blender installation.")
                    return None
                
                # Execute export with common CryEngine-compatible settings
                self.bpy.ops.export_scene.fbx(
                    filepath=absolute_output_path, # Use absolute path for export command
                    use_selection=False,
                    path_mode='RELATIVE', # Crucial setting
                    embed_textures=False,
                    global_scale=1.0,
                    apply_scale_options='FBX_SCALE_NONE',
                    axis_forward='-Z',
                    axis_up='Y',
                    bake_space_transform=True,
                    use_mesh_modifiers=True,
                    mesh_smooth_type='OFF',
                    add_leaf_bones=False,
                    primary_bone_axis='Y',
                    secondary_bone_axis='X',
                    use_armature_deform_only=False,
                    bake_anim=False
                )
                print(f"Blender export operation completed successfully.")
            except Exception as e:
                print(f"Error during Blender export operation: {e}")
                traceback.print_exc()
                return None
            
            print(f"Successfully exported model to {absolute_output_path}")
            return absolute_output_path
            
        except Exception as e:
            print(f"Error exporting model: {e}")
            traceback.print_exc()
            return None

    def _setup_materials_for_export(self, fbx_output_path, texture_output_dir, texture_data):
        """
        Clears existing material nodes and creates a simple setup assigning
        a relative path to a hypothetical '_diff.tif' texture based on material name.

        Args:
            fbx_output_path (str): Absolute path where the FBX file will be saved.
            texture_output_dir (str): Absolute path to the directory where textures are expected.
            texture_data (dict, optional): Maps material names to dicts of
                                            {texture_type: original_absolute_path}.
                                            See `export` method docstring for details.
        """
        if not self.initialized:
            print("Error: bpy not initialized.")
            return

        bpy = self.bpy
        fbx_dir = os.path.dirname(fbx_output_path)

        print(f"Rebuilding materials for FBX export:")
        print(f"  FBX Directory: {fbx_dir}")
        print(f"  Texture Directory: {texture_output_dir}")

        # Ensure texture output directory exists (might be needed for relative path calculation)
        os.makedirs(texture_output_dir, exist_ok=True)

        for material in bpy.data.materials:
            # Skip default/unwanted materials if necessary
            # Added "Material" based on ClaudeCode.md notes on mtl_exporter filtering
            if not material or material.name in ["Dots Stroke", "Material"]:
                 print(f"Skipping material: {material.name}")
                 continue

            print(f"Processing material: {material.name}")

            # Ensure nodes are enabled
            material.use_nodes = True
            nodes = material.node_tree.nodes
            links = material.node_tree.links

            # Clear existing nodes
            nodes.clear()

            # Create essential nodes
            output_node = nodes.new(type='ShaderNodeOutputMaterial')
            output_node.location = (300, 0)
            bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
            bsdf_node.location = (0, 0)

            # Link BSDF to output
            links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])

            # --- Diffuse Texture Setup ---
            # Determine the base name for the output texture file
            base_name_for_texture = material.name.split('.')[0] # Default/fallback: use material name
            original_diffuse_path = None

            # Use the correct parameter name 'texture_data' here
            if texture_data and material.name in texture_data:
                mat_info = texture_data[material.name]
                # Prioritize 'diffuse', then 'albedo'
                if 'diffuse' in mat_info and isinstance(mat_info['diffuse'], str):
                    original_diffuse_path = mat_info['diffuse']
                elif 'albedo' in mat_info and isinstance(mat_info['albedo'], str):
                    original_diffuse_path = mat_info['albedo']

                if original_diffuse_path:
                    try:
                        # Extract base name from the original file path
                        original_filename = os.path.basename(original_diffuse_path)
                        # Attempt to remove known suffixes to get a cleaner base name
                        # This part might need refinement based on actual naming conventions used
                        # For now, just remove the extension
                        base_name_for_texture = os.path.splitext(original_filename)[0]
                        # Further cleaning (optional): remove common suffixes like _albedo, _diffuse, _d etc.
                        # This requires knowledge of the NameParser logic or passing it in.
                        # Simple example:
                        suffixes_to_remove = ['_albedo', '_diffuse', '_d', '_basecolor', '_color']
                        temp_name = base_name_for_texture.lower()
                        for suffix in suffixes_to_remove:
                            if temp_name.endswith(suffix):
                                base_name_for_texture = base_name_for_texture[:-len(suffix)]
                                break # Remove only one suffix
                        print(f"  Using base name from original texture '{original_filename}': {base_name_for_texture}")
                    except Exception as e:
                        print(f"  Error processing original path '{original_diffuse_path}': {e}. Falling back to material name.")
                        base_name_for_texture = material.name.split('.')[0]
                else:
                    print(f"  No diffuse/albedo found in texture data for {material.name}. Using material name as base.")
            else:
                 # Also correct the variable name in this print statement
                 print(f"  Material '{material.name}' not found in texture data or data not provided. Using material name as base.")


            # Construct the expected output texture filename
            diff_texture_filename = f"{base_name_for_texture}_diff.tif"
            absolute_diff_texture_path = os.path.join(texture_output_dir, diff_texture_filename)

            # Calculate the relative path from the FBX directory to the texture
            try:
                # Use Path objects for more robust relative path calculation
                fbx_path_obj = Path(fbx_dir)
                tex_path_obj = Path(absolute_diff_texture_path)
                relative_diff_path = os.path.relpath(tex_path_obj, start=fbx_path_obj)
                # Ensure forward slashes for cross-platform compatibility within FBX/Blender
                relative_diff_path = str(Path(relative_diff_path)).replace("\\", "/") # Convert back to string
                print(f"  Assigning relative diffuse path: {relative_diff_path}")
            except ValueError as e:
                print(f"  Error calculating relative path for {material.name}: {e}. Using absolute path as fallback.")
                relative_diff_path = str(Path(absolute_diff_texture_path)).replace("\\", "/")


            # Create the image texture node
            tex_image_node = nodes.new(type='ShaderNodeTexImage')
            tex_image_node.location = (-300, 100)

            # Assign the relative filepath. Blender stores this string.
            # We need to create a placeholder image data-block if one doesn't exist
            # or find an existing one if the path matches.

            # Blender's relative paths often start with '//'
            blender_relative_path = f"//{relative_diff_path}"

            existing_image = None
            for img in bpy.data.images:
                # Check against both raw relative and Blender's '//' prefix
                if img.filepath == relative_diff_path or img.filepath == blender_relative_path:
                    existing_image = img
                    break

            if existing_image:
                tex_image_node.image = existing_image
                print(f"  Reusing existing image data-block for: {relative_diff_path}")
            else:
                # Create a new placeholder image data-block
                placeholder_name = diff_texture_filename
                count = 1
                while placeholder_name in bpy.data.images:
                    placeholder_name = f"{diff_texture_filename}.{count:03d}"
                    count += 1

                # Create the image data-block but don't load the file
                new_image = bpy.data.images.new(name=placeholder_name, width=1, height=1, alpha=True)
                new_image.filepath = blender_relative_path # Set the crucial relative path string with '//'
                new_image.source = 'FILE' # Indicate it's supposed to come from a file
                tex_image_node.image = new_image
                print(f"  Created new placeholder image data-block for: {blender_relative_path}")


            # Set colorspace for the image node (important for color textures)
            if tex_image_node.image:
                 tex_image_node.image.colorspace_settings.name = 'sRGB'

            # Link the texture node to the BSDF's Base Color input
            links.new(tex_image_node.outputs['Color'], bsdf_node.inputs['Base Color'])

            print(f"  Finished setting up material: {material.name}")

        print("Material rebuilding complete.")

    # Note: The old _clear_and_create_materials and _update_texture_paths are removed by this replacement.

    def create_cryengine_mtl(self, model, output_dir):
        """
        Create CryEngine material files (.mtl) for a model.
        This method is kept for compatibility, but is handled separately
        by the mtl_exporter.py module.

        Args:
            model: Model object
            output_dir: Directory to save material files

        Returns:
            List of paths to created material files
        """
        print("Note: MTL file generation is handled by mtl_exporter.py")
        return []

# Any trailing code from the previous incorrect replacement is removed here.
# The class definition should end after the create_cryengine_mtl method.
