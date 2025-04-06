#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Group Panel

This module provides UI components for displaying and managing texture groups.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

class TextureGroupPanel:
    """
    UI panel for displaying and managing texture groups.
    """
    
    def __init__(self, parent):
        """
        Initialize the texture group panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.texture_groups = []  # List to store grouped textures
        self.preview_panel = None
        
        # Create frame
        self.frame = parent
        
        # Create UI elements
        self._init_ui()
    
    def _init_ui(self):
        """
        Initialize UI components and layout.
        """
        # Create main frame with padding
        main_frame = ttk.Frame(self.frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create group list frame
        list_frame = ttk.LabelFrame(main_frame, text="Detected Texture Groups")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for texture groups with scrollbars
        self.tree_frame = ttk.Frame(list_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create vertical scrollbar
        self.vsb = ttk.Scrollbar(self.tree_frame, orient="vertical")
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create horizontal scrollbar
        self.hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal")
        self.hsb.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create treeview
        self.tree = ttk.Treeview(
            self.tree_frame, 
            columns=("base_name", "textures", "unknown"),
            show="headings",
            yscrollcommand=self.vsb.set,
            xscrollcommand=self.hsb.set
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        self.vsb.config(command=self.tree.yview)
        self.hsb.config(command=self.tree.xview)
        
        # Configure columns
        self.tree.heading("base_name", text="Base Name")
        self.tree.heading("textures", text="Detected Textures")
        self.tree.heading("unknown", text="Unknown Textures")
        self.tree.column("base_name", width=200, anchor=tk.W)
        self.tree.column("textures", width=300, anchor=tk.W)
        self.tree.column("unknown", width=200, anchor=tk.W)
        
        # Bind double click event
        self.tree.bind("<Double-1>", self._on_group_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_group_select)
        
        # Create group details frame
        details_frame = ttk.LabelFrame(main_frame, text="Group Details")
        details_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Group details
        ttk.Label(details_frame, text="Base Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.base_name_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.base_name_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(details_frame, text="Texture Types:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.types_var = tk.StringVar()
        ttk.Label(details_frame, textvariable=self.types_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Create unknowns frame for unidentified textures
        unknown_frame = ttk.LabelFrame(main_frame, text="Unknown Textures")
        unknown_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Unknown textures list
        self.unknown_list = tk.Listbox(unknown_frame, height=4)
        unknown_scrollbar = ttk.Scrollbar(unknown_frame, orient="vertical", command=self.unknown_list.yview)
        self.unknown_list.configure(yscrollcommand=unknown_scrollbar.set)
        
        self.unknown_list.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        unknown_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Unknown texture classification frame
        classify_frame = ttk.Frame(unknown_frame)
        classify_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Type selection for unknown textures
        ttk.Label(classify_frame, text="Set Type:").pack(side=tk.LEFT, padx=5)
        
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(classify_frame, textvariable=self.type_var, width=15)
        type_combo['values'] = ('diffuse', 'normal', 'specular', 'glossiness', 'roughness', 
                                'displacement', 'metallic', 'ao', 'alpha', 'emissive', 'sss', 'arm')
        type_combo.pack(side=tk.LEFT, padx=5)
        
        # Classify button
        classify_button = ttk.Button(classify_frame, text="Set Type", command=self._set_texture_type)
        classify_button.pack(side=tk.LEFT, padx=5)
        
        # Bind selection events
        self.unknown_list.bind('<<ListboxSelect>>', self._on_unknown_select)
    
    def set_preview_panel(self, preview_panel):
        """
        Set the preview panel for texture display.
        
        Args:
            preview_panel: Preview panel instance
        """
        self.preview_panel = preview_panel
    
    def _on_group_select(self, event):
        """
        Handle group selection event.
        
        Args:
            event: Event object
        """
        # Get selected item
        selected_items = self.tree.selection()
        if not selected_items:
            return
        
        # Get group data from selection
        item = selected_items[0]
        group_idx = int(self.tree.item(item, "text"))
        if group_idx < 0 or group_idx >= len(self.texture_groups):
            return
            
        group = self.texture_groups[group_idx]
        
        # Update details based on group type
        if hasattr(group, 'base_name'):
            # It's a TextureGroup object
            self.base_name_var.set(group.base_name)
            
            # Get texture types in group
            types = []
            for texture_type, texture in group.textures.items():
                if texture_type != "unknown" and texture is not None:
                    types.append(texture_type)
                    
            self.types_var.set(", ".join(types))
            
            # Update unknown textures list
            self.unknown_list.delete(0, tk.END)
            
            unknown_textures = group.textures.get("unknown", [])
            for i, texture in enumerate(unknown_textures):
                self.unknown_list.insert(tk.END, os.path.basename(texture.get("path", f"Unknown {i}")))
                # Set background color to highlight unknown textures
                # Using tags for coloring in Tkinter
                # Note: In a real implementation, would need to handle tags properly
        else:
            # It's a dictionary (for compatibility)
            self.base_name_var.set(group.get("base_name", ""))
            
            types = [texture.get("type", "unknown") for texture in group.get("textures", [])]
            self.types_var.set(", ".join(types))
            
            # Clear unknown list for dictionary-based groups
            self.unknown_list.delete(0, tk.END)
    
    def _on_group_double_click(self, event):
        """
        Handle group double-click event.
        
        Args:
            event: Event object
        """
        # Get selected item
        selected_items = self.tree.selection()
        if not selected_items:
            return
        
        # Get group data from selection
        item = selected_items[0]
        group_idx = int(self.tree.item(item, "text"))
        if group_idx < 0 or group_idx >= len(self.texture_groups):
            return
            
        group = self.texture_groups[group_idx]
        
        # Collect all textures from the group based on group type
        all_textures = []
        
        if hasattr(group, 'base_name'):
            # It's a TextureGroup object
            for texture_type, texture in group.textures.items():
                if texture_type != "unknown" and texture is not None:
                    all_textures.append(texture)
                elif texture_type == "unknown":
                    all_textures.extend(texture)  # Unknown is a list
        else:
            # It's a dictionary (for compatibility)
            all_textures = group.get("textures", [])
        
        # Show group textures in preview panel if available
        if self.preview_panel:
            self.preview_panel.set_textures(all_textures)
    
    def set_texture_groups(self, groups):
        """
        Set texture groups to display.
        
        Args:
            groups: List of texture group objects
        """
        self.texture_groups = groups
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add groups to treeview
        for i, group in enumerate(groups):
            # Handle both TextureGroup objects and dictionaries
            if hasattr(group, 'base_name'):
                # It's a TextureGroup object
                base_name = group.base_name
                
                # Get texture types (excluding unknown)
                texture_types = []
                for texture_type, texture in group.textures.items():
                    if texture_type != "unknown" and texture is not None:
                        texture_types.append(texture_type)
                
                # Get unknown textures
                unknown_textures = group.textures.get("unknown", [])
                unknown_summary = "" if not unknown_textures else f"{len(unknown_textures)} unknown"
            else:
                # It's still a dictionary (for compatibility)
                base_name = group.get("base_name", "Unknown")
                textures = group.get("textures", [])
                texture_types = [texture.get("type", "unknown") for texture in textures]
                unknown_summary = ""
            
            # Add to treeview with highlighting for groups with unknown textures
            item = self.tree.insert(
                "", 
                "end", 
                text=str(i),  # Store index as text for retrieval
                values=(base_name, ", ".join(texture_types), unknown_summary)
            )
            
            # If there are unknown textures, highlight the row
            if unknown_textures:
                # In a full implementation, would use tags to highlight the row
                pass
    
    def _on_unknown_select(self, event):
        """
        Handle unknown texture selection event.
        
        Args:
            event: Event object
        """
        # Get selected indices
        selected_items = self.unknown_list.curselection()
        if not selected_items:
            return
            
        # Set a default texture type based on filename pattern
        current_group_idx = self._get_current_group_index()
        if current_group_idx is None:
            return
            
        group = self.texture_groups[current_group_idx]
        unknown_textures = group.textures.get("unknown", [])
        
        if selected_items[0] < len(unknown_textures):
            texture = unknown_textures[selected_items[0]]
            filename = os.path.basename(texture.get("path", "")).lower()
            
            # Simple pattern matching to suggest texture type
            texture_type = "diffuse"  # Default suggestion
            
            if "_n" in filename or "normal" in filename or "norm" in filename:
                texture_type = "normal"
            elif "_s" in filename or "spec" in filename:
                texture_type = "specular"
            elif "_g" in filename or "gloss" in filename:
                texture_type = "glossiness"
            elif "_r" in filename or "rough" in filename:
                texture_type = "roughness"
            elif "_h" in filename or "height" in filename or "disp" in filename:
                texture_type = "displacement"
            elif "_m" in filename or "metal" in filename:
                texture_type = "metallic"
            elif "_ao" in filename or "ambient" in filename or "occl" in filename:
                texture_type = "ao"
            elif "_e" in filename or "emiss" in filename or "glow" in filename:
                texture_type = "emissive"
            elif "_sss" in filename or "subsurf" in filename:
                texture_type = "sss"
            elif "_arm" in filename:
                texture_type = "arm"
            
            # Set the suggested type in the combobox
            self.type_var.set(texture_type)
        
    def _set_texture_type(self):
        """
        Set the type of the selected unknown texture.
        """
        # Get selected texture
        selected_items = self.unknown_list.curselection()
        if not selected_items:
            return
            
        # Get current group
        current_group_idx = self._get_current_group_index()
        if current_group_idx is None:
            return
            
        group = self.texture_groups[current_group_idx]
        if not hasattr(group, 'textures'):
            return
            
        unknown_textures = group.textures.get("unknown", [])
        
        if selected_items[0] < len(unknown_textures):
            texture = unknown_textures[selected_items[0]]
            new_type = self.type_var.get()
            
            # Directly update the texture in the current group
            # First, remove from unknown list
            unknown_textures.pop(selected_items[0])
            
            # Update texture type
            texture["type"] = new_type
            texture["is_unknown"] = False
            
            # Add to the appropriate type in the group
            if new_type in group.textures:
                # If there's already a texture of this type, replace it
                group.textures[new_type] = texture
            
            # Refresh the display
            self.unknown_list.delete(selected_items[0])
            
            # Update the treeview
            self._refresh_group_display(current_group_idx)
    
    def _get_current_group_index(self):
        """
        Get the index of the currently selected group.
        
        Returns:
            Group index or None if no group is selected
        """
        selected_items = self.tree.selection()
        if not selected_items:
            return None
            
        item = selected_items[0]
        group_idx = int(self.tree.item(item, "text"))
        if group_idx < 0 or group_idx >= len(self.texture_groups):
            return None
            
        return group_idx
    
    def _refresh_group_display(self, group_idx):
        """
        Refresh the display for a specific group.
        
        Args:
            group_idx: Index of the group to refresh
        """
        if 0 <= group_idx < len(self.texture_groups):
            group = self.texture_groups[group_idx]
            
            # Find the item in the treeview
            for item in self.tree.get_children():
                if int(self.tree.item(item, "text")) == group_idx:
                    # Update the display values based on group type
                    if hasattr(group, 'base_name'):
                        # It's a TextureGroup object
                        texture_types = []
                        for texture_type, texture in group.textures.items():
                            if texture_type != "unknown" and texture is not None:
                                texture_types.append(texture_type)
                        
                        unknown_textures = group.textures.get("unknown", [])
                        unknown_summary = "" if not unknown_textures else f"{len(unknown_textures)} unknown"
                        
                        self.tree.item(item, values=(group.base_name, ", ".join(texture_types), unknown_summary))
                    else:
                        # It's a dictionary (for compatibility)
                        base_name = group.get("base_name", "Unknown")
                        textures = group.get("textures", [])
                        type_summary = ", ".join([t.get("type", "unknown") for t in textures])
                        
                        self.tree.item(item, values=(base_name, type_summary, ""))
                    break
    
    def get_texture_groups(self):
        """
        Get the current texture groups.
        
        Returns:
            List of texture group dictionaries
        """
        return self.texture_groups
