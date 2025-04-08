#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FBX Export with NumPy Compatibility Fix

This script creates a separate environment with NumPy 1.x to fix export issues
when the main environment has NumPy 2.x installed.

Usage:
python fbx_export_numpy_fix.py [model_file] [output_path] [texture_dir]
"""

import os
import sys
import subprocess
import argparse
import platform
import venv
import tempfile
import shutil
import json

def create_venv_with_numpy1(venv_path):
    """
    Create a virtual environment with NumPy 1.x installed.
    
    Args:
        venv_path: Path where to create the virtual environment
        
    Returns:
        dict: Path to the python executable and pip in the virtual environment
    """
    print(f"Creating virtual environment at: {venv_path}")
    venv.create(venv_path, with_pip=True)
    
    # Get paths to python and pip in the virtual environment
    if platform.system() == "Windows":
        python_exe = os.path.join(venv_path, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_path, "Scripts", "pip.exe")
    else:
        python_exe = os.path.join(venv_path, "bin", "python")
        pip_exe = os.path.join(venv_path, "bin", "pip")
    
    if not os.path.exists(python_exe) or not os.path.exists(pip_exe):
        raise RuntimeError(f"Failed to create virtual environment at {venv_path}")
    
    # Install NumPy 1.x
    print("Installing NumPy 1.24.4 in virtual environment...")
    try:
        subprocess.check_call([pip_exe, "install", "numpy==1.24.4"])
        print("Installed NumPy 1.24.4 successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing NumPy 1.24.4: {e}")
        raise
    
    # Install other dependencies if needed (like Blender Python API)
    
    return {"python": python_exe, "pip": pip_exe}

def create_export_script(model_file, output_path, texture_dir, script_path):
    """
    Create a temporary script to perform the FBX export.
    
    Args:
        model_file: Path to the model file to export
        output_path: Path where to save the FBX file
        texture_dir: Directory where textures are stored relative to the model
        script_path: Path where to save the temporary script
        
    Returns:
        str: Path to the created script
    """
    script_content = f"""
import os
import sys
import traceback

# First, verify NumPy version
try:
    import numpy
    print(f"NumPy version: {{numpy.__version__}}")
    if numpy.__version__.startswith("2."):
        print("ERROR: NumPy 2.x detected, but this script should be run with NumPy 1.x")
        sys.exit(1)
except ImportError:
    print("NumPy not installed. This may affect Blender Python API functionality.")

# Try to import bpy
try:
    import bpy
    print(f"Using Blender {{bpy.app.version_string}}")
except ImportError as e:
    print(f"ERROR: Failed to import bpy module. {{e}}")
    sys.exit(1)

# Settings
model_file = {repr(model_file)}
output_path = {repr(output_path)}
texture_dir = {repr(texture_dir)}

# Load the model file
bpy.ops.wm.open_mainfile(filepath=model_file)

# Get model data
model = {{"materials": bpy.data.materials}}

# Update texture paths
texture_dir_formatted = texture_dir.replace("\\\\", "/")
for material in bpy.data.materials:
    if not material.use_nodes:
        continue
    
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            # Get the original full path
            original_path = node.image.filepath
            
            # Get just the filename
            filename = os.path.basename(original_path)
            
            # Create new relative path
            relative_path = os.path.join(texture_dir_formatted, filename).replace("\\\\", "/")
            
            # Update the filepath
            node.image.filepath = relative_path
            
            print(f"Updated texture path: {{original_path}} -> {{relative_path}}")

# Ensure output directory exists
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# Set the path mode to RELATIVE for the FBX export
bpy.context.scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
bpy.context.scene.render.filepath = "//"

# Export FBX
try:
    print(f"Exporting model to {{output_path}}")
    bpy.ops.export_scene.fbx(
        filepath=output_path,
        use_selection=False,
        path_mode='RELATIVE',
        embed_textures=False
    )
    print(f"Successfully exported model to {{output_path}}")
except Exception as e:
    print(f"ERROR exporting FBX: {{e}}")
    traceback.print_exc()
    sys.exit(1)

# Exit successfully
sys.exit(0)
"""
    
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    return script_path

def run_blender_export(python_exe, script_path):
    """
    Run the export script in Blender.
    
    Args:
        python_exe: Path to the Python executable in the virtual environment
        script_path: Path to the export script
        
    Returns:
        bool: True if the export was successful, False otherwise
    """
    try:
        print("Running FBX export script...")
        # Set PYTHONPATH to include the current directory
        env = os.environ.copy()
        
        # Run the script
        result = subprocess.run(
            [python_exe, script_path],
            env=env,
            capture_output=True,
            text=True
        )
        
        # Print stdout and stderr
        print("\n----- Export Script Output -----")
        print(result.stdout)
        
        if result.stderr:
            print("\n----- Export Script Errors -----")
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running export script: {e}")
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Export FBX model with NumPy 1.x compatibility")
    parser.add_argument("model_file", help="Path to the model file to export")
    parser.add_argument("output_path", help="Path where to save the FBX file")
    parser.add_argument("texture_dir", help="Directory where textures are stored relative to the model")
    parser.add_argument("--venv-path", help="Path to create the virtual environment (optional)")
    args = parser.parse_args()
    
    # Create a temporary directory for the virtual environment if not specified
    venv_path = args.venv_path
    temp_dir = None
    
    if not venv_path:
        temp_dir = tempfile.mkdtemp(prefix="fbx_export_venv_")
        venv_path = temp_dir
    
    try:
        # Create the virtual environment
        venv_info = create_venv_with_numpy1(venv_path)
        
        # Create the export script
        script_path = os.path.join(venv_path, "export_script.py")
        create_export_script(args.model_file, args.output_path, args.texture_dir, script_path)
        
        # Run the export
        success = run_blender_export(venv_info["python"], script_path)
        
        if success:
            print("\nFBX export completed successfully.")
            print(f"FBX file saved at: {args.output_path}")
        else:
            print("\nFBX export failed. See errors above.")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        # Clean up the temporary directory if we created one
        if temp_dir and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
