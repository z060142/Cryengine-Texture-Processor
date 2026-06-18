#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inspect FBX material table evidence with Blender."""

import argparse
import json
import os
import subprocess
import tempfile

from tools.blender_material_fixture import build_blender_command, discover_default_blender


DEFAULT_MANIFEST_SUFFIX = ".fbx_material_manifest.json"


def default_manifest_path(fbx_path):
    return os.path.splitext(os.path.abspath(fbx_path))[0] + DEFAULT_MANIFEST_SUFFIX


def _blender_script(fbx_path, manifest_path):
    fbx_expr = repr(fbx_path)
    manifest_expr = repr(manifest_path)
    return f"""
import json
import os

import bpy
from mathutils import Vector

fbx_path = {fbx_expr}
manifest_path = {manifest_expr}

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.import_scene.fbx(filepath=fbx_path)

material_slots = []
material_name_to_slot = {{}}
objects = []
polygons = []

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
mesh_objects.sort(key=lambda obj: obj.name)

for obj in mesh_objects:
    objects.append(obj.name)
    world = obj.matrix_world
    for local_slot, mat in enumerate(obj.data.materials):
        if mat is None:
            material_name = 'unassigned'
        else:
            material_name = mat.name
        if material_name not in material_name_to_slot:
            material_name_to_slot[material_name] = len(material_slots)
            material_slots.append({{
                'slot': material_name_to_slot[material_name],
                'name': material_name,
                'first_object': obj.name,
                'first_local_slot': local_slot,
            }})

    for polygon in obj.data.polygons:
        local_slot = int(polygon.material_index)
        mat = obj.data.materials[local_slot] if local_slot < len(obj.data.materials) else None
        material_name = mat.name if mat is not None else 'unassigned'
        material_slot = material_name_to_slot.setdefault(material_name, len(material_slots))
        if material_slot == len(material_slots):
            material_slots.append({{
                'slot': material_slot,
                'name': material_name,
                'first_object': obj.name,
                'first_local_slot': local_slot,
            }})

        center = Vector((0.0, 0.0, 0.0))
        for vertex_index in polygon.vertices:
            center += world @ obj.data.vertices[vertex_index].co
        center = center / max(1, len(polygon.vertices))
        polygon_index = len(polygons)
        polygons.append({{
            'polygon': polygon_index,
            'object': obj.name,
            'object_polygon': int(polygon.index),
            'vertices': [int(vertex_index) for vertex_index in polygon.vertices],
            'material_slot': local_slot,
            'material_table_slot': material_slot,
            'material_name': material_name,
            'expected_cgf_material_id': material_slot,
            'center': [float(center.x), float(center.y), float(center.z)],
            'center_x': float(center.x),
        }})

manifest = {{
    'manifest_kind': 'blender-fbx-material-inspection',
    'fbx': fbx_path,
    'objects': objects,
    'materials': material_slots,
    'polygons': polygons,
    'expect_cgf_material_ids': sorted(set(polygon['expected_cgf_material_id'] for polygon in polygons)),
}}

os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"""


def inspect_fbx_materials(blender_path, fbx_path, manifest_path=None):
    blender_path = blender_path or discover_default_blender()
    fbx_path = os.path.abspath(fbx_path)
    manifest_path = os.path.abspath(manifest_path or default_manifest_path(fbx_path))

    if not blender_path:
        raise RuntimeError("Blender executable path is required")
    if not os.path.exists(blender_path):
        raise RuntimeError(f"Blender executable not found: {blender_path}")
    if not os.path.exists(fbx_path):
        raise RuntimeError(f"FBX file not found: {fbx_path}")

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script_file:
        script_path = script_file.name
        script_file.write(_blender_script(fbx_path, manifest_path))

    command = build_blender_command(blender_path, script_path)
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout or f"Blender exited with code {completed.returncode}")
    if not os.path.exists(manifest_path):
        raise RuntimeError(f"Blender did not create manifest: {manifest_path}")

    return {
        "success": True,
        "blender": blender_path,
        "command": command,
        "fbx": fbx_path,
        "manifest": manifest_path,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect FBX material table evidence with Blender.")
    parser.add_argument("--blender", default=discover_default_blender(), help="Path to blender.exe")
    parser.add_argument("--fbx", required=True, help="Path to source FBX")
    parser.add_argument("--manifest", default="", help="Output manifest path")
    args = parser.parse_args(argv)

    result = inspect_fbx_materials(args.blender, args.fbx, args.manifest or None)
    print(f"success: {result['success']}")
    print(f"blender: {result['blender']}")
    print(f"fbx: {result['fbx']}")
    print(f"manifest: {result['manifest']}")
    if result["stdout"]:
        print(result["stdout"])
    if result["stderr"]:
        print(result["stderr"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
