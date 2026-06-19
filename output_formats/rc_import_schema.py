#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Source-backed CryEngine RC FBX import request schema."""

from model_processing.rc_material_policy import (
    RC_MAX_SUB_MATERIALS,
    RC_PHYSICALIZE_VALUES,
    normalize_rc_sub_index,
)

RC_IMPORT_REQUEST_SOURCE = {
    "request_wrapper": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp",
        "lines": "275-284",
        "field": "request",
    },
    "root_fields": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp",
        "lines": "131-172",
    },
    "node_fields": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp",
        "lines": "22-44",
    },
    "material_fields": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp",
        "lines": "47-85",
    },
    "joint_physics_fields": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/ImportRequest.cpp",
        "lines": "98-128",
    },
    "supported_output_extensions": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp",
        "lines": "2783-2790",
    },
    "material_mapping": {
        "source": "Code/Tools/RC/ResourceCompilerPC/FBX/FbxConverter.cpp",
        "lines": "90-109",
    },
}

RC_IMPORT_ROOT_FIELDS = {
    "source_filename",
    "output_ext",
    "material_filename",
    "forward_up_axes",
    "unit_size",
    "scale",
    "physics_primitive",
    "merge_all_nodes",
    "scene_origin",
    "ignore_custom_normals",
    "ignore_uv",
    "materials",
    "nodes",
    "autolodsettings",
    "animation",
    "jointPhysicsData",
}

RC_IMPORT_NODE_FIELDS = {
    "path",
    "name",
    "mass",
    "density",
    "no_hit_refinement",
    "dynamic",
    "entity",
    "pieces",
    "primitive",
    "no_explosion_occlusion",
    "stiffness",
    "hardness",
    "max_stretch",
    "max_impulse",
    "skin_dist",
    "thickness",
    "explosion_scale",
    "gameplay_critical",
    "player_can_break",
    "constraint_limit",
    "constraint_minang",
    "constraint_maxang",
    "constraint_damping",
    "constraint_collides",
    "udp",
    "nodes",
}

RC_IMPORT_MATERIAL_FIELDS = {"name", "physicalize", "sub_index"}

RC_IMPORT_JOINT_PHYSICS_FIELDS = {
    "jointNodePath",
    "proxyNodePath",
    "snapToJoint",
    "jointLimits",
}

RC_IMPORT_JOINT_LIMIT_FIELDS = {
    "min_x",
    "min_y",
    "min_z",
    "max_x",
    "max_y",
    "max_z",
}

RC_IMPORT_PHYSICALIZE_VALUES = RC_PHYSICALIZE_VALUES

RC_IMPORT_PRIMITIVE_VALUES = {
    "default",
    "box",
    "cylinder",
    "capsule",
    "sphere",
    "notaprim",
}

RC_IMPORT_OUTPUT_EXTENSIONS = {"cgf", "chr", "skin", "caf", "i_caf"}
RC_IMPORT_MAX_SUB_MATERIALS = RC_MAX_SUB_MATERIALS


def _type_name(value):
    return type(value).__name__


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_non_empty_string(value):
    return isinstance(value, str) and bool(value)


def _is_list(value):
    return isinstance(value, list)


def _list_items(value):
    if not isinstance(value, list):
        return []
    return enumerate(value)


def collect_unknown_request_fields(request):
    if not isinstance(request, dict):
        return {}

    unknown = {"root": sorted(set(request) - RC_IMPORT_ROOT_FIELDS), "nodes": [], "materials": [], "jointPhysicsData": []}

    def visit_node(node, path):
        if not isinstance(node, dict):
            return
        unknown_fields = sorted(set(node) - RC_IMPORT_NODE_FIELDS)
        if unknown_fields:
            unknown["nodes"].append({"path": path, "fields": unknown_fields})
        for index, child in _list_items(node.get("nodes", [])):
            visit_node(child, f"{path}/nodes[{index}]")

    for index, node in _list_items(request.get("nodes", [])):
        visit_node(node, f"nodes[{index}]")

    for index, material in _list_items(request.get("materials", [])):
        if not isinstance(material, dict):
            continue
        unknown_fields = sorted(set(material) - RC_IMPORT_MATERIAL_FIELDS)
        if unknown_fields:
            unknown["materials"].append({"index": index, "fields": unknown_fields})

    for index, physics_data in _list_items(request.get("jointPhysicsData", [])):
        if not isinstance(physics_data, dict):
            continue
        unknown_fields = sorted(set(physics_data) - RC_IMPORT_JOINT_PHYSICS_FIELDS)
        joint_limits = physics_data.get("jointLimits", {}) or {}
        if not isinstance(joint_limits, dict):
            joint_limits = {}
        joint_limit_unknown = sorted(set(joint_limits) - RC_IMPORT_JOINT_LIMIT_FIELDS)
        if unknown_fields or joint_limit_unknown:
            unknown["jointPhysicsData"].append(
                {
                    "index": index,
                    "fields": unknown_fields,
                    "jointLimitFields": joint_limit_unknown,
                }
            )

    return {key: value for key, value in unknown.items() if value}


def collect_request_value_diagnostics(request):
    diagnostics = []

    if not isinstance(request, dict):
        return [
            {
                "severity": "error",
                "code": "rc_request_invalid_root",
                "location": "request",
                "value_type": _type_name(request),
                "schema_source": RC_IMPORT_REQUEST_SOURCE["request_wrapper"],
                "message": "RC import request must be a JSON object under the request wrapper.",
            }
        ]

    output_ext = request.get("output_ext")
    if output_ext not in RC_IMPORT_OUTPUT_EXTENSIONS:
        diagnostics.append(
            {
                "severity": "error",
                "code": "rc_request_invalid_output_ext",
                "location": "output_ext",
                "value": output_ext,
                "value_type": _type_name(output_ext),
                "allowed_values": sorted(RC_IMPORT_OUTPUT_EXTENSIONS),
                "schema_source": RC_IMPORT_REQUEST_SOURCE["supported_output_extensions"],
                "message": "RC import request output_ext is not one of the source-backed FBX converter output extensions.",
            }
        )

    for field in ("materials", "nodes", "jointPhysicsData"):
        if field in request and not _is_list(request.get(field)):
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_collection",
                    "location": field,
                    "field": field,
                    "value_type": _type_name(request.get(field)),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["root_fields"],
                    "message": "RC import request collection field must be a JSON array.",
                }
            )

    materials = request.get("materials", [])
    for index, material in _list_items(materials):
        location = f"materials[{index}]"
        if not isinstance(material, dict):
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_material_row",
                    "location": location,
                    "material_index": index,
                    "value_type": _type_name(material),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["material_fields"],
                    "message": "RC import request materials entries must be JSON objects.",
                }
            )
            continue

        name = material.get("name")
        if not _is_non_empty_string(name):
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_material_name",
                    "location": f"{location}.name",
                    "material_index": index,
                    "value": name,
                    "value_type": _type_name(name),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["material_fields"],
                    "message": "RC import request material name must be a non-empty string.",
                }
            )

        physicalize = material.get("physicalize")
        if physicalize not in RC_IMPORT_PHYSICALIZE_VALUES:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_material_physicalize",
                    "location": f"{location}.physicalize",
                    "material_index": index,
                    "value": physicalize,
                    "value_type": _type_name(physicalize),
                    "allowed_values": sorted(RC_IMPORT_PHYSICALIZE_VALUES),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["material_fields"],
                    "message": "RC import request material physicalize value must match the source-backed enum.",
                }
            )

        sub_index = material.get("sub_index")
        if not _is_int(sub_index) or sub_index < -1 or sub_index >= RC_IMPORT_MAX_SUB_MATERIALS:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_material_sub_index",
                    "location": f"{location}.sub_index",
                    "material_index": index,
                    "value": sub_index,
                    "value_type": _type_name(sub_index),
                    "min_value": -1,
                    "max_value": RC_IMPORT_MAX_SUB_MATERIALS - 1,
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["material_fields"],
                    "message": "RC-facing material sub_index must be an integer from -1 through MAX_SUB_MATERIALS - 1.",
                }
            )

    nodes = request.get("nodes", [])
    for index, node in _list_items(nodes):
        if not isinstance(node, dict):
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_node_row",
                    "location": f"nodes[{index}]",
                    "node_index": index,
                    "value_type": _type_name(node),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["node_fields"],
                    "message": "RC import request node entries must be JSON objects.",
                }
            )

    joint_physics_data = request.get("jointPhysicsData", [])
    for index, physics_data in _list_items(joint_physics_data):
        if not isinstance(physics_data, dict):
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_invalid_joint_physics_row",
                    "location": f"jointPhysicsData[{index}]",
                    "joint_physics_index": index,
                    "value_type": _type_name(physics_data),
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["joint_physics_fields"],
                    "message": "RC import request joint physics entries must be JSON objects.",
                }
            )

    return diagnostics


def collect_request_schema_diagnostics(request):
    unknown = collect_unknown_request_fields(request)
    diagnostics = collect_request_value_diagnostics(request)

    for field in unknown.get("root", []):
        diagnostics.append(
            {
                "severity": "error",
                "code": "rc_request_unknown_root_field",
                "location": field,
                "field": field,
                "schema_source": RC_IMPORT_REQUEST_SOURCE["root_fields"],
                "message": "RC import request root contains a field not backed by the source-derived schema.",
            }
        )

    for node in unknown.get("nodes", []):
        for field in node["fields"]:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_unknown_node_field",
                    "location": f"{node['path']}.{field}",
                    "field": field,
                    "node_path": node["path"],
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["node_fields"],
                    "message": "RC import request node contains a field not backed by the source-derived schema.",
                }
            )

    for material in unknown.get("materials", []):
        for field in material["fields"]:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_unknown_material_field",
                    "location": f"materials[{material['index']}].{field}",
                    "field": field,
                    "material_index": material["index"],
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["material_fields"],
                    "message": "RC import request material contains a field not backed by the source-derived schema.",
                }
            )

    for physics_data in unknown.get("jointPhysicsData", []):
        for field in physics_data["fields"]:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_unknown_joint_physics_field",
                    "location": f"jointPhysicsData[{physics_data['index']}].{field}",
                    "field": field,
                    "joint_physics_index": physics_data["index"],
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["joint_physics_fields"],
                    "message": "RC import request joint physics data contains a field not backed by the source-derived schema.",
                }
            )
        for field in physics_data["jointLimitFields"]:
            diagnostics.append(
                {
                    "severity": "error",
                    "code": "rc_request_unknown_joint_limit_field",
                    "location": f"jointPhysicsData[{physics_data['index']}].jointLimits.{field}",
                    "field": field,
                    "joint_physics_index": physics_data["index"],
                    "schema_source": RC_IMPORT_REQUEST_SOURCE["joint_physics_fields"],
                    "message": "RC import request joint limit data contains a field not backed by the source-derived schema.",
                }
            )

    return diagnostics


def assert_rc_import_request_schema(request):
    diagnostics = collect_request_schema_diagnostics(request)
    if diagnostics:
        locations = ", ".join(diagnostic["location"] for diagnostic in diagnostics[:5])
        if len(diagnostics) > 5:
            locations = f"{locations}, ..."
        raise ValueError(f"RC import request contains source-unsupported fields: {locations}")
    return request
