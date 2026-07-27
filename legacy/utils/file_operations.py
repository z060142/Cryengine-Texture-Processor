#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File Operations Utilities

This module provides utility functions for file and directory operations.
"""

import os
import shutil
import re

class FileOperations:
    """
    Class providing file and directory operation utilities.
    """
    
    @staticmethod
    def ensure_directory(directory_path):
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            True if directory exists or was created, False otherwise
        """
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating directory {directory_path}: {e}")
            return False
    
    @staticmethod
    def get_files_by_extension(directory, extensions):
        """
        Get all files in a directory with specific extensions.
        
        Args:
            directory: Directory to search
            extensions: List of extensions to include (e.g., ['.png', '.jpg'])
            
        Returns:
            List of file paths
        """
        files = []
        
        # Convert extensions to lowercase for case-insensitive comparison
        extensions = [ext.lower() for ext in extensions]
        
        # Check if directory exists
        if not os.path.exists(directory):
            return files
        
        # Walk through directory and subdirectories
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in extensions:
                    files.append(os.path.join(root, filename))
        
        return files
    
    @staticmethod
    def copy_file(source, destination, overwrite=True):
        """
        Copy a file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite destination if it exists
            
        Returns:
            True if copy was successful, False otherwise
        """
        try:
            # Check if destination exists and overwrite is not allowed
            if os.path.exists(destination) and not overwrite:
                return False
            
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            
            # Copy file
            shutil.copy2(source, destination)
            return True
        except Exception as e:
            print(f"Error copying file from {source} to {destination}: {e}")
            return False
    
    @staticmethod
    def get_relative_path(file_path, base_path):
        """
        Get a path relative to a base path.
        
        Args:
            file_path: File path to convert to relative
            base_path: Base path to make file_path relative to
            
        Returns:
            Relative path
        """
        try:
            return os.path.relpath(file_path, base_path)
        except Exception as e:
            print(f"Error getting relative path: {e}")
            return file_path
    
    @staticmethod
    def clean_filename(filename):
        """
        Clean a filename by removing invalid characters.
        
        Args:
            filename: Filename to clean
            
        Returns:
            Cleaned filename
        """
        # Replace characters that are not allowed in filenames
        # with underscores
        return re.sub(r'[\\/*?:"<>|]', '_', filename)
    
    @staticmethod
    def get_unique_filename(directory, base_filename):
        """
        Get a unique filename in a directory by adding a number if needed.
        
        Args:
            directory: Directory to check for existing files
            base_filename: Base filename to use
            
        Returns:
            Unique filename
        """
        # Split base filename into name and extension
        name, ext = os.path.splitext(base_filename)
        
        # Check if file already exists
        filename = base_filename
        counter = 1
        
        while os.path.exists(os.path.join(directory, filename)):
            # File exists, add a number and try again
            filename = f"{name}_{counter}{ext}"
            counter += 1
        
        return filename
