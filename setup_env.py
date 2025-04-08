#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Environment Setup Script for CryEngine Texture Processor

This script helps set up the correct Python environment for running the application,
especially dealing with NumPy version compatibility issues.
"""

import os
import sys
import subprocess
import platform

def main():
    """
    Set up the Python environment with correct dependencies.
    """
    print("=" * 80)
    print("CryEngine Texture Processor - Environment Setup")
    print("=" * 80)
    print("\nThis script will set up a Python virtual environment with the correct dependencies.")
    print("It will help resolve NumPy version compatibility issues with Blender Python API (bpy).")

    # Get Python version
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"\nCurrent Python version: {python_version}")

    # Detect OS
    os_name = platform.system()
    print(f"Operating System: {os_name}")

    # Check if pip is installed
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        print("\nERROR: pip is not installed. Please install pip first.")
        input("\nPress Enter to exit...")
        return

    # Ask for confirmation
    response = input("\nDo you want to create a virtual environment and install dependencies? (y/n): ")
    if response.lower() != 'y':
        print("Setup canceled.")
        return

    # Create a venv directory if it doesn't exist
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")
    
    if os.path.exists(venv_dir):
        response = input(f"\nVirtual environment directory already exists at {venv_dir}. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Setup canceled.")
            return
        
    print(f"\nCreating virtual environment in {venv_dir}...")
    
    try:
        # Create virtual environment
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        print("Virtual environment created successfully.")
        
        # Determine the Python executable in the virtual environment
        if os_name == "Windows":
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
            # pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe") # Not used
        else:
            python_exe = os.path.join(venv_dir, "bin", "python")
            # pip_exe = os.path.join(venv_dir, "bin", "pip") # Not used
        
        # Upgrade pip
        print("\nUpgrading pip...")
        subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install dependencies
        print("\nInstalling dependencies...")
        # Install older NumPy version for compatibility with bpy
        subprocess.check_call([python_exe, "-m", "pip", "install", "numpy<2.0.0"])
        
        # Install other dependencies
        dependencies = [
            "pillow",       # PIL for image processing
            "wand",         # ImageMagick for image processing
            "bpy",     # For model importing (if needed)
        ]
        
        for dep in dependencies:
            try:
                print(f"Installing {dep}...")
                subprocess.check_call([python_exe, "-m", "pip", "install", dep])
            except subprocess.CalledProcessError:
                print(f"WARNING: Failed to install {dep}, it may not be available via pip.")
        
        # Create activation script
        if os_name == "Windows":
            activate_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.bat")
            with open(activate_script, 'w') as f:
                f.write(f'@echo off\n')
                f.write(f'echo Activating virtual environment...\n')
                f.write(f'call "{os.path.join(venv_dir, "Scripts", "activate.bat")}"\n')
                f.write(f'python main.py\n')
            
            print(f"\nCreated activation script: {activate_script}")
            print("You can now run the application using this script.")
        else:
            activate_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.sh")
            with open(activate_script, 'w') as f:
                f.write(f'#!/bin/bash\n')
                f.write(f'echo "Activating virtual environment..."\n')
                f.write(f'source "{os.path.join(venv_dir, "bin", "activate")}"\n')
                f.write(f'python main.py\n')
            
            # Make the script executable
            os.chmod(activate_script, 0o755)
            
            print(f"\nCreated activation script: {activate_script}")
            print("You can now run the application using this script.")
        
        print("\nEnvironment setup completed successfully!")
        print(f"NumPy version 1.x has been installed to ensure compatibility with Blender Python API.")
        
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Setup failed: {str(e)}")
    except Exception as e:
        print(f"\nERROR: {str(e)}")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    main()
