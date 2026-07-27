#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Language Manager

This module provides functionality for managing UI language and localization.
"""

import os
import importlib
from utils.config_manager import ConfigManager

class LanguageManager:
    """
    Class for managing UI languages and translations.
    """
    
    def __init__(self):
        """
        Initialize the language manager.
        """
        # Load config
        self.config_manager = ConfigManager()
        
        # Default language
        self.current_language = self.config_manager.get("language", "EN")
        self.language_dict = {}
        self.available_languages = []
        self.language_names = {}
        
        # Load languages
        self._load_available_languages()
        self.load_language(self.current_language)
    
    def _load_available_languages(self):
        """
        Load list of available language files.
        """
        # Get path to language files
        language_dir = self._get_language_dir()
        
        # Check language directory
        if not os.path.exists(language_dir):
            return
        
        # Get all Python modules in language directory
        self.available_languages = []
        self.language_names = {}
        
        for file_name in os.listdir(language_dir):
            if file_name.endswith('.py') and not file_name.startswith('__'):
                language_code = os.path.splitext(file_name)[0]
                self.available_languages.append(language_code)
                
                # Try to load language name
                try:
                    module_name = f"language.{language_code}"
                    language_module = importlib.import_module(module_name)
                    
                    if hasattr(language_module, 'LANGUAGE_NAME'):
                        self.language_names[language_code] = language_module.LANGUAGE_NAME
                    else:
                        self.language_names[language_code] = language_code
                except Exception:
                    self.language_names[language_code] = language_code
        
        # Ensure we always have English
        if "EN" not in self.available_languages and os.path.exists(os.path.join(language_dir, "EN.py")):
            self.available_languages.append("EN")
            self.language_names["EN"] = "English"
    
    def _get_language_dir(self):
        """
        Get the path to the language directory.
        
        Returns:
            Path to the language directory
        """
        # Get directory of this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Return language directory
        return current_dir
    
    def load_language(self, language_code):
        """
        Load a language file.
        
        Args:
            language_code: Language code to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to import the language module
            module_name = f"language.{language_code}"
            language_module = importlib.import_module(module_name)
            
            # Get language dictionary from module
            if hasattr(language_module, 'LANGUAGE_DICT'):
                self.language_dict = language_module.LANGUAGE_DICT
                self.current_language = language_code
                
                # Save language preference to config
                self.config_manager.set("language", language_code)
                self.config_manager.save_config()
                
                return True
            else:
                print(f"Language module {module_name} does not contain LANGUAGE_DICT")
                # If failed to load, try to load English as fallback
                if language_code != "EN":
                    return self.load_language("EN")
                return False
        except Exception as e:
            print(f"Error loading language module: {e}")
            # If failed to load, try to load English as fallback
            if language_code != "EN":
                return self.load_language("EN")
            return False
    
    def get_text(self, key, default=None):
        """
        Get translated text for a key.
        
        Args:
            key: Text key
            default: Default text if key not found
            
        Returns:
            Translated text
        """
        # Handle nested keys (e.g., "menu.file.open")
        if "." in key:
            parts = key.split(".")
            current = self.language_dict
            
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default if default is not None else key
            
            return current
        
        # Handle direct keys
        return self.language_dict.get(key, default if default is not None else key)
    
    def get_current_language(self):
        """
        Get the current language code.
        
        Returns:
            Current language code
        """
        return self.current_language
    
    def get_language_name(self, language_code=None):
        """
        Get the display name of a language.
        
        Args:
            language_code: Language code or None for current language
            
        Returns:
            Language display name
        """
        if language_code is None:
            language_code = self.current_language
            
        return self.language_names.get(language_code, language_code)
    
    def get_available_languages(self):
        """
        Get list of available languages.
        
        Returns:
            List of available language codes
        """
        return self.available_languages
    
    def get_language_display_names(self):
        """
        Get dictionary mapping language codes to display names.
        
        Returns:
            Dictionary of language codes to display names
        """
        return self.language_names


# Create global instance
_instance = None

def get_instance():
    """
    Get singleton instance of LanguageManager.
    
    Returns:
        LanguageManager instance
    """
    global _instance
    if _instance is None:
        _instance = LanguageManager()
    return _instance

def get_text(key, default=None):
    """
    Convenience function to get translated text.
    
    Args:
        key: Text key
        default: Default text if key not found
        
    Returns:
        Translated text
    """
    return get_instance().get_text(key, default)

def change_language(language_code):
    """
    Convenience function to change language.
    
    Args:
        language_code: Language code
        
    Returns:
        True if successful, False otherwise
    """
    return get_instance().load_language(language_code)
