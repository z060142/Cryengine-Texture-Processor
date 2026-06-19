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


def collect_unknown_request_fields(request):
    unknown = {"root": sorted(set(request or {}) - RC_IMPORT_ROOT_FIELDS), "nodes": [], "materials": [], "jointPhysicsData": []}

    def visit_node(node, path):
        unknown_fields = sorted(set(node or {}) - RC_IMPORT_NODE_FIELDS)
        if unknown_fields:
            unknown["nodes"].append({"path": path, "fields": unknown_fields})
        for index, child in enumerate((node or {}).get("nodes", []) or []):
            visit_node(child, f"{path}/nodes[{index}]")

    for index, node in enumerate((request or {}).get("nodes", []) or []):
        visit_node(node, f"nodes[{index}]")

    for index, material in enumerate((request or {}).get("materials", []) or []):
        unknown_fields = sorted(set(material or {}) - RC_IMPORT_MATERIAL_FIELDS)
        if unknown_fields:
            unknown["materials"].append({"index": index, "fields": unknown_fields})

    for index, physics_data in enumerate((request or {}).get("jointPhysicsData", []) or []):
        unknown_fields = sorted(set(physics_data or {}) - RC_IMPORT_JOINT_PHYSICS_FIELDS)
        joint_limits = (physics_data or {}).get("jointLimits", {}) or {}
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


def collect_request_schema_diagnostics(request):
    unknown = collect_unknown_request_fields(request)
    diagnostics = []

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
