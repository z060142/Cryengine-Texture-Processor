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
        self.last_model_path = None # Store path of the last processed model
        self.last_extracted_textures = [] # Store textures from the last processed model
        self.imported_models_info = [] # List to store info about all imported models
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
        
        import_button = ttk.Button(import_frame, text="Import Model(s)", command=self.import_model) # Changed button text slightly
        import_button.pack(side=tk.LEFT, padx=(0, 5))

        # --- Add Imported Models List Frame ---
        models_list_frame = ttk.LabelFrame(main_frame, text="Imported Models")
        models_list_frame.pack(fill=tk.X, padx=5, pady=(10, 5)) # Add some padding

        self.models_listbox = tk.Listbox(models_list_frame, height=5) # Limit initial height
        models_scrollbar_y = ttk.Scrollbar(models_list_frame, orient="vertical", command=self.models_listbox.yview)
        models_scrollbar_x = ttk.Scrollbar(models_list_frame, orient="horizontal", command=self.models_listbox.xview)
        self.models_listbox.configure(yscrollcommand=models_scrollbar_y.set, xscrollcommand=models_scrollbar_x.set)
        # --- Bind selection event ---
        self.models_listbox.bind('<<ListboxSelect>>', self._on_model_select)
        # --- End Bind ---

        models_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        models_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.models_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # --- End Imported Models List Frame ---

        # Create model info frame (Now shows info for the *selected* model)
        info_frame = ttk.LabelFrame(main_frame, text="Selected Model Information") # Changed title
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
    
    def import_model(self, initial_file_paths=None): # Renamed parameter
        """
        Import one or more model files.
        
        Args:
            initial_file_paths: List of paths to model files or None to open file dialog
            
        Returns:
            List of model objects that were successfully loaded (or dummy models on failure)
        """
        paths_to_process = []
        if initial_file_paths is None:
            # Called from button, open dialog
            selected_paths = filedialog.askopenfilenames( # Use a different variable name
                title="Select Model Files",
                filetypes=(
                    ("3D model files", "*.fbx *.obj *.dae *.3ds *.blend"),
                    ("All files", "*.*")
                )
            )
            if not selected_paths:  # User canceled
                return []
            paths_to_process = selected_paths # Assign selected paths
        else:
            # Called with paths provided directly
            paths_to_process = initial_file_paths

        if not paths_to_process: # Double check if paths list is empty
             return []

        # --- Clear previous import results if started via button ---
        if initial_file_paths is None:
            self.imported_models_info.clear()
            self.models_listbox.delete(0, tk.END)
            self.last_model_path = None
            self.last_extracted_textures = []
            self.path_var.set("")
            self.materials_var.set("0")
            self.textures_var.set("0")
            for item in self.tree.get_children(): # Clear last model's texture list too
                self.tree.delete(item)
            self.parent.update()
        # --- End Clear ---

        loaded_models = []
        total_files = len(paths_to_process)
        success_count = 0
        error_count = 0
        all_extracted_texture_paths = []

        # Show loading message
        self.parent.config(cursor="wait")
        self.parent.update()

        # Use the determined paths_to_process list
        for i, file_path in enumerate(paths_to_process):
            print(f"Importing model {i+1}/{total_files}: {file_path}")
            self.last_model_path = file_path
            
            # Update UI path for current model being processed
            self.path_var.set(file_path)
            
            # Clear the panel's texture list for the current model
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.last_extracted_textures = []
            self.textures_var.set("0") # Reset texture count display
            self.materials_var.set("0") # Reset material count display
            self.add_to_processing_button.config(state=tk.DISABLED) # Disable button initially
            self.parent.update() # Force UI update

            # Load model using ModelLoader
            try:
                model = self.model_loader.load(file_path)
                loaded_models.append(model)

                if model and not model.get("is_dummy", False):
                    # Update statistics for the current model
                    self.materials_var.set(str(len(model.get("materials", []))))
                    
                    # Extract textures for the current model
                    current_extracted_refs = self.texture_extractor.extract(model)
                    
                    # Store basic info for the successfully loaded model
                    model_info = {
                        "path": file_path,
                        "filename": os.path.basename(file_path),
                        "materials": len(model.get("materials", [])),
                        "model_obj": model # Store the loaded model object itself if needed later
                    }
                    self.imported_models_info.append(model_info)

                    # Get accurate types and populate the panel's tree for the *current* model
                    self.last_extracted_textures = self._get_accurate_texture_info(current_extracted_refs)
                    self._populate_treeview(self.last_extracted_textures)
                    self.textures_var.set(str(len(self.last_extracted_textures)))

                    # Collect paths to add to processing later
                    current_texture_paths = [tex["path"] for tex in self.last_extracted_textures if tex.get("path")]
                    all_extracted_texture_paths.extend(current_texture_paths)

                    success_count += 1
                else:
                    print(f"Failed to load model or dummy model returned for: {file_path}")
                    # Store placeholder info for failed models
                    model_info = {
                        "path": file_path,
                        "filename": os.path.basename(file_path) + " (Load Failed)",
                        "materials": 0,
                        "model_obj": None
                    }
                    self.imported_models_info.append(model_info) # Add failed info to list
                    error_count += 1

            except Exception as e:
                error_count += 1
                print(f"Error importing model {file_path}: {e}")
                # Add a dummy model to keep track of failures if needed
                loaded_models.append(self.model_loader._create_dummy_model(file_path))
                # Optionally show error immediately or aggregate
                # messagebox.showerror("Import Error", f"Error importing model {os.path.basename(file_path)}: {e}")

        # Restore cursor
        self.parent.config(cursor="")

        # --- Update the new Imported Models list display ---
        self._update_model_list_display()
        # --- End Update ---

        # Add all collected unique texture paths to the main processing panel
        if all_extracted_texture_paths:
            print(f"Adding {len(all_extracted_texture_paths)} extracted texture paths to processing...")
            if self.texture_import_panel:
                 # Filter to existing files only before adding
                unique_existing_paths = list(set(path for path in all_extracted_texture_paths if os.path.exists(path)))
                if unique_existing_paths:
                    self.texture_import_panel.import_textures(unique_existing_paths)
                else:
                     print("No valid texture files found among extracted paths.")
            else:
                messagebox.showerror("Error", "Texture import panel not available.")

        # Update UI based on the *last* processed model's info (as decided)
        if self.last_model_path:
             self.path_var.set(self.last_model_path)
             # The material/texture counts and treeview were updated in the loop for the last model
             if self.last_extracted_textures:
                 self.add_to_processing_button.config(state=tk.NORMAL) # Enable if last model had textures
             else:
                 self.add_to_processing_button.config(state=tk.DISABLED)
        else: # If no files were processed
             self.path_var.set("")
             self.materials_var.set("0")
             self.textures_var.set("0")
             self.add_to_processing_button.config(state=tk.DISABLED)


        # Show summary message
        summary_msg = f"Finished importing {total_files} models.\n"
        summary_msg += f"Successfully loaded: {success_count}\n"
        summary_msg += f"Errors: {error_count}"
        messagebox.showinfo("Multi-Import Complete", summary_msg)
        
        # Enable the extract button (now maybe redundant as extraction happens automatically)
        # Let's disable it as extraction is now part of the import loop.
        self.extract_button.config(state=tk.DISABLED) 

        return loaded_models
    
    def _extract_textures(self):
        """
        Extract textures from the currently loaded model (self.model).
        This is now primarily used internally by import_model for each model.
        The 'Extract Textures' button might become redundant.
        """
        # This method is kept for potential future use or if the button logic is restored.
        # The main extraction now happens within the import_model loop.
        
        # Get the currently stored model (likely the last one loaded)
        current_model = getattr(self, 'model', None) 
        if not current_model or current_model.get("is_dummy", False):
             # messagebox.showerror("Error", "No valid model loaded to extract textures from.")
             print("No valid model loaded to extract textures from.")
             return [] # Return empty list

        try:
            # Extract textures
            texture_refs = self.texture_extractor.extract(current_model)
            
            # Get accurate types
            accurate_textures = self._get_accurate_texture_info(texture_refs)
            
            # Populate the treeview for this model
            self._populate_treeview(accurate_textures)
            
            # Update statistics display
            self.textures_var.set(str(len(accurate_textures)))
            
            # Enable/disable button based on results
            if accurate_textures:
                self.add_to_processing_button.config(state=tk.NORMAL)
            else:
                self.add_to_processing_button.config(state=tk.DISABLED)

            return accurate_textures # Return the list of texture dicts

        except Exception as e:
            messagebox.showerror("Extraction Error", f"Error extracting textures: {e}")
            return [] # Return empty list on error

    def _get_accurate_texture_info(self, texture_refs):
        """
        Takes a list of TextureReference objects and returns a list of dictionaries
        with accurately classified texture types.
        """
        accurate_textures = []
        accurate_texture_manager = None
        if self.texture_import_panel and hasattr(self.texture_import_panel, 'texture_manager'):
            accurate_texture_manager = self.texture_import_panel.texture_manager

        for ref in texture_refs:
            accurate_type = ref.texture_type # Default to preliminary type
            base_name = "Unknown" # Default base name

            # Use the main texture manager for accurate classification if available
            if accurate_texture_manager and ref.path and os.path.exists(ref.path):
                try:
                    accurate_type, base_name = accurate_texture_manager.classify_texture(ref.path)
                except Exception as e:
                    print(f"Warning: Could not accurately classify {ref.path}: {e}")
                    accurate_type = ref.texture_type # Fallback
                    try:
                        _, base_name = accurate_texture_manager.classify_texture(ref.path)
                    except:
                         filename_no_ext = os.path.splitext(os.path.basename(ref.path))[0]
                         base_name = filename_no_ext # Simplified fallback

            # Create dictionary using the accurate type
            texture_dict = {
                "path": ref.path,
                "type": accurate_type,
                "material": ref.material_name,
                "filename": ref.filename,
                "processed_path": ref.processed_path,
                "base_name": base_name
            }
            accurate_textures.append(texture_dict)
        return accurate_textures

    def _populate_treeview(self, texture_list):
        """
        Clears and populates the internal treeview with a list of texture dictionaries.
        """
        # Clear existing textures in the treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add to treeview using the accurate type from the dictionary
        for texture in texture_list:
            self.tree.insert(
                "", 
                "end", 
                values=(
                    texture.get("material", "Unknown"),
                    texture.get("type", "Unknown"), # Display the accurate type
                    texture.get("path", "")
                )
            )

    def _on_model_select(self, event):
        """
        Handles selection changes in the imported models listbox.
        Updates the info panel and texture list to reflect the selected model.
        """
        selected_indices = self.models_listbox.curselection()
        if not selected_indices:
            # No selection, clear details
            self.path_var.set("")
            self.materials_var.set("0")
            self.textures_var.set("0")
            self._populate_treeview([]) # Clear texture list
            self.add_to_processing_button.config(state=tk.DISABLED)
            return

        selected_index = selected_indices[0]
        if 0 <= selected_index < len(self.imported_models_info):
            model_info = self.imported_models_info[selected_index]
            model_obj = model_info.get("model_obj")

            # Update info panel
            self.path_var.set(model_info.get("path", ""))
            self.materials_var.set(str(model_info.get("materials", 0)))

            # Check if the model was loaded successfully
            if model_obj and not model_obj.get("is_dummy", False):
                # Extract textures for the selected model
                try:
                    texture_refs = self.texture_extractor.extract(model_obj)
                    accurate_textures = self._get_accurate_texture_info(texture_refs)
                    self._populate_treeview(accurate_textures)
                    self.textures_var.set(str(len(accurate_textures)))
                    # Store these textures temporarily in case "Add to Processing" is clicked
                    self.currently_selected_model_textures = accurate_textures 
                    # Enable button if textures exist
                    if accurate_textures:
                        self.add_to_processing_button.config(state=tk.NORMAL)
                    else:
                        self.add_to_processing_button.config(state=tk.DISABLED)
                except Exception as e:
                    print(f"Error extracting textures for selected model {model_info.get('path', '')}: {e}")
                    self._populate_treeview([]) # Clear texture list on error
                    self.textures_var.set("Error")
                    self.add_to_processing_button.config(state=tk.DISABLED)
                    self.currently_selected_model_textures = []
            else:
                # Model failed to load or is a dummy
                self._populate_treeview([]) # Clear texture list
                self.textures_var.set("0 (Load Failed)")
                self.add_to_processing_button.config(state=tk.DISABLED)
                self.currently_selected_model_textures = []
        else:
             # Index out of bounds, clear details
            self.path_var.set("")
            self.materials_var.set("0")
            self.textures_var.set("0")
            self._populate_treeview([])
            self.add_to_processing_button.config(state=tk.DISABLED)
            self.currently_selected_model_textures = []


    def _update_model_list_display(self):
        """
        Updates the listbox displaying imported models.
        """
        self.models_listbox.delete(0, tk.END) # Clear existing list
        for model_info in self.imported_models_info:
            display_text = model_info.get("filename", "Unknown Model")
            # Optionally add more info like material count:
            # display_text += f" (Mats: {model_info.get('materials', 0)})"
            self.models_listbox.insert(tk.END, display_text)

    def _add_to_processing(self):
        """
        Add textures from the *currently selected model* in the list to the main processing list.
        The 'Add to Processing' button now acts on the textures associated with the
        model currently selected in the 'Imported Models' listbox.
        """
        # Use the textures stored when the model was selected
        textures_to_add = getattr(self, 'currently_selected_model_textures', [])

        if not textures_to_add:
            messagebox.showerror("Error", "No textures from the selected model to add.")
            return

        if not self.texture_import_panel:
            messagebox.showerror(
                "Error",
                "Texture import panel not available. Cannot add textures to processing."
            )
            return

        # Get texture paths from the selected model's textures
        texture_paths = [texture["path"] for texture in textures_to_add if texture.get("path")]

        # Filter to existing files only
        existing_paths = [path for path in texture_paths if os.path.exists(path)]

        if not existing_paths:
            messagebox.showerror("Error", "No valid texture files found for the selected model.")
            return

        # Add to texture import panel (will handle duplicates)
        selected_model_filename = "Selected Model"
        selected_indices = self.models_listbox.curselection()
        if selected_indices:
             selected_index = selected_indices[0]
             if 0 <= selected_index < len(self.imported_models_info):
                  selected_model_filename = self.imported_models_info[selected_index].get("filename", selected_model_filename)

        print(f"Adding {len(existing_paths)} textures from {selected_model_filename} to processing...")
        imported_textures = self.texture_import_panel.import_textures(existing_paths)

        # Show success message (might report 0 added if all were duplicates)
        messagebox.showinfo(
            "Added to Processing",
            f"Attempted to add {len(existing_paths)} textures from {selected_model_filename}. See main list for results (duplicates are skipped)."
        )
