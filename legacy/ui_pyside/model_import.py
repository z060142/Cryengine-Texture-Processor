#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Model import panel for the PySide6 UI."""

import json
import os

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from language.language_manager import get_text
from model_processing.material_index_assigner import build_omitted_material_diagnostics
from model_processing.material_slot_table import build_material_slot_records
from model_processing.material_manifest import (
    discover_material_manifest,
    load_material_manifest,
    material_manifest_summary,
    material_manifest_table_diagnostics,
    material_manifest_table_rows,
)
from model_processing.model_loader import ModelLoader
from model_processing.texture_extractor import TextureExtractor
from output_formats.cryengine_mtl_schema import exported_texture_map_policy
from output_formats.material_diagnostics_exporter import collect_mtl_texture_map_diagnostics
from tools.blender_material_inspector import inspect_fbx_materials
from tools.rc_smoke_test import material_specs_from_manifest, run_rc_smoke_test
from ui_pyside.progress_dialog import ProgressDialog
from utils.config_manager import ConfigManager


AUTHORITATIVE_MODEL_LOAD_STATUS = {"", "loaded"}
LOAD_STATUS_LABELS = {
    "": "loaded",
    "loaded": "loaded",
    "import_only": "import_only (filesystem texture scan)",
    "dummy": "dummy (model load failed)",
    "error": "error",
}
SOURCE_MODE_LABELS = {
    "": "unknown",
    "blender": "blender material data",
    "filesystem_import_only": "filesystem scan (import_only)",
    "filesystem_no_bpy": "filesystem scan (no bpy)",
    "filesystem_legacy": "filesystem scan (legacy)",
}


def _degraded_model_load_diagnostics(model_data):
    load_status = (model_data or {}).get("load_status", "")
    if load_status in AUTHORITATIVE_MODEL_LOAD_STATUS:
        return []
    return [
        {
            "severity": "warning",
            "code": "degraded_model_load_status",
            "material": "",
            "fbx_slot": None,
            "sub_index": None,
            "load_status": load_status,
            "load_warning": model_data.get("load_warning", ""),
            "load_error": model_data.get("load_error", ""),
            "message": (
                "Model was loaded in a degraded mode. Material and texture data may come from fallback recovery paths."
            ),
        }
    ]


def _degraded_texture_reference_diagnostics(material_name, material):
    evidence = material.get("texture_ref_evidence", [])
    source_modes = sorted(
        {
            item.get("source_mode", "")
            for item in evidence
            if item.get("source_mode", "") not in {"", "blender"}
        }
    )
    if not source_modes:
        return []
    return [
        {
            "severity": "warning",
            "code": "degraded_texture_reference_source",
            "material": material_name,
            "fbx_slot": material.get("index"),
            "sub_index": material.get("sub_index"),
            "source_modes": source_modes,
            "texture_ref_evidence": evidence,
            "message": (
                "Texture references include filesystem-scan fallback evidence instead of authoritative Blender data."
            ),
        }
    ]


def _rc_unassigned_material_diagnostics(smoke_info):
    diagnostics = []
    for item in (smoke_info or {}).get("unassigned_slot_diagnostics", []):
        slot = item.get("slot")
        diagnostic_type = item.get("type", "")
        request_name = item.get("request_name", "")
        mtl_name = item.get("mtl_slot_name", "")
        severity = "hazard" if diagnostic_type == "used_unassigned_material" or not item.get("ok", True) else "info"
        if diagnostic_type == "used_unassigned_material":
            message = (
                "CGF geometry uses an unassigned placeholder material. Fix the source material assignment before export."
            )
        elif diagnostic_type == "gap_unassigned_placeholder":
            message = "Unassigned material slot is preserved as an index gap placeholder."
        elif diagnostic_type == "trailing_unassigned_placeholder":
            message = "Trailing unassigned material slot is an unused RC placeholder."
        else:
            message = "RC reported an unassigned material placeholder."
        diagnostics.append(
            {
                "severity": severity,
                "code": diagnostic_type or "unassigned_material_placeholder",
                "material": request_name or mtl_name,
                "fbx_slot": slot,
                "sub_index": slot,
                "request_name": request_name,
                "mtl_slot_name": mtl_name,
                "used_by_cgf": item.get("used_by_cgf"),
                "max_used_material_id": item.get("max_used_material_id"),
                "message": message,
            }
        )
    return diagnostics


def _rc_cgf_material_id_diagnostics(smoke_info):
    diagnostics = []
    for check in (smoke_info or {}).get("cgf_material_id_alignment_checks", []):
        if check.get("ok", False):
            continue
        material_id = check.get("material_id")
        request_name = check.get("request_name", "")
        mtl_name = check.get("mtl_slot_name", "")
        if check.get("used_unassigned"):
            message = "CGF material id uses an unassigned placeholder material."
        elif not check.get("in_request", False) and not check.get("in_mtl", False):
            message = "CGF material id is missing from both the RC request and generated MTL slot table."
        elif not check.get("in_request", False):
            message = "CGF material id is missing from the RC request material table."
        elif not check.get("in_mtl", False):
            message = "CGF material id is missing from the generated MTL slot table."
        else:
            message = "CGF material id did not align with the RC request and generated MTL."
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "cgf_material_id_alignment_mismatch",
                "material": request_name or mtl_name,
                "fbx_slot": material_id,
                "sub_index": material_id,
                "material_id": material_id,
                "request_name": request_name,
                "mtl_slot_name": mtl_name,
                "in_request": check.get("in_request"),
                "in_mtl": check.get("in_mtl"),
                "used_unassigned": check.get("used_unassigned"),
                "message": message,
            }
        )
    return diagnostics


def _rc_material_slot_evidence_diagnostics(smoke_info):
    diagnostics = []
    for row in (smoke_info or {}).get("material_slot_evidence_rows", []):
        if row.get("ok", False):
            continue
        slot = row.get("slot")
        status = row.get("status", "material_slot_evidence_mismatch")
        request_names = row.get("request_names", []) or []
        manifest_names = row.get("manifest_names", []) or []
        material = (
            (request_names[0] if request_names else "")
            or row.get("mtl_name", "")
            or row.get("cgf_mtl_name", "")
            or (manifest_names[0] if manifest_names else "")
        )
        diagnostics.append(
            {
                "severity": "hazard",
                "code": status,
                "material": material,
                "fbx_slot": slot,
                "sub_index": slot,
                "slot": slot,
                "manifest_names": manifest_names,
                "request_names": request_names,
                "mtl_slot_name": row.get("mtl_name", ""),
                "cgf_mtl_name": row.get("cgf_mtl_name", ""),
                "used_by_cgf": row.get("used_by_cgf"),
                "message": "Material slot evidence row does not align across manifest, request, MTL, and CGF.",
            }
        )
    return diagnostics


def _mtl_texture_map_diagnostics(material_name, record):
    fbx_id = record.get("fbx_material_id")
    fbx_slot = (
        fbx_id - 1
        if isinstance(fbx_id, int) and not isinstance(fbx_id, bool) and fbx_id >= 1
        else record["material"].get("index")
    )
    report_item = {
        "name": material_name,
        "fbx_slot": fbx_slot,
        "sub_index": record["sub_index"],
        "mtl_texture_map_policy": exported_texture_map_policy(record["material"].get("textures", {})),
    }
    return collect_mtl_texture_map_diagnostics(report_item)


def collect_model_material_diagnostics(model_data):
    diagnostics = _degraded_model_load_diagnostics(model_data or {})
    rc_smoke = (model_data or {}).get("rc_material_smoke", {})
    diagnostics.extend(_rc_unassigned_material_diagnostics(rc_smoke))
    diagnostics.extend(_rc_cgf_material_id_diagnostics(rc_smoke))
    diagnostics.extend(_rc_material_slot_evidence_diagnostics(rc_smoke))
    materials = model_data.get("materials", []) if model_data else []
    records = build_material_slot_records(
        materials,
        material_manifest_info=(model_data or {}).get("material_manifest"),
    )
    diagnostics.extend(material_manifest_table_diagnostics((model_data or {}).get("material_manifest")))
    diagnostics.extend(build_omitted_material_diagnostics(materials, records))
    for record in records:
        diagnostics.extend(_degraded_texture_reference_diagnostics(record["clean_name"], record["material"]))
        diagnostics.extend(_mtl_texture_map_diagnostics(record["clean_name"], record))
        for diagnostic in record.get("diagnostics", []):
            diagnostics.append(
                {
                    **diagnostic,
                    "source_order": record["source_order"],
                    "assignment_reason": diagnostic.get("assignment_reason", record["reason"]),
                    "original_name": record["original_name"],
                    "polygon_count": record["material"].get("polygon_count"),
                    "used_by_polygons": record["material"].get("used_by_polygons"),
                    "mesh_names": record["material"].get("mesh_names", []),
                    "material_names": record["material"].get("material_names", []),
                    "slot_name_conflict": record["material"].get("slot_name_conflict", False),
                }
            )
    return diagnostics


def load_model_material_manifest(model_path):
    manifest_path = discover_material_manifest(model_path)
    manifest = load_material_manifest(manifest_path)
    return {
        "path": manifest_path,
        "manifest": manifest,
        "summary": material_manifest_summary(manifest, manifest_path) if manifest else {},
        "materials": material_manifest_table_rows(manifest),
    }


def material_manifest_summary_text(material_manifest_info):
    summary = (material_manifest_info or {}).get("summary", {})
    if not summary:
        return "not found"
    kind = summary.get("kind") or "material manifest"
    return f"{summary.get('material_count', 0)} slots / {summary.get('polygon_count', 0)} polygons ({kind})"


def generate_model_material_manifest(model_path, inspector_func=inspect_fbx_materials):
    inspector_func("", model_path)
    return load_model_material_manifest(model_path)


def default_rc_smoke_work_dir(model_path):
    model_path = os.path.abspath(model_path)
    model_dir = os.path.dirname(model_path)
    model_stem = os.path.splitext(os.path.basename(model_path))[0] or "model"
    return os.path.join(model_dir, f"{model_stem}_rc_smoke_work")


def _load_rc_material_report(report_path):
    if not report_path or not os.path.exists(report_path):
        return {}
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def _alignment_ok(report, key):
    alignment = (report or {}).get(key, {})
    if not alignment:
        return None
    return alignment.get("ok")


def _material_id_alignment(report):
    return (report or {}).get("cgf_material_id_alignment", {}) or {}


def _material_report_summary(report):
    return (report or {}).get("summary", {}) or {}


def run_model_material_rc_smoke(
    model_path,
    rc_exe_path,
    work_dir=None,
    smoke_runner=run_rc_smoke_test,
    material_spec_loader=material_specs_from_manifest,
):
    work_dir = os.path.abspath(work_dir or default_rc_smoke_work_dir(model_path))
    asset_name = os.path.splitext(os.path.basename(model_path))[0] or "model"
    result_info = {
        "success": False,
        "work_dir": work_dir,
        "rc_exe_path": rc_exe_path or "",
        "source_fbx_path": os.path.abspath(model_path) if model_path else "",
        "material_report_path": "",
        "semantic_alignment_ok": None,
        "cgf_material_id_alignment_ok": None,
        "cgf_material_id_alignment_checks": [],
        "unassigned_slot_diagnostics": [],
        "unassigned_slot_diagnostics_ok": None,
        "material_report_summary": {},
        "error": "",
    }

    try:
        material_specs = material_spec_loader(model_path)
    except Exception as e:
        result_info["error"] = str(e)
        return result_info

    result = smoke_runner(
        rc_exe_path,
        model_path,
        work_dir,
        asset_name=asset_name,
        material_specs=material_specs,
    )
    report_path = getattr(result, "material_report_path", "") or ""
    report = _load_rc_material_report(report_path)
    material_id_alignment = _material_id_alignment(report)
    material_report_summary = _material_report_summary(report)
    slot_evidence = (report or {}).get("material_slot_evidence", {}) or {}
    result_info.update(
        {
            "success": bool(getattr(result, "success", False)),
            "copied_fbx_path": getattr(result, "copied_fbx_path", ""),
            "mtl_path": getattr(result, "mtl_path", ""),
            "json_path": getattr(result, "json_path", ""),
            "expected_output_path": getattr(result, "expected_output_path", ""),
            "material_report_path": report_path,
            "semantic_alignment_ok": _alignment_ok(report, "fixture_material_semantic_alignment"),
            "cgf_material_id_alignment_ok": material_id_alignment.get("ok"),
            "cgf_material_id_alignment_checks": material_id_alignment.get("checks", []),
            "unassigned_slot_diagnostics": material_id_alignment.get("unassigned_slot_diagnostics", []),
            "unassigned_slot_diagnostics_ok": material_id_alignment.get("unassigned_slot_diagnostics_ok"),
            "material_slot_evidence_summary": slot_evidence.get("summary", {}),
            "material_slot_evidence_rows": slot_evidence.get("rows", []),
            "material_report_summary": material_report_summary,
            "error": getattr(result, "error", "") or "",
        }
    )
    return result_info


def rc_material_smoke_summary_text(smoke_info):
    if not smoke_info:
        return "not run"
    if smoke_info.get("error"):
        return f"failed: {smoke_info.get('error')}"

    status = "passed" if smoke_info.get("success") else "failed"
    checks = []
    semantic_ok = smoke_info.get("semantic_alignment_ok")
    cgf_ok = smoke_info.get("cgf_material_id_alignment_ok")
    unassigned_ok = smoke_info.get("unassigned_slot_diagnostics_ok")
    if semantic_ok is not None:
        checks.append("semantic ok" if semantic_ok else "semantic mismatch")
    if cgf_ok is not None:
        checks.append("CGF ids ok" if cgf_ok else "CGF ids mismatch")
    if unassigned_ok is not None:
        summary = smoke_info.get("material_report_summary", {}) or {}
        used_unassigned_count = summary.get("used_unassigned_material_count", 0)
        placeholder_count = summary.get("unassigned_placeholder_count", 0)
        if used_unassigned_count:
            checks.append(f"used unassigned x{used_unassigned_count}")
        elif placeholder_count:
            checks.append(f"unassigned placeholders x{placeholder_count}")
        else:
            checks.append("unassigned ok" if unassigned_ok else "used unassigned")
    return " / ".join([status, *checks])


def model_load_state_text(model_info):
    status = (model_info or {}).get("load_status", "")
    return LOAD_STATUS_LABELS.get(status, status or "loaded")


def texture_source_mode_text(source_mode):
    label = SOURCE_MODE_LABELS.get(source_mode, source_mode or "unknown")
    if not source_mode or label == source_mode:
        return label
    return f"{label} [{source_mode}]"


def texture_source_summary_text(textures):
    counts = {}
    for texture in textures or []:
        source_mode = texture.get("source_mode", "")
        counts[source_mode] = counts.get(source_mode, 0) + 1
    if not counts:
        return "none"
    return ", ".join(
        f"{texture_source_mode_text(source_mode)} x{count}"
        for source_mode, count in sorted(counts.items(), key=lambda item: item[0])
    )


def model_display_name(model_info):
    filename = model_info.get("filename", "Unknown Model")
    diagnostics = model_info.get("material_diagnostics", [])
    load_status = model_info.get("load_status", "")
    state_suffix = "" if load_status in AUTHORITATIVE_MODEL_LOAD_STATUS else f" [{load_status}]"
    if any(item.get("severity") == "hazard" for item in diagnostics):
        return f"{filename}{state_suffix} [hazard]"
    if diagnostics:
        return f"{filename}{state_suffix} [diagnostics]"
    return f"{filename}{state_suffix}"


class ModelImportPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.imported_models_info = []
        self.model_loader = ModelLoader()
        self.texture_extractor = TextureExtractor()
        self.texture_import_panel = None
        self.currently_selected_model_textures = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        import_button = QPushButton(get_text("model_import.import_button", "Import Model(s)"))
        import_button.clicked.connect(self.import_model)
        button_row.addWidget(import_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        models_box = QGroupBox(get_text("model_import.imported_models", "Imported Models"))
        models_layout = QVBoxLayout(models_box)
        self.models_list = QListWidget()
        self.models_list.itemSelectionChanged.connect(self._on_model_select)
        models_layout.addWidget(self.models_list)
        layout.addWidget(models_box)

        info_box = QGroupBox(get_text("model_import.selected_info", "Selected Model Information"))
        info_layout = QFormLayout(info_box)
        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.load_state_label = QLabel("loaded")
        self.materials_label = QLabel("0")
        self.material_manifest_label = QLabel("not found")
        self.material_manifest_label.setWordWrap(True)
        self.rc_smoke_label = QLabel("not run")
        self.rc_smoke_label.setWordWrap(True)
        self.textures_label = QLabel("0")
        self.texture_sources_label = QLabel("none")
        self.texture_sources_label.setWordWrap(True)
        self.diagnostics_label = QLabel("0")
        info_layout.addRow(get_text("model_import.path_label", "Path:"), self.path_label)
        info_layout.addRow(get_text("model_import.load_state_label", "Load State:"), self.load_state_label)
        info_layout.addRow(get_text("model_import.materials_label", "Materials:"), self.materials_label)
        info_layout.addRow(get_text("model_import.material_manifest_label", "Material Table:"), self.material_manifest_label)
        info_layout.addRow(get_text("model_import.rc_smoke_label", "RC Material Smoke:"), self.rc_smoke_label)
        info_layout.addRow(get_text("model_import.textures_label", "Textures:"), self.textures_label)
        info_layout.addRow(get_text("model_import.texture_sources_label", "Texture Sources:"), self.texture_sources_label)
        info_layout.addRow(get_text("model_import.diagnostics_label", "Diagnostics:"), self.diagnostics_label)
        layout.addWidget(info_box)

        material_table_box = QGroupBox(get_text("model_import.material_table", "RC Material Table"))
        material_table_layout = QVBoxLayout(material_table_box)
        material_table_actions = QHBoxLayout()
        self.generate_material_manifest_button = QPushButton(
            get_text("model_import.generate_material_manifest", "Generate Material Table")
        )
        self.generate_material_manifest_button.clicked.connect(self._generate_material_manifest)
        self.generate_material_manifest_button.setEnabled(False)
        material_table_actions.addWidget(self.generate_material_manifest_button)
        self.run_rc_material_smoke_button = QPushButton(
            get_text("model_import.run_rc_material_smoke", "Run RC Material Smoke")
        )
        self.run_rc_material_smoke_button.clicked.connect(self._run_rc_material_smoke)
        self.run_rc_material_smoke_button.setEnabled(False)
        material_table_actions.addWidget(self.run_rc_material_smoke_button)
        material_table_actions.addStretch(1)
        material_table_layout.addLayout(material_table_actions)
        self.material_table = QTableWidget(0, 4)
        self.material_table.setHorizontalHeaderLabels(
            [
                get_text("model_import.col_slot", "Slot"),
                get_text("model_import.col_material", "Material"),
                get_text("model_import.col_source", "Source"),
                get_text("model_import.col_local_slot", "Local Slot"),
            ]
        )
        self.material_table.horizontalHeader().setStretchLastSection(True)
        self.material_table.setMinimumHeight(95)
        material_table_layout.addWidget(self.material_table)
        layout.addWidget(material_table_box)

        diagnostics_box = QGroupBox(get_text("model_import.material_diagnostics", "Material Slot Diagnostics"))
        diagnostics_layout = QVBoxLayout(diagnostics_box)
        self.diagnostics_table = QTableWidget(0, 5)
        self.diagnostics_table.setHorizontalHeaderLabels(
            [
                get_text("model_import.col_severity", "Severity"),
                get_text("model_import.col_material", "Material"),
                get_text("model_import.col_slot", "Slot"),
                get_text("model_import.col_usage", "Usage"),
                get_text("model_import.col_message", "Message"),
            ]
        )
        self.diagnostics_table.horizontalHeader().setStretchLastSection(True)
        self.diagnostics_table.setMinimumHeight(110)
        diagnostics_layout.addWidget(self.diagnostics_table)
        layout.addWidget(diagnostics_box)

        textures_box = QGroupBox(get_text("model_import.extracted_textures", "Extracted Textures"))
        textures_layout = QVBoxLayout(textures_box)
        self.texture_table = QTableWidget(0, 4)
        self.texture_table.setHorizontalHeaderLabels(
            [
                get_text("model_import.col_material", "Material"),
                get_text("model_import.col_type", "Type"),
                get_text("model_import.col_source", "Source"),
                get_text("model_import.col_path", "Path"),
            ]
        )
        self.texture_table.horizontalHeader().setStretchLastSection(True)
        textures_layout.addWidget(self.texture_table)
        layout.addWidget(textures_box, 1)

        action_row = QHBoxLayout()
        self.add_to_processing_button = QPushButton(get_text("model_import.add_button", "Add to Processing"))
        self.add_to_processing_button.clicked.connect(self._add_to_processing)
        self.add_to_processing_button.setEnabled(False)
        action_row.addWidget(self.add_to_processing_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

    def set_texture_import_panel(self, panel):
        self.texture_import_panel = panel

    def import_model(self, initial_file_paths=None):
        if initial_file_paths is False:
            initial_file_paths = None

        if initial_file_paths is None:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                get_text("model_import.dialog_title", "Select Model Files"),
                os.getcwd(),
                "3D model files (*.fbx *.obj *.dae *.3ds *.blend);;All files (*.*)",
            )
            if not file_paths:
                return
        else:
            file_paths = list(initial_file_paths)

        self.imported_models_info.clear()
        self.models_list.clear()
        self.generate_material_manifest_button.setEnabled(False)
        self.run_rc_material_smoke_button.setEnabled(False)
        self._populate_material_table([])
        self._populate_table([])

        progress_dialog = ProgressDialog(
            self,
            title=get_text("model_import.progress_title", "Importing Models..."),
            allow_cancel=True,
        )

        all_texture_paths = []
        success_count = 0
        error_count = 0

        for index, file_path in enumerate(file_paths):
            if progress_dialog.is_cancelled():
                break

            filename = os.path.basename(file_path)
            progress_dialog.update_progress(
                (index + 1) / len(file_paths),
                get_text("model_import.progress_loading", "Loading: {filename}").format(filename=filename),
                get_text("model_import.progress_status", "Model {current}/{total}").format(
                    current=index + 1,
                    total=len(file_paths),
                ),
            )

            model_info = {
                "path": file_path,
                "filename": filename,
                "load_status": "error",
                "load_warning": "",
                "load_error": "",
                "materials": 0,
                "model_obj": None,
                "extracted_textures": [],
                "material_diagnostics": [],
                "material_manifest": {},
                "rc_material_smoke": {},
            }

            try:
                model = self.model_loader.load(file_path)
                if model:
                    model_info["load_status"] = model.get("load_status", "")
                    model_info["load_warning"] = model.get("load_warning", "")
                    model_info["load_error"] = model.get("load_error", "")
                    model_info["material_diagnostics"] = collect_model_material_diagnostics(model)
                if model and not model.get("is_dummy", False):
                    model_info["model_obj"] = model
                    model_info["materials"] = len(model.get("materials", []))
                    model_info["material_manifest"] = load_model_material_manifest(file_path)
                    model["material_manifest"] = model_info["material_manifest"]
                    refs = self.texture_extractor.extract(model)
                    textures = self._get_accurate_texture_info(refs)
                    model_info["extracted_textures"] = textures
                    all_texture_paths.extend(
                        texture["path"]
                        for texture in textures
                        if texture.get("path") and os.path.exists(texture["path"])
                    )
                    success_count += 1
                else:
                    model_info["filename"] += get_text("model_import.load_failed_suffix", " (Load Failed)")
                    error_count += 1
            except Exception as e:
                print(f"Error importing model {file_path}: {e}")
                model_info["load_status"] = "error"
                model_info["load_error"] = str(e)
                model_info["filename"] += get_text("model_import.load_error_suffix", " (Error)")
                error_count += 1

            self.imported_models_info.append(model_info)

        progress_dialog.show_completion(True, True)
        progress_dialog.close()
        self._update_model_list_display()

        if all_texture_paths and self.texture_import_panel:
            self.texture_import_panel.import_textures(sorted(set(all_texture_paths)))

        QMessageBox.information(
            self,
            get_text("model_import.summary_title", "Multi-Import Complete"),
            get_text(
                "model_import.summary_finished",
                "Finished importing {total} models.\nSuccessfully loaded: {success}\nErrors: {errors}",
            ).format(total=len(file_paths), success=success_count, errors=error_count),
        )

    def _get_accurate_texture_info(self, texture_refs):
        accurate_textures = []
        texture_manager = None
        if self.texture_import_panel and hasattr(self.texture_import_panel, "texture_manager"):
            texture_manager = self.texture_import_panel.texture_manager

        for ref in texture_refs:
            accurate_type = ref.texture_type
            base_name = "Unknown"
            abs_path = None

            if ref.path:
                if os.path.isabs(ref.path):
                    abs_path = ref.path
                elif getattr(self.model_loader, "last_loaded_dir", None):
                    candidate = os.path.join(self.model_loader.last_loaded_dir, ref.path)
                    if os.path.exists(candidate):
                        abs_path = os.path.normpath(candidate)

            if texture_manager and abs_path and os.path.exists(abs_path):
                try:
                    accurate_type, base_name = texture_manager.classify_texture(abs_path)
                except Exception as e:
                    print(f"Warning: Could not classify {abs_path}: {e}")
            elif abs_path:
                base_name = os.path.splitext(os.path.basename(abs_path))[0]
            else:
                accurate_type = "Missing"
                base_name = os.path.splitext(ref.filename)[0] if ref.filename else "Unknown"

            accurate_textures.append(
                {
                    "path": abs_path,
                    "type": accurate_type,
                    "material": ref.material_name,
                    "filename": ref.filename,
                    "processed_path": ref.processed_path,
                    "base_name": base_name,
                    "source_mode": getattr(ref, "source_mode", ""),
                }
            )

        return accurate_textures

    def _update_model_list_display(self):
        self.models_list.clear()
        for model_info in self.imported_models_info:
            self.models_list.addItem(model_display_name(model_info))
        if self.imported_models_info:
            self.models_list.setCurrentRow(0)

    def _on_model_select(self):
        row = self.models_list.currentRow()
        if row < 0 or row >= len(self.imported_models_info):
            self.path_label.setText("")
            self.load_state_label.setText("loaded")
            self.materials_label.setText("0")
            self.material_manifest_label.setText("not found")
            self.rc_smoke_label.setText("not run")
            self.textures_label.setText("0")
            self.texture_sources_label.setText("none")
            self.diagnostics_label.setText("0")
            self._populate_diagnostics_table([])
            self._populate_material_table([])
            self._populate_table([])
            self.currently_selected_model_textures = []
            self.add_to_processing_button.setEnabled(False)
            self.generate_material_manifest_button.setEnabled(False)
            self.run_rc_material_smoke_button.setEnabled(False)
            return

        model_info = self.imported_models_info[row]
        textures = model_info.get("extracted_textures", [])
        diagnostics = model_info.get("material_diagnostics", [])
        material_manifest = model_info.get("material_manifest", {})
        rc_smoke = model_info.get("rc_material_smoke", {})
        self.path_label.setText(model_info.get("path", ""))
        self.load_state_label.setText(model_load_state_text(model_info))
        self.materials_label.setText(str(model_info.get("materials", 0)))
        self.material_manifest_label.setText(material_manifest_summary_text(material_manifest))
        self.rc_smoke_label.setText(rc_material_smoke_summary_text(rc_smoke))
        self.textures_label.setText(str(len(textures)))
        self.texture_sources_label.setText(texture_source_summary_text(textures))
        self.diagnostics_label.setText(str(len(diagnostics)))
        self.currently_selected_model_textures = textures
        self._populate_diagnostics_table(diagnostics)
        self._populate_material_table(material_manifest.get("materials", []))
        self._populate_table(textures)
        self.add_to_processing_button.setEnabled(
            any(texture.get("path") and os.path.exists(texture["path"]) for texture in textures)
        )
        self.generate_material_manifest_button.setEnabled(
            model_info.get("path", "").lower().endswith(".fbx") and os.path.exists(model_info.get("path", ""))
        )
        self.run_rc_material_smoke_button.setEnabled(
            model_info.get("path", "").lower().endswith(".fbx") and os.path.exists(model_info.get("path", ""))
        )

    def _populate_table(self, textures):
        self.texture_table.setRowCount(0)
        for texture in textures:
            row = self.texture_table.rowCount()
            self.texture_table.insertRow(row)
            self.texture_table.setItem(row, 0, QTableWidgetItem(texture.get("material", "Unknown")))
            self.texture_table.setItem(row, 1, QTableWidgetItem(texture.get("type", "Unknown")))
            self.texture_table.setItem(
                row,
                2,
                QTableWidgetItem(texture_source_mode_text(texture.get("source_mode", ""))),
            )
            self.texture_table.setItem(row, 3, QTableWidgetItem(texture.get("path") or texture.get("filename", "N/A")))

    def _populate_material_table(self, materials):
        self.material_table.setRowCount(0)
        for material in materials:
            row = self.material_table.rowCount()
            self.material_table.insertRow(row)
            local_slot = material.get("local_slot")
            self.material_table.setItem(row, 0, QTableWidgetItem(str(material.get("slot", ""))))
            self.material_table.setItem(row, 1, QTableWidgetItem(material.get("name", "")))
            self.material_table.setItem(row, 2, QTableWidgetItem(material.get("source", "")))
            self.material_table.setItem(row, 3, QTableWidgetItem("" if local_slot is None else str(local_slot)))

    def _generate_material_manifest(self):
        row = self.models_list.currentRow()
        if row < 0 or row >= len(self.imported_models_info):
            return

        model_info = self.imported_models_info[row]
        model_path = model_info.get("path", "")
        if not model_path or not model_path.lower().endswith(".fbx"):
            QMessageBox.warning(
                self,
                get_text("error.title", "Error"),
                get_text("model_import.material_manifest_fbx_only", "Material table inspection requires an FBX file."),
            )
            return

        try:
            material_manifest = generate_model_material_manifest(model_path)
        except Exception as e:
            QMessageBox.warning(
                self,
                get_text("error.title", "Error"),
                get_text("model_import.material_manifest_failed", "Failed to generate material table:\n{error}").format(
                    error=e
                ),
            )
            return

        model_info["material_manifest"] = material_manifest
        if model_info.get("model_obj"):
            model_info["model_obj"]["material_manifest"] = material_manifest
        self.material_manifest_label.setText(material_manifest_summary_text(material_manifest))
        self._populate_material_table(material_manifest.get("materials", []))
        QMessageBox.information(
            self,
            get_text("model_import.material_manifest_title", "Material Table"),
            get_text("model_import.material_manifest_generated", "Material table generated successfully."),
        )

    def _run_rc_material_smoke(self):
        row = self.models_list.currentRow()
        if row < 0 or row >= len(self.imported_models_info):
            return

        model_info = self.imported_models_info[row]
        model_path = model_info.get("path", "")
        if not model_path or not model_path.lower().endswith(".fbx"):
            QMessageBox.warning(
                self,
                get_text("error.title", "Error"),
                get_text("model_import.rc_smoke_fbx_only", "RC material smoke requires an FBX file."),
            )
            return

        material_manifest = load_model_material_manifest(model_path)
        if not material_manifest.get("summary"):
            QMessageBox.warning(
                self,
                get_text("error.title", "Error"),
                get_text(
                    "model_import.rc_smoke_manifest_required",
                    "Generate or provide an FBX material table before running RC material smoke.",
                ),
            )
            return

        rc_exe_path = ConfigManager().get("rc_exe_path", "")
        smoke_info = run_model_material_rc_smoke(model_path, rc_exe_path)
        model_info["material_manifest"] = material_manifest
        model_info["rc_material_smoke"] = smoke_info
        if model_info.get("model_obj"):
            model_info["model_obj"]["material_manifest"] = material_manifest
            model_info["model_obj"]["rc_material_smoke"] = smoke_info
            model_info["material_diagnostics"] = collect_model_material_diagnostics(model_info["model_obj"])
        else:
            model_info["material_diagnostics"] = collect_model_material_diagnostics(model_info)
        self.material_manifest_label.setText(material_manifest_summary_text(material_manifest))
        self.rc_smoke_label.setText(rc_material_smoke_summary_text(smoke_info))
        self.diagnostics_label.setText(str(len(model_info.get("material_diagnostics", []))))
        self._populate_material_table(material_manifest.get("materials", []))
        self._populate_diagnostics_table(model_info.get("material_diagnostics", []))
        self._update_model_list_display()
        self.models_list.setCurrentRow(row)

        message = rc_material_smoke_summary_text(smoke_info)
        if smoke_info.get("material_report_path"):
            message += f"\n{smoke_info['material_report_path']}"
        if smoke_info.get("success"):
            QMessageBox.information(self, get_text("model_import.rc_smoke_title", "RC Material Smoke"), message)
        else:
            QMessageBox.warning(self, get_text("model_import.rc_smoke_title", "RC Material Smoke"), message)

    def _populate_diagnostics_table(self, diagnostics):
        self.diagnostics_table.setRowCount(0)
        for diagnostic in diagnostics:
            row = self.diagnostics_table.rowCount()
            self.diagnostics_table.insertRow(row)
            fbx_slot = diagnostic.get("fbx_slot")
            sub_index = diagnostic.get("sub_index")
            polygon_count = diagnostic.get("polygon_count")
            used_by_polygons = diagnostic.get("used_by_polygons")
            slot_text = f"FBX {fbx_slot} -> sub {sub_index}"
            usage_text = "unknown"
            if polygon_count is not None:
                usage_text = f"{polygon_count} polygons"
                if used_by_polygons is False:
                    usage_text += " (unused)"
                elif used_by_polygons is True:
                    usage_text += " (used)"
            self.diagnostics_table.setItem(row, 0, QTableWidgetItem(diagnostic.get("severity", "")))
            self.diagnostics_table.setItem(
                row,
                1,
                QTableWidgetItem(diagnostic.get("material") or diagnostic.get("original_name", "")),
            )
            self.diagnostics_table.setItem(row, 2, QTableWidgetItem(slot_text))
            self.diagnostics_table.setItem(row, 3, QTableWidgetItem(usage_text))
            self.diagnostics_table.setItem(row, 4, QTableWidgetItem(diagnostic.get("message", "")))

    def _add_to_processing(self):
        paths = [
            texture["path"]
            for texture in self.currently_selected_model_textures
            if texture.get("path") and os.path.exists(texture["path"])
        ]
        if not paths:
            QMessageBox.warning(self, get_text("error.title", "Error"), "No valid texture files found.")
            return
        if not self.texture_import_panel:
            QMessageBox.warning(self, get_text("error.title", "Error"), "Texture import panel not available.")
            return
        self.texture_import_panel.import_textures(paths)
