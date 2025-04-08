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
import threading # Added
import queue     # Added
from model_processing.model_loader import ModelLoader
from model_processing.texture_extractor import TextureExtractor
from ui.progress_dialog import ProgressDialog # Added for type hinting/clarity
from language.language_manager import get_text # Added

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
        self.imported_models_info = [] # List to store info about all imported models (populated by worker)
        self.model_loader = ModelLoader()
        self.texture_extractor = TextureExtractor()
        self.texture_import_panel = None  # Will be set by main window
        self.progress_dialog = None # Added to hold progress dialog instance
        self.progress_queue = None # Added for thread communication
        self.worker_thread = None # Added to hold worker thread instance
        self.currently_selected_model_textures = [] # Keep track of textures for the selected model in the list

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

        # Use translated text for button
        import_button = ttk.Button(import_frame, text=get_text("model_import.import_button", "Import Model(s)"), command=self.import_model)
        import_button.pack(side=tk.LEFT, padx=(0, 5))

        # --- Add Imported Models List Frame ---
        models_list_frame = ttk.LabelFrame(main_frame, text=get_text("model_import.imported_models", "Imported Models"))
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
        info_frame = ttk.LabelFrame(main_frame, text=get_text("model_import.selected_info", "Selected Model Information")) # Changed title
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        # Model path
        ttk.Label(info_frame, text=get_text("model_import.path_label", "Path:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.path_var = tk.StringVar()
        ttk.Label(info_frame, textvariable=self.path_var, wraplength=350).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5) # Added wraplength

        # Model statistics
        ttk.Label(info_frame, text=get_text("model_import.materials_label", "Materials:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.materials_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.materials_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(info_frame, text=get_text("model_import.textures_label", "Textures:")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.textures_var = tk.StringVar(value="0")
        ttk.Label(info_frame, textvariable=self.textures_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Create texture list frame
        list_frame = ttk.LabelFrame(main_frame, text=get_text("model_import.extracted_textures", "Extracted Textures"))
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
        self.tree.heading("material", text=get_text("model_import.col_material", "Material"))
        self.tree.heading("type", text=get_text("model_import.col_type", "Type"))
        self.tree.heading("path", text=get_text("model_import.col_path", "Path"))
        self.tree.column("material", width=100, anchor=tk.W)
        self.tree.column("type", width=100, anchor=tk.W)
        self.tree.column("path", width=300, anchor=tk.W)

        # Create action buttons frame
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=5)

        # Extract button is now redundant as it happens during import
        # extract_button = ttk.Button(
        #     action_frame,
        #     text="Extract Textures",
        #     command=self._extract_textures,
        #     state=tk.DISABLED
        # )
        # extract_button.pack(side=tk.LEFT, padx=5)
        # self.extract_button = extract_button

        add_to_processing_button = ttk.Button(
            action_frame,
            text=get_text("model_import.add_button", "Add to Processing"),
            command=self._add_to_processing,
            state=tk.DISABLED # Initially disabled, enabled when a model with textures is selected
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

    def import_model(self, initial_file_paths=None):
        """
        Initiates the import of one or more model files using a background thread.

        Args:
            initial_file_paths: List of paths to model files or None to open file dialog
        """
        # Prevent starting a new import if one is already running
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning(get_text("model_import.already_running_title", "Import in Progress"),
                                   get_text("model_import.already_running_msg", "An import process is already running. Please wait for it to complete."))
            return

        paths_to_process = []
        if initial_file_paths is None:
            # Called from button, open dialog
            selected_paths = filedialog.askopenfilenames(
                title=get_text("model_import.dialog_title", "Select Model Files"),
                filetypes=(
                    (get_text("model_import.filetype_3d", "3D model files"), "*.fbx *.obj *.dae *.3ds *.blend"),
                    (get_text("model_import.filetype_all", "All files"), "*.*")
                )
            )
            if not selected_paths:  # User canceled
                return
            paths_to_process = selected_paths
        else:
            # Called with paths provided directly
            paths_to_process = initial_file_paths

        if not paths_to_process:
             return

        # --- Clear previous import results if started via button ---
        if initial_file_paths is None:
            self.imported_models_info.clear()
            self.models_listbox.delete(0, tk.END)
            self.path_var.set("")
            self.materials_var.set("0")
            self.textures_var.set("0")
            for item in self.tree.get_children(): # Clear last model's texture list too
                self.tree.delete(item)
            self.add_to_processing_button.config(state=tk.DISABLED) # Disable button
            self.parent.update()
        # --- End Clear ---

        # --- Setup for Background Processing ---
        self.progress_queue = queue.Queue()
        self.progress_dialog = ProgressDialog(
            self.parent,
            title=get_text("model_import.progress_title", "Importing Models..."),
            allow_cancel=True
        )
        self.progress_dialog.set_cancel_callback(self._cancel_import)

        # Start worker thread
        self.worker_thread = threading.Thread(
            target=self._worker_import_models,
            args=(paths_to_process, self.progress_queue),
            daemon=True # Allows main program to exit even if thread is running
        )
        self.worker_thread.start()

        # Start checking the queue for updates
        self.parent.after(100, self._check_progress_queue)
        # --- End Setup ---

    def _worker_import_models(self, file_paths, progress_queue):
        """
        Worker thread function to load models and extract textures.

        Args:
            file_paths: List of model file paths to process.
            progress_queue: Queue to send progress updates back to the main thread.
        """
        loaded_models_data = [] # Store results locally first
        all_extracted_texture_paths = []
        total_files = len(file_paths)
        success_count = 0
        error_count = 0
        cancelled = False

        try:
            for i, file_path in enumerate(file_paths):
                # Check for cancellation flag from main thread via progress dialog state
                # This check is done within the main thread's queue check now
                # if progress_queue.empty() and hasattr(self, 'progress_dialog') and self.progress_dialog and self.progress_dialog.is_cancelled():
                #      cancelled = True
                #      progress_queue.put({"type": "cancelled"}) # Inform main thread
                #      break # Exit loop if cancelled

                progress = (i + 1) / total_files
                filename = os.path.basename(file_path)
                current_op_text = get_text("model_import.progress_loading", "Loading: {filename}").format(filename=filename)
                status_text = get_text("model_import.progress_status", "Model {current}/{total}").format(current=i+1, total=total_files)

                # Send progress update
                progress_queue.put({
                    "type": "progress",
                    "progress": progress,
                    "current": current_op_text,
                    "status": status_text
                })

                # Check for cancellation *after* sending progress, before heavy work
                if self.progress_dialog and self.progress_dialog.is_cancelled():
                    cancelled = True
                    break # Exit loop if cancelled

                model = None
                current_extracted_refs = []
                model_info = { # Initialize info dict
                    "path": file_path,
                    "filename": filename,
                    "materials": 0,
                    "model_obj": None, # Store the loaded model object
                    "extracted_textures": [] # Store accurately classified textures for this model
                }

                try:
                    # Load model using ModelLoader
                    model = self.model_loader.load(file_path)

                    if model and not model.get("is_dummy", False):
                        model_info["model_obj"] = model # Store the actual model object
                        model_info["materials"] = len(model.get("materials", []))

                        # Extract textures for the current model
                        current_extracted_refs = self.texture_extractor.extract(model)

                        # Get accurate types and store them with the model info
                        accurate_textures = self._get_accurate_texture_info(current_extracted_refs)
                        model_info["extracted_textures"] = accurate_textures

                        # Collect paths to add to processing later
                        current_texture_paths = [tex["path"] for tex in accurate_textures if tex.get("path") and os.path.exists(tex["path"])]
                        all_extracted_texture_paths.extend(current_texture_paths)

                        success_count += 1
                    else:
                        print(f"Failed to load model or dummy model returned for: {file_path}")
                        model_info["filename"] += get_text("model_import.load_failed_suffix", " (Load Failed)")
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"Error importing model {file_path}: {e}")
                    model_info["filename"] += get_text("model_import.load_error_suffix", " (Error)")
                    # Optionally add dummy model if needed downstream
                    # loaded_models.append(self.model_loader._create_dummy_model(file_path))

                loaded_models_data.append(model_info) # Add info for this model (success or fail)

                # --- Attempt Memory Release (Optional/Experimental) ---
                # Explicit memory management from threads with libraries like bpy is complex and often unsafe.
                # Relying on Python's GC after the loop might be the most practical approach.
                # If using assimp, check its documentation for potential cleanup functions.
                del model # Help Python's GC, may or may not release significant memory immediately
                # --- End Memory Release ---


            # Send completion message
            if cancelled:
                 progress_queue.put({"type": "cancelled"})
            else:
                progress_queue.put({
                    "type": "completed",
                    "results": loaded_models_data,
                    "texture_paths": list(set(all_extracted_texture_paths)), # Unique paths
                    "success_count": success_count,
                    "error_count": error_count,
                    "total_files": total_files
                })

        except Exception as e:
            # Send error message if worker crashes
            print(f"Critical error in model import worker thread: {e}")
            progress_queue.put({"type": "error", "message": str(e)})


    def _check_progress_queue(self):
        """
        Checks the queue for messages from the worker thread and updates the UI.
        Called periodically from the main thread using `after`.
        """
        # Check if the dialog was closed prematurely (e.g., by user closing main window)
        if not self.progress_dialog or not self.progress_dialog.dialog.winfo_exists():
            self._cleanup_after_import()
            return

        try:
            while True: # Process all messages currently in the queue
                message = self.progress_queue.get_nowait()

                if message["type"] == "progress":
                    if not self.progress_dialog.is_cancelled():
                        self.progress_dialog.update_progress(
                            message["progress"],
                            current=message["current"],
                            status=message["status"]
                        )
                elif message["type"] == "completed":
                    # --- Final UI Updates After Successful Completion ---
                    self.imported_models_info = message["results"] # Update main list
                    self._update_model_list_display() # Update listbox

                    # Add textures to main processing panel
                    texture_paths_to_add = message["texture_paths"]
                    if texture_paths_to_add:
                        print(f"Adding {len(texture_paths_to_add)} unique extracted texture paths to processing...")
                        if self.texture_import_panel:
                            # This might still block the UI briefly if many textures are added,
                            # consider if texture_import_panel.import_textures needs optimization too.
                            self.texture_import_panel.import_textures(texture_paths_to_add)
                        else:
                            messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_texture_panel_missing", "Texture import panel not available."))

                    # Close progress dialog
                    self.progress_dialog.show_completion(success=True)
                    # Keep dialog open briefly?
                    self.parent.after(1000, self._safe_close_progress) # Close after 1 sec

                    # Show summary message
                    summary_msg = get_text("model_import.summary_finished", "Finished importing {total} models.\nSuccessfully loaded: {success}\nErrors: {errors}").format(
                        total=message["total_files"],
                        success=message["success_count"],
                        errors=message["error_count"]
                    )
                    messagebox.showinfo(get_text("model_import.summary_title", "Multi-Import Complete"), summary_msg)

                    self._cleanup_after_import()
                    return # Stop checking queue

                elif message["type"] == "cancelled":
                    print("Model import cancelled by user.")
                    self._safe_close_progress()
                    messagebox.showwarning(get_text("model_import.cancelled_title", "Import Cancelled"), get_text("model_import.cancelled_msg", "Model import process was cancelled."))
                    self._cleanup_after_import()
                    return # Stop checking queue

                elif message["type"] == "error":
                    print(f"Model import failed: {message['message']}")
                    self._safe_close_progress()
                    messagebox.showerror(get_text("model_import.error_title", "Import Error"), get_text("model_import.error_msg", "An error occurred during model import: {error}").format(error=message['message']))
                    self._cleanup_after_import()
                    return # Stop checking queue

        except queue.Empty:
            # Queue is empty, check if thread is still running
            if self.worker_thread and self.worker_thread.is_alive():
                # Reschedule check
                self.parent.after(100, self._check_progress_queue)
            else:
                # Thread finished but no completion/error message? (Should not happen ideally)
                print("Worker thread finished unexpectedly.")
                self._safe_close_progress()
                self._cleanup_after_import()
        except Exception as e:
            # Handle unexpected errors during queue processing
            print(f"Error processing progress queue: {e}")
            self._safe_close_progress()
            self._cleanup_after_import() # Ensure cleanup happens

    def _cancel_import(self):
        """Callback function when the cancel button is pressed in the progress dialog."""
        print("Cancel requested by user.")
        # The worker thread will check `self.progress_dialog.is_cancelled()`
        # No direct thread interruption needed here, just let the dialog handle its state.

    def _cleanup_after_import(self):
        """Resets state variables after import finishes or is cancelled/errored."""
        self.progress_queue = None
        self.worker_thread = None
        # Don't reset self.progress_dialog here, _safe_close_progress handles it
        print("Import process finished or terminated.")

    def _safe_close_progress(self):
        """Safely close the progress dialog if it exists."""
        if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
            self.progress_dialog.close()
        self.progress_dialog = None # Clear reference

    def _extract_textures(self):
        """
        Extract textures from the currently loaded model (self.model).
        This is now primarily used internally by import_model for each model.
        The 'Extract Textures' button might become redundant.
        """
        # This method is kept for potential future use or if the button logic is restored.
        # The main extraction now happens within the import_model loop.

        # Get the currently stored model (likely the last one loaded)
        # This logic needs rethinking as models are processed in a thread now.
        # It should probably operate on the *selected* model from the listbox.
        selected_indices = self.models_listbox.curselection()
        if not selected_indices:
             messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_no_model_selected", "No model selected to extract textures from."))
             return []

        selected_index = selected_indices[0]
        if not (0 <= selected_index < len(self.imported_models_info)):
            messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_invalid_selection", "Invalid model selection."))
            return []

        model_info = self.imported_models_info[selected_index]
        current_model = model_info.get("model_obj")

        if not current_model or current_model.get("is_dummy", False):
             messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_no_valid_model_data", "No valid model data loaded for the selected item."))
             # print("No valid model loaded to extract textures from.")
             return [] # Return empty list

        try:
            # Extract textures (This might be slow if model data needs reloading)
            # Ideally, texture refs are stored during import. We use the stored ones.
            accurate_textures = model_info.get("extracted_textures", [])

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
            messagebox.showerror(get_text("model_import.error_extraction_failed_title", "Extraction Error"), get_text("model_import.error_extraction_failed_msg", "Error extracting textures: {error}").format(error=e))
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
            abs_path = None

            # Resolve absolute path if possible
            if ref.path:
                 if os.path.isabs(ref.path):
                     abs_path = ref.path
                 elif self.model_loader.last_loaded_dir: # Use directory of the model file
                     potential_path = os.path.join(self.model_loader.last_loaded_dir, ref.path)
                     if os.path.exists(potential_path):
                         abs_path = os.path.normpath(potential_path)
                     else: # Fallback: try relative to CWD (less likely)
                         potential_path_cwd = os.path.join(os.getcwd(), ref.path)
                         if os.path.exists(potential_path_cwd):
                              abs_path = os.path.normpath(potential_path_cwd)

            # Use the main texture manager for accurate classification if available and path exists
            if accurate_texture_manager and abs_path and os.path.exists(abs_path):
                try:
                    # Use the absolute path for classification
                    accurate_type, base_name = accurate_texture_manager.classify_texture(abs_path)
                except Exception as e:
                    print(f"Warning: Could not accurately classify {abs_path}: {e}")
                    accurate_type = ref.texture_type # Fallback
                    try: # Try getting base name even if type fails
                        _, base_name = accurate_texture_manager.classify_texture(abs_path)
                    except:
                         filename_no_ext = os.path.splitext(os.path.basename(abs_path))[0]
                         base_name = filename_no_ext # Simplified fallback
            elif abs_path: # Path exists but no manager or classification failed earlier
                 filename_no_ext = os.path.splitext(os.path.basename(abs_path))[0]
                 base_name = filename_no_ext # Simplified fallback based on filename
            else: # No valid absolute path found
                 accurate_type = "Missing"
                 base_name = os.path.splitext(ref.filename)[0] if ref.filename else "Unknown"


            # Create dictionary using the accurate type and absolute path
            texture_dict = {
                "path": abs_path, # Store the resolved absolute path
                "type": accurate_type,
                "material": ref.material_name,
                "filename": ref.filename, # Original filename from model
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
            display_path = texture.get("path", texture.get("filename", "N/A")) # Show path or filename
            self.tree.insert(
                "",
                "end",
                values=(
                    texture.get("material", "Unknown"),
                    texture.get("type", "Unknown"), # Display the accurate type
                    display_path
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
            self.currently_selected_model_textures = []
            return

        selected_index = selected_indices[0]
        if 0 <= selected_index < len(self.imported_models_info):
            model_info = self.imported_models_info[selected_index]
            # model_obj = model_info.get("model_obj") # No longer need the full object here

            # Update info panel
            self.path_var.set(model_info.get("path", ""))
            self.materials_var.set(str(model_info.get("materials", 0)))

            # Use the stored extracted textures
            accurate_textures = model_info.get("extracted_textures", [])
            self._populate_treeview(accurate_textures)
            self.textures_var.set(str(len(accurate_textures)))

            # Store these textures temporarily in case "Add to Processing" is clicked
            self.currently_selected_model_textures = accurate_textures
            # Enable button if textures exist and are valid paths
            valid_textures_exist = any(tex.get("path") and os.path.exists(tex["path"]) for tex in accurate_textures)
            if valid_textures_exist:
                self.add_to_processing_button.config(state=tk.NORMAL)
            else:
                self.add_to_processing_button.config(state=tk.DISABLED)

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
        # Select the first item by default if list is not empty
        if self.imported_models_info:
             self.models_listbox.selection_set(0)
             self._on_model_select(None) # Trigger update for the first item


    def _add_to_processing(self):
        """
        Add textures from the *currently selected model* in the list to the main processing list.
        The 'Add to Processing' button now acts on the textures associated with the
        model currently selected in the 'Imported Models' listbox.
        """
        # Use the textures stored when the model was selected
        textures_to_add = self.currently_selected_model_textures # Already filtered/processed

        if not textures_to_add:
            messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_no_textures_selected", "No textures from the selected model to add."))
            return

        if not self.texture_import_panel:
            messagebox.showerror(
                get_text("error.title", "Error"),
                get_text("model_import.error_texture_panel_missing", "Texture import panel not available. Cannot add textures to processing.")
            )
            return

        # Get valid, existing texture paths from the selected model's textures
        existing_paths = [texture["path"] for texture in textures_to_add if texture.get("path") and os.path.exists(texture["path"])]

        if not existing_paths:
            messagebox.showerror(get_text("error.title", "Error"), get_text("model_import.error_no_valid_files_selected", "No valid texture files found for the selected model."))
            return

        # Add to texture import panel (will handle duplicates)
        selected_model_filename = "Selected Model"
        selected_indices = self.models_listbox.curselection()
        if selected_indices:
             selected_index = selected_indices[0]
             if 0 <= selected_index < len(self.imported_models_info):
                  selected_model_filename = self.imported_models_info[selected_index].get("filename", selected_model_filename)

        print(f"Adding {len(existing_paths)} textures from {selected_model_filename} to processing...")
        # Assuming import_textures returns number added or similar info
        self.texture_import_panel.import_textures(existing_paths)

        # Show success message (might report 0 added if all were duplicates)
        messagebox.showinfo(
            get_text("model_import.added_title", "Added to Processing"),
            get_text("model_import.added_msg", "Attempted to add {count} textures from {model}. See main list for results (duplicates are skipped).").format(count=len(existing_paths), model=selected_model_filename)
        )
