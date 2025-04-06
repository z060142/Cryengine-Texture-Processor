#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration Manager

This module provides functionality for managing application configuration.
"""

import os
import json

class ConfigManager:
    """
    Class for managing application configuration.
    """
    
    def __init__(self, config_file=None):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to the configuration file or None to use default
        """
        self.config_file = config_file or self._get_default_config_path()
        self.config = self._load_config()
    
    def _get_default_config_path(self):
        """
        Get the default configuration file path.
        
        Returns:
            Default configuration file path
        """
        # This is a placeholder for the actual implementation
        # In reality, this would use appropriate directories based on OS
        
        return os.path.expanduser("~/.cryengine_texture_processor.json")
    
    def _load_config(self):
        """
        Load configuration from file.
        
        Returns:
            Loaded configuration dictionary
        """
        # Start with default configuration
        config = self._get_default_config()
        
        # Try to load from file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                
                # Update default config with loaded values
                config.update(loaded_config)
            except Exception as e:
                print(f"Error loading configuration from {self.config_file}: {e}")
        
        return config
    
    def _get_default_config(self):
        """
        Get default configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "output_directory": "",
            "diff_format": "albedo",
            "normal_flip_green": False,
            "generate_missing_spec": True,
            "output_format": "tif",
            "output_resolution": "original",
            "recent_files": [],
            "recent_directories": [],
            "rc_exe_path": "",
            "generate_cry_dds": False
        }
    
    def save_config(self):
        """
        Save configuration to file.
        
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Save to file
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            
            return True
        except Exception as e:
            print(f"Error saving configuration to {self.config_file}: {e}")
            return False
    
    def get(self, key, default=None):
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key, value):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
    
    def add_recent_file(self, file_path, max_recent=10):
        """
        Add a file to the recent files list.
        
        Args:
            file_path: File path to add
            max_recent: Maximum number of recent files to keep
        """
        # Get current recent files
        recent_files = self.config.get("recent_files", [])
        
        # Remove if already in list
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Add to beginning of list
        recent_files.insert(0, file_path)
        
        # Trim to max_recent
        recent_files = recent_files[:max_recent]
        
        # Update config
        self.config["recent_files"] = recent_files
    
    def add_recent_directory(self, directory, max_recent=10):
        """
        Add a directory to the recent directories list.
        
        Args:
            directory: Directory path to add
            max_recent: Maximum number of recent directories to keep
        """
        # Get current recent directories
        recent_dirs = self.config.get("recent_directories", [])
        
        # Remove if already in list
        if directory in recent_dirs:
            recent_dirs.remove(directory)
        
        # Add to beginning of list
        recent_dirs.insert(0, directory)
        
        # Trim to max_recent
        recent_dirs = recent_dirs[:max_recent]
        
        # Update config
        self.config["recent_directories"] = recent_dirs
