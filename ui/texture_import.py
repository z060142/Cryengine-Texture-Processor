#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Import UI Component

This module provides the UI components for importing and classifying textures.
"""

import os
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.texture_manager import TextureManager, TextureGroup

class TextureImportPanel:
    """
    UI panel for texture import and classification.
    """
    
    def __init__(self, parent):
        """
        Initialize the texture import panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.texture_groups = []  # List to store grouped textures
        self.group_panel = None  # Reference to texture group panel
        self.preview_panel = None  # Reference to preview panel
        self.suffix_settings = {}  # Suffix settings
        
        # Load suffix settings
        self.load_suffix_settings()
        
        # Create frame
        self.frame = parent
        
        # Create UI elements
        self._init_ui()
        
        # Initialize texture manager
        self.texture_manager = TextureManager()
    
    def _init_ui(self):
        """
        Initialize UI components and layout.
        """
        # Create main frame with padding
        main_frame = ttk.Frame(self.frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Import button frame
        import_frame = ttk.Frame(main_frame)
        import_frame.pack(fill=tk.X, pady=(0, 10))
        
        import_button = ttk.Button(import_frame, text="Import Textures", command=self.import_textures)
        import_button.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_button = ttk.Button(import_frame, text="Clear All", command=self.clear_textures)
        clear_button.pack(side=tk.LEFT, padx=(0, 5))

        # Delete selected button (Moved here)
        self.delete_button = ttk.Button(import_frame, text="Delete Selected", command=self._delete_selected)
        self.delete_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Create texture list frame
        list_frame = ttk.LabelFrame(main_frame, text="Imported Textures")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create texture list with scrollbar
        self.texture_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED)  # Enable multiple selection
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.texture_list.yview)
        self.texture_list.configure(yscrollcommand=scrollbar.set)
        
        self.texture_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind list selection event
        self.texture_list.bind('<<ListboxSelect>>', self._on_texture_select)
        
        # Create classification options frame
        classify_frame = ttk.LabelFrame(main_frame, text="Classification Options")
        classify_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Classification controls
        ttk.Label(classify_frame, text="Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.classification_var = tk.StringVar()
        classification_combo = ttk.Combobox(classify_frame, textvariable=self.classification_var)
        classification_combo['values'] = ('Diffuse', 'Normal', 'Specular', 'Glossiness', 
                                         'Roughness', 'Displacement', 'Metallic', 'AO', 'Alpha', 'Emissive', 'SSS', 'ARM')
        classification_combo.current(0)
        classification_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Set type button
        set_button = ttk.Button(classify_frame, text="Set", command=self._set_texture_type)
        set_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Delete selected button (Definition moved to import_frame)
        # delete_button = ttk.Button(classify_frame, text="Delete Selected", command=self._delete_selected)
        # delete_button.grid(row=0, column=3, padx=5, pady=5)
    
    def set_group_panel(self, group_panel):
        """
        Set the texture group panel reference.
        
        Args:
            group_panel: TextureGroupPanel instance
        """
        self.group_panel = group_panel
    
    def set_preview_panel(self, preview_panel):
        """
        Set the preview panel reference.
        
        Args:
            preview_panel: PreviewPanel instance
        """
        self.preview_panel = preview_panel
    
    def load_suffix_settings(self):
        """
        Load suffix settings from file.
        """
        settings_file = self._get_suffix_settings_file()
        
        # Default settings
        default_settings = {
            "diffuse": ["diff", "diffuse", "albedo", "basecolor", "color", "col", "_d"],
            "normal": ["normal", "nrm", "norm", "_n"],
            "specular": ["spec", "specular", "_s"],
            "glossiness": ["gloss", "glossiness", "smoothness", "_g"],
            "roughness": ["rough", "roughness", "_r"],
            "displacement": ["disp", "displacement", "height", "bump", "_h"],
            "metallic": ["metal", "metallic", "metalness", "_m"],
            "ao": ["ao", "ambient", "occlusion"],
            "alpha": ["alpha", "opacity", "transparency", "_a"],
            "emissive": ["emissive", "emission", "glow", "_e"],
            "sss": ["sss", "subsurface"]
        }
        
        # Try to load settings from file
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    self.suffix_settings = json.load(f)
            else:
                self.suffix_settings = default_settings
        except Exception as e:
            print(f"Failed to load suffix settings: {e}")
            self.suffix_settings = default_settings
    
    def _get_suffix_settings_file(self):
        """
        Get the path to the suffix settings file.
        
        Returns:
            Path to the suffix settings file
        """
        return os.path.expanduser("~/.cryengine_texture_processor_suffixes.json")
    
    def _on_texture_select(self, event):
        """
        Handle texture selection event.
        
        Args:
            event: Event object
        """
        # Get selected indices
        selected = self.texture_list.curselection()
        if not selected:
            return
        
        # Get selected texture
        index = selected[0]
        if index < 0 or index >= len(self.all_textures):
            return
        
        texture = self.all_textures[index]
        
        # Show in preview panel if available
        if self.preview_panel:
            self.preview_panel.set_current_texture(texture)
            
    def clear_textures(self):
        """
        Clear all imported textures.
        """
        if not hasattr(self, 'all_textures') or not self.all_textures:
            return
            
        # Confirm with user
        result = messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all imported textures?")
        if not result:
            return
            
        # Clear the list
        self.texture_list.delete(0, tk.END)
        
        # Clear stored textures
        self.all_textures = []
        
        # Reset texture manager
        self.texture_manager = TextureManager()
        
        # Update texture group panel if available
        if self.group_panel:
            self.group_panel.set_texture_groups([])
            
        messagebox.showinfo("Cleared", "All textures have been cleared.")
    
    def import_textures(self, file_paths=None):
        """
        Import textures from files.
        
        Args:
            file_paths: List of file paths or None to open file dialog
            
        Returns:
            List of imported texture objects
        """
        if file_paths is None:
            # Open file dialog to select texture files
            file_paths = filedialog.askopenfilenames(
                title="Select Texture Files",
                filetypes=(
                    ("Image files", "*.jpg *.jpeg *.png *.tga *.tif *.tiff *.bmp *.hdr *.exr"),
                    ("All files", "*.*")
                )
            )
            
            if not file_paths:  # User canceled
                return []
        
        # Add textures to existing list without clearing, checking for duplicates
        textures_added = []
        duplicates_skipped = 0
        
        # Ensure self.all_textures exists
        if not hasattr(self, 'all_textures'):
            self.all_textures = []
            
        # Get existing paths for quick lookup
        existing_paths = {tex.get("path") for tex in self.all_textures if tex.get("path")}

        for path in file_paths:
            # --- Check for duplicates ---
            if path in existing_paths:
                print(f"Skipping duplicate texture: {path}")
                duplicates_skipped += 1
                continue
            # --- End Check ---

            # Add to the manager which handles classification, grouping, and duplicate checking
            texture = self.texture_manager.add_texture(path)

            if texture is None: # TextureManager indicated it's a duplicate
                print(f"Skipping duplicate texture (already managed): {path}")
                duplicates_skipped += 1
                continue # Skip the rest of the loop for this path
            
            # If texture is not None, it's a new texture
            textures_added.append(texture)
            
            # Add to list display
            self.texture_list.insert(tk.END, os.path.basename(path))
            
            # Add the original path to the set for this import session's check
            # Note: The manager now handles persistent duplicate checking via absolute paths
            existing_paths.add(path)
        
        # Store newly added textures
        self.all_textures.extend(textures_added)
        
        # Update texture group panel if available
        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())
        
        # Show success message (including skipped count)
        success_msg = f"Successfully imported {len(textures_added)} textures."
        if duplicates_skipped > 0:
            success_msg += f"\nSkipped {duplicates_skipped} duplicate textures."
        messagebox.showinfo("Import Complete", success_msg)
        
        return textures_added
    
    def _set_texture_type(self):
        """
        Set the type of the selected textures to the selected classification.
        """
        if not hasattr(self, 'all_textures') or not self.all_textures:
            messagebox.showinfo("Info", "No textures loaded.")
            return
        
        # Get selected indices
        selected_indices = self.texture_list.curselection()
        if not selected_indices:
            messagebox.showinfo("Info", "No textures selected.")
            return
        
        # Get the new type from the combobox
        new_type = self.classification_var.get().lower()
        
        # Update textures
        updated_textures = []
        for index in selected_indices:
            if index < len(self.all_textures):
                texture = self.all_textures[index]
                old_type = texture.get("type")
                
                # Update texture type
                texture["type"] = new_type
                updated_textures.append(texture)
                
                # Update the display in texture list
                filename = os.path.basename(texture.get("path", ""))
                self.texture_list.delete(index)
                self.texture_list.insert(index, filename)
        
        # Re-organize groups with the updated textures
        self.texture_manager = TextureManager()
        for texture in self.all_textures:
            self.texture_manager.add_texture(texture["path"], texture["type"])
        
        # Update texture group panel if available
        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())
        
        # Show success message
        messagebox.showinfo("Update Successful", f"Successfully updated {len(updated_textures)} textures to type '{new_type}'.")
    
    def _delete_selected(self):
        """
        Delete the selected textures from the list.
        """
        if not hasattr(self, 'all_textures') or not self.all_textures:
            messagebox.showinfo("Info", "No textures loaded.")
            return
        
        # Get selected indices in reverse order (to avoid index shifting)
        selected_indices = sorted(self.texture_list.curselection(), reverse=True)
        if not selected_indices:
            messagebox.showinfo("Info", "No textures selected.")
            return
        
        # Confirm deletion
        count = len(selected_indices)
        result = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {count} selected textures?")
        if not result:
            return
        
        # Delete from the listbox and the texture list
        deleted_paths = []
        for index in selected_indices:
            if index < len(self.all_textures):
                # Keep track of the deleted texture paths
                deleted_paths.append(self.all_textures[index]["path"])
                # Delete from the UI list
                self.texture_list.delete(index)
        
        # Create a new list without the deleted textures
        self.all_textures = [texture for texture in self.all_textures if texture["path"] not in deleted_paths]
        
        # Rebuild texture manager with the remaining textures
        self.texture_manager = TextureManager()
        for texture in self.all_textures:
            self.texture_manager.add_texture(texture["path"])
        
        # Update texture group panel if available
        if self.group_panel:
            self.group_panel.set_texture_groups(self.texture_manager.get_all_groups())
        
        # Show success message
        messagebox.showinfo("Delete Successful", f"Successfully deleted {count} textures.")
    
    def classify_textures(self, textures):
        """
        Classify textures by type based on filename and content.
        
        Args:
            textures: List of texture objects
            
        Returns:
            Dictionary mapping texture types to lists of textures
        """
        # Placeholder implementation
        classified = {
            "diffuse": [],
            "normal": [],
            "specular": [],
            "glossiness": [],
            "roughness": [],
            "displacement": [],
            "metallic": [],
            "ao": [],
            "alpha": [],
            "emissive": [],
            "sss": [],
            "unknown": []
        }
        
        # Classification based on filename using suffix settings
        for texture in textures:
            filename = texture["filename"].lower()
            texture_type = "unknown"
            
            # Check each texture type for matching suffixes
            for type_name, suffixes in self.suffix_settings.items():
                for suffix in suffixes:
                    # Ensure the suffix is surrounded by characters that aren't letters or numbers
                    # This helps prevent partial matches (e.g., 'color' shouldn't match 'colorful')
                    pattern = r'[^a-z0-9]' + re.escape(suffix.lower()) + r'([^a-z0-9]|$)'
                    if re.search(pattern, filename):
                        texture_type = type_name
                        break
                if texture_type != "unknown":
                    break
            
            # Store the classified type in the texture
            texture["type"] = texture_type
            
            # Add to appropriate list
            if texture_type in classified:
                classified[texture_type].append(texture)
            else:
                classified["unknown"].append(texture)
        
        return classified
    
    def group_textures(self, classified_textures):
        """
        Group related textures that belong to the same material.
        
        Args:
            classified_textures: Dictionary mapping texture types to texture lists
            
        Returns:
            List of texture groups, each containing related textures
        """
        # Get all textures
        all_textures = []
        for texture_list in classified_textures.values():
            all_textures.extend(texture_list)
        
        # Group by base name (removing ALL suffixes)
        base_names = {}
        
        # Create a pattern to match any suffix
        all_suffixes = []
        for suffixes in self.suffix_settings.values():
            all_suffixes.extend(suffixes)
        
        # Sort suffixes by length (longest first) to avoid partial matches
        all_suffixes.sort(key=len, reverse=True)
        
        # Add common resolution suffixes
        resolution_suffixes = ["1k", "2k", "4k", "8k", "512", "1024", "2048", "4096", "8192"]
        all_suffixes.extend(resolution_suffixes)
        
        for texture in all_textures:
            filename = texture["filename"]
            
            # Remove extension
            base_name = os.path.splitext(filename)[0]
            
            # Remove all recognized suffixes
            original_base_name = base_name
            changed = True
            while changed:
                changed = False
                for suffix in all_suffixes:
                    # Pattern to match suffix at the end or before an underscore or hyphen
                    pattern = f"(.+?)[-_]{re.escape(suffix)}([-_]|$)"
                    match = re.match(pattern, base_name, re.IGNORECASE)
                    if match:
                        base_name = match.group(1)
                        changed = True
                        break
            
            # If no suffixes were found, use the original name
            if base_name == original_base_name:
                # Try another approach - look for the last underscore or hyphen
                last_separator = max(base_name.rfind('_'), base_name.rfind('-'))
                if last_separator > 0:
                    base_name = base_name[:last_separator]
            
            # Add to base name dictionary
            if base_name not in base_names:
                base_names[base_name] = []
            
            base_names[base_name].append(texture)
        
        # Create texture groups
        groups = []
        for base_name, textures in base_names.items():
            group = {
                "base_name": base_name,
                "textures": textures
            }
            groups.append(group)
        
        return groups
