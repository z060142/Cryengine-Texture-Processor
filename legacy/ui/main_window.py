#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Window for CryEngine Texture Processor

This module provides the main application window and coordinates 
the interaction between different UI components.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from .texture_import import TextureImportPanel
from .model_import import ModelImportPanel
from .preview_panel import PreviewPanel
from .export_settings import ExportSettingsPanel
from .texture_group_panel import TextureGroupPanel
from .suffix_settings import SuffixSettingsDialog
from .preferences_dialog import PreferencesDialog
from language.language_manager import get_instance as get_language_manager
from language.language_manager import get_text, change_language

class MainWindow:
    """
    Main application window class that integrates all UI components.
    """
    
    def __init__(self, root):
        """
        Initialize the main window and its components.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title(get_text("app.title", "CryEngine Texture Processor"))
        self.root.iconbitmap('main.ico') # 設定程式圖標
        
        # Create menu
        self._create_menu()
        
        # Create main paned window
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create left panel (Import)
        self.left_frame = ttk.Frame(self.main_paned, width=300)
        self.main_paned.add(self.left_frame, weight=1)
        
        # Create left panel notebook for texture/model import
        self.left_notebook = ttk.Notebook(self.left_frame)
        self.left_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create texture import tab
        self.texture_frame = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.texture_frame, text=get_text("import.texture.title", "Texture Import"))
        
        # Create model import tab
        self.model_frame = ttk.Frame(self.left_notebook)
        self.left_notebook.add(self.model_frame, text=get_text("import.model.title", "Model Import"))
        
        # Create center panel
        self.center_paned = ttk.PanedWindow(self.main_paned, orient=tk.VERTICAL)
        self.main_paned.add(self.center_paned, weight=2)
        
        # Create preview panel (top of center)
        self.preview_frame = ttk.Frame(self.center_paned)
        self.center_paned.add(self.preview_frame, weight=1)
        
        # Create texture groups panel (bottom of center)
        self.groups_frame = ttk.Frame(self.center_paned)
        self.center_paned.add(self.groups_frame, weight=1)
        
        # Create right panel (Export Settings)
        self.right_frame = ttk.Frame(self.main_paned, width=300)
        self.main_paned.add(self.right_frame, weight=1)
        
        # Initialize UI components
        self.texture_import_panel = TextureImportPanel(self.texture_frame)
        self.model_import_panel = ModelImportPanel(self.model_frame)
        self.preview_panel = PreviewPanel(self.preview_frame)
        self.texture_group_panel = TextureGroupPanel(self.groups_frame)
        self.export_settings_panel = ExportSettingsPanel(self.right_frame)
        
        # Connect components
        self.texture_import_panel.set_group_panel(self.texture_group_panel)
        self.texture_import_panel.set_preview_panel(self.preview_panel)
        self.texture_group_panel.set_preview_panel(self.preview_panel)
        self.model_import_panel.set_texture_import_panel(self.texture_import_panel)
        
        # Create status bar
        self.status_bar = ttk.Label(self.root, text=get_text("app.ready", "Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Make this instance available to the root window for other components to access
        root.main_window = self
    
    def _create_menu(self):
        """
        Create application menu.
        """
        menu_bar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(
            label=get_text("menu.file.import_textures", "Import Textures..."), 
            command=self._import_textures
        )
        file_menu.add_command(
            label=get_text("menu.file.import_model", "Import Model..."), 
            command=self._import_model
        )
        file_menu.add_separator()
        file_menu.add_command(
            label=get_text("menu.file.export", "Export..."), 
            command=self._export
        )
        file_menu.add_separator()
        file_menu.add_command(
            label=get_text("menu.file.exit", "Exit"), 
            command=self.root.quit
        )
        menu_bar.add_cascade(
            label=get_text("menu.file.title", "File"), 
            menu=file_menu
        )
        
        # Edit menu
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(
            label=get_text("menu.edit.suffix_settings", "Suffix Settings..."), 
            command=self._show_suffix_settings
        )
        edit_menu.add_command(
            label=get_text("menu.edit.preferences", "Preferences..."), 
            command=self._show_preferences
        )
        
        # Language submenu
        language_menu = tk.Menu(edit_menu, tearoff=0)
        
        # Get available languages
        language_manager = get_language_manager()
        available_languages = language_manager.get_available_languages()
        current_language = language_manager.get_current_language()
        language_names = language_manager.get_language_display_names()
        
        # Add language options
        for lang_code in available_languages:
            # Get display name
            lang_name = language_names.get(lang_code, lang_code)
            
            # Add a check mark to the current language
            language_menu.add_radiobutton(
                label=f"{lang_name} ({lang_code})",
                command=lambda code=lang_code: self._change_language(code),
                variable=tk.StringVar(value=current_language),
                value=lang_code
            )
        
        edit_menu.add_cascade(
            label=get_text("menu.edit.language", "Language"), 
            menu=language_menu
        )
        
        menu_bar.add_cascade(
            label=get_text("menu.edit.title", "Edit"), 
            menu=edit_menu
        )
        
        # Help menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(
            label=get_text("menu.help.about", "About"), 
            command=self._show_about
        )
        menu_bar.add_cascade(
            label=get_text("menu.help.title", "Help"), 
            menu=help_menu
        )
        
        self.root.config(menu=menu_bar)
    
    def _change_language(self, language_code):
        """
        Change the UI language.
        
        Args:
            language_code: Language code to change to
        """
        if change_language(language_code):
            # Get language manager and language name
            language_manager = get_language_manager()
            language_name = language_manager.get_language_name(language_code)
            
            # Update UI immediately for some components
            self.root.title(get_text("app.title", "CryEngine Texture Processor"))
            self.status_bar.config(text=get_text("app.ready", "Ready"))
            
            # Re-create menu with new language
            self._create_menu()
            
            # Update tab titles
            self.left_notebook.tab(0, text=get_text("import.texture.title", "Texture Import"))
            self.left_notebook.tab(1, text=get_text("import.model.title", "Model Import"))
            
            # Show success message
            messagebox.showinfo(
                get_text("language.title", "Language"),
                get_text("language.changed", "Language changed to {0}. Some changes will take effect immediately, but for a complete update, please restart the application.").format(language_name)
            )
    
    def _import_textures(self):
        """
        Import textures.
        """
        # Switch to texture import tab
        self.left_notebook.select(0)
        
        # Call texture import functionality
        self.texture_import_panel.import_textures()
    
    def _import_model(self):
        """
        Import model.
        """
        # Switch to model import tab
        self.left_notebook.select(1)
        
        # Call model import functionality
        self.model_import_panel.import_model()
    
    def _export(self):
        """
        Export processed textures.
        """
        # Get texture groups directly from the texture manager
        texture_groups = self.texture_import_panel.texture_manager.get_all_groups()
        
        # Debug info
        print(f"MainWindow._export: Found {len(texture_groups)} texture groups")
        
        # Call export functionality
        self.export_settings_panel.export_textures(texture_groups)
    
    def _show_suffix_settings(self):
        """
        Show suffix settings dialog.
        """
        dialog = SuffixSettingsDialog(self.root)
        if dialog.result:
            # Reload texture import panel with new suffix settings
            self.texture_import_panel.load_suffix_settings()
            # Show success message
            messagebox.showinfo(
                get_text("suffix_settings.title", "Settings Updated"), 
                get_text("suffix_settings.success", "Suffix settings have been updated.")
            )
    
    def _show_preferences(self):
        """
        Show preferences dialog.
        """
        # Create and show preferences dialog
        dialog = PreferencesDialog(self.root)
    
    def _show_about(self):
        """
        Show about dialog.
        """
        messagebox.showinfo(
            get_text("about.title", "About"),
            get_text("about.content", "CryEngine Texture Processor\n\nA tool for processing textures for use in CryEngine.\n\nVersion: 0.1")
        )
    
    def update_status(self, message):
        """
        Update status bar message.
        
        Args:
            message: Message to display
        """
        self.status_bar.config(text=message)
    
    def start_batch_processing(self):
        """
        Start batch processing of texture groups.
        This method is intended to be set by the main application.
        """
        # This is a placeholder that will be overridden in main.py
        messagebox.showinfo(
            get_text("batch.title", "Batch Processing"),
            get_text("batch.not_configured", "Batch processing is not fully configured yet.")
        )
        
    def get_texture_manager(self):
        """
        Get the texture manager from the texture import panel.
        
        Returns:
            TextureManager instance
        """
        return self.texture_import_panel.texture_manager
