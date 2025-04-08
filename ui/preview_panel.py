#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Texture Preview Panel

This module provides UI components for previewing textures and
visualizing texture processing results.
"""

import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class PreviewPanel:
    """
    UI panel for texture preview and comparison.
    """
    
    def __init__(self, parent):
        """
        Initialize the preview panel.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.current_texture = None
        self.original_image = None
        self.processed_image = None
        self.original_pil_image = None  # Store the PIL image to prevent garbage collection
        
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
        
        # Create controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Texture info
        info_frame = ttk.Frame(controls_frame)
        info_frame.grid(row=0, column=0, sticky=tk.W)
        
        ttk.Label(info_frame, text="Texture:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.name_var = tk.StringVar()
        name_label = ttk.Label(info_frame, textvariable=self.name_var)
        name_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(info_frame, text="Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.type_var = tk.StringVar()
        type_label = ttk.Label(info_frame, textvariable=self.type_var)
        type_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(info_frame, text="Dimensions:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.dimensions_var = tk.StringVar()
        dimensions_label = ttk.Label(info_frame, textvariable=self.dimensions_var)
        dimensions_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Initialize view mode as original without UI controls
        self.view_var = tk.StringVar(value="original")
        
        # Create preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas for image preview
        self.canvas = tk.Canvas(preview_frame, bg="lightgray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind canvas resize event
        self.canvas.bind("<Configure>", self._on_canvas_resize)
    
    def _on_canvas_resize(self, event):
        """
        Handle canvas resize event.
        
        Args:
            event: Event object
        """
        # Update preview to fit new size
        self._update_preview()
    
    def set_textures(self, textures):
        """
        Set available textures for preview.
        
        Args:
            textures: List of texture objects
        """
        if not textures:
            self.set_current_texture(None)
            return
        
        # Set first texture as current
        self.set_current_texture(textures[0])
    
    def set_current_texture(self, texture):
        """
        Set the current texture to preview.
        
        Args:
            texture: Texture object to preview
        """
        self.current_texture = texture
        
        if texture is None:
            # Clear preview
            self.name_var.set("")
            self.type_var.set("")
            self.dimensions_var.set("")
            self.original_image = None
            self.processed_image = None
            self.original_pil_image = None
            self._update_preview()
            return
        
        # Update info
        self.name_var.set(os.path.basename(texture.get("path", "")))
        self.type_var.set(texture.get("type", "Unknown"))
        
        # Clear existing images
        self.original_image = None
        self.processed_image = None
        
        # Load the actual image
        try:
            file_path = texture.get("path", "")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            # Load image using PIL
            pil_image = Image.open(file_path)
            self.original_pil_image = pil_image
            
            # Update dimensions info
            self.dimensions_var.set(f"{pil_image.width} x {pil_image.height}")
            
            # Create PhotoImage for display
            scaled_image = self._create_scaled_image(pil_image)
            if scaled_image:
                self.original_image = ImageTk.PhotoImage(scaled_image)
            else:
                self.original_image = self._create_placeholder(300, 300, "Error")
            
            # Create processed image (for now, just a copy of original)
            self.processed_image = self.original_image
            
        except Exception as e:
            print(f"Error loading image: {e}")
            self.original_image = self._create_placeholder(300, 300, "Error")
            self.processed_image = self._create_placeholder(300, 300, "Error")
            self.dimensions_var.set("Error loading image")
        
        # Update preview
        self._update_preview()
    
    def _create_scaled_image(self, pil_image):
        """
        Create a scaled version of the PIL image to fit the canvas.
        
        Args:
            pil_image: PIL Image object
            
        Returns:
            Scaled PIL Image object
        """
        if not pil_image:
            return None
            
        try:
            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Use at least 300x300 if canvas is too small
            canvas_width = max(canvas_width, 300)
            canvas_height = max(canvas_height, 300)
            
            # Calculate scaled dimensions
            width, height = self._get_scaled_dimensions(pil_image.width, pil_image.height, canvas_width, canvas_height)
            
            # Resize image (use LANCZOS for best quality)
            if pil_image.mode in ["RGBA", "LA"]:
                # Handle images with alpha channel
                return pil_image.resize((width, height), Image.LANCZOS)
            else:
                # Convert other modes to RGB
                return pil_image.convert("RGB").resize((width, height), Image.LANCZOS)
                
        except Exception as e:
            print(f"Error creating scaled image: {e}")
            return None
    
    def _get_scaled_dimensions(self, width, height, canvas_width=None, canvas_height=None):
        """
        Get scaled dimensions to fit the canvas while maintaining aspect ratio.
        
        Args:
            width: Original width
            height: Original height
            canvas_width: Canvas width (optional)
            canvas_height: Canvas height (optional)
            
        Returns:
            Tuple of (scaled_width, scaled_height)
        """
        if canvas_width is None:
            canvas_width = self.canvas.winfo_width()
        if canvas_height is None:
            canvas_height = self.canvas.winfo_height()
        
        # Ensure minimum size
        canvas_width = max(canvas_width, 10)
        canvas_height = max(canvas_height, 10)
        
        # Calculate aspect ratios
        image_ratio = width / height
        canvas_ratio = canvas_width / canvas_height
        
        if image_ratio > canvas_ratio:
            # Image is wider than canvas
            scaled_width = canvas_width
            scaled_height = max(1, int(scaled_width / image_ratio))
        else:
            # Image is taller than canvas
            scaled_height = canvas_height
            scaled_width = max(1, int(scaled_height * image_ratio))
        
        return int(scaled_width), int(scaled_height)
    
    def _update_preview(self):
        """
        Update the preview display with the current texture.
        """
        # Clear canvas
        self.canvas.delete("all")
        
        if not self.original_image:
            # No image to display
            self.canvas.create_text(
                self.canvas.winfo_width() // 2,
                self.canvas.winfo_height() // 2,
                text="No texture selected",
                font=("Arial", 12)
            )
            return
        
        # Always show original image since we removed the view mode selection
        self.canvas.create_image(
            self.canvas.winfo_width() // 2,
            self.canvas.winfo_height() // 2,
            image=self.original_image,
            anchor=tk.CENTER
        )
    
    def _create_placeholder(self, width, height, text):
        """
        Create a placeholder image.
        
        Args:
            width: Image width
            height: Image height
            text: Text to display on the placeholder
            
        Returns:
            PhotoImage object
        """
        # Create a PhotoImage
        placeholder = tk.PhotoImage(width=width, height=height)
        
        # Fill with checkerboard pattern (simple placeholder)
        for x in range(width):
            for y in range(height):
                color = "gray85" if (x // 20 + y // 20) % 2 == 0 else "gray75"
                placeholder.put(color, (x, y))
        
        return placeholder
    
    def compare_original_and_processed(self, original, processed):
        """
        Display the original texture (processed comparison removed).
        
        Args:
            original: Original texture object
            processed: Processed texture object (not used)
        """
        # Set current texture
        self.set_current_texture(original)
        
        # Update preview
        self._update_preview()
