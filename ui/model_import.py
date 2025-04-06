#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Model Import UI Component

This module provides the UI components for importing model files and
extracting texture references from them.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from model_processing.model_loader import ModelLoader
from model_processing.texture_extractor import TextureExtractor

class ModelImportPanel:
    """
    UI panel for model import and texture extraction.
    """
    
    def __init__(self, parent):
        """
        Initialize the model import panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.model_path = None
        self.extracted_textures = []
        self.model_loader = ModelLoader()
        self.texture_extractor = TextureExtractor()
        self.texture_import_panel = None  # Will be set by main window
        
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
        
        # Import button frame
        import_frame = ttk.Frame(main_frame)
        import_frame.pack(fill=tk.X, pady=(0, 10))
        
        import_button = ttk.Button(import_frame, text="Import Model", command=self.import_model)
        import_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Create model info frame
        info_frame = ttk.LabelFrame(main_frame, text="Model Information")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Model path
        ttk.Label(info_frame, text="Path:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.path_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.path_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Model statistics
        ttk.Label(info_frame, text="Materials:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.materials_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.materials_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(info_frame, text="Textures:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.textures_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.textures_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Create texture list frame
        list_frame = ttk.LabelFrame(main_frame, text="Extracted Textures")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create texture treeview with scrollbars
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
            columns=("material", "type", "path"),
            show="headings",
            yscrollcommand=self.vsb.set,
            xscrollcommand=self.hsb.set
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbars
        self.vsb.config(command=self.tree.yview)
        self.hsb.config(command=self.tree.xview)
        
        # Configure columns
        self.tree.heading("material", text="Material")
        self.tree.heading("type", text="Type")
        self.tree.heading("path", text="Path")
        self.tree.column("material", width=100, anchor=tk.W)
        self.tree.column("type", width=100, anchor=tk.W)
        self.tree.column("path", width=300, anchor=tk.W)
        
        # Create action buttons frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        extract_button = ttk.Button(
            action_frame, 
            text="Extract Textures", 
            command=self._extract_textures,
            state=tk.DISABLED
        )
        extract_button.pack(side=tk.LEFT, padx=5)
        self.extract_button = extract_button
        
        add_to_processing_button = ttk.Button(
            action_frame, 
            text="Add to Processing", 
            command=self._add_to_processing,
            state=tk.DISABLED
        )
        add_to_processing_button.pack(side=tk.LEFT, padx=5)
        self.add_to_processing_button = add_to_processing_button
    
    def set_texture_import_panel(self, panel):
        """
        Set the texture import panel reference for adding textures.
        
        Args:
            panel: TextureImportPanel instance
        """
        self.texture_import_panel = panel
    
    def import_model(self, file_path=None):
        """
        Import a model file.
        
        Args:
            file_path: Path to model file or None to open file dialog
            
        Returns:
            Model object or None if import failed
        """
        if file_path is None:
            # Open file dialog to select model file
            file_path = filedialog.askopenfilename(
                title="Select Model File",
                filetypes=(
                    ("3D model files", "*.fbx *.obj *.dae *.3ds *.blend"),
                    ("All files", "*.*")
                )
            )
            
            if not file_path:  # User canceled
                return None
        
        self.model_path = file_path
        
        # Update UI
        self.path_var.set(file_path)
        
        # Clear existing textures
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.extracted_textures = []
        
        # Load model using ModelLoader
        try:
            # Show loading message
            self.parent.config(cursor="wait")
            self.parent.update()
            
            # Load model
            try:
                self.model = self.model_loader.load(file_path)
                
                # Restore cursor
                self.parent.config(cursor="")
                
                # Update statistics
                self.materials_var.set(str(len(self.model.get("materials", []))))
                
                # Enable extract button
                self.extract_button.config(state=tk.NORMAL)
                
                # Show success message
                messagebox.showinfo("Import Successful", f"Successfully imported {os.path.basename(file_path)}.")
                
                # Automatically extract textures
                self._extract_textures()
                
                return self.model
            except Exception as e:
                # Restore cursor
                self.parent.config(cursor="")
                
                # Show error message with more details
                error_msg = f"Error importing model: {e}\n\nIf this is related to bpy or NumPy, try reinstalling Blender or downgrading NumPy to version 1.x."
                messagebox.showerror("Import Error", error_msg)
                return None
            
        except Exception as e:
            # Restore cursor
            self.parent.config(cursor="")
            
            # Show error message
            messagebox.showerror("Import Error", f"Error importing model: {e}")
            return None
    
    def _extract_textures(self):
        """
        Extract textures from the imported model.
        """
        if not hasattr(self, 'model'):
            messagebox.showerror("Error", "No model loaded.")
            return
        
        try:
            # Show loading message
            self.parent.config(cursor="wait")
            self.parent.update()
            
            # Extract textures
            texture_refs = self.texture_extractor.extract(self.model)
            
            # Clear existing textures
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Convert TextureReference objects to dictionaries
            self.extracted_textures = [ref.as_dict() for ref in texture_refs]
            
            # Add to treeview
            for texture in self.extracted_textures:
                self.tree.insert(
                    "", 
                    "end", 
                    values=(
                        texture.get("material", "Unknown"),
                        texture.get("type", "Unknown"),
                        texture.get("path", "")
                    )
                )
            
            # Update statistics
            self.textures_var.set(str(len(self.extracted_textures)))
            
            # Enable add to processing button if textures were found
            if self.extracted_textures:
                self.add_to_processing_button.config(state=tk.NORMAL)
            else:
                self.add_to_processing_button.config(state=tk.DISABLED)
            
            # Restore cursor
            self.parent.config(cursor="")
            
            # Show success message
            messagebox.showinfo(
                "Extraction Successful", 
                f"Successfully extracted {len(self.extracted_textures)} textures."
            )
            
        except Exception as e:
            # Restore cursor
            self.parent.config(cursor="")
            
            # Show error message
            messagebox.showerror("Extraction Error", f"Error extracting textures: {e}")
    
    def _add_to_processing(self):
        """
        Add extracted textures to the texture processing list.
        """
        if not self.extracted_textures:
            messagebox.showerror("Error", "No textures to add.")
            return
        
        if not self.texture_import_panel:
            messagebox.showerror(
                "Error", 
                "Texture import panel not available. Cannot add textures to processing."
            )
            return
        
        # Get texture paths
        texture_paths = [texture["path"] for texture in self.extracted_textures if texture["path"]]
        
        # Filter to existing files only
        existing_paths = [path for path in texture_paths if os.path.exists(path)]
        
        if not existing_paths:
            messagebox.showerror("Error", "No valid texture files found.")
            return
        
        # Add to texture import panel
        imported_textures = self.texture_import_panel.import_textures(existing_paths)
        
        # Show success message
        messagebox.showinfo(
            "Added to Processing", 
            f"Successfully added {len(imported_textures)} textures to processing."
        )
