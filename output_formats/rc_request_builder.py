#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build CryEngine Resource Compiler FBX import requests."""

import importlib
import os
import re
import traceback

from model_processing.material_index_assigner import assign_material_sub_indices

VALID_WRAPPER_NAMES = {"request", "metadata"}


def get_node_path(node_name, parent_path=None):
    if parent_path is None:
        return [node_name]
    return parent_path + [node_name]


def detect_node_type(node_name):
    node_info = {
        "is_lod": False,
        "is_proxy": False,
        "is_helper": False,
        "lod_level": None,
    }
    name_lower = (node_name or "").lower()

    lod_prefix_match = re.search(r"^(\$lod|lod)(\d+)(?:_|$)", name_lower)
    lod_suffix_match = re.search(r"_lod(\d+)$", name_lower)
    if lod_prefix_match:
        node_info["is_lod"] = True
        node_info["lod_level"] = int(lod_prefix_match.group(2))
    elif lod_suffix_match:
        node_info["is_lod"] = True
        node_info["lod_level"] = int(lod_suffix_match.group(1))

    proxy_patterns = [
        r"^\$proxy",
        r"^\$physics",
        r"^proxy_",
        r"^physics_",
        r"_proxy$",
        r"_physics$",
        r"_phys$",
    ]
    node_info["is_proxy"] = any(re.search(pattern, name_lower) for pattern in proxy_patterns)

    helper_patterns = ["_helper", "_control", "_pivot", "_locator", "_target"]
    node_info["is_helper"] = any(pattern in name_lower for pattern in helper_patterns)
    return node_info


def get_material_physicalize_type(material_name):
    name_lower = (material_name or "").lower()
    proxy_patterns = ["proxy", "phys", "physics", "collision", "collider"]
    if any(pattern in name_lower for pattern in proxy_patterns):
        return "proxy_only"
    return "no_collide"


def extract_blender_scene_hierarchy():
    try:
        bpy = importlib.import_module("bpy")
        top_level_objects = [obj for obj in bpy.data.objects if obj.parent is None]

        def extract_children(obj):
            return [
                {"name": child.name, "children": extract_children(child)}
                for child in obj.children
            ]

        return [
            {"name": obj.name, "children": extract_children(obj)}
            for obj in top_level_objects
        ]
    except Exception as e:
        print(f"Error extracting Blender scene hierarchy: {e}")
        traceback.print_exc()
        return []


def extract_scene_hierarchy_from_model(model_data):
    if "scene_hierarchy" in model_data:
        return model_data["scene_hierarchy"]

    blender_hierarchy = extract_blender_scene_hierarchy()
    if blender_hierarchy:
        return blender_hierarchy

    fallback_hierarchy = []
    for mesh in model_data.get("meshes", []):
        fallback_hierarchy.append(
            {
                "name": mesh.get("name", "UnnamedMesh"),
                "children": [],
            }
        )

    if not fallback_hierarchy:
        filename = os.path.basename(model_data.get("path", "unknown"))
        fallback_hierarchy.append(
            {
                "name": os.path.splitext(filename)[0],
                "children": [],
            }
        )

    return fallback_hierarchy


def process_node_hierarchy(nodes, parent_path=None):
    result = []
    for node in nodes or []:
        node_name = node.get("name", "UnnamedNode")
        node_path = get_node_path(node_name, parent_path)
        node_type = detect_node_type(node_name)

        json_node = {
            "name": node_name,
            "path": node_path,
            "nodes": [],
        }

        if node_type["is_lod"] and node_type["lod_level"] is not None:
            json_node["lod"] = node_type["lod_level"]
        if node_type["is_proxy"]:
            json_node["bIsProxy"] = True
        if node_type["is_helper"]:
            json_node["helper"] = True

        children = node.get("children", [])
        if children:
            json_node["nodes"] = process_node_hierarchy(children, node_path)

        result.append(json_node)
    return result


def find_joint_physics_relations(processed_nodes):
    joint_physics_data = []

    def find_proxy_relations(nodes):
        for node in nodes or []:
            node_path = node.get("path", [])
            if node.get("bIsProxy", False) and len(node_path) > 1:
                joint_physics_data.append(
                    {
                        "jointNodePath": node_path[:-1],
                        "proxyNodePath": node_path,
                        "snapToJoint": True,
                    }
                )
            find_proxy_relations(node.get("nodes", []))

    find_proxy_relations(processed_nodes)
    return joint_physics_data


def build_material_requests(materials, existing_submaterial_names=None, include_diagnostics=False):
    material_requests = []
    for material in assign_material_sub_indices(materials, existing_submaterial_names):
        request_material = {
            "name": material["clean_name"],
            "physicalize": get_material_physicalize_type(material["original_name"]),
            "sub_index": material["sub_index"],
        }
        if include_diagnostics and material.get("diagnostics"):
            request_material["diagnostics"] = material["diagnostics"]
        material_requests.append(request_material)
    return material_requests


def build_import_request(
    model_data,
    source_filename,
    material_filename=None,
    output_ext="cgf",
    unit_size="cm",
    scale=1.0,
    forward_up_axes="-Y+Z",
    merge_all_nodes=False,
    scene_origin=False,
    ignore_custom_normals=False,
    ignore_uv=False,
    autolodsettings=None,
    existing_submaterial_names=None,
):
    base_name = os.path.splitext(os.path.basename(source_filename))[0]
    node_hierarchy = extract_scene_hierarchy_from_model(model_data)
    processed_nodes = process_node_hierarchy(node_hierarchy)

    request = {
        "source_filename": source_filename,
        "output_ext": (output_ext or "cgf").lower(),
        "material_filename": material_filename or base_name,
        "unit_size": unit_size,
        "scale": scale,
        "forward_up_axes": forward_up_axes,
        "merge_all_nodes": merge_all_nodes,
        "scene_origin": scene_origin,
        "ignore_custom_normals": ignore_custom_normals,
        "ignore_uv": ignore_uv,
        "materials": build_material_requests(model_data.get("materials", []), existing_submaterial_names),
        "nodes": processed_nodes,
        "jointPhysicsData": find_joint_physics_relations(processed_nodes),
        "autolodsettings": autolodsettings or {"GenerateAutomaticLODs": False},
    }
    return request


def wrap_import_request(request, wrapper_name="request"):
    if wrapper_name not in VALID_WRAPPER_NAMES:
        raise ValueError(f"Invalid RC request wrapper: {wrapper_name}")
    return {wrapper_name: request}
