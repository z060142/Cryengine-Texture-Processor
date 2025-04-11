#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CGF Processor

This module provides functionality for generating CGF files for CryEngine using RC.exe.
"""

import os
import subprocess
import threading
from utils.config_manager import ConfigManager

class CGFProcessor:
    """
    Class for processing JSON config files into CGF files for CryEngine.
    """
    
    def __init__(self):
        """
        Initialize the CGF processor.
        """
        self.config_manager = ConfigManager()
        self.rc_exe_path = self.config_manager.get("rc_exe_path", "")
        self.processing_thread = None
        self.cancel_flag = False
        self.progress_callback = None
    
    def set_progress_callback(self, callback):
        """
        Set progress callback function.
        
        Args:
            callback: Callback function taking progress (0.0-1.0), current task, and status
        """
        self.progress_callback = callback
    
    def process_json_file(self, json_file, output_file=None, overwrite=True):
        """
        Process a JSON config file into a CGF file.
        
        Args:
            json_file (str): Path to the JSON configuration file
            output_file (str, optional): Path to the desired output CGF file. 
                                         If None, will use the json filename with .cgf extension
            overwrite (bool): Whether to overwrite existing CGF files
            
        Returns:
            True if processing started successfully, False otherwise
        """
        # Check if RC.exe path is set
        if not self.rc_exe_path:
            print("RC.exe path not set")
            return False
        
        # Check if RC.exe exists
        if not os.path.exists(self.rc_exe_path):
            print(f"RC.exe not found at {self.rc_exe_path}")
            return False
        
        # Check if already processing
        if self.processing_thread and self.processing_thread.is_alive():
            return False
            
        # Reset cancel flag
        self.cancel_flag = False
        
        # If no output file provided, derive from json file
        if not output_file:
            base_name = os.path.splitext(json_file)[0]
            output_file = f"{base_name}.cgf"
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_thread,
            args=(json_file, output_file, overwrite),
            daemon=True
        )
        self.processing_thread.start()
        
        return True
    
    def process_json_files(self, json_files, output_dir=None, overwrite=True):
        """
        Process multiple JSON config files into CGF files.
        
        Args:
            json_files (list): List of JSON file paths to process
            output_dir (str, optional): Directory to save CGF files. If None, 
                                         CGF files will be saved in the same directory as JSON files
            overwrite (bool): Whether to overwrite existing CGF files
            
        Returns:
            True if processing started successfully, False otherwise
        """
        # Check if RC.exe path is set
        if not self.rc_exe_path:
            print("RC.exe path not set")
            return False
        
        # Check if RC.exe exists
        if not os.path.exists(self.rc_exe_path):
            print(f"RC.exe not found at {self.rc_exe_path}")
            return False
        
        # Check if already processing
        if self.processing_thread and self.processing_thread.is_alive():
            return False
            
        # Reset cancel flag
        self.cancel_flag = False
        
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_files_thread,
            args=(json_files, output_dir, overwrite),
            daemon=True
        )
        self.processing_thread.start()
        
        return True
    
    def _process_files_thread(self, json_files, output_dir, overwrite):
        """
        Thread function to process multiple JSON files.
        
        Args:
            json_files (list): List of JSON file paths to process
            output_dir (str): Directory to save CGF files
            overwrite (bool): Whether to overwrite existing CGF files
        """
        try:
            total_files = len(json_files)
            
            # Exit if no files
            if total_files == 0:
                if self.progress_callback:
                    self.progress_callback(1.0, "No JSON files to process", "")
                return
            
            # Update progress
            if self.progress_callback:
                self.progress_callback(0.0, "Starting CGF generation", f"Found {total_files} JSON files")
            
            # Process each file
            completed = 0
            for i, json_file in enumerate(json_files):
                # Check if cancelled
                if self.cancel_flag:
                    if self.progress_callback:
                        self.progress_callback(
                            completed / total_files,
                            "CGF generation cancelled",
                            f"Processed {completed} of {total_files} files"
                        )
                    break
                
                # Update progress
                if self.progress_callback:
                    self.progress_callback(
                        i / total_files,
                        f"Processing {os.path.basename(json_file)}",
                        f"File {i + 1} of {total_files}"
                    )
                
                # Determine output file path
                if output_dir:
                    base_name = os.path.splitext(os.path.basename(json_file))[0]
                    output_file = os.path.join(output_dir, f"{base_name}.cgf")
                else:
                    base_name = os.path.splitext(json_file)[0]
                    output_file = f"{base_name}.cgf"
                
                # Process the file
                success = self._process_json_file(json_file, output_file, overwrite)
                if success:
                    completed += 1
            
            # Final progress update
            if self.progress_callback and not self.cancel_flag:
                self.progress_callback(
                    1.0,
                    "CGF generation complete",
                    f"Processed {completed} of {total_files} files"
                )
                
        except Exception as e:
            print(f"Error processing JSON files: {e}")
            if self.progress_callback:
                self.progress_callback(
                    0.0,
                    "Error during CGF generation",
                    f"Error: {str(e)}"
                )
    
    def _process_thread(self, json_file, output_file, overwrite):
        """
        Thread function to process a single JSON file.
        
        Args:
            json_file (str): Path to the JSON configuration file
            output_file (str): Path to the output CGF file
            overwrite (bool): Whether to overwrite existing CGF files
        """
        try:
            # Update progress
            if self.progress_callback:
                self.progress_callback(
                    0.0,
                    f"Processing {os.path.basename(json_file)}",
                    f"Converting to {os.path.basename(output_file)}"
                )
            
            # Process the file
            success = self._process_json_file(json_file, output_file, overwrite)
            
            # Final progress update
            if self.progress_callback:
                if success:
                    self.progress_callback(
                        1.0,
                        "CGF generation complete",
                        f"Created {os.path.basename(output_file)}"
                    )
                else:
                    self.progress_callback(
                        0.0,
                        "CGF generation failed",
                        f"Failed to create {os.path.basename(output_file)}"
                    )
                
        except Exception as e:
            print(f"Error processing JSON file: {e}")
            if self.progress_callback:
                self.progress_callback(
                    0.0,
                    "Error during CGF generation",
                    f"Error: {str(e)}"
                )
    
    def _process_json_file(self, json_file, output_file, overwrite):
        """
        Process a single JSON file with RC.exe.
        
        Args:
            json_file (str): Path to the JSON configuration file
            output_file (str): Path to the output CGF file
            overwrite (bool): Whether to overwrite existing CGF files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if processing was cancelled
            if self.cancel_flag:
                return False
            
            # Check if JSON file exists
            if not os.path.exists(json_file):
                print(f"JSON file not found: {json_file}")
                return False
            
            # Check if output file exists and overwrite is False
            if os.path.exists(output_file) and not overwrite:
                print(f"Output file already exists: {output_file}")
                return False
            
            # Get output extension (cgf by default)
            output_ext = os.path.splitext(output_file)[1].lstrip('.').lower()
            if not output_ext:
                output_ext = "cgf"
            
            # Get output filename without path
            output_filename = os.path.basename(output_file)
            
            # Prepare RC.exe command
            # Format: RC.exe input.json /overwriteextension=fbx /overwritefilename="output.cgf"
            cmd = [
                self.rc_exe_path,
                json_file,
                "/overwriteextension=fbx"
            ]
            
            # Add output filename if needed
            if output_filename:
                cmd.append(f'/overwritefilename="{output_filename}"')
            
            # Log the command
            print(f"Running RC.exe command: {' '.join(cmd)}")
            
            # Run RC.exe
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True
            )
            
            # Log the output
            print(f"RC.exe output for {json_file}:")
            print(result.stdout)
            
            if result.returncode != 0:
                print(f"RC.exe error for {json_file}:")
                print(result.stderr)
                return False
            
            # Check if output file was created
            if not os.path.exists(output_file):
                print(f"Output file not created: {output_file}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            return False
    
    def cancel(self):
        """
        Cancel ongoing processing.
        """
        self.cancel_flag = True
    
    def is_processing(self):
        """
        Check if processing is ongoing.
        
        Returns:
            True if processing, False otherwise
        """
        return self.processing_thread is not None and self.processing_thread.is_alive()