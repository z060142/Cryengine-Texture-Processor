#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FBX Exporter

This module provides functionality for exporting models to FBX format using Blender's Python API.
"""

import os
import sys
import traceback


DIFFUSE_TEXTURE_KEYS = ("diff", "diffuse", "albedo")


def resolve_texture_output_dir(fbx_output_path, texture_dir=None):
    """
    Resolve the texture output directory used by FBX material paths.

    `texture_dir` may be absolute or relative. Relative paths are anchored to
    the FBX output directory, matching how the normal model export calls this
    exporter with texture_dir="textures".
    """
    fbx_dir = os.path.dirname(os.path.abspath(fbx_output_path))
    if not texture_dir:
        return os.path.join(fbx_dir, "textures")

    texture_dir = os.fspath(texture_dir)
    if os.path.isabs(texture_dir):
        return os.path.abspath(texture_dir)
    return os.path.abspath(os.path.join(fbx_dir, texture_dir))


def select_diffuse_texture_path(material_name, texture_data):
    """
    Return the processed diffuse texture path for a material, if one is known.

    The current texture resolver emits CryEngine-style keys such as `diff`;
    older call sites may still provide `diffuse` or `albedo`.
    """
    if not texture_data:
        return None

    material_textures = texture_data.get(material_name)
    if not isinstance(material_textures, dict):
        return None

    for texture_key in DIFFUSE_TEXTURE_KEYS:
        texture_path = material_textures.get(texture_key)
        if isinstance(texture_path, str) and texture_path:
            return texture_path
    return None


def relative_blender_texture_path(fbx_output_path, texture_path):
    """
    Build a Blender/FBX-friendly relative path from the FBX directory.

    Falls back to a normalized absolute path when Windows cannot calculate a
    relative path, for example across different drives.
    """
    fbx_dir = os.path.dirname(os.path.abspath(fbx_output_path))
    texture_path = os.path.abspath(os.fspath(texture_path))
    try:
        relative_path = os.path.relpath(texture_path, start=fbx_dir)
    except ValueError:
        relative_path = texture_path
    return relative_path.replace("\\", "/")


def fallback_diffuse_texture_path(material_name, texture_output_dir):
    """Compatibility fallback for exports that do not have resolved texture data."""
    base_name_for_texture = material_name.split(".")[0]
    return os.path.join(texture_output_dir, f"{base_name_for_texture}_diff.tif")


def resolve_diffuse_texture_assignment(material_name, fbx_output_path, texture_output_dir, texture_data):
    """Resolve the diffuse texture assignment and expose fallback diagnostics."""
    selected_diffuse_path = select_diffuse_texture_path(material_name, texture_data)
    used_fallback = not bool(selected_diffuse_path)
    absolute_diff_texture_path = (
        selected_diffuse_path
        if selected_diffuse_path
        else fallback_diffuse_texture_path(material_name, texture_output_dir)
    )
    relative_diff_path = relative_blender_texture_path(fbx_output_path, absolute_diff_texture_path)
    warning = None
    if used_fallback:
        warning = {
            "severity": "warning",
            "code": "fbx_diffuse_texture_fallback",
            "material": material_name,
            "texture_path": absolute_diff_texture_path,
            "relative_texture_path": relative_diff_path,
            "message": (
                "No processed diffuse texture path was provided for this material. "
                "FBX export used the compatibility '<material>_diff.tif' fallback path."
            ),
        }

    return {
        "material": material_name,
        "texture_path": absolute_diff_texture_path,
        "relative_texture_path": relative_diff_path,
        "used_fallback": used_fallback,
        "warning": warning,
    }


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
        self.last_texture_warnings = []
        
        try:
            # Try to import bpy
            import bpy
            self.bpy = bpy
            self.initialized = True
            print(f"Successfully imported bpy (Blender Python API) version {bpy.app.version_string}")
            
            # Reset scene to factory settings
            self._reset_scene()
                
        except ImportError as e:
            print(f"WARNING: bpy (Blender Python API) is not available: {e}")
            print("FBX export functionality will be limited.")
            print("Please ensure Blender is installed and the Python environment has access to bpy.")
        except Exception as e:
            print(f"ERROR initializing FBX exporter: {e}")
            import traceback
            traceback.print_exc()
            
    def _reset_scene(self):
        """
        Clear existing objects, materials and images from the Blender scene.
        Uses a more conservative approach to avoid crashes.
        """
        if not self.initialized:
            return
            
        bpy = self.bpy
        try:
            # 取消所有選擇
            bpy.ops.object.select_all(action='DESELECT')

            # 清除所有物體 - 先選擇所有物體
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

            # 清除未使用的材質
            for material in list(bpy.data.materials):
                if not material.users:
                    bpy.data.materials.remove(material)

            # 清除未使用的圖像
            for image in list(bpy.data.images):
                if not image.users:
                    bpy.data.images.remove(image)

            # 清除未使用的材質節點樹
            for node_group in list(bpy.data.node_groups):
                if not node_group.users:
                    bpy.data.node_groups.remove(node_group)

            # 確保場景確實空
            if len(bpy.data.objects) > 0:
                print(f"Warning: After cleanup, still found {len(bpy.data.objects)} objects.")

            print("Scene cleanup complete")
            
        except Exception as e:
            print(f"Error during scene cleanup: {e}")
    
    def export(self, model, output_path, texture_dir=None, texture_data=None):
        """
        Export a model to FBX format.
        
        Args:
            model: Model object to export
            output_path: Path to save the FBX file
            texture_dir: Directory where textures are saved, relative to model
            texture_data: Dictionary mapping material names to processed texture
                          paths, e.g. {'Body': {'diff': 'path/to/Body_diff.tif'}}
            
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
            
            absolute_output_path = os.path.abspath(output_path)
            absolute_texture_dir = resolve_texture_output_dir(absolute_output_path, texture_dir)

            # Pass texture_data to the setup function
            self.last_texture_warnings = self._setup_materials_for_export(
                absolute_output_path,
                absolute_texture_dir,
                texture_data,
            )

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
        a relative diffuse texture path for export.

        Args:
            fbx_output_path (str): Absolute path where the FBX file will be saved.
            texture_output_dir (str): Absolute path to the directory where textures are expected.
            texture_data (dict, optional): Maps material names to dicts of
                                            {texture_type: processed_absolute_path}.
                                            See `export` method docstring for details.
        """
        if not self.initialized:
            print("Error: bpy not initialized.")
            return []

        bpy = self.bpy
        fbx_dir = os.path.dirname(fbx_output_path)

        print(f"Rebuilding materials for FBX export:")
        print(f"  FBX Directory: {fbx_dir}")
        print(f"  Texture Directory: {texture_output_dir}")

        # Ensure texture output directory exists (might be needed for relative path calculation)
        os.makedirs(texture_output_dir, exist_ok=True)
        texture_warnings = []

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

            texture_assignment = resolve_diffuse_texture_assignment(
                material.name,
                fbx_output_path,
                texture_output_dir,
                texture_data,
            )
            absolute_diff_texture_path = texture_assignment["texture_path"]
            relative_diff_path = texture_assignment["relative_texture_path"]
            if texture_assignment["used_fallback"]:
                texture_warnings.append(texture_assignment["warning"])
                print(f"  Warning: {texture_assignment['warning']['message']}")
                print(f"  Fallback diffuse texture: {absolute_diff_texture_path}")
            else:
                print(f"  Using processed diffuse texture: {absolute_diff_texture_path}")

            # Calculate the relative path from the FBX directory to the texture
            print(f"  Assigning relative diffuse path: {relative_diff_path}")

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
                diff_texture_filename = os.path.basename(absolute_diff_texture_path)
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
        return texture_warnings

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
