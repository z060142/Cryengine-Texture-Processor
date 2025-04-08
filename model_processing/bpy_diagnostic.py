#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Blender Python API (bpy) Diagnostic Tool

This script checks if the Blender Python API is available and provides
detailed information about the environment to help diagnose issues.
"""

import os
import sys
import platform
import traceback

def check_bpy():
    """
    Check if Blender Python API (bpy) is available and provide detailed diagnostics.
    """
    print("-" * 80)
    print("Blender Python API (bpy) Diagnostic Tool")
    print("-" * 80)
    
    # Print system information
    print(f"Operating System: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python Version: {platform.python_version()}")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Path: {sys.path}")
    print("-" * 80)
    
    # Check if bpy is installed
    try:
        import bpy
        print("SUCCESS: bpy module successfully imported!")
        print(f"bpy Version: {bpy.app.version_string}")
        print(f"Blender Version: {bpy.app.version}")
        print(f"Blender Path: {bpy.app.binary_path}")
        print("-" * 80)
        print("Blender Python API (bpy) is available and can be used for FBX export.")
        return True
    except ImportError as e:
        print(f"ERROR: Failed to import bpy module. {e}")
        print("-" * 80)
        print("Common causes for bpy import failures:")
        print("1. Blender is not installed on this system")
        print("2. The Python environment doesn't have access to the Blender Python modules")
        print("3. Version incompatibility between Python and Blender")
        print("-" * 80)
        print("Potential solutions:")
        print("1. Install Blender if not already installed")
        print("2. Add Blender's Python modules to your Python path")
        print("   - Windows: Add paths like C:\\Program Files\\Blender Foundation\\Blender X.XX\\X.XX\\python\\lib")
        print("   - macOS: Add paths like /Applications/Blender.app/Contents/Resources/X.XX/python/lib")
        print("   - Linux: Add paths like /usr/share/blender/X.XX/python/lib")
        print("3. Run this script using Blender's Python instead of system Python:")
        print("   blender --background --python bpy_diagnostic.py")
        print("-" * 80)
        return False
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        traceback.print_exc()
        print("-" * 80)
        return False

if __name__ == "__main__":
    check_bpy()
