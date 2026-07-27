#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DDS Processor

This module provides functionality for generating DDS files for CryEngine using RC.exe.
"""

import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from utils.config_manager import ConfigManager
from utils.image_processing import ImageProcessor

class DDSProcessor:
    """
    Class for processing TIF files into DDS files for CryEngine.
    """
    
    def __init__(self):
        """
        Initialize the DDS processor.
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
    
    def process_tif_files(self, tif_files, max_workers=12):
        """
        Process TIF files into DDS files.
        
        Args:
            tif_files: List of TIF file paths to process
            max_workers: Maximum number of worker threads
            
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
            target=self._process_thread,
            args=(tif_files, max_workers),
            daemon=True
        )
        self.processing_thread.start()
        
        return True
    
    def _process_thread(self, tif_files, max_workers):
        """
        Thread function to process TIF files.
        
        Args:
            tif_files: List of TIF file paths to process
            max_workers: Maximum number of worker threads
        """
        try:
            total_files = len(tif_files)
            
            # Exit if no files
            if total_files == 0:
                if self.progress_callback:
                    self.progress_callback(1.0, "No TIF files to process", "")
                return
            
            # Update progress
            if self.progress_callback:
                self.progress_callback(0.0, "Starting DDS generation", f"Found {total_files} TIF files")
            
            # Process files with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Start all tasks
                futures = {
                    executor.submit(self._process_tif_file, file_path, i, total_files): (i, file_path)
                    for i, file_path in enumerate(tif_files)
                }
                
                # Wait for all futures to complete
                completed = 0
                for future in futures:
                    try:
                        future.result()
                        completed += 1
                        
                        # Check if cancelled
                        if self.cancel_flag:
                            # Update progress with cancelled status
                            if self.progress_callback:
                                self.progress_callback(
                                    completed / total_files,
                                    "DDS generation cancelled",
                                    f"Processed {completed} of {total_files} files"
                                )
                            # Cancel all pending futures
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            break
                    except Exception as e:
                        print(f"Error in future: {e}")
            
            # Final progress update
            if self.progress_callback and not self.cancel_flag:
                self.progress_callback(
                    1.0,
                    "DDS generation complete",
                    f"Processed {completed} of {total_files} files"
                )
                
        except Exception as e:
            print(f"Error processing TIF files: {e}")
            if self.progress_callback:
                self.progress_callback(
                    0.0,
                    "Error during DDS generation",
                    f"Error: {str(e)}"
                )
    
    def _process_tif_file(self, tif_path, index, total):
        """
        Process a single TIF file with RC.exe.
        
        Args:
            tif_path: Path to the TIF file
            index: Index of the file in the list
            total: Total number of files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if processing was cancelled
            if self.cancel_flag:
                return False
                
            # Update progress
            if self.progress_callback:
                self.progress_callback(
                    index / total,
                    f"Processing {os.path.basename(tif_path)}",
                    f"File {index + 1} of {total}"
                )
            
            # Run RC.exe with the TIF file
            result = subprocess.run(
                [self.rc_exe_path, tif_path],
                check=False,
                capture_output=True,
                text=True
            )
            
            # Log the output
            print(f"RC.exe output for {tif_path}:")
            print(result.stdout)
            
            if result.returncode != 0:
                print(f"RC.exe error for {tif_path}:")
                print(result.stderr)
                return False
            
            # Generate thumbnail for DDS file
            thumbnail_path = f"{os.path.splitext(tif_path)[0]}.dds.thmb.png"
            ImageProcessor.generate_thumbnail(tif_path, thumbnail_path, (256, 256))
            
            return True
            
        except Exception as e:
            print(f"Error processing {tif_path}: {e}")
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
