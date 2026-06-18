#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate controlled multi-material FBX fixtures with Blender."""

import argparse
import json
import os
import subprocess
import tempfile


DEFAULT_BLENDER_CANDIDATES = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
)

DEFAULT_MATERIALS = ("Slot_0_Red", "Slot_1_Green", "Slot_2_Blue")


def discover_default_blender(candidates=DEFAULT_BLENDER_CANDIDATES):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def _blender_script(output_fbx_path, manifest_path, material_names):
    material_names_expr = repr(list(material_names))
    output_fbx_expr = repr(output_fbx_path)
    manifest_expr = repr(manifest_path)
    return f"""
import json
import math
import os

import bpy
from mathutils import Vector

output_fbx_path = {output_fbx_expr}
manifest_path = {manifest_expr}
material_names = {material_names_expr}

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

mesh = bpy.data.meshes.new('CE_MaterialSlotProbeMesh')
verts = [
    (-1.0, -1.0, 0.0),
    (1.0, -1.0, 0.0),
    (1.0, 1.0, 0.0),
    (-1.0, 1.0, 0.0),
]
faces = [
    (0, 1, 2),
    (0, 2, 3),
]
mesh.from_pydata(verts, [], faces)
mesh.update()

obj = bpy.data.objects.new('CE_MaterialSlotProbe', mesh)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

colors = [
    (1.0, 0.05, 0.05, 1.0),
    (0.05, 1.0, 0.05, 1.0),
    (0.05, 0.05, 1.0, 1.0),
]
for index, name in enumerate(material_names):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = colors[index % len(colors)]
    obj.data.materials.append(mat)

for polygon in obj.data.polygons:
    polygon.material_index = polygon.index % len(material_names)

bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

os.makedirs(os.path.dirname(output_fbx_path), exist_ok=True)
bpy.ops.export_scene.fbx(
    filepath=output_fbx_path,
    use_selection=True,
    object_types={{'MESH'}},
    apply_unit_scale=True,
    global_scale=1.0,
    axis_forward='-Y',
    axis_up='Z',
    add_leaf_bones=False,
    bake_anim=False,
    use_mesh_modifiers=True,
    path_mode='AUTO',
)

manifest = {{
    'object': obj.name,
    'fbx': output_fbx_path,
    'materials': [
        {{'slot': index, 'name': name}}
        for index, name in enumerate(material_names)
    ],
    'polygons': [
        {{
            'polygon': polygon.index,
            'vertices': list(polygon.vertices),
            'material_slot': polygon.material_index,
            'material_name': material_names[polygon.material_index],
        }}
        for polygon in obj.data.polygons
    ],
    'expect_cgf_material_ids': sorted(set(polygon.material_index for polygon in obj.data.polygons)),
}}
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"""


def build_blender_command(blender_path, script_path):
    return [blender_path, "--background", "--factory-startup", "--python", script_path]


def generate_material_fixture(blender_path, output_dir, asset_name="CE_MaterialSlotProbe", material_names=None):
    blender_path = blender_path or discover_default_blender()
    output_dir = os.path.abspath(output_dir)
    material_names = tuple(material_names or DEFAULT_MATERIALS)

    if not blender_path:
        raise RuntimeError("Blender executable path is required")
    if not os.path.exists(blender_path):
        raise RuntimeError(f"Blender executable not found: {blender_path}")
    if not material_names:
        raise RuntimeError("At least one material name is required")

    os.makedirs(output_dir, exist_ok=True)
    output_fbx_path = os.path.join(output_dir, f"{asset_name}.fbx")
    manifest_path = os.path.join(output_dir, f"{asset_name}.fixture_manifest.json")

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script_file:
        script_path = script_file.name
        script_file.write(_blender_script(output_fbx_path, manifest_path, material_names))

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
    if not os.path.exists(output_fbx_path):
        raise RuntimeError(f"Blender did not create FBX: {output_fbx_path}")
    if not os.path.exists(manifest_path):
        raise RuntimeError(f"Blender did not create manifest: {manifest_path}")

    return {
        "success": True,
        "blender": blender_path,
        "command": command,
        "fbx": output_fbx_path,
        "manifest": manifest_path,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def material_names_from_arg(value):
    names = [item.strip() for item in (value or "").split(",") if item.strip()]
    return names or list(DEFAULT_MATERIALS)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a controlled multi-material FBX fixture with Blender.")
    parser.add_argument("--blender", default=discover_default_blender(), help="Path to blender.exe")
    parser.add_argument("--output-dir", required=True, help="Directory for generated fixture files")
    parser.add_argument("--asset-name", default="CE_MaterialSlotProbe", help="Output FBX base name")
    parser.add_argument("--materials", default=",".join(DEFAULT_MATERIALS), help="Comma-separated material names")
    args = parser.parse_args(argv)

    result = generate_material_fixture(
        args.blender,
        args.output_dir,
        asset_name=args.asset_name,
        material_names=material_names_from_arg(args.materials),
    )

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
