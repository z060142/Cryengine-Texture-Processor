#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PySide6 entry point for CryEngine Texture Processor.

The legacy Tkinter entry point is preserved as legacy_tk_main.py while the
application is migrated to Qt.
"""

import gc
import os
import sys
import time
import traceback

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.batch_processor import BatchProcessor
from language.language_manager import get_instance as get_language_manager
from language.language_manager import get_text
from model_processing.model_export_context import (
    attach_material_manifest,
    build_model_export_context,
)
from model_processing.texture_extractor import TextureExtractor
from output_formats.json_exporter import export_json
from output_formats.material_diagnostics_exporter import export_material_diagnostics
from output_formats.mtl_exporter import export_mtl
from ui_pyside.main_window import MainWindow
from ui_pyside.progress_dialog import ProgressDialog
from utils.config_manager import ConfigManager
from utils.dds_processor import DDSProcessor
from utils.rc_import_runner import RCImportRunner
from utils.thumbnail_generator import generate_thumbnail


def _show_error(parent, title, message):
    QMessageBox.critical(parent, title, message)


def _show_warning(parent, title, message):
    QMessageBox.warning(parent, title, message)


def _show_info(parent, title, message):
    QMessageBox.information(parent, title, message)


def main():
    gc.enable()

    try:
        import numpy as np

        np.seterr(all="warn")
        print(f"NumPy version: {np.__version__}")
    except ImportError:
        print("NumPy not available - some functionality may be limited")
    except Exception as e:
        print(f"Error configuring NumPy: {e}")

    config_manager = ConfigManager()
    language_manager = get_language_manager()
    saved_language = config_manager.get("language", "EN")
    if saved_language and saved_language != language_manager.get_current_language():
        language_manager.load_language(saved_language)

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(get_text("app.title", "CryEngine Texture Processor"))

    window = MainWindow()
    window.resize(1200, 800)

    def start_batch_processing(texture_groups=None, export_settings=None):
        print(
            "start_batch_processing called with "
            f"{len(texture_groups) if texture_groups else 'all'} groups and "
            f"{'provided' if export_settings else 'no'} settings."
        )

        texture_manager = window.texture_import_panel.texture_manager
        if not texture_manager:
            _show_error(window, get_text("export.error", "Error"), "Cannot access Texture Manager.")
            return False

        batch_processor = BatchProcessor(texture_manager)
        if texture_groups is None:
            texture_groups = texture_manager.get_all_groups()
            print(f"Retrieved {len(texture_groups)} groups from TextureManager.")

        settings = export_settings if export_settings is not None else window.export_settings_panel.get_settings()
        output_dir = settings.get("texture_output_directory", "")

        if not output_dir:
            output_dir = QFileDialog.getExistingDirectory(
                window,
                get_text("export.select_texture_directory", "Select Texture Output Directory"),
                os.getcwd(),
            )
            if not output_dir:
                return False
            settings["texture_output_directory"] = output_dir
            window.export_settings_panel.set_settings(settings)

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                window.export_settings_panel.update_directory_statuses()
            except Exception as e:
                _show_error(
                    window,
                    get_text("export.error", "Error"),
                    get_text(
                        "export.create_texture_dir_error",
                        "Failed to create texture output directory: {0}",
                    ).format(str(e)),
                )
                return False

        if not texture_groups:
            _show_warning(
                window,
                get_text("export.warning", "Warning"),
                get_text("export.no_textures", "No texture groups to process."),
            )
            return False

        batch_processor.set_output_dir(output_dir)
        batch_processor.set_settings(settings)

        window.update_status(get_text("status.preparing", "Preparing for batch processing..."))
        progress_dialog = ProgressDialog(window, get_text("progress.processing", "Processing Textures"))

        def progress_callback(progress, stage_text, current_task, status):
            progress_dialog.update_stage(stage_text)
            progress_dialog.update_progress(progress, current_task, status)
            if current_task:
                window.update_status(current_task)

        def cancel_callback():
            batch_processor.cancel()
            window.update_status(get_text("status.cancelling", "Cancelling..."))

        progress_dialog.set_cancel_callback(cancel_callback)
        batch_processor.set_progress_callback(progress_callback)
        batch_processor.process_all_groups()

        processing_successful = True
        while batch_processor.is_processing():
            if progress_dialog.is_cancelled():
                batch_processor.cancel()
                processing_successful = False
                break
            QApplication.processEvents()
            time.sleep(0.1)

        if progress_dialog.is_cancelled() or batch_processor.cancel_flag:
            processing_successful = False
            progress_dialog.show_completion(False, True)
            window.update_status(get_text("status.processing_cancelled", "Processing cancelled"))
        elif settings.get("generate_cry_dds", False):
            tif_files = []
            for group in texture_groups:
                for _, output_path in group.output.items():
                    if output_path and output_path.lower().endswith(".tif"):
                        tif_files.append(output_path)

            if tif_files and settings.get("output_format", "tif").lower() == "tif":
                progress_dialog.update_stage("Post-Process: Generating DDS")
                progress_dialog.update_progress(
                    0.0,
                    get_text("progress.generating_dds", "Generating CryEngine DDS files"),
                    "",
                )
                dds_processor = DDSProcessor()

                def dds_progress_callback(progress, current, status):
                    progress_dialog.update_progress(progress, current, status)
                    if current:
                        window.update_status(current)

                dds_processor.set_progress_callback(dds_progress_callback)
                dds_processor.process_tif_files(tif_files)

                while dds_processor.is_processing():
                    if progress_dialog.is_cancelled():
                        dds_processor.cancel()
                        processing_successful = False
                        break
                    QApplication.processEvents()
                    time.sleep(0.1)

                if progress_dialog.is_cancelled() or dds_processor.cancel_flag:
                    processing_successful = False
                    progress_dialog.show_completion(False, True)
                else:
                    progress_dialog.show_completion(True, True)
            else:
                progress_dialog.show_completion(True, True)
        else:
            progress_dialog.show_completion(True, True)

        if processing_successful and not progress_dialog.is_cancelled() and not batch_processor.cancel_flag:
            texture_report_path = batch_processor.texture_output_report_path
            if texture_report_path:
                report_summary = (batch_processor.texture_output_report or {}).get("summary", {})
                diagnostic_count = report_summary.get("diagnostic_count", 0)
                report_status = f"Texture diagnostics: {diagnostic_count}; report: {texture_report_path}"
                progress_dialog.update_progress(1.0, None, report_status)
                window.update_status(report_status)

        return processing_successful

    def run_model_mtl_export(settings, progress_dialog=None):
        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory")
        texture_manager = window.texture_import_panel.texture_manager
        imported_models = window.model_import_panel.imported_models_info

        if not imported_models:
            _show_info(window, get_text("export.info", "Info"), "No models have been imported yet.")
            return 0, 0, []

        texture_extractor = TextureExtractor()
        exported_count = 0
        error_count = 0
        error_messages = []
        total_models = len(imported_models)

        if progress_dialog:
            progress_dialog.update_stage("Exporting Models (MTL)")
            progress_dialog.update_progress(0.0, "Starting model export...", f"Found {total_models} models")

        for index, model_info in enumerate(imported_models):
            if progress_dialog and progress_dialog.is_cancelled():
                error_messages.append("MTL export cancelled by user.")
                error_count += total_models - index
                break

            model_path = model_info.get("path", "")
            model_filename = model_info.get("filename", "unknown_model")
            current_progress = (index + 1) / total_models
            if progress_dialog:
                progress_dialog.update_progress(
                    current_progress,
                    f"Processing: {model_filename}",
                    f"Model {index + 1} of {total_models}",
                )
                QApplication.processEvents()

            if not model_path or not os.path.exists(model_path):
                error_count += 1
                error_messages.append(f"Invalid model path: {model_path}")
                continue

            if model_info.get("is_dummy", False) or model_info.get("is_import_only", False):
                print(f"Skipping MTL export for failed/dummy/import-only model: {model_filename}")
                continue

            model_obj = model_info.get("model_obj")
            if not model_obj:
                print(f"Warning: No model object data available for {model_filename}")
                continue

            try:
                texture_refs = texture_extractor.extract(model_obj)
                export_context = build_model_export_context(
                    model_obj,
                    model_filename,
                    model_output_dir,
                    texture_output_dir,
                    texture_refs,
                    texture_manager,
                    settings.get("output_format", "tif"),
                )
                if not export_context.mtl_materials:
                    print(f"No processable material data found for {model_filename}. Skipping MTL export.")
                    continue

                success, result = export_mtl(
                    export_context.mtl_materials,
                    model_output_dir,
                    texture_output_dir,
                    export_context.mtl_filename,
                )
                if success:
                    exported_count += 1
                    print(f"Successfully exported MTL: {result}")
                    try:
                        diagnostics_path = export_material_diagnostics(
                            export_context.mtl_materials,
                            model_output_dir,
                            f"{export_context.base_filename}.material_diagnostics.json",
                            existing_submaterial_names=export_context.existing_submaterial_names,
                            source_model=model_filename,
                            artifact_kind="mtl",
                            source_materials=export_context.model_data.get("materials", []),
                        )
                        print(f"Successfully exported material diagnostics: {diagnostics_path}")
                    except Exception as diagnostics_error:
                        message = f"{model_filename}: failed to export material diagnostics: {diagnostics_error}"
                        print(f"Warning: {message}")
                        error_messages.append(message)
                else:
                    error_count += 1
                    error_messages.append(f"{model_filename}: {result}")
            except Exception as e:
                error_count += 1
                error_msg = f"Unexpected error exporting MTL for {model_filename}: {e}"
                print(error_msg)
                traceback.print_exc()
                error_messages.append(error_msg)

        if progress_dialog:
            progress_dialog.update_progress(
                1.0,
                "Model export complete" if not progress_dialog.is_cancelled() else "Model export cancelled",
                f"Exported: {exported_count} MTL, Errors: {error_count}",
            )

        return exported_count, error_count, error_messages

    def run_model_fbx_export(settings, progress_dialog=None):
        from model_processing.fbx_exporter import FbxExporter
        from model_processing.model_loader import ModelLoader

        model_output_dir = settings.get("model_output_directory")
        texture_output_dir = settings.get("texture_output_directory")
        texture_rel_dir = "textures"
        texture_manager = window.texture_import_panel.texture_manager
        imported_models = window.model_import_panel.imported_models_info

        if not imported_models:
            _show_info(window, get_text("export.info", "Info"), "No models have been imported yet.")
            return 0, 0, []

        model_loader = ModelLoader()
        fbx_exporter = FbxExporter()
        if not fbx_exporter.initialized or not model_loader.bpy:
            error_msg = "Blender Python API (bpy) is not available. Cannot export FBX."
            _show_error(window, get_text("export.error", "Error"), error_msg)
            return 0, 1, [error_msg]

        texture_extractor = TextureExtractor()
        exported_count = 0
        error_count = 0
        error_messages = []
        total_models = len(imported_models)

        if progress_dialog:
            progress_dialog.update_stage("Exporting Models (FBX & JSON)")
            progress_dialog.update_progress(0.0, "Starting FBX export...", f"Found {total_models} models")

        for index, model_info in enumerate(imported_models):
            if progress_dialog and progress_dialog.is_cancelled():
                error_messages.append("FBX export cancelled by user.")
                error_count += total_models - index
                break

            model_path = model_info.get("path", "")
            model_filename = model_info.get("filename", "unknown_model")
            current_progress = (index + 1) / total_models
            if progress_dialog:
                progress_dialog.update_progress(
                    current_progress,
                    f"Processing: {model_filename}",
                    f"Model {index + 1} of {total_models}",
                )
                QApplication.processEvents()

            if not model_path or not os.path.exists(model_path):
                error_count += 1
                error_messages.append(f"Invalid model path: {model_path}")
                continue

            if model_info.get("is_dummy", False) or model_info.get("is_import_only", False):
                print(f"Skipping FBX export for non-exportable model: {model_filename}")
                continue

            try:
                model_loader._clear_scene()
                reloaded_model = model_loader.load(model_path)
                if not reloaded_model or reloaded_model.get("is_dummy", False):
                    error_count += 1
                    error_messages.append(f"Failed to reload model: {model_filename}")
                    continue
                attach_material_manifest(reloaded_model, model_info)

                texture_refs = texture_extractor.extract(reloaded_model)
                export_context = build_model_export_context(
                    reloaded_model,
                    model_filename,
                    model_output_dir,
                    texture_output_dir,
                    texture_refs,
                    texture_manager,
                    settings.get("output_format", "tif"),
                    texture_rel_dir=texture_rel_dir,
                )
                if not export_context.fbx_texture_data:
                    print(f"No processed textures found for model {model_filename}. Skipping FBX export.")
                    continue

                os.makedirs(export_context.model_texture_dir, exist_ok=True)
                result = fbx_exporter.export(
                    reloaded_model,
                    export_context.fbx_output_path,
                    texture_dir=export_context.texture_rel_dir,
                    texture_data=export_context.fbx_texture_data,
                )

                json_success, json_result = export_json(
                    reloaded_model,
                    export_context.fbx_filename,
                    model_output_dir,
                    texture_output_dir,
                )
                try:
                    diagnostics_path = export_material_diagnostics(
                        reloaded_model.get("materials", []),
                        model_output_dir,
                        f"{export_context.base_filename}.material_diagnostics.json",
                        existing_submaterial_names=export_context.existing_submaterial_names,
                        source_model=export_context.fbx_filename,
                        artifact_kind="fbx_json",
                        material_manifest_info=reloaded_model.get("material_manifest"),
                        source_materials=reloaded_model.get("materials", []),
                    )
                    print(f"Successfully exported material diagnostics: {diagnostics_path}")
                except Exception as diagnostics_error:
                    message = f"{model_filename}: failed to export material diagnostics: {diagnostics_error}"
                    print(f"Warning: {message}")
                    error_messages.append(message)
                if json_success:
                    print(f"Successfully exported JSON configuration: {json_result}")
                    rc_exe_path = ConfigManager().get("rc_exe_path", "")
                    if rc_exe_path:
                        rc_result = RCImportRunner(rc_exe_path).run(
                            json_result,
                            source_fbx_path=export_context.fbx_output_path,
                        )
                        if rc_result.success:
                            print(f"Successfully generated RC output: {rc_result.expected_output_path}")
                        else:
                            print(f"Warning: RC import failed: {rc_result.error}")
                            if rc_result.stdout:
                                print(rc_result.stdout)
                            if rc_result.stderr:
                                print(rc_result.stderr)
                    else:
                        print("RC executable path is not configured; skipping RC import.")
                else:
                    print(f"Warning: Failed to export JSON for {model_filename}: {json_result}")

                if result:
                    exported_count += 1
                    thumbnail_path = os.path.join(
                        model_output_dir,
                        f"{export_context.base_filename}.cgf.thmb.png",
                    )
                    try:
                        generate_thumbnail(export_context.fbx_output_path, thumbnail_path)
                    except Exception as thumb_e:
                        print(f"Thumbnail generation failed for {model_filename}: {thumb_e}")
                else:
                    error_count += 1
                    error_messages.append(f"Failed to export FBX for {model_filename}")
            except Exception as e:
                error_count += 1
                error_msg = f"Unexpected error exporting FBX for {model_filename}: {e}"
                print(error_msg)
                traceback.print_exc()
                error_messages.append(error_msg)

        if progress_dialog:
            progress_dialog.update_progress(
                1.0,
                "Model export complete" if not progress_dialog.is_cancelled() else "Model export cancelled",
                f"Exported: {exported_count} FBX+JSON, Errors: {error_count}",
            )

        return exported_count, error_count, error_messages

    window.start_batch_processing = start_batch_processing
    window.run_model_mtl_export = run_model_mtl_export
    window.run_model_fbx_export = run_model_fbx_export
    window.show()

    try:
        return qt_app.exec()
    finally:
        print("Application closing, performing final cleanup...")
        gc.collect()


if __name__ == "__main__":
    sys.exit(main())
