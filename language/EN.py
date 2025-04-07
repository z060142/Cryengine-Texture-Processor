#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
English Language Module

This module contains the English language dictionary for UI text.
"""

# Language name for display in UI
LANGUAGE_NAME = "English"

LANGUAGE_DICT = {
    "app": {
        "title": "CryEngine Texture Processor",
        "ready": "Ready"
    },
    "menu": {
        "file": {
            "title": "File",
            "import_textures": "Import Textures...",
            "import_model": "Import Model...",
            "export": "Export...",
            "exit": "Exit"
        },
        "edit": {
            "title": "Edit",
            "suffix_settings": "Suffix Settings...",
            "preferences": "Preferences...",
            "language": "Language"
        },
        "help": {
            "title": "Help",
            "about": "About"
        }
    },
    "import": {
        "texture": {
            "title": "Texture Import",
            "button": "Import Textures",
            "list_title": "Imported Textures",
            "classification_title": "Classification Options",
            "default_classification": "Default Classification:",
            "reclassify": "Re-Classify",
            "import_success": "Successfully imported {0} textures."
        },
        "model": {
            "title": "Model Import",
            "button": "Import Model",
            "info_title": "Model Information",
            "path": "Path:",
            "materials": "Materials:",
            "textures": "Textures:",
            "list_title": "Extracted Textures",
            "extract_button": "Extract Textures",
            "update_button": "Update Materials",
            "extract_success": "Successfully extracted {0} textures.",
            "update_success": "Successfully updated materials.",
            "import_success": "Successfully imported {0}."
        }
    },
    "preview": {
        "title": "Preview",
        "texture": "Texture:",
        "type": "Type:",
        "view": "View:",
        "original": "Original",
        "processed": "Processed",
        "no_texture": "No texture selected"
    },
    "groups": {
        "title": "Detected Texture Groups",
        "details_title": "Group Details",
        "base_name": "Base Name:",
        "texture_types": "Texture Types:"
    },
    "export": {
        "title": "Export Settings",
        "texture_output_directory": "Texture Output Directory", # Renamed
        "model_output_directory": "Model Output Directory",   # Added
        "select_texture_directory": "Select Texture Output Directory", # Renamed
        "select_model_directory": "Select Model Output Directory",   # Added
        "no_directory_selected": "No directory selected. Will prompt when exporting.", # Added generic version
        "directory_valid": "Directory is valid and writable.", # Added generic version
        "directory_not_writable": "Warning: Directory is not writable!", # Added generic version
        "directory_not_exist": "Directory does not exist. It will be created when exporting.", # Added generic version
        "create_texture_dir_error": "Failed to create texture output directory: {0}", # Renamed
        "create_model_dir_error": "Failed to create model output directory: {0}",     # Added
        "diff_format": "Diffuse Format:",
        "normal_flip": "Flip Normal Map Green Channel",
        "spec_generate": "Generate Missing Specular Maps",
        "output_format": "Output Format:",
        "output_resolution": "Output Resolution:",
        "generate_cry_dds": "Generate CryEngine DDS",
        "types_title": "Output Texture Types",
        "diff": "Diffuse (_diff)",
        "spec": "Specular (_spec)",
        "ddna": "Normal & Gloss (_ddna)",
        "displ": "Displacement (_displ)",
        "emissive": "Emissive (_emissive)",
        "sss": "Subsurface Scattering (_sss)",
        "export_textures": "Export Textures", # Key changed slightly for clarity
        "export_model": "Export Model", # Added
        "save_settings": "Save Settings",
        "settings_saved_title": "Settings Saved", # Added title key
        "settings_saved_message": "Export settings have been saved.", # Added message key
        "error_no_texture_dir": "Texture output directory is not set.", # Renamed
        "error_no_model_dir": "Model output directory is not set.", # Added
        "warning_no_groups": "No texture groups to export.",
        "export_preview_title": "Export Preview",
        "preview_message": "Would export {0} texture groups with the following settings:", # Added key
        "preview_texture_dir": "Texture Output Directory: {0}", # Added key
        "preview_diff": "Diffuse Format: {0}", # Added key
        "preview_flip": "Flip Normal Green Channel: {0}", # Added key
        "preview_spec": "Generate Missing Specular: {0}", # Added key
        "preview_metallic": "Convert Metallic to Albedo+Reflection: {0}", # Added key
        "preview_format": "Output Format: {0}", # Added key
        "preview_resolution": "Output Resolution: {0}", # Added key
        "preview_types": "Enabled Texture Types: {0}", # Added key
        "model_export_not_implemented": "Model export (including MTL generation) is planned but not yet fully implemented. Selected Model Directory: {0}", # Added
        "no_model_dir": "Please select a Model Output Directory first.", # Added warning
        "not_implemented": "Not Implemented", # Added generic key
        "batch_not_available": "Batch processing is not available yet." # Added key
    },
    "suffix_settings": {
        "title": "Texture Suffix Settings",
        "instruction": "Configure suffixes for each texture type. Separate multiple suffixes with commas.",
        "save": "Save",
        "cancel": "Cancel",
        "diffuse": "Diffuse/Albedo",
        "normal": "Normal Maps",
        "specular": "Specular Maps",
        "glossiness": "Glossiness Maps",
        "roughness": "Roughness Maps",
        "displacement": "Displacement/Height Maps",
        "metallic": "Metallic Maps",
        "ao": "Ambient Occlusion Maps",
        "alpha": "Alpha/Transparency Maps",
        "emissive": "Emissive/Glow Maps",
        "sss": "Subsurface Scattering Maps",
        "success": "Suffix settings have been updated."
    },
    "about": {
        "title": "About",
        "content": "CryEngine Texture Processor\n\nA tool for processing textures for use in CryEngine.\n\nVersion: 0.1"
    },
    "errors": {
        "no_model": "No model loaded.",
        "no_model_or_textures": "No model or textures loaded.",
        "suffix_load_error": "Failed to load suffix settings: {0}",
        "suffix_save_error": "Failed to save suffix settings: {0}"
    },
    "language": {
        "title": "Language",
        "changed": "Language changed to {0}. Some changes will take effect immediately, but for a complete update, please restart the application."
    },
    "status": {
        "preparing": "Preparing for batch processing...",
        "processing_cancelled": "Processing cancelled",
        "processing_complete": "Processing complete. Processed {0} texture groups.",
        "generating_dds": "Generating DDS files..."
    },
    "progress": {
        "title": "Processing Textures",
        "preparing": "Preparing...",
        "processing": "Processing Textures",
        "complete": "Operation complete",
        "failed": "Operation failed",
        "generating_dds": "Generating CryEngine DDS files"
    },
    "button": {
        "ok": "OK",
        "cancel": "Cancel",
        "close": "Close",
        "browse": "Browse..."
    },
    "file": {
        "exe": "Executable files",
        "all": "All files"
    },
    "preferences": {
        "title": "Preferences",
        "cry_integration": "CryEngine Integration",
        "rc_exe": "RC.exe Path:",
        "select_rc_exe": "Select RC.exe",
        "rc_not_selected": "RC.exe not selected",
        "rc_not_found": "RC.exe file not found",
        "rc_not_file": "Selected path is not a file",
        "rc_not_executable": "Selected file is not executable",
        "rc_not_exe": "Selected file is not an .exe file",
        "rc_valid": "RC.exe path is valid"
    }
}
