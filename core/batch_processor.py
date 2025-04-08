#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch Processor

This module provides functionality for batch processing texture groups.
"""

import os
import threading
import time
import shutil
from pathlib import Path
from intermediate_formats.albedo_processor import AlbedoProcessor
from intermediate_formats.normal_processor import NormalProcessor
from intermediate_formats.reflection_processor import ReflectionProcessor
from intermediate_formats.glossiness_processor import GlossinessProcessor
from intermediate_formats.height_processor import HeightProcessor
from intermediate_formats.ao_processor import AOProcessor
from intermediate_formats.arm_processor import ARMProcessor
from output_formats.diff_exporter import DiffExporter
from output_formats.spec_exporter import SpecExporter
from output_formats.ddna_exporter import DDNAExporter
from output_formats.displ_exporter import DisplExporter
from output_formats.emissive_exporter import EmissiveExporter
from output_formats.sss_exporter import SSSExporter

class BatchProcessor:
    """
    Class for batch processing texture groups.
    """
    
    def __init__(self, texture_manager):
        """
        Initialize the batch processor.
        
        Args:
            texture_manager: TextureManager instance
        """
        self.texture_manager = texture_manager
        self.output_dir = ""
        self.settings = {}
        self.progress_callback = None # Expected signature: callback(progress, stage_text, current_task, status)
        self.cancel_flag = False
        self.processing_thread = None
        self._temp_dir_path = None # To store the path for cleanup

        # Initialize processors
        self.albedo_processor = AlbedoProcessor()
        self.normal_processor = NormalProcessor()
        self.reflection_processor = ReflectionProcessor()
        self.glossiness_processor = GlossinessProcessor()
        self.height_processor = HeightProcessor()
        self.ao_processor = AOProcessor()
        self.arm_processor = ARMProcessor()
        
        # Initialize exporters
        self.diff_exporter = DiffExporter()
        self.spec_exporter = SpecExporter()
        self.ddna_exporter = DDNAExporter()
        self.displ_exporter = DisplExporter()
        self.emissive_exporter = EmissiveExporter()
        self.sss_exporter = SSSExporter()
    
    def set_output_dir(self, output_dir):
        """
        Set output directory for processed textures.
        
        Args:
            output_dir: Output directory path
        """
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def set_settings(self, settings):
        """
        Set processing settings.
        
        Args:
            settings: Dictionary of processing settings
        """
        self.settings = settings
    
    def set_progress_callback(self, callback):
        """
        Set progress callback function.
        
        Args:
            callback: Callback function taking progress (0.0-1.0), stage_text, current_task, and status
        """
        self.progress_callback = callback
    
    def process_all_groups(self):
        """
        Process all texture groups in the texture manager.
        
        Returns:
            True if started successfully, False otherwise
        """
        # Check if already processing
        if self.processing_thread and self.processing_thread.is_alive():
            return False
            
        # Reset cancel flag
        self.cancel_flag = False
        
        # Check if we have an output directory
        if not self.output_dir:
            return False
            
        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self._process_thread,
            daemon=True  # Make thread a daemon so it doesn't block program exit
        )
        self.processing_thread.start()
        
        return True
    
    def _process_thread(self):
        """
        Thread function to process all texture groups.
        Handles temporary directory creation and cleanup.
        """
        # --- Temporary Directory Management ---
        self._temp_dir_path = None # Reset path for this run
        try:
            # Define and create the temporary directory for this batch run
            temp_dir_base = Path(__file__).parent.parent / ".texproc_temp"
            self._temp_dir_path = temp_dir_base / str(os.getpid())
            os.makedirs(self._temp_dir_path, exist_ok=True)
            print(f"Batch Processor: Created temporary directory: {self._temp_dir_path}")

            # --- Main Processing Logic ---
            # Get texture groups
            texture_groups = self.texture_manager.get_all_groups()
            total_groups = len(texture_groups)
            
            # --- Stage 1: Generate Intermediate Formats ---
            stage1_text = "Stage 1/2: Generating Intermediates"
            self._update_progress(0.0, stage1_text, "Starting...", f"Found {total_groups} texture groups")

            if total_groups == 0:
                self._update_progress(1.0, stage1_text, "No texture groups to process", "")
                return

            for i, group in enumerate(texture_groups):
                if self.cancel_flag:
                    self._update_progress(i / (total_groups * 2), stage1_text, "Processing cancelled", f"Processed {i} of {total_groups} groups")
                    return
                
                progress_stage1 = i / (total_groups * 2) # Progress within 0.0 to 0.5
                self._update_progress(
                    progress_stage1,
                    stage1_text,
                    f"Processing {group.base_name}",
                    f"Group {i+1} of {total_groups}"
                )
                self._generate_intermediate_formats(group)
                time.sleep(0.01)

            # --- Stage 2: Generate Output Formats ---
            stage2_text = "Stage 2/2: Exporting Textures"
            self._update_progress(0.5, stage2_text, "Starting export...", "") # Start stage 2 at 50%

            for i, group in enumerate(texture_groups):
                if self.cancel_flag:
                    self._update_progress(0.5 + (i / (total_groups * 2)), stage2_text, "Processing cancelled", f"Processed {i} of {total_groups} groups")
                    return

                progress_stage2 = 0.5 + (i / (total_groups * 2)) # Progress within 0.5 to 1.0
                self._update_progress(
                    progress_stage2,
                    stage2_text,
                    f"Exporting {group.base_name}",
                    f"Group {i+1} of {total_groups}"
                )
                self._generate_output_formats(group)
                time.sleep(0.01)

            # Final progress update
            self._update_progress(
                1.0,
                "Batch processing complete", # Keep final message simple
                "Finished",
                f"Processed {total_groups} texture groups"
            )

        except Exception as e:
            # Update progress with error - report current stage if possible
            current_stage = stage2_text if 'stage2_text' in locals() else stage1_text
            self._update_progress(
                self.progress_var.get() / 100.0 if hasattr(self, 'progress_var') else 0.0, # Try to get last known progress
                current_stage,
                "Error during batch processing",
                f"Error: {str(e)}"
            )
            
            # Re-raise for debugging
            raise
        finally:
            # --- Cleanup Temporary Directory ---
            if self._temp_dir_path and os.path.exists(self._temp_dir_path):
                try:
                    shutil.rmtree(self._temp_dir_path)
                    print(f"Batch Processor: Cleaned up temporary directory: {self._temp_dir_path}")
                except Exception as cleanup_e:
                    print(f"Batch Processor: Error cleaning up temporary directory {self._temp_dir_path}: {cleanup_e}")
            self._temp_dir_path = None # Clear path after cleanup attempt
            # --- End Cleanup ---

    def _process_group(self, group):
        """
        Process a single texture group.
        
        Args:
            group: TextureGroup instance
        """
        try:
            # Step 1: Generate intermediate formats
            self._generate_intermediate_formats(group)
            
            # Step 2: Generate output formats
            self._generate_output_formats(group)
            
        except Exception as e:
            print(f"Error processing group {group.base_name}: {str(e)}")
    
    def _generate_intermediate_formats(self, group):
        """
        Generate intermediate formats for a texture group.
        
        Args:
            group: TextureGroup instance
        """
        # Process ARM texture if present
        if group.has_texture("arm"):
            arm_texture = group.textures["arm"]
            arm_result = self.arm_processor.process(arm_texture)
            
            if arm_result:
                # Store the *intermediate* textures (with paths to saved files)
                # into the group's intermediate dictionary.
                # This makes them the primary source for subsequent steps.
                if arm_result.get("ao"):
                    print("Storing AO extracted from ARM into intermediates.")
                    group.intermediate["ao"] = arm_result.get("ao") 
                if arm_result.get("roughness"):
                    print("Storing Roughness extracted from ARM into intermediates.")
                    group.intermediate["roughness"] = arm_result.get("roughness")
                if arm_result.get("metallic"):
                    print("Storing Metallic extracted from ARM into intermediates.")
                    group.intermediate["metallic"] = arm_result.get("metallic")
                # We no longer need to put these back into group.textures
        
        # Generate Albedo (No change needed here, it uses textures['diffuse'] or textures['albedo'])
        if group.has_texture("diffuse"):
            if group.has_texture("ao"):
                group.intermediate["albedo"] = self.albedo_processor.process_from_diffuse(
                    group.textures["diffuse"],
                    group.textures["ao"]
                )
            else:
                group.intermediate["albedo"] = self.albedo_processor.process_from_diffuse(
                    group.textures["diffuse"]
                )
        elif group.has_texture("albedo"):
            group.intermediate["albedo"] = self.albedo_processor.process_from_basecolor(
                group.textures["albedo"]
            )
        elif group.has_texture("diffuse") and group.has_texture("metallic") and self.settings.get("process_metallic", True):
            group.intermediate["albedo"] = self.albedo_processor.process_from_diffuse_and_metallic(
                group.textures["diffuse"],
                group.textures["metallic"]
            )
        
        # Generate Normal
        if group.has_texture("normal"):
            # Determine if DirectX or OpenGL format
            from core.name_parser import TextureNameParser
            name_parser = TextureNameParser()
            
            is_directx = name_parser.is_directx_normal(
                group.textures["normal"].get("filename", "")
            )
            
            group.intermediate["normal"] = self.normal_processor.process(
                group.textures["normal"],
                is_directx
            )
        elif group.has_texture("displacement") or group.has_texture("height"):
            # Generate normal from height/displacement
            height_texture = group.textures.get("displacement") or group.textures.get("height")
            strength = self.settings.get("normal_from_height_strength", 10.0)
            
            group.intermediate["normal"] = self.normal_processor.generate_from_height(
                height_texture,
                strength
            )
        
        # Generate Reflection
        if group.has_texture("specular"):
            group.intermediate["reflection"] = self.reflection_processor.process_from_specular(
                group.textures["specular"],
                group.intermediate.get("glossiness")
            )
        elif group.has_texture("metallic") and group.has_texture("diffuse") and self.settings.get("process_metallic", True):
            group.intermediate["reflection"] = self.reflection_processor.process_from_metallic(
                group.textures["metallic"], # Still uses original metallic texture if needed
                group.textures["diffuse"]
            )
        elif group.intermediate.get("metallic"): # Check intermediate metallic (from ARM)
             # Check if diffuse exists for processing
             diffuse_for_refl = group.textures.get("diffuse")
             if diffuse_for_refl and self.settings.get("process_metallic", True):
                 print("Processing reflection from intermediate metallic (from ARM) and diffuse.")
                 # NOTE: process_from_metallic expects texture objects, but intermediate only has path.
                 # We might need to load the intermediate metallic image here, or refactor 
                 # reflection_processor to accept paths or load images itself. (DONE in previous step)
                 # For now, let's assume reflection_processor needs adjustment or this path won't be hit often. (No longer needed)
                 # TODO: Review reflection_processor logic if this becomes an issue. (No longer needed)
                 # Uncomment the actual call:
                 group.intermediate["reflection"] = self.reflection_processor.process_from_metallic(
                     group.intermediate["metallic"], # Pass intermediate object (contains path)
                     diffuse_for_refl
                 )
                 # print("WARN: Reflection processing from intermediate metallic not fully implemented yet.") # Remove warning
             else:
                 print("Skipping reflection generation from intermediate metallic (missing diffuse or setting disabled).")


        # --- Ensure Reliable Intermediate Glossiness ---
        # This call remains the same. ensure_intermediate_glossiness will now correctly
        # find the intermediate roughness path saved by arm_processor if it exists.
        # This single call now handles finding the best source (gloss, intermediate rough, original rough) 
        # and after attempting to process standalone gloss/roughness.
        # It will find the best source (gloss, intermediate rough, original rough) 
        # and create a standardized intermediate gloss file.
        intermediate_gloss_texture = self.glossiness_processor.ensure_intermediate_glossiness(group, self.settings)
        if intermediate_gloss_texture:
            # Store the result (which contains the path to the saved intermediate file)
            group.intermediate["glossiness"] = intermediate_gloss_texture 
        else:
             # If ensure_intermediate_glossiness failed, remove any potentially invalid 
             # glossiness entry from previous steps to avoid confusing the exporter.
             if "glossiness" in group.intermediate:
                 print("Removing potentially invalid intermediate glossiness entry.")
                 del group.intermediate["glossiness"]
        # --- End Ensure Intermediate Glossiness ---

        # Generate Height
        if group.has_texture("displacement") or group.has_texture("height"):
            height_texture = group.textures.get("displacement") or group.textures.get("height")
            group.intermediate["height"] = self.height_processor.process(height_texture)
        
        # Generate AO - Only process standalone AO if not already generated from ARM
        if "ao" not in group.intermediate and group.has_texture("ao"):
             print("Processing standalone AO map.")
             group.intermediate["ao"] = self.ao_processor.process(group.textures["ao"])
        elif "ao" in group.intermediate:
             print("Using AO intermediate (likely from ARM).")
        else:
             print("No AO source found.")
    
    def _generate_output_formats(self, group):
        """
        Generate output formats for a texture group.
        
        Args:
            group: TextureGroup instance
        """
        # Get texture types to export from settings
        texture_types = self.settings.get("texture_types", {})
        
        # Export _diff
        if texture_types.get("diff", True):
            output_path = self.diff_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["diff"] = output_path
        
        # Export _spec
        if texture_types.get("spec", True):
            output_path = self.spec_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["spec"] = output_path
        
        # Export _ddna
        if texture_types.get("ddna", True):
            output_path = self.ddna_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["ddna"] = output_path
        
        # Export _displ
        if texture_types.get("displ", True):
            output_path = self.displ_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["displ"] = output_path
        
        # Export _emissive
        if texture_types.get("emissive", True):
            output_path = self.emissive_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["emissive"] = output_path
        
        # Export _sss
        if texture_types.get("sss", True):
            output_path = self.sss_exporter.export(group, self.settings, self.output_dir)
            if output_path:
                group.output["sss"] = output_path

    # Corrected function definition to accept stage_text
    def _update_progress(self, progress, stage_text, current=None, status=None):
        """
        Update progress callback if available.
        
        Args:
            progress: Progress value (0.0-1.0)
            stage_text: Text describing the current major stage
            current: Current specific operation text
            status: Status text (e.g., group count)
        """
        if self.progress_callback:
            # Call with the new signature, ensuring all args are passed
            self.progress_callback(progress, stage_text, current, status)

    def cancel(self):
        """
        Cancel ongoing processing.
        """
        self.cancel_flag = True
        
        # Wait a bit for thread to notice cancellation
        if self.processing_thread and self.processing_thread.is_alive():
            # Don't join, as it might hang if thread is stuck
            pass
    
    def is_processing(self):
        """
        Check if processing is ongoing.
        
        Returns:
            True if processing, False otherwise
        """
        return self.processing_thread is not None and self.processing_thread.is_alive()
