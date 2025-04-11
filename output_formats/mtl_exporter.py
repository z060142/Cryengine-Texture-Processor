#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MTL Exporter Module

This module provides functionality to export CryEngine compatible .mtl files
based on processed texture data and model information.
"""

import os
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom
from PIL import Image

def _has_alpha_channel(image_path):
    """
    Detects if the image has an alpha channel and if that alpha channel contains
    meaningful transparency information (not just all 255 values).
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        bool: True if the image has a meaningful alpha channel, False otherwise
    """
    try:
        if not os.path.exists(image_path):
            return False
            
        image = Image.open(image_path)
        
        # Check if the image even has an alpha channel
        if image.mode not in ('RGBA', 'LA'):
            return False
            
        # Split the image into channels
        channels = image.split()
        
        # Get the alpha channel (last channel)
        alpha_channel = channels[-1]
        
        # Check if alpha channel has any transparency
        # Convert to a list of values and check if any value is less than 255
        alpha_data = list(alpha_channel.getdata())
        
        # Check a sample of the alpha values to see if there's meaningful transparency
        # (if all values are 255, it's not really being used for transparency)
        sample_size = min(1000, len(alpha_data))  # Check up to 1000 pixels
        sample_step = max(1, len(alpha_data) // sample_size)
        
        for i in range(0, len(alpha_data), sample_step):
            if alpha_data[i] < 255:  # If any pixel is not fully opaque
                return True
                
        return False  # All sampled pixels were fully opaque
        
    except Exception as e:
        print(f"Error checking alpha channel in {image_path}: {e}")
        return False


def _calculate_relative_path(target_path, start_path):
    """
    Calculates the relative path from start_path to target_path,
    ensuring forward slashes.

    Args:
        target_path (str): The absolute path to the target file (e.g., texture).
        start_path (str): The absolute path to the directory from which the
                          relative path should start (e.g., model output dir).

    Returns:
        str: The relative path using forward slashes.
    """
    if not target_path or not start_path:
        return ""
    try:
        # Calculate relative path
        relative = os.path.relpath(target_path, start_path)
        # Ensure forward slashes
        relative = relative.replace("\\", "/")
        # Prepend './' if it's not already relative from parent or absolute
        if not relative.startswith(("../", "/", ".")):
             relative = "./" + relative
        return relative
    except ValueError:
        # Handle cases where paths are on different drives (Windows)
        # In this scenario, returning the absolute path might be the fallback,
        # but CryEngine typically expects relative paths within the project.
        # For now, return the original target path or an empty string.
        print(f"Warning: Could not calculate relative path between {start_path} and {target_path}. Paths might be on different drives.")
        # Return the filename part as a fallback? Or the full path?
        # Let's return the filename for now, assuming it might be placed alongside the mtl.
        return os.path.basename(target_path)


def _pretty_print_xml(elem):
    """
    Formats the XML ElementTree element for pretty printing.

    Args:
        elem (ET.Element): The root element of the XML tree.

    Returns:
        str: A pretty-printed XML string.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Indent with spaces, add newline
    return reparsed.toprettyxml(indent=" ")


def export_mtl(materials_data, model_output_dir, texture_output_dir, output_filename):
    """
    Exports a .mtl file based on the provided material data.

    Args:
        materials_data (list): A list of dictionaries, where each dictionary
                               represents a material and contains:
                               - 'name' (str): The material name.
                               - 'textures' (dict): A dictionary mapping CryEngine
                                 texture map types (e.g., 'Diffuse', 'Bumpmap',
                                 'Specular') to their absolute file paths (str).
                                 Example: {'Diffuse': '/path/to/tex_diff.dds', ...}
        model_output_dir (str): The absolute path to the directory where the
                                .mtl file should be saved.
        texture_output_dir (str): The absolute path to the directory where the
                                  processed textures (.dds) are saved. This is
                                  currently used for reference but the relative
                                  path calculation relies on model_output_dir.
        output_filename (str): The desired name for the output .mtl file
                               (e.g., 'mymodel.mtl').

    Returns:
        bool: True if export was successful, False otherwise.
        str: Path to the generated MTL file if successful, or an error message.
    """
    mtl_file_path = os.path.join(model_output_dir, output_filename)

    try:
        # Create the root <Material> element
        # MtlFlags="524544" seems common for the root
        root_material = ET.Element("Material", MtlFlags="524544", vertModifType="0")

        # Create <SubMaterials> element
        sub_materials = ET.SubElement(root_material, "SubMaterials")

        if not materials_data:
            print("Warning: No material data provided for MTL export.")
            # Create a default empty material? Or just return?
            # Let's create one default material to avoid empty SubMaterials tag
            default_mat = ET.SubElement(sub_materials, "Material", Name="Default", MtlFlags="524416", Shader="Illum")
            ET.SubElement(default_mat, "Textures") # Add empty Textures tag
        else:
            # Define materials to ignore
            ignored_materials = {"Material", "Dots Stroke"} # Use a set for efficient lookup

            # 清理材質數據，去除數字後綴並卻除重複
            cleaned_materials_data = []
            seen_clean_names = set()
            
            for mat_info in materials_data:
                # 獲取材質名稱和紐理
                mat_name = mat_info.get('name', 'UnnamedMaterial')
                textures = mat_info.get('textures', {})
                # 檢查材質名稱是否應該被忽略
                mat_name_check = mat_info.get('name')
                if mat_name_check in ignored_materials:
                    print(f"Skipping ignored material: {mat_name_check}") # Optional: Log skipped material
                    continue # Skip this material
                    
                # 清除數字後綴 (.001, .002 等)
                import re
                original_name = mat_info.get('name', 'UnnamedMaterial')
                clean_name = re.sub(r'\.[0-9]{3}$', '', original_name)
                
                # 如果清理後的名稱已經存在，則跳過
                if clean_name in seen_clean_names:
                    print(f"Skipping duplicate material after cleaning: {original_name} -> {clean_name}")
                    continue
                    
                # 記錄這個名稱已被使用
                seen_clean_names.add(clean_name)
                
                # 建立新的材質資訊結構
                new_mat_info = mat_info.copy()  # 複製原始數據
                new_mat_info['name'] = clean_name  # 使用清理後的名稱
                new_mat_info['original_name'] = original_name  # 保存原始名稱以便參考
                
                cleaned_materials_data.append(new_mat_info)

            # 使用清理後的材質數據
            materials_data = cleaned_materials_data
            
            for mat_info in materials_data:
                # 獲取材質名稱和紐理
                mat_name = mat_info.get('name', 'UnnamedMaterial')
                textures = mat_info.get('textures', {})

                # Create a <Material> element for this sub-material
                # Default attributes based on the example
                # MtlFlags="524416", Shader="Illum" are common defaults
                material_attrs = {
                    "Name": mat_name,
                    "MtlFlags": "524416", # Common flag for sub-materials
                    "Shader": "Illum", # Default shader
                    # GenMask and StringGenMask will be added dynamically below
                    "SurfaceType": "", # Keep empty unless specified
                    "MatTemplate": "", # Keep empty unless specified
                    "Diffuse": "1,1,1", # Default white
                    "Specular": "1,1,1", # Adjusted default based on example
                    "Emittance": "0,0,0,0", # Default no emittance, will be overridden if emissive texture exists
                    "Opacity": "1",
                    "Shininess": "255", # Adjusted default based on example
                    # AlphaTest is now only added conditionally below
                }
                
                # Check if this material has an alpha/transparency map or uses maps that typically include alpha
                has_alpha_map = False
                
                # Alpha related texture types to check for
                alpha_related_types = {
                    'alpha', 'transparency', 'opacity', 'mask'
                }
                
                # Check if material has any alpha-related texture type
                for tex_type, tex_path in textures.items():
                    tex_type_lower = tex_type.lower()
                    
                    # Direct match with alpha-related types
                    if tex_type_lower in alpha_related_types:
                        has_alpha_map = True
                        break
                        
                    # Check for alpha/transparency terms within texture type names
                    if any(alpha_term in tex_type_lower for alpha_term in alpha_related_types):
                        has_alpha_map = True
                        break
                
                # If no dedicated alpha map was found, check if diffuse texture has alpha channel
                if not has_alpha_map:
                    # Check diffuse texture for alpha channel
                    diffuse_texture_path = textures.get('diffuse')
                    if diffuse_texture_path and os.path.exists(diffuse_texture_path):
                        if _has_alpha_channel(diffuse_texture_path):
                            print(f"Detected alpha channel in diffuse texture: {diffuse_texture_path}")
                            has_alpha_map = True
                
                # Only add AlphaTest parameter if we have an alpha map
                if has_alpha_map:
                    material_attrs["AlphaTest"] = "0.5"
                
                # Create the material element with our attribute dictionary
                sub_mat = ET.SubElement(sub_materials, "Material", **material_attrs)

                # Create <Textures> element
                textures_elem = ET.SubElement(sub_mat, "Textures")

                # Map our internal types to CryEngine MTL Map types
                # Note: Normal map goes to 'Bumpmap' in CryEngine MTL
                cryengine_map_types = {
                    'diffuse': 'Diffuse',
                    'specular': 'Specular',
                    'normal': 'Bumpmap', # DDNA usually goes here
                    'glossiness': None, # Gloss is part of DDNA, not separate usually
                    'height': 'Heightmap', # Or Displacement? Check CryEngine docs
                    'displacement': 'Heightmap', # Map displacement to Heightmap
                    'emissive': 'Emittance',
                    'ao': None, # AO often baked or part of Diffuse/DDNA alpha
                    'opacity': 'Opacity',
                    'alpha': 'Opacity', # Map alpha to Opacity as well
                    'transparency': 'Opacity', # Map transparency to Opacity as well
                    'mask': 'Opacity', # Mask maps often used for transparency/alpha
                    # Add others if needed based on project's texture types
                }

                # Add <Texture> elements for each map
                for map_type, abs_texture_path in textures.items():
                    ce_map_type = cryengine_map_types.get(map_type.lower())
                    if ce_map_type and abs_texture_path:
                        # Calculate relative path from the MTL's directory
                        relative_texture_path = _calculate_relative_path(abs_texture_path, model_output_dir)

                        if relative_texture_path:
                            tex_elem = ET.SubElement(textures_elem, "Texture",
                                                     Map=ce_map_type,
                                                     File=relative_texture_path)
                            # Add default TexMod sub-element as seen in example
                            ET.SubElement(tex_elem, "TexMod",
                                          TexMod_RotateType="0",
                                          TexMod_TexGenType="0",
                                          TexMod_bTexGenProjected="0")
                        else:
                             print(f"Warning: Could not determine path for texture '{abs_texture_path}' in material '{mat_name}'. Skipping.")


                # --- Dynamically generate GenMask and StringGenMask based on found textures ---
                # Based on cliff_side1.mtl example and common CE usage
                # NOTE: Exact GenMask bit values can be complex and shader-dependent.
                # These are common flags associated with the texture maps.
                gen_mask_value = 0
                string_gen_mask_parts = []
                public_params = {"EmittanceMapGamma": "1", "SSSIndex": "0"} # Base public params

                # Check which texture types were successfully found and added
                if 'diffuse' in textures:
                    # Diffuse itself doesn't usually add a specific flag, but alpha might
                    # TODO: Check if diffuse texture has alpha for AlphaTest flag?
                    pass
                if 'normal' in textures: # Mapped to Bumpmap
                    gen_mask_value |= 0x4000000000000 # Assume this is NORMAL_MAP bit
                    string_gen_mask_parts.append("%NORMAL_MAP")
                if 'specular' in textures:
                    gen_mask_value |= 0x80000 # Assume this is SPECULAR_MAP bit
                    string_gen_mask_parts.append("%SPECULAR_MAP")
                if 'displacement' in textures: # Mapped to Heightmap
                    gen_mask_value |= 0x200000000000 # Assume this is DISPLACEMENT_MAPPING bit
                    string_gen_mask_parts.append("%DISPLACEMENT_MAPPING")
                    # Add tessellation flags if displacement map exists, as per example
                    gen_mask_value |= 0x10000000000000 # Assume this is PHONG_TESSELLATION bit
                    string_gen_mask_parts.append("%PHONG_TESSELLATION")
                    # Add tessellation public params
                    public_params.update({
                        "TessellationDispBias": "0.5",
                        "TessellationFactor": "1", # Keep low by default
                        "TessellationFactorMax": "32", # Example values
                        "TessellationFactorMin": "1",  # Example values
                        "TessellationHeightScale": "1" # Default scale
                    })
                if 'emissive' in textures: # Mapped to Emittance
                    # Set Emittance attribute on the material itself
                    sub_mat.set("Emittance", "1,1,1,10") # Use example value when texture exists
                    # Emissive map itself might not have a specific GenMask bit, depends on shader
                    # string_gen_mask_parts.append("%EMITTANCE_MAP") # Add if needed
                # For diffuse with alpha channel, we need to check if the texture has alpha
                if 'diffuse' in textures and os.path.exists(textures['diffuse']):
                    if _has_alpha_channel(textures['diffuse']):
                        # Diffuse texture has alpha channel, add AlphaTest parameter
                        sub_mat.set("AlphaTest", "0.5")
                
                # Check conventional opacity maps
                if 'opacity' in textures or 'alpha' in textures or 'transparency' in textures or 'mask' in textures:
                    # Dedicated opacity/alpha map, add AlphaTest parameter
                    sub_mat.set("AlphaTest", "0.5") # Add AlphaTest parameter for opacity maps

                # Add SSS flag by default? Or make it optional? Example had it often.
                gen_mask_value |= 0x20 # Assume this is SUBSURFACE_SCATTERING bit
                string_gen_mask_parts.append("%SUBSURFACE_SCATTERING")

                # Set the calculated masks, ensuring StringGenMask is not empty if GenMask is non-zero
                sub_mat.set("GenMask", str(gen_mask_value))
                if string_gen_mask_parts:
                    sub_mat.set("StringGenMask", "".join(sorted(list(set(string_gen_mask_parts))))) # Sort for consistency
                else:
                     # Ensure StringGenMask is empty if GenMask is 0 or only has flags without string equivalents
                     sub_mat.set("StringGenMask", "")
                # --- End Mask Generation ---

                # Add <PublicParams> with potentially updated values
                ET.SubElement(sub_mat, "PublicParams", **public_params)


        # Add default <PublicParams> to root - TODO: Make dynamic?
        ET.SubElement(root_material, "PublicParams", EmittanceMapGamma="1", SSSIndex="0")

        # Generate pretty XML string
        xml_string = _pretty_print_xml(root_material)

        # Write to file
        os.makedirs(model_output_dir, exist_ok=True) # Ensure directory exists
        with open(mtl_file_path, "w", encoding="utf-8") as f:
            f.write(xml_string)

        print(f"Successfully exported MTL file to: {mtl_file_path}")
        
        # Generate and export .mtl.cryasset file after successful .mtl export
        success_cryasset, cryasset_result = export_mtl_cryasset(materials_data, mtl_file_path)
        if not success_cryasset:
            print(f"Warning: MTL file exported successfully, but cryasset file failed: {cryasset_result}")
            # Continue even if cryasset fails - not critical
        
        return True, mtl_file_path

    except Exception as e:
        error_msg = f"Failed to export MTL file '{output_filename}': {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return False, error_msg


def export_mtl_cryasset(materials_data, mtl_file_path):
    """
    Exports a .mtl.cryasset file based on the provided material data and MTL file path.
    This file serves as metadata for the CryEngine resource system.
    
    Args:
        materials_data (list): A list of dictionaries, where each dictionary
                               represents a material and contains texture information.
        mtl_file_path (str): The absolute path to the .mtl file that was generated.
                           
    Returns:
        bool: True if export was successful, False otherwise.
        str: Path to the generated .mtl.cryasset file if successful, or an error message.
    """
    try:
        # Determine output path for .mtl.cryasset file
        cryasset_file_path = mtl_file_path + ".cryasset"  # Simply append .cryasset to the mtl file path
        mtl_filename = os.path.basename(mtl_file_path)  # Extract just the filename for reference in the XML
        
        # Count number of sub-materials and textures
        # Ignore materials that match those in ignored_materials set
        ignored_materials = {"Material", "Dots Stroke"}
        valid_materials = [mat for mat in materials_data if mat.get('name') not in ignored_materials]
        sub_material_count = len(valid_materials)
        
        # Collect all unique texture paths as dependencies
        texture_paths = set()
        for material in valid_materials:
            textures = material.get('textures', {})
            for texture_type, texture_path in textures.items():
                if texture_path:  # Skip None/empty paths
                    texture_paths.add(texture_path)
                    
                    # If it's a diffuse texture with alpha channel, we might want to
                    # add specific handling here in the future if needed
        
        # Generate a UUID for the asset
        # Standard uuid4 format like ab463a09-a602-2798-be4f-e2617eacb919 (example from user)
        asset_guid = str(uuid.uuid4())  # This already has the correct format with dashes
        
        # Create the XML structure
        root = ET.Element("AssetMetadata", version="0", type="Material", guid=asset_guid)
        
        # Add Files section
        files = ET.SubElement(root, "Files")
        # Use relative path within the XML - just the filename is typically enough
        ET.SubElement(files, "File", path=mtl_filename)
        
        # Add Details section
        details = ET.SubElement(root, "Details")
        ET.SubElement(details, "Detail", name="subMaterialCount").text = str(sub_material_count)
        ET.SubElement(details, "Detail", name="textureCount").text = str(len(texture_paths))
        
        # Add Dependencies section
        dependencies = ET.SubElement(root, "Dependencies")
        
        # Collect engine textures first (from the example, these often start with %ENGINE%)
        engine_textures = [
            "%ENGINE%/EngineAssets/Textures/white.dds",
            "%ENGINE%/EngineAssets/Textures/white_ddna.dds",
            "%ENGINE%/EngineAssets/Textures/white_displ.dds"
        ]
        
        # Add engine textures first
        for texture_path in engine_textures:
            ET.SubElement(dependencies, "Path", usageCount="1").text = texture_path
        
        # Then add project textures
        for texture_path in sorted(texture_paths):  # Sort for consistent order
            # Convert to relative paths using forward slashes as needed
            # Check if it's a DDS file (more likely to match CryEngine expectations)
            if texture_path.lower().endswith('.dds'):
                rel_path = _calculate_relative_path(texture_path, os.path.dirname(mtl_file_path))
                # Prefix with './' to match example format
                if not rel_path.startswith(('./', '../', '%')):
                    rel_path = './' + rel_path
                ET.SubElement(dependencies, "Path", usageCount="1").text = rel_path
        
        # Generate XML string that matches the cryasset format
        # We want formatting similar to the example, with single space indentation
        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        # Use single space for indent and remove XML declaration line
        xml_string = reparsed.toprettyxml(indent=" ")
        # Remove XML declaration line (<?xml version="1.0" ?>)
        xml_string = '\n'.join(xml_string.split('\n')[1:])
        
        # Write to file
        with open(cryasset_file_path, "w", encoding="utf-8") as f:
            f.write(xml_string)
        
        print(f"Successfully exported MTL.cryasset file to: {cryasset_file_path}")
        return True, cryasset_file_path
    
    except Exception as e:
        error_msg = f"Failed to export MTL.cryasset file for '{mtl_file_path}': {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return False, error_msg


# Example Usage (for testing purposes)
if __name__ == '__main__':
    print("Testing MTL Exporter...")
    # Define dummy data similar to what the application might provide
    dummy_materials = [
        {
            'name': 'cliff_side1_test',
            'textures': {
                'diffuse': r'z:\mcp\dandan\processed_textures\cliff_side_diff.dds',
                'normal': r'z:\mcp\dandan\processed_textures\cliff_side_ddna.dds', # Our internal 'normal' maps to CE 'Bumpmap'
                'specular': r'z:\mcp\dandan\processed_textures\cliff_side_spec.dds',
                'displacement': r'z:\mcp\dandan\processed_textures\cliff_side_displ.dds',
                'emissive': r'z:\mcp\dandan\processed_textures\cliff_side_emissive.dds'
            }
        },
        {
            'name': 'rock_face_test',
            'textures': {
                'diffuse': r'z:\mcp\dandan\processed_textures\model\rock_face_01_diff.dds',
                'normal': r'z:\mcp\dandan\processed_textures\model\rock_face_01_ddna.dds'
            }
        },
        {
            'name': 'transparent_material_test',
            'textures': {
                # For testing alpha detection in diffuse textures
                'diffuse': r'z:\mcp\dandan\processed_textures\alpha_test_diff.dds'
            }
        }
    ]
    # Define dummy output directories
    dummy_model_dir = r'z:\mcp\dandan\output\model_export'
    dummy_texture_dir = r'z:\mcp\dandan\output\texture_export' # For reference, not used in path calc
    dummy_filename = 'test_export.mtl'

    print(f"Model Output Dir: {dummy_model_dir}")
    print(f"Texture Output Dir: {dummy_texture_dir}")
    print(f"Output Filename: {dummy_filename}")
    print(f"Materials Data: {dummy_materials}")

    # Ensure the dummy texture directory exists for the sake of the example paths
    # (though the function itself only needs model_output_dir for relpath)
    os.makedirs(os.path.dirname(dummy_materials[0]['textures']['diffuse']), exist_ok=True)
    os.makedirs(os.path.dirname(dummy_materials[1]['textures']['diffuse']), exist_ok=True)


    # Call the export function
    success, result = export_mtl(dummy_materials, dummy_model_dir, dummy_texture_dir, dummy_filename)

    if success:
        print(f"\n--- Generated MTL Content ({result}) ---")
        try:
            with open(result, 'r', encoding='utf-8') as f:
                print(f.read())
        except Exception as e:
            print(f"Error reading generated file: {e}")
        print("--- End of Content ---")
        
        # Check if cryasset file was also generated
        cryasset_path = result + ".cryasset"
        if os.path.exists(cryasset_path):
            print(f"\n--- Generated MTL.cryasset Content ({cryasset_path}) ---")
            try:
                with open(cryasset_path, 'r', encoding='utf-8') as f:
                    print(f.read())
            except Exception as e:
                print(f"Error reading generated cryasset file: {e}")
            print("--- End of Cryasset Content ---")
    else:
        print(f"\nMTL Export failed: {result}")

    print("\nMTL Exporter test finished.")
