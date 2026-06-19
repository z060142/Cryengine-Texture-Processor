#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Prepare and run a minimal RC FBX import smoke test."""

import argparse
from dataclasses import dataclass
import json
import os
import shutil

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from model_processing.material_manifest import (
    coerce_material_name,
    coerce_material_slot,
    discover_material_manifest,
    iter_manifest_material_rows,
    iter_manifest_polygon_rows,
    load_material_manifest,
    material_manifest_materials,
    material_manifest_scene_hierarchy,
    material_manifest_table_diagnostics,
)
from model_processing.material_index_assigner import build_omitted_material_diagnostics
from model_processing.material_slot_table import build_material_slot_records
from model_processing.material_texture_resolver import build_mtl_material_data
from output_formats.json_exporter import export_json
from output_formats.mtl_exporter import export_mtl
from output_formats.texture_output_diagnostics import (
    build_texture_output_report_from_paths,
    write_texture_output_report,
)
from tools.material_report_summary import compact_material_report_summary, format_summary, load_report
from tools.material_mapping_report import build_material_mapping_report, write_material_mapping_report
from tools.mtl_material_state_compare import write_material_state_compare_report
from tools.mtl_schema_report import build_mtl_schema_report, write_mtl_schema_report
from tools.obj_mtl_report import parse_obj_mtl
from utils.rc_import_runner import RCImportRunner, RCImportResult


DEFAULT_RC_CANDIDATES = (
    r"S:\Crytek\crytek\cryengine-57-lts\5.7.1\Tools\rc\rc.exe",
    r"S:\Crytek\crytek\CRYENGINE_Source-release\Tools\rc\rc.exe",
)

DEFAULT_FBX_CANDIDATES = (
    r"S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubao\CubeA.fbx",
    r"S:\Crytek\crytek\cryengine-gamesdk-sample-project\5.7.1\gamesdk\objects\cubez\CubeA.fbx",
)


@dataclass
class RCSmokeResult:
    success: bool
    work_dir: str
    rc_exe_path: str
    source_fbx_path: str
    copied_fbx_path: str = ""
    mtl_path: str = ""
    json_path: str = ""
    expected_output_path: str = ""
    material_report_path: str = ""
    material_state_compare_path: str = ""
    mtl_schema_gate_path: str = ""
    texture_output_gate_path: str = ""
    rc_result: RCImportResult | None = None
    error: str = ""


def discover_default_rc(candidates=DEFAULT_RC_CANDIDATES):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def discover_default_fbx(candidates=DEFAULT_FBX_CANDIDATES):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def material_names_from_arg(value):
    names = [item.strip() for item in (value or "").split(",") if item.strip()]
    return names or ["Default"]


def material_specs_from_arg(value):
    specs = []
    for index, item in enumerate((value or "").split(",")):
        item = item.strip()
        if not item:
            continue

        name = item
        deleted = False
        explicit_sub_index = None
        if ":" in item:
            name, marker = item.rsplit(":", 1)
            name = name.strip()
            marker = marker.strip().lower()
            if marker in {"deleted", "delete", "removed", "-1"}:
                deleted = True
                explicit_sub_index = -1
            elif marker:
                explicit_sub_index = int(marker)

        spec = {
            "name": name,
            "id": index + 1,
            "index": index,
        }
        if deleted:
            spec["deleted"] = True
        if explicit_sub_index is not None:
            spec["sub_index"] = explicit_sub_index
            if explicit_sub_index >= 0:
                spec["auto_assigned"] = False
        specs.append(spec)

    if not specs:
        return [{"name": "Default", "id": 1, "index": 0}]
    return specs


def material_specs_from_manifest_path(manifest_path):
    manifest = load_material_manifest(manifest_path)
    if not manifest:
        raise RuntimeError(f"Material manifest not found: {manifest_path}")
    return material_manifest_materials([], {"path": manifest_path, "manifest": manifest})


def material_specs_from_manifest(source_fbx_path, manifest_path=""):
    return material_specs_from_manifest_path(manifest_path or discover_material_manifest(source_fbx_path))


def load_material_overrides(overrides_path):
    if not overrides_path:
        return {}
    with open(overrides_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict) and isinstance(payload.get("material_overrides"), dict):
        return payload["material_overrides"]
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Material overrides JSON must be an object: {overrides_path}")


def load_external_material_texture_evidence(evidence_path):
    if not evidence_path:
        return None
    if evidence_path.lower().endswith(".json"):
        with open(evidence_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return parse_obj_mtl(evidence_path)


def apply_material_overrides_to_specs(material_specs, material_overrides=None):
    material_overrides = material_overrides or {}
    materials = []
    for spec in material_specs or []:
        name = spec.get("name", "")
        override = material_overrides.get(name, {})
        materials.append({**spec, **override} if isinstance(override, dict) else dict(spec))
    return materials


def source_material_specs_from_manifest_path(manifest_path):
    manifest = load_material_manifest(manifest_path)
    if not manifest:
        return []

    materials_by_name = {}
    for _, material in iter_manifest_material_rows(manifest):
        name = coerce_material_name(material.get("name", ""))
        if not name:
            continue
        slot = coerce_material_slot(material.get("slot"))
        if slot is None:
            continue
        materials_by_name[name] = {
            "name": name,
            "id": slot + 1,
            "index": slot,
            "material_table_slot": slot,
            "polygon_count": 0,
            "used_by_polygons": False,
        }

    for _, polygon in iter_manifest_polygon_rows(manifest):
        name = coerce_material_name(polygon.get("material_name", ""))
        if not name:
            continue
        slot = polygon.get("material_table_slot", polygon.get("expected_cgf_material_id", polygon.get("material_slot", 0)))
        slot = coerce_material_slot(slot)
        if slot is None:
            continue
        material = materials_by_name.setdefault(
            name,
            {
                "name": name,
                "id": slot + 1,
                "index": slot,
                "material_table_slot": slot,
                "polygon_count": 0,
                "used_by_polygons": False,
            },
        )
        material["polygon_count"] = int(material.get("polygon_count", 0)) + 1
        material["used_by_polygons"] = True

    return sorted(materials_by_name.values(), key=lambda item: int(item.get("index", 0)))


def source_material_specs_from_manifest(source_fbx_path, manifest_path=""):
    return source_material_specs_from_manifest_path(manifest_path or discover_material_manifest(source_fbx_path))


def _normalize_material_specs(material_names=None, material_specs=None):
    if material_specs is not None:
        return [
            {
                **spec,
                "id": spec.get("id", index + 1),
                "index": spec.get("index", index),
            }
            for index, spec in enumerate(material_specs)
        ]
    return [
        {
            "name": name,
            "id": index + 1,
            "index": index,
        }
        for index, name in enumerate(material_names or ["Default"])
    ]


def build_smoke_model_data(asset_name, material_names=None, material_specs=None, scene_hierarchy=None):
    material_specs = _normalize_material_specs(material_names, material_specs)
    return {
        "path": f"{asset_name}.fbx",
        "materials": material_specs,
        "scene_hierarchy": scene_hierarchy if scene_hierarchy is not None else [],
        "meshes": [],
    }


def _copy_material_manifest(source_fbx_path, copied_fbx_path, material_manifest_path=""):
    manifest_path = material_manifest_path or discover_material_manifest(source_fbx_path)
    if not manifest_path:
        return ""
    source_stem = os.path.splitext(os.path.abspath(source_fbx_path))[0]
    copied_stem = os.path.splitext(os.path.abspath(copied_fbx_path))[0]
    manifest_abs = os.path.abspath(manifest_path)
    suffix = manifest_abs[len(source_stem) :] if manifest_abs.startswith(source_stem) else ".fbx_material_manifest.json"
    copied_manifest_path = copied_stem + suffix
    if manifest_abs != os.path.abspath(copied_manifest_path):
        shutil.copy2(manifest_path, copied_manifest_path)
    return copied_manifest_path


def collect_material_slot_diagnostics(
    material_specs,
    existing_submaterial_names=None,
    material_manifest_info=None,
    source_materials=None,
):
    records = build_material_slot_records(
        material_specs,
        existing_submaterial_names,
        material_manifest_info=material_manifest_info,
    )
    diagnostics = [
        {
            **diagnostic,
            "assignment_reason": diagnostic.get("assignment_reason", "omitted_source_material"),
            "original_name": diagnostic.get("material", ""),
        }
        for diagnostic in build_omitted_material_diagnostics(source_materials if source_materials is not None else material_specs, records)
    ]
    diagnostics.extend(material_manifest_table_diagnostics(material_manifest_info))
    for record in records:
        for diagnostic in record.get("diagnostics", []):
            diagnostics.append(
                {
                    **diagnostic,
                    "source_order": record["source_order"],
                    "assignment_reason": diagnostic.get("assignment_reason", record["reason"]),
                    "original_name": record["original_name"],
                }
            )
    return diagnostics


def build_smoke_materials_data(
    source_fbx_path,
    material_specs,
    manifest_info=None,
    texture_output_dir="",
    texture_output_format="tif",
    material_overrides=None,
    external_material_texture_evidence=None,
    model_loader_factory=None,
    texture_extractor_factory=None,
):
    fallback_materials = [
        {**spec, "textures": {}}
        for spec in apply_material_overrides_to_specs(material_specs, material_overrides)
    ]
    texture_diagnostics = []
    if not texture_output_dir:
        return fallback_materials, texture_diagnostics

    try:
        from model_processing.model_loader import ModelLoader
        from model_processing.texture_extractor import TextureExtractor

        model_loader_factory = model_loader_factory or ModelLoader
        texture_extractor_factory = texture_extractor_factory or TextureExtractor
        model_data = model_loader_factory().load(source_fbx_path)
        if not isinstance(model_data, dict) or model_data.get("is_dummy"):
            texture_diagnostics.append(
                {
                    "severity": "warning",
                    "code": "texture_backed_mtl_model_load_failed",
                    "message": "Texture-backed MTL export requested, but the source FBX could not be loaded.",
                    "load_status": model_data.get("load_status") if isinstance(model_data, dict) else "",
                    "load_error": model_data.get("load_error") if isinstance(model_data, dict) else "",
                }
            )
            return fallback_materials, texture_diagnostics

        if not model_data.get("materials"):
            model_data["materials"] = material_specs
        if manifest_info:
            model_data["material_manifest"] = manifest_info
        if material_overrides:
            model_data["material_overrides"] = material_overrides
        if external_material_texture_evidence:
            model_data["external_material_texture_evidence"] = external_material_texture_evidence

        texture_refs = texture_extractor_factory().extract(model_data)
        materials_data = build_mtl_material_data(
            model_data,
            texture_refs,
            None,
            texture_output_dir,
            texture_output_format,
        )
        texture_diagnostics.append(
            {
                "severity": "info",
                "code": "texture_backed_mtl_material_summary",
                "source_texture_ref_count": len(texture_refs),
                "texture_material_count": sum(1 for material in materials_data if material.get("textures")),
                "material_count": len(materials_data),
                "texture_output_dir": texture_output_dir,
                "texture_output_format": texture_output_format,
                "external_material_texture_evidence": bool(external_material_texture_evidence),
            }
        )
        return materials_data or fallback_materials, texture_diagnostics
    except Exception as e:
        texture_diagnostics.append(
            {
                "severity": "warning",
                "code": "texture_backed_mtl_export_failed",
                "message": str(e),
                "texture_output_dir": texture_output_dir,
                "texture_output_format": texture_output_format,
            }
        )
        return fallback_materials, texture_diagnostics


def prepare_smoke_bundle(
    source_fbx_path,
    work_dir,
    asset_name=None,
    material_names=None,
    material_specs=None,
    texture_output_dir="",
    texture_output_format="tif",
    material_overrides=None,
    external_material_texture_evidence=None,
    material_manifest_path="",
):
    source_fbx_path = os.path.abspath(source_fbx_path)
    work_dir = os.path.abspath(work_dir)
    asset_name = asset_name or os.path.splitext(os.path.basename(source_fbx_path))[0]
    material_specs = _normalize_material_specs(material_names, material_specs)

    os.makedirs(work_dir, exist_ok=True)
    copied_fbx_path = os.path.join(work_dir, f"{asset_name}.fbx")
    if os.path.abspath(source_fbx_path) != os.path.abspath(copied_fbx_path):
        shutil.copy2(source_fbx_path, copied_fbx_path)
    copied_manifest_path = _copy_material_manifest(source_fbx_path, copied_fbx_path, material_manifest_path)
    manifest_info = {"path": copied_manifest_path, "manifest": load_material_manifest(copied_manifest_path)} if copied_manifest_path else None
    source_materials = source_material_specs_from_manifest(source_fbx_path, material_manifest_path)

    materials_data, texture_diagnostics = build_smoke_materials_data(
        source_fbx_path,
        material_specs,
        manifest_info=manifest_info,
        texture_output_dir=texture_output_dir,
        texture_output_format=texture_output_format,
        material_overrides=material_overrides,
        external_material_texture_evidence=external_material_texture_evidence,
    )
    mtl_filename = f"{asset_name}.mtl"
    mtl_success, mtl_result = export_mtl(
        materials_data,
        work_dir,
        work_dir,
        mtl_filename,
        include_trailing_unassigned=True,
        material_overrides=material_overrides,
    )
    if not mtl_success:
        raise RuntimeError(mtl_result)

    model_data = build_smoke_model_data(
        asset_name,
        material_specs=material_specs,
        scene_hierarchy=material_manifest_scene_hierarchy(manifest_info),
    )
    if manifest_info:
        model_data["material_manifest"] = manifest_info
    json_success, json_result = export_json(
        model_data,
        f"{asset_name}.fbx",
        work_dir,
        material_filename=asset_name,
        include_trailing_unassigned=True,
    )
    if not json_success:
        raise RuntimeError(json_result)

    return {
        "copied_fbx_path": copied_fbx_path,
        "copied_manifest_path": copied_manifest_path,
        "mtl_path": mtl_result,
        "json_path": json_result,
        "material_diagnostics": collect_material_slot_diagnostics(
            materials_data,
            material_manifest_info=manifest_info,
            source_materials=source_materials or materials_data,
        ),
        "texture_diagnostics": texture_diagnostics,
    }


def run_rc_smoke_test(
    rc_exe_path,
    source_fbx_path,
    work_dir,
    asset_name=None,
    material_names=None,
    material_specs=None,
    texture_output_dir="",
    texture_output_format="tif",
    material_overrides=None,
    external_material_texture_evidence=None,
    material_manifest_path="",
    reference_mtl_path="",
    material_state_compare_output_path="",
    mtl_schema_gate_output_path="",
    texture_output_gate_output_path="",
    runner_factory=RCImportRunner,
):
    rc_exe_path = rc_exe_path or ""
    source_fbx_path = os.path.abspath(source_fbx_path) if source_fbx_path else ""
    work_dir = os.path.abspath(work_dir)

    if not rc_exe_path:
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error="RC executable path is required")
    if not os.path.exists(rc_exe_path):
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error=f"RC executable not found: {rc_exe_path}")
    if not source_fbx_path:
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error="Source FBX path is required")
    if not os.path.exists(source_fbx_path):
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error=f"Source FBX not found: {source_fbx_path}")

    try:
        bundle = prepare_smoke_bundle(
            source_fbx_path,
            work_dir,
            asset_name=asset_name,
            material_names=material_names,
            material_specs=material_specs,
            texture_output_dir=texture_output_dir,
            texture_output_format=texture_output_format,
            material_overrides=material_overrides,
            external_material_texture_evidence=external_material_texture_evidence,
            material_manifest_path=material_manifest_path,
        )
    except Exception as e:
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error=str(e))

    runner = runner_factory(rc_exe_path)
    rc_result = runner.run(bundle["json_path"], source_fbx_path=bundle["copied_fbx_path"])
    report_path = os.path.join(work_dir, f"{os.path.splitext(os.path.basename(bundle['json_path']))[0]}.material_report.json")
    material_state_compare_path = ""
    material_state_compare_report = None
    material_state_compare_error = ""
    mtl_schema_gate_path = mtl_schema_gate_output_path or os.path.join(
        work_dir,
        f"{os.path.splitext(os.path.basename(bundle['json_path']))[0]}.mtl_schema_gate.json",
    )
    mtl_schema_gate_report = None
    mtl_schema_gate_error = ""
    texture_output_gate_path = ""
    texture_output_gate_report = None
    texture_output_gate_error = ""
    material_mapping_report = None
    if reference_mtl_path:
        material_state_compare_path = material_state_compare_output_path or os.path.join(
            work_dir,
            f"{os.path.splitext(os.path.basename(bundle['json_path']))[0]}.material_state_compare.json",
        )
        try:
            material_state_compare_report = write_material_state_compare_report(
                reference_mtl_path,
                bundle["mtl_path"],
                material_state_compare_path,
            )
        except Exception as e:
            material_state_compare_error = f"Failed to compare material state: {e}"
    try:
        mtl_schema_gate_report = build_mtl_schema_report(
            [bundle["mtl_path"]],
            material_overrides=material_overrides,
        )
        write_mtl_schema_report(mtl_schema_gate_report, mtl_schema_gate_path)
    except Exception as e:
        mtl_schema_gate_error = f"Failed to run MTL schema gate: {e}"
    if texture_output_dir:
        texture_output_gate_path = texture_output_gate_output_path or os.path.join(
            work_dir,
            f"{os.path.splitext(os.path.basename(bundle['json_path']))[0]}.texture_output_gate.json",
        )
        try:
            texture_output_gate_report = build_texture_output_report_from_paths(
                [texture_output_dir],
                source="rc_smoke_texture_output_gate",
            )
            write_texture_output_report(texture_output_gate_report, texture_output_gate_path)
        except Exception as e:
            texture_output_gate_error = f"Failed to run texture output gate: {e}"
    try:
        material_mapping_report = build_material_mapping_report(
            bundle["json_path"],
            bundle["mtl_path"],
            expected_output_path=rc_result.expected_output_path,
            rc_exe_path=rc_exe_path,
            source_fbx_path=source_fbx_path,
            copied_fbx_path=bundle["copied_fbx_path"],
            rc_returncode=rc_result.returncode,
        )
        material_mapping_report["preflight_material_diagnostics"] = bundle.get("material_diagnostics", [])
        material_mapping_report["preflight_texture_diagnostics"] = bundle.get("texture_diagnostics", [])
        if material_state_compare_report is not None:
            material_mapping_report["material_state_compare"] = material_state_compare_report
        if material_state_compare_error:
            material_mapping_report["material_state_compare_error"] = material_state_compare_error
        if mtl_schema_gate_report is not None:
            material_mapping_report["mtl_schema_gate"] = mtl_schema_gate_report.get("gate", {})
            material_mapping_report["mtl_schema_gate_path"] = mtl_schema_gate_path
        if mtl_schema_gate_error:
            material_mapping_report["mtl_schema_gate_error"] = mtl_schema_gate_error
        if texture_output_gate_report is not None:
            material_mapping_report["texture_output_gate"] = texture_output_gate_report
            material_mapping_report["texture_output_gate_path"] = texture_output_gate_path
        if texture_output_gate_error:
            material_mapping_report["texture_output_gate_error"] = texture_output_gate_error
        write_material_mapping_report(material_mapping_report, report_path)
    except Exception as e:
        report_path = ""
        if rc_result.success:
            rc_result = RCImportResult(
                success=False,
                command=rc_result.command,
                json_path=rc_result.json_path,
                expected_output_path=rc_result.expected_output_path,
                returncode=rc_result.returncode,
                stdout=rc_result.stdout,
                stderr=rc_result.stderr,
                error=f"Failed to write material mapping report: {e}",
            )

    if rc_result.success and material_state_compare_error:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=material_state_compare_error,
        )
    if rc_result.success and material_mapping_report is not None and material_mapping_report.get("summary", {}).get("action_required"):
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=f"Material mapping report requires action: {report_path}",
        )
    if rc_result.success and mtl_schema_gate_error:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=mtl_schema_gate_error,
        )
    if rc_result.success and texture_output_gate_error:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=texture_output_gate_error,
        )
    if rc_result.success and material_state_compare_report is not None and not material_state_compare_report["comparison"]["ok"]:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=f"Material state compare failed: {material_state_compare_path}",
        )
    if rc_result.success and mtl_schema_gate_report is not None and not mtl_schema_gate_report["gate"]["summary"]["ok"]:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=f"MTL schema gate failed: {mtl_schema_gate_path}",
        )
    if rc_result.success and texture_output_gate_report is not None and not texture_output_gate_report["summary"]["ok"]:
        rc_result = RCImportResult(
            success=False,
            command=rc_result.command,
            json_path=rc_result.json_path,
            expected_output_path=rc_result.expected_output_path,
            returncode=rc_result.returncode,
            stdout=rc_result.stdout,
            stderr=rc_result.stderr,
            error=f"Texture output gate failed: {texture_output_gate_path}",
        )

    return RCSmokeResult(
        success=rc_result.success,
        work_dir=work_dir,
        rc_exe_path=rc_exe_path,
        source_fbx_path=source_fbx_path,
        copied_fbx_path=bundle["copied_fbx_path"],
        mtl_path=bundle["mtl_path"],
        json_path=bundle["json_path"],
        expected_output_path=rc_result.expected_output_path,
        material_report_path=report_path,
        material_state_compare_path=material_state_compare_path,
        mtl_schema_gate_path=mtl_schema_gate_path,
        texture_output_gate_path=texture_output_gate_path,
        rc_result=rc_result,
        error=rc_result.error,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a minimal CryEngine RC FBX import smoke test.")
    parser.add_argument("--rc", default=discover_default_rc(), help="Path to rc.exe")
    parser.add_argument("--fbx", default=discover_default_fbx(), help="Path to a source FBX sample")
    parser.add_argument("--work-dir", required=True, help="Directory for generated smoke-test files")
    parser.add_argument("--asset-name", default=None, help="Output asset base name")
    parser.add_argument("--materials", default="Default", help="Comma-separated material names")
    parser.add_argument(
        "--materials-from-manifest",
        action="store_true",
        help="Use the source FBX material manifest sidecar to build request and MTL materials",
    )
    parser.add_argument(
        "--material-manifest",
        default="",
        help="Optional explicit FBX material manifest path. Keeps validation sidecars in the work directory.",
    )
    parser.add_argument(
        "--texture-output-dir",
        default="",
        help="Optional directory containing processed texture outputs to reference from the generated MTL.",
    )
    parser.add_argument(
        "--texture-output-format",
        default="tif",
        help="Processed texture extension(s) to probe, for example 'tif', 'dds', 'dds,tif', or 'auto'.",
    )
    parser.add_argument(
        "--material-overrides",
        default="",
        help="Optional JSON file containing material_overrides keyed by material name.",
    )
    parser.add_argument(
        "--obj-mtl-evidence",
        default="",
        help="Optional Wavefront OBJ .mtl or obj_mtl_report JSON used as fallback material texture evidence.",
    )
    parser.add_argument(
        "--reference-mtl",
        default="",
        help="Optional reference/native .mtl to compare against the generated .mtl material state.",
    )
    parser.add_argument(
        "--material-state-compare-output",
        default="",
        help="Optional output path for the material-state compare JSON report.",
    )
    parser.add_argument(
        "--mtl-schema-gate-output",
        default="",
        help="Optional output path for the generated MTL schema gate JSON report.",
    )
    parser.add_argument(
        "--texture-output-gate-output",
        default="",
        help="Optional output path for the texture output gate JSON report.",
    )
    parser.add_argument(
        "--no-rc-log",
        action="store_true",
        help="Do not print RC stdout/stderr after the compact smoke result.",
    )
    parser.add_argument(
        "--report-summary",
        action="store_true",
        help="Print a compact material report summary after the smoke result.",
    )
    args = parser.parse_args(argv)
    material_specs = (
        material_specs_from_manifest(args.fbx, args.material_manifest)
        if args.materials_from_manifest
        else material_specs_from_arg(args.materials)
    )
    material_overrides = load_material_overrides(args.material_overrides) if args.material_overrides else {}
    external_material_texture_evidence = (
        load_external_material_texture_evidence(args.obj_mtl_evidence)
        if args.obj_mtl_evidence
        else None
    )

    result = run_rc_smoke_test(
        args.rc,
        args.fbx,
        args.work_dir,
        asset_name=args.asset_name,
        material_specs=material_specs,
        texture_output_dir=args.texture_output_dir,
        texture_output_format=args.texture_output_format,
        material_overrides=material_overrides,
        external_material_texture_evidence=external_material_texture_evidence,
        material_manifest_path=args.material_manifest,
        reference_mtl_path=args.reference_mtl,
        material_state_compare_output_path=args.material_state_compare_output,
        mtl_schema_gate_output_path=args.mtl_schema_gate_output,
        texture_output_gate_output_path=args.texture_output_gate_output,
    )

    print(f"success: {result.success}")
    print(f"work_dir: {result.work_dir}")
    print(f"rc: {result.rc_exe_path}")
    print(f"fbx: {result.copied_fbx_path or result.source_fbx_path}")
    print(f"mtl: {result.mtl_path}")
    print(f"json: {result.json_path}")
    print(f"expected_output: {result.expected_output_path}")
    print(f"material_report: {result.material_report_path}")
    print(f"material_state_compare: {result.material_state_compare_path}")
    print(f"mtl_schema_gate: {result.mtl_schema_gate_path}")
    print(f"texture_output_gate: {result.texture_output_gate_path}")
    if result.error:
        print(f"error: {result.error}")
    if args.report_summary and result.material_report_path:
        print("material_report_summary:")
        print(format_summary(compact_material_report_summary(load_report(result.material_report_path))))
    if not args.no_rc_log and result.rc_result and result.rc_result.stdout:
        print(result.rc_result.stdout)
    if not args.no_rc_log and result.rc_result and result.rc_result.stderr:
        print(result.rc_result.stderr)

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
