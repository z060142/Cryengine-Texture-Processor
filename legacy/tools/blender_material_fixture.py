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
DEFAULT_POLYGON_SLOTS = (0, 1)
FIXTURE_KIND_SINGLE_MESH = "single-mesh"
FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT = "multi-mesh-name-conflict"
FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL = "multi-mesh-shared-material"
FIXTURE_KINDS = (
    FIXTURE_KIND_SINGLE_MESH,
    FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT,
    FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL,
)
MULTI_MESH_CONFLICT_MATERIALS = ("LocalSlot0_Wood", "LocalSlot0_Metal")
MULTI_MESH_SHARED_MATERIALS = ("SharedSlot0_Surface",)


def discover_default_blender(candidates=DEFAULT_BLENDER_CANDIDATES):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def _single_mesh_blender_script(output_fbx_path, manifest_path, material_names, polygon_material_slots):
    material_names_expr = repr(list(material_names))
    polygon_slots_expr = repr(list(polygon_material_slots))
    output_fbx_expr = repr(output_fbx_path)
    manifest_expr = repr(manifest_path)
    return f"""
import json
import os

import bpy

output_fbx_path = {output_fbx_expr}
manifest_path = {manifest_expr}
material_names = {material_names_expr}
polygon_material_slots = {polygon_slots_expr}

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

mesh = bpy.data.meshes.new('CE_MaterialSlotProbeMesh')
verts = []
faces = []
for polygon_index, material_slot in enumerate(polygon_material_slots):
    x = float(polygon_index) * 3.0
    base = len(verts)
    verts.extend([
        (x - 1.0, -1.0, 0.0),
        (x + 1.0, -1.0, 0.0),
        (x, 1.0, 0.0),
    ])
    faces.append((base, base + 1, base + 2))
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
    polygon.material_index = polygon_material_slots[polygon.index]

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
            'object': obj.name,
            'center_x': float(polygon.index) * 3.0,
        }}
        for polygon in obj.data.polygons
    ],
    'polygon_material_slots': polygon_material_slots,
    'expect_cgf_material_ids': sorted(set(polygon.material_index for polygon in obj.data.polygons)),
}}
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"""


def _multi_mesh_name_conflict_blender_script(output_fbx_path, manifest_path, material_names):
    material_names_expr = repr(list(material_names))
    output_fbx_expr = repr(output_fbx_path)
    manifest_expr = repr(manifest_path)
    return f"""
import json
import os

import bpy

output_fbx_path = {output_fbx_expr}
manifest_path = {manifest_expr}
material_names = {material_names_expr}

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

colors = [
    (0.7, 0.36, 0.12, 1.0),
    (0.2, 0.55, 0.75, 1.0),
]
objects = []
polygons = []
for object_index, material_name in enumerate(material_names):
    x = float(object_index) * 3.0
    mesh = bpy.data.meshes.new(f'CE_MultiMeshSlotProbeMesh_{{object_index}}')
    mesh.from_pydata(
        [
            (x - 1.0, -1.0, 0.0),
            (x + 1.0, -1.0, 0.0),
            (x, 1.0, 0.0),
        ],
        [],
        [(0, 1, 2)],
    )
    mesh.update()

    obj = bpy.data.objects.new(f'CE_MultiMeshSlotProbe_{{object_index}}', mesh)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new(material_name)
    mat.diffuse_color = colors[object_index % len(colors)]
    obj.data.materials.append(mat)
    obj.data.polygons[0].material_index = 0
    obj.select_set(True)
    objects.append(obj)
    polygons.append({{
        'polygon': object_index,
        'object_polygon': 0,
        'vertices': list(obj.data.polygons[0].vertices),
        'material_slot': 0,
        'requested_material_name': material_name,
        'material_name': mat.name,
        'expected_cgf_material_id': object_index,
        'object': obj.name,
        'center_x': x,
    }})

bpy.context.view_layer.objects.active = objects[0]
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
    'fixture_kind': '{FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT}',
    'objects': [obj.name for obj in objects],
    'fbx': output_fbx_path,
    'materials': [
        {{'slot': index, 'name': polygon['material_name'], 'requested_name': polygon['requested_material_name']}}
        for index, polygon in enumerate(polygons)
    ],
    'polygons': polygons,
    'polygon_material_slots': [polygon['material_slot'] for polygon in polygons],
    'expect_cgf_material_ids': list(range(len(material_names))),
    'probe_question': 'Two mesh objects each use local material slot 0 with different material names.',
}}
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"""


def _multi_mesh_shared_material_blender_script(output_fbx_path, manifest_path, material_names):
    material_name_expr = repr(list(material_names)[0])
    output_fbx_expr = repr(output_fbx_path)
    manifest_expr = repr(manifest_path)
    return f"""
import json
import os

import bpy

output_fbx_path = {output_fbx_expr}
manifest_path = {manifest_expr}
material_name = {material_name_expr}

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

shared_mat = bpy.data.materials.new(material_name)
shared_mat.diffuse_color = (0.45, 0.68, 0.22, 1.0)

objects = []
polygons = []
for object_index in range(2):
    x = float(object_index) * 3.0
    mesh = bpy.data.meshes.new(f'CE_SharedMaterialProbeMesh_{{object_index}}')
    mesh.from_pydata(
        [
            (x - 1.0, -1.0, 0.0),
            (x + 1.0, -1.0, 0.0),
            (x, 1.0, 0.0),
        ],
        [],
        [(0, 1, 2)],
    )
    mesh.update()

    obj = bpy.data.objects.new(f'CE_SharedMaterialProbe_{{object_index}}', mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(shared_mat)
    obj.data.polygons[0].material_index = 0
    obj.select_set(True)
    objects.append(obj)
    polygons.append({{
        'polygon': object_index,
        'object_polygon': 0,
        'vertices': list(obj.data.polygons[0].vertices),
        'material_slot': 0,
        'requested_material_name': material_name,
        'material_name': shared_mat.name,
        'expected_cgf_material_id': 0,
        'object': obj.name,
        'center_x': x,
    }})

bpy.context.view_layer.objects.active = objects[0]
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
    'fixture_kind': '{FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL}',
    'objects': [obj.name for obj in objects],
    'fbx': output_fbx_path,
    'materials': [
        {{'slot': 0, 'name': shared_mat.name, 'requested_name': material_name}}
    ],
    'polygons': polygons,
    'polygon_material_slots': [polygon['material_slot'] for polygon in polygons],
    'expect_cgf_material_ids': [0],
    'probe_question': 'Two mesh objects both use local material slot 0 and the same Blender material datablock.',
}}
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write('\\n')
"""


def _blender_script(output_fbx_path, manifest_path, material_names, polygon_material_slots, fixture_kind):
    if fixture_kind == FIXTURE_KIND_SINGLE_MESH:
        return _single_mesh_blender_script(output_fbx_path, manifest_path, material_names, polygon_material_slots)
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT:
        return _multi_mesh_name_conflict_blender_script(output_fbx_path, manifest_path, material_names)
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL:
        return _multi_mesh_shared_material_blender_script(output_fbx_path, manifest_path, material_names)
    raise RuntimeError(f"Unsupported fixture kind: {fixture_kind}")


def build_blender_command(blender_path, script_path):
    return [blender_path, "--background", "--factory-startup", "--python", script_path]


def generate_material_fixture(
    blender_path,
    output_dir,
    asset_name="CE_MaterialSlotProbe",
    material_names=None,
    polygon_material_slots=None,
    fixture_kind=FIXTURE_KIND_SINGLE_MESH,
):
    blender_path = blender_path or discover_default_blender()
    output_dir = os.path.abspath(output_dir)
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT and material_names is None:
        material_names = MULTI_MESH_CONFLICT_MATERIALS
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL and material_names is None:
        material_names = MULTI_MESH_SHARED_MATERIALS
    material_names = tuple(material_names or DEFAULT_MATERIALS)
    polygon_material_slots = tuple(polygon_material_slots or DEFAULT_POLYGON_SLOTS)

    if not blender_path:
        raise RuntimeError("Blender executable path is required")
    if not os.path.exists(blender_path):
        raise RuntimeError(f"Blender executable not found: {blender_path}")
    if fixture_kind not in FIXTURE_KINDS:
        raise RuntimeError(f"Unsupported fixture kind: {fixture_kind}")
    if not material_names:
        raise RuntimeError("At least one material name is required")
    if not polygon_material_slots:
        raise RuntimeError("At least one polygon material slot is required")
    if fixture_kind == FIXTURE_KIND_SINGLE_MESH:
        max_slot = max(polygon_material_slots)
        min_slot = min(polygon_material_slots)
        if min_slot < 0:
            raise RuntimeError("Polygon material slots must be zero or positive")
        if max_slot >= len(material_names):
            raise RuntimeError(
                f"Polygon material slot {max_slot} has no matching material; only {len(material_names)} materials were provided"
            )
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_NAME_CONFLICT and len(material_names) < 2:
        raise RuntimeError("Multi-mesh name conflict fixture requires at least two material names")
    if fixture_kind == FIXTURE_KIND_MULTI_MESH_SHARED_MATERIAL and len(material_names) != 1:
        raise RuntimeError("Multi-mesh shared material fixture requires exactly one material name")

    os.makedirs(output_dir, exist_ok=True)
    output_fbx_path = os.path.join(output_dir, f"{asset_name}.fbx")
    manifest_path = os.path.join(output_dir, f"{asset_name}.fixture_manifest.json")

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script_file:
        script_path = script_file.name
        script_file.write(
            _blender_script(output_fbx_path, manifest_path, material_names, polygon_material_slots, fixture_kind)
        )

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


def polygon_slots_from_arg(value):
    if not value:
        return list(DEFAULT_POLYGON_SLOTS)
    slots = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        slots.append(int(item))
    return slots or list(DEFAULT_POLYGON_SLOTS)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a controlled multi-material FBX fixture with Blender.")
    parser.add_argument("--blender", default=discover_default_blender(), help="Path to blender.exe")
    parser.add_argument("--output-dir", required=True, help="Directory for generated fixture files")
    parser.add_argument("--asset-name", default="CE_MaterialSlotProbe", help="Output FBX base name")
    parser.add_argument(
        "--fixture-kind",
        choices=FIXTURE_KINDS,
        default=FIXTURE_KIND_SINGLE_MESH,
        help="Controlled fixture topology to generate",
    )
    parser.add_argument("--materials", default="", help="Comma-separated material names")
    parser.add_argument(
        "--polygon-slots",
        default=",".join(str(slot) for slot in DEFAULT_POLYGON_SLOTS),
        help="Comma-separated material slot index for each generated triangle",
    )
    args = parser.parse_args(argv)

    result = generate_material_fixture(
        args.blender,
        args.output_dir,
        asset_name=args.asset_name,
        material_names=material_names_from_arg(args.materials) if args.materials else None,
        polygon_material_slots=polygon_slots_from_arg(args.polygon_slots),
        fixture_kind=args.fixture_kind,
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
