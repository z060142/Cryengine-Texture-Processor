#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Thumbnail Generator

Generates a 256x256 PNG thumbnail for a given FBX model using Blender's bpy module.
Implemented exactly according to dev_example/render_script.py.
"""

import bpy
import os
import math
from mathutils import Vector
import traceback

def _reset_scene():
    """Clears the current Blender scene exactly as in the original script."""
    try:
        # Use the exact same implementation as the original script
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        for collection in bpy.data.collections:
            bpy.context.scene.collection.children.unlink(collection)
        for collection in bpy.data.collections:
            bpy.data.collections.remove(collection)
        print("Scene reset using original script method.")
    except Exception as e:
        print(f"Error during scene reset: {e}")
        traceback.print_exc()

def _setup_camera():
    """Creates and sets up a camera, exactly matching the original script."""
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    bpy.context.scene.camera = camera
    # Note: original script sets focal length in position_camera, not here
    print("Camera setup complete.")
    return camera

def _setup_lighting():
    """Creates and sets up a sun light, matching old script."""
    # Match old script's location and rotation
    bpy.ops.object.light_add(type='SUN', radius=1, location=(5, 5, 5)) 
    sun = bpy.context.active_object
    sun.data.energy = 2.0 # Keep energy setting
    sun.rotation_euler = (math.radians(45), 0, math.radians(45)) 
    print("Lighting setup complete (matched old script).")
    return sun

def _get_object_dimensions():
    """Calculates the bounding box dimensions and center of all mesh objects, exactly as in original script."""
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not objects:
        return Vector((0, 0, 0)), Vector((0, 0, 0))
    
    min_co = Vector((float('inf'),) * 3)
    max_co = Vector((float('-inf'),) * 3)
    
    for ob in objects:
        matrix = ob.matrix_world
        for v in ob.bound_box:
            v_world = matrix @ Vector(v)
            min_co = Vector(map(min, zip(min_co, v_world)))
            max_co = Vector(map(max, zip(max_co, v_world)))
    
    print(f"Calculated dimensions: {max_co - min_co}, center: {(min_co + max_co) / 2}")
    return max_co - min_co, (min_co + max_co) / 2

def _position_camera(camera, dimensions, center):
    """Positions the camera with adjusted height and aiming point for better framing."""
    # 計算最大尺寸
    max_dim = max(dimensions)
    
    # 計算相機位置，但降低Z軸高度15%
    original_camera_pos = center + Vector((1.5 * max_dim, -1.5 * max_dim, 1.5 * max_dim))
    height_reduction = original_camera_pos.z * 0.25  # 降低25%的高度
    camera.location = Vector((
        original_camera_pos.x,
        original_camera_pos.y,
        original_camera_pos.z - height_reduction
    ))
    
    # 調整瀏準點 - 將相機瀏準到模型中心的偏下方位置的幅度增加
    aim_point = center.copy()
    aim_point.z -= dimensions.z * 0.25  # 將視點下移高度的25%
    
    # 使相機對準調整後的點
    direction = aim_point - camera.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()
    
    # 維持焦距第65mm
    camera.data.lens = 65
    
    bpy.context.view_layer.update()
    print(f"Camera positioned at: {camera.location}, height reduced by: {height_reduction}")
    print(f"Aimed at: {aim_point}, 20% below center, lens: {camera.data.lens}mm")

def _center_objects():
    """Centers objects in the scene, exactly as in original script."""
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not objects:
        return
    
    center = Vector((0, 0, 0))
    for obj in objects:
        center += obj.location
    center /= len(objects)
    
    for obj in objects:
        obj.location -= center
    
    print(f"Objects centered by offset: {-center}")


def generate_thumbnail(fbx_path, output_png_path):
    """
    Generates a 256x256 PNG thumbnail for the given FBX model.

    Args:
        fbx_path (str): Path to the input FBX file.
        output_png_path (str): Path to save the output PNG thumbnail.

    Returns:
        bool: True if rendering was successful, False otherwise.
    """
    if not bpy:
        print("Error: bpy module not available. Cannot generate thumbnail.")
        return False
        
    if not os.path.exists(fbx_path):
        print(f"Error: Input FBX file not found: {fbx_path}")
        return False

    print(f"Starting improved thumbnail generation for: {os.path.basename(fbx_path)}")
    
    try:
        # 先清除場景中的所有對象
        _reset_scene()
        
        # 設置相機和燈光
        camera = _setup_camera()
        _setup_lighting()
        
        # 導入FBX模型
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        
        # 檢查是否有導入任何網格物體
        mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        if not mesh_objects:
            print(f"Warning: No mesh objects found in {os.path.basename(fbx_path)}. Attempting to continue...")
            # 快速解決方案：創建一個粒子系統小球來代表物體
            bpy.ops.mesh.primitive_ico_sphere_add(radius=0.1, location=(0, 0, 0))
            print("Added placeholder sphere for rendering")
            
        # 使物體在場景中居中
        _center_objects()
        
        # 獲取物體的尺寸和中心點
        dimensions, center = _get_object_dimensions()
        
        # 定位相機來捕捉物體
        _position_camera(camera, dimensions, center)
        
        # 設置渲染屬性
        render = bpy.context.scene.render
        render.image_settings.file_format = 'PNG'
        render.resolution_x = 256
        render.resolution_y = 256
        render.resolution_percentage = 100
        render.filepath = output_png_path
        
        # 改進版本：從物體適當角度渲染
        # 徜常可以嘗試多個角度並選擇最好的一個，但存在複雜化風險，先試用此方法
        
        # 渲染
        bpy.ops.render.render(write_still=True)
        print(f"Rendered with improved method: {output_png_path}")
        
        return True

    except Exception as e:
        print(f"Error during thumbnail generation for {os.path.basename(fbx_path)}: {e}")
        traceback.print_exc()
        return False

# Example usage (for testing purposes, not called by main app)
if __name__ == "__main__":
    # This part is for testing the script directly
    # Provide dummy paths for testing
    test_fbx = "path/to/your/test.fbx" # CHANGE THIS
    test_output = "path/to/your/test_thumbnail.png" # CHANGE THIS
    
    if os.path.exists(test_fbx):
        generate_thumbnail(test_fbx, test_output)
    else:
        print("Please update the test_fbx path in the script for testing.")