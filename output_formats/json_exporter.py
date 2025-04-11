#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JSON Exporter Module for CryEngine

This module provides functionality to export CryEngine compatible JSON configuration files
that are used by the CryEngine Resource Compiler (RC) for compiling models.
"""

import os
import json
import re
import traceback
from pathlib import Path
import importlib

def _get_node_path(node_name, parent_path=None):
    """
    Constructs a node path array based on the node name and optional parent path.
    
    Args:
        node_name (str): The name of the current node
        parent_path (list, optional): The parent node's path as a list
        
    Returns:
        list: The full path to the node as a list of strings
    """
    if parent_path is None:
        return [node_name]
    return parent_path + [node_name]

def _detect_node_type(node_name):
    """
    Detects the type of node based on naming conventions.
    
    Args:
        node_name (str): The name of the node
        
    Returns:
        dict: A dictionary with detected node properties like is_lod, is_proxy, lod_level
    """
    # Initialize properties
    node_info = {
        "is_lod": False,
        "is_proxy": False,
        "is_helper": False,
        "lod_level": None
    }
    
    # 轉換為小寫以進行不區分大小寫的比較
    name_lower = node_name.lower()
    
    # LOD 檢測模式
    # 檢查帶有前綴的 LOD 模式 ($lod1, $lod2, lod1_, lod2_)
    lod_prefix_match = re.search(r'^(\$lod|lod)(\d+)(?:_|$)', name_lower)
    # 檢查帶有後綴的 LOD 模式 (_lod1, _lod2, _lod3)
    lod_suffix_match = re.search(r'_lod(\d+)$', name_lower)
    
    if lod_prefix_match:
        node_info["is_lod"] = True
        node_info["lod_level"] = int(lod_prefix_match.group(2))
    elif lod_suffix_match:
        node_info["is_lod"] = True
        node_info["lod_level"] = int(lod_suffix_match.group(1))
    
    # Proxy 檢測模式
    # 檢查前綴 ($proxy, $physics, proxy_, physics_)
    proxy_prefix_patterns = [r'^\$proxy', r'^\$physics', r'^proxy_', r'^physics_']
    # 檢查後綴 (_proxy, _physics)
    proxy_suffix_patterns = [r'_proxy$', r'_physics$', r'_phys$']
    
    for pattern in proxy_prefix_patterns + proxy_suffix_patterns:
        if re.search(pattern, name_lower):
            node_info["is_proxy"] = True
            break
    
    # Helper 節點檢測
    helper_patterns = [r'_helper', r'_control', r'_pivot', r'_locator', r'_target']
    for pattern in helper_patterns:
        if pattern in name_lower:
            node_info["is_helper"] = True
            break
    
    return node_info

def _get_material_physicalize_type(material_name, total_polygons=None):
    """
    Determines the appropriate physicalize type for a material based on its name.
    
    Args:
        material_name (str): The name of the material
        total_polygons (int, optional): Total number of polygons in the model (not used)
        
    Returns:
        str: The physicalize type ("no_collide", "proxy_only", etc.)
    """
    # Convert to lowercase for case-insensitive comparison
    name_lower = material_name.lower()
    
    # Proxy-only materials (used for physics proxies only)
    proxy_patterns = ["proxy", "phys", "physics", "collision", "collider"]
    if any(pattern in name_lower for pattern in proxy_patterns):
        return "proxy_only"
    
    # 所有材質無論面數都設置為無碰擊
    return "no_collide"

def _extract_blender_scene_hierarchy():
    """
    Extracts the hierarchy of objects from the current Blender scene.
    
    Returns:
        list: A list of node dictionaries representing the scene hierarchy
    """
    try:
        # Try to import bpy
        bpy = importlib.import_module('bpy')
        
        # Get top-level objects (objects without parents)
        top_level_objects = [obj for obj in bpy.data.objects if obj.parent is None]
        
        # Function to recursively extract child hierarchy
        def extract_children(obj):
            children = []
            for child in obj.children:
                child_dict = {
                    "name": child.name,
                    "children": extract_children(child)
                }
                children.append(child_dict)
            return children
        
        # Start with top-level objects
        hierarchy = []
        for obj in top_level_objects:
            obj_dict = {
                "name": obj.name,
                "children": extract_children(obj)
            }
            hierarchy.append(obj_dict)
        
        return hierarchy
    except Exception as e:
        print(f"Error extracting Blender scene hierarchy: {e}")
        traceback.print_exc()
        return []

def _process_node_hierarchy(nodes, parent_path=None):
    """
    Recursively processes a node hierarchy and converts it to the JSON format.
    
    Args:
        nodes (list): List of node objects
        parent_path (list, optional): Path to the parent node
        
    Returns:
        list: Processed node hierarchy in the required JSON format
    """
    result = []
    
    for node in nodes:
        node_name = node.get("name", "UnnamedNode")
        node_path = _get_node_path(node_name, parent_path)
        node_type = _detect_node_type(node_name)
        
        # Create the basic node structure
        json_node = {
            "name": node_name,
            "path": node_path,
            "nodes": []  # Will be populated with children
        }
        
        # Add specialized properties based on node type
        if node_type["is_lod"] and node_type["lod_level"] is not None:
            json_node["lod"] = node_type["lod_level"]
        
        if node_type["is_proxy"]:
            json_node["bIsProxy"] = True
        
        if node_type["is_helper"]:
            json_node["helper"] = True
        
        # Process child nodes recursively if they exist
        if "children" in node and node["children"]:
            json_node["nodes"] = _process_node_hierarchy(node["children"], node_path)
        
        # Add the processed node to the result
        result.append(json_node)
    
    return result

def _find_joint_physics_relations(processed_nodes):
    """
    Identifies joint-proxy relationships within the processed node hierarchy.
    
    Args:
        processed_nodes (list): The processed node hierarchy
        
    Returns:
        list: Joint physics data in the required format
    """
    joint_physics_data = []
    
    def _find_proxy_relations(nodes, current_path=None):
        """Helper function to recursively find proxy relations."""
        if current_path is None:
            current_path = []
        
        for node in nodes:
            node_name = node.get("name", "")
            node_path = node.get("path", [])
            is_proxy = node.get("bIsProxy", False)
            
            # If this is a proxy node, try to find its parent joint
            if is_proxy:
                # The parent joint is typically the parent node or a node with similar name without '_proxy'
                # Here, we're assuming the proxy's direct parent is the joint
                if len(node_path) > 1:
                    joint_path = node_path[:-1]  # Parent's path
                    
                    # Add to joint physics data
                    joint_physics_data.append({
                        "jointNodePath": joint_path,
                        "proxyNodePath": node_path,
                        "snapToJoint": True  # Default to true
                    })
            
            # Recursively process child nodes
            if "nodes" in node and node["nodes"]:
                _find_proxy_relations(node["nodes"], node_path)
    
    # Start the recursive search
    _find_proxy_relations(processed_nodes)
    
    return joint_physics_data

def _get_ui_material_name(material_name):
    """
    Generates a UI material name by removing number suffixes (.001, .002 etc.)
    to better match with MTL material names.
    
    Args:
        material_name (str): The internal material name
        
    Returns:
        str: Material name without numeric suffixes
    """
    # 先清除數字後綴，如 .001, .002 等
    # 此正則表達式會匹配像 .001, .002 等這樣的數字後綴
    clean_name = re.sub(r'\.[0-9]{3}$', '', material_name)
    
    return clean_name

def _extract_scene_hierarchy_from_model(model_data):
    """
    Extracts the scene hierarchy from a model data dictionary.
    
    Args:
        model_data (dict): The model data dictionary
        
    Returns:
        list: A list of node objects representing the scene hierarchy
    """
    # First check if the model has a "scene_hierarchy" key 
    if "scene_hierarchy" in model_data:
        return model_data["scene_hierarchy"]
        
    # Try to extract scene hierarchy from the Blender scene
    blender_hierarchy = _extract_blender_scene_hierarchy()
    if blender_hierarchy:
        return blender_hierarchy
    
    # Fallback to a simple hierarchy based on objects in the model
    # Extract meshes as top-level nodes
    fallback_hierarchy = []
    meshes = model_data.get("meshes", [])
    for mesh in meshes:
        # Create a simple node for this mesh
        mesh_node = {
            "name": mesh.get("name", "UnnamedMesh"),
            "children": []
        }
        
        # Check if we can identify LOD or proxy nodes based on the name
        node_type = _detect_node_type(mesh_node["name"])
        if node_type["is_lod"] or node_type["is_proxy"]:
            # If this is a LOD or proxy node, try to find a parent
            # In this simple fallback, just add it to the top level
            fallback_hierarchy.append(mesh_node)
        else:
            # Add this as a regular node
            fallback_hierarchy.append(mesh_node)
    
    # If we have no mesh data, create a single node based on the filename
    if not fallback_hierarchy:
        filename = os.path.basename(model_data.get("path", "unknown"))
        base_name = os.path.splitext(filename)[0]
        fallback_hierarchy.append({
            "name": base_name,
            "children": []
        })
    
    return fallback_hierarchy

def export_json(model_data, source_filename, output_path, texture_output_dir):
    """
    Exports a CryEngine-compatible JSON configuration file for the given model data.
    
    Args:
        model_data (dict): Model data containing materials, nodes, etc.
        source_filename (str): The original filename of the source model (e.g., "Tree.fbx")
        output_path (str): Path to save the JSON file to
        texture_output_dir (str): Directory where texture files are stored
        
    Returns:
        tuple: (success, result_path_or_message)
            - success (bool): True if export was successful, False otherwise
            - result_path_or_message (str): Path to the exported file or error message
    """
    try:
        # Get the base name for the output file (without extension)
        base_name = os.path.splitext(os.path.basename(source_filename))[0]
        json_filename = f"{base_name}.json"
        json_file_path = os.path.join(output_path, json_filename)
        
        # Get material data from the model
        materials = model_data.get("materials", [])
        
        # Get node hierarchy from the model
        node_hierarchy = _extract_scene_hierarchy_from_model(model_data)
        
        # Create base JSON structure
        json_data = {
            "metadata": {
                "version": 1,
                "source_filename": source_filename,
                "output_ext": "cgf",  # Default to cgf, could be dynamic based on model type
                "material_filename": base_name,  # Same as base model name without extension
                "unit_size": "cm",  # Default, could be extracted from model if available
                "scale": 1.0,  # Default, could be extracted from model if available
                "forward_up_axes": "-Y+Z",  # Default for CryEngine, could be dynamic
                "merge_all_nodes": False,  # Default, could be a user setting
                "scene_origin": False,  # 設置預設為false,不使用場景原點
                "ignore_custom_normals": False,  # Default, could be a user setting
                "ignore_uv": False,  # Default, could be a user setting
                "materials": [],
                "nodes": [],
                "jointPhysicsData": [],
                "use_32_bit_positions": False,  # Default, could be a user setting
                "autolodsettings": {
                    "GenerateAutomaticLODs": False  # Default, could be a user setting
                }
            }
        }
        
        # 計算模型的總多邊形面數
        total_polygons = 0
        meshes = model_data.get("meshes", [])
        for mesh in meshes:
            total_polygons += mesh.get("polygons", 0)
        
        print(f"Total polygons in model: {total_polygons}")
        
        # 處理材質索引與名稱兼容性
        # 1. 清除數字後綴 (.001, .002)
        # 2. 去除重複材質（清除後綴後可能產生重複名稱）
        # 3. 確保sub_index是連續的整數，從0開始
        
        # 準備材質數據，保存清理後的名稱和唯一材質列表
        clean_materials = []
        seen_clean_names = set()
        
        for i, material in enumerate(materials):
            material_name = material.get("name", f"Material_{i}")
            
            # 跳過默認/不需要的材質
            if material_name in ["Material", "Dots Stroke"]:
                continue
            
            # 清除數字後綴
            clean_name = re.sub(r'\.[0-9]{3}$', '', material_name)
            
            # 如果清理後的名稱已存在，跳過這個材質
            if clean_name in seen_clean_names:
                print(f"跳過重複材質（清理後綴後）: {material_name} -> {clean_name}")
                continue
            
            # 記錄這個清理後的名稱
            seen_clean_names.add(clean_name)
            
            # 添加到清理後的材質列表
            clean_materials.append({
                "original_name": material_name,
                "clean_name": clean_name,
                "index": len(clean_materials)  # 使用連續的索引
            })
        
        # 處理材質
        for mat_data in clean_materials:
            material_entry = {
                "name": mat_data["clean_name"],  # 使用清理後的名稱作為材質名
                "file": f"{base_name}.mtl",
                "physicalize": _get_material_physicalize_type(mat_data["original_name"], total_polygons),
                "sub_index": mat_data["index"],  # 使用連續的索引
                "ui_name": mat_data["clean_name"],  # UI名稱也使用清理後的名稱
                "ui_autoflag": True
            }
            
            json_data["metadata"]["materials"].append(material_entry)
        
        # Process nodes hierarchy
        processed_nodes = _process_node_hierarchy(node_hierarchy)
        json_data["metadata"]["nodes"] = processed_nodes
        
        # Find joint-proxy relationships
        json_data["metadata"]["jointPhysicsData"] = _find_joint_physics_relations(processed_nodes)
        
        # Write the JSON file
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        with open(json_file_path, "w", encoding="utf-8") as f:
            # Pretty print with 2-space indentation
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully exported JSON configuration to: {json_file_path}")
        return True, json_file_path
    
    except Exception as e:
        error_msg = f"Failed to export JSON configuration file '{source_filename}': {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg

# Example usage (for testing purposes)
if __name__ == "__main__":
    print("Testing JSON Exporter...")
    
    # Define dummy model data similar to what the application might provide
    dummy_model_data = {
        "materials": [
            {"name": "Trunk_Material"},
            {"name": "Leaves_Material"},
            {"name": "Material"},  # Should be skipped
        ],
        "nodes": [
            {
                "name": "Trunk",
                "children": [
                    {
                        "name": "Trunk_LOD1",
                        "children": []
                    },
                    {
                        "name": "Trunk_Proxy",
                        "children": []
                    }
                ]
            },
            {
                "name": "Leaves",
                "children": []
            }
        ]
    }
    
    # Define dummy paths
    dummy_source_filename = "Tree.fbx"
    dummy_output_path = "Z:/mcp/dandan/output/model_export"
    dummy_texture_dir = "Z:/mcp/dandan/output/texture_export"
    
    # Ensure output directory exists
    os.makedirs(dummy_output_path, exist_ok=True)
    
    # Call the export function
    success, result = export_json(dummy_model_data, dummy_source_filename, dummy_output_path, dummy_texture_dir)
    
    if success:
        print(f"\n--- Generated JSON Content ({result}) ---")
        try:
            with open(result, "r", encoding="utf-8") as f:
                print(json.dumps(json.load(f), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error reading generated file: {e}")
        print("--- End of Content ---")
    else:
        print(f"\nJSON Export failed: {result}")
    
    print("\nJSON Exporter test finished.")