#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Progress Dialog

This module provides a progress dialog UI component to display
progress information during lengthy operations.
"""

import tkinter as tk
from tkinter import ttk
from language.language_manager import get_text

class ProgressDialog:
    """
    Progress dialog UI component.
    """
    
    def __init__(self, parent, title=None, allow_cancel=True):
        """
        Initialize the progress dialog.
        
        Args:
            parent: Parent window
            title: Dialog title or None to use default
            allow_cancel: Whether to show cancel button
        """
        self.parent = parent
        self.cancelled = False
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title or get_text("progress.title", "Processing..."))
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        
        # Set minimum size
        self.dialog.minsize(400, 150)
        
        # Position dialog in center of parent
        self._center_window()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.dialog, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Stage label (New)
        self.stage_var = tk.StringVar(value="")
        self.stage_label = ttk.Label(
            self.main_frame,
            textvariable=self.stage_var,
            font=("TkDefaultFont", 10, "bold") # Make stage stand out
        )
        self.stage_label.pack(fill=tk.X, pady=(0, 5))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.main_frame,
            variable=self.progress_var,
            maximum=100.0,
            length=360,
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Current operation label
        self.current_var = tk.StringVar(value=get_text("progress.preparing", "Preparing..."))
        self.current_label = ttk.Label(
            self.main_frame,
            textvariable=self.current_var
        )
        self.current_label.pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(
            self.main_frame,
            textvariable=self.status_var
        )
        self.status_label.pack(fill=tk.X, pady=(0, 10))
        
        # Cancel button (if allowed)
        if allow_cancel:
            self.button_frame = ttk.Frame(self.main_frame)
            self.button_frame.pack(fill=tk.X)
            
            self.cancel_button = ttk.Button(
                self.button_frame,
                text=get_text("button.cancel", "Cancel"),
                command=self._on_cancel
            )
            self.cancel_button.pack(side=tk.RIGHT)
            
            # Bind Escape key to cancel
            self.dialog.bind("<Escape>", lambda e: self._on_cancel())
        
        # Close button (initially disabled, shown when complete)
        self.close_button = ttk.Button(
            self.main_frame,
            text=get_text("button.close", "Close"),
            command=self.close,
            state=tk.DISABLED
        )
        if not allow_cancel:
            self.close_button.pack(side=tk.RIGHT, pady=(10, 0))
        else:
            self.close_button.pack_forget()
        
        # Cancel callback
        self.cancel_callback = None
        
        # Prevent window close button
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close_request)
        
        # Update UI
        self.dialog.update()

    def update_stage(self, stage_text):
        """
        Update the stage description text.

        Args:
            stage_text: Text to display for the current stage
        """
        self.stage_var.set(stage_text)
        self.dialog.update() # Ensure immediate update
    
    def _center_window(self):
        """
        Center the dialog window on parent.
        """
        # Get parent geometry
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Get dialog size
        width = 400
        height = 150
        
        # Calculate position
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        
        # Set geometry
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def update_progress(self, progress, current=None, status=None):
        """
        Update progress dialog.
        
        Args:
            progress: Progress value (0.0 to 1.0)
            current: Current operation text
            status: Status text
        """
        # Update progress bar
        self.progress_var.set(progress * 100.0)
        
        # Update current operation text if provided
        if current is not None:
            self.current_var.set(current)
        
        # Update status text if provided
        if status is not None:
            self.status_var.set(status)
        
        # Update UI
        self.dialog.update()
    
    def set_cancel_callback(self, callback):
        """
        Set callback function to be called when cancel button is clicked.
        
        Args:
            callback: Callback function
        """
        self.cancel_callback = callback
    
    def _on_cancel(self):
        """
        Handle cancel button click.
        """
        self.cancelled = True
        if self.cancel_callback:
            self.cancel_callback()
        
        # Disable cancel button to prevent multiple clicks
        if hasattr(self, 'cancel_button'):
            self.cancel_button.config(state=tk.DISABLED)
    
    def _on_close_request(self):
        """
        Handle window close request (X button).
        """
        # Redirect to cancel button if operation in progress
        if not self.is_complete():
            self._on_cancel()
        else:
            self.close()
    
    def show_completion(self, success=True, allow_close=True):
        """
        Update dialog to show completion status.
        
        Args:
            success: Whether operation was successful
            allow_close: Whether to enable close button
        """
        # Set progress to 100%
        self.progress_var.set(100.0)
        
        # Update current text
        if success:
            self.current_var.set(get_text("progress.complete", "Operation complete"))
        else:
            self.current_var.set(get_text("progress.failed", "Operation failed"))
        
        # Hide cancel button if exists
        if hasattr(self, 'cancel_button'):
            self.cancel_button.pack_forget()
        
        # Show and enable close button if allowed
        if allow_close:
            self.close_button.config(state=tk.NORMAL)
            if hasattr(self, 'button_frame'):
                self.close_button.pack(in_=self.button_frame, side=tk.RIGHT)
            else:
                self.close_button.pack(side=tk.RIGHT, pady=(10, 0))
        
        # Update UI
        self.dialog.update()
    
    def is_complete(self):
        """
        Check if operation is complete (progress at 100%).
        
        Returns:
            True if complete, False otherwise
        """
        return self.progress_var.get() >= 99.9
    
    def is_cancelled(self):
        """
        Check if operation was cancelled.
        
        Returns:
            True if cancelled, False otherwise
        """
        return self.cancelled
    
    def close(self):
        """
        Close the dialog.
        """
        self.dialog.destroy()
