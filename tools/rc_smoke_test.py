#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Prepare and run a minimal RC FBX import smoke test."""

import argparse
from dataclasses import dataclass
import os
import shutil

from output_formats.json_exporter import export_json
from output_formats.mtl_exporter import export_mtl
from tools.material_mapping_report import build_material_mapping_report, write_material_mapping_report
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


def build_smoke_model_data(asset_name, material_names):
    return {
        "path": f"{asset_name}.fbx",
        "materials": [
            {
                "name": name,
                "id": index + 1,
                "index": index,
            }
            for index, name in enumerate(material_names)
        ],
        # Empty nodes avoids guessing Blender/FBX scene paths for arbitrary samples.
        "scene_hierarchy": [],
        "meshes": [],
    }


def prepare_smoke_bundle(source_fbx_path, work_dir, asset_name=None, material_names=None):
    source_fbx_path = os.path.abspath(source_fbx_path)
    work_dir = os.path.abspath(work_dir)
    asset_name = asset_name or os.path.splitext(os.path.basename(source_fbx_path))[0]
    material_names = material_names or ["Default"]

    os.makedirs(work_dir, exist_ok=True)
    copied_fbx_path = os.path.join(work_dir, f"{asset_name}.fbx")
    if os.path.abspath(source_fbx_path) != os.path.abspath(copied_fbx_path):
        shutil.copy2(source_fbx_path, copied_fbx_path)

    materials_data = [{"name": name, "id": index + 1, "textures": {}} for index, name in enumerate(material_names)]
    mtl_filename = f"{asset_name}.mtl"
    mtl_success, mtl_result = export_mtl(materials_data, work_dir, work_dir, mtl_filename)
    if not mtl_success:
        raise RuntimeError(mtl_result)

    model_data = build_smoke_model_data(asset_name, material_names)
    json_success, json_result = export_json(
        model_data,
        f"{asset_name}.fbx",
        work_dir,
        material_filename=asset_name,
    )
    if not json_success:
        raise RuntimeError(json_result)

    return {
        "copied_fbx_path": copied_fbx_path,
        "mtl_path": mtl_result,
        "json_path": json_result,
    }


def run_rc_smoke_test(
    rc_exe_path,
    source_fbx_path,
    work_dir,
    asset_name=None,
    material_names=None,
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
        )
    except Exception as e:
        return RCSmokeResult(False, work_dir, rc_exe_path, source_fbx_path, error=str(e))

    runner = runner_factory(rc_exe_path)
    rc_result = runner.run(bundle["json_path"], source_fbx_path=bundle["copied_fbx_path"])
    report_path = os.path.join(work_dir, f"{os.path.splitext(os.path.basename(bundle['json_path']))[0]}.material_report.json")
    try:
        report = build_material_mapping_report(
            bundle["json_path"],
            bundle["mtl_path"],
            expected_output_path=rc_result.expected_output_path,
            rc_exe_path=rc_exe_path,
            source_fbx_path=source_fbx_path,
            copied_fbx_path=bundle["copied_fbx_path"],
            rc_returncode=rc_result.returncode,
        )
        write_material_mapping_report(report, report_path)
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
    args = parser.parse_args(argv)

    result = run_rc_smoke_test(
        args.rc,
        args.fbx,
        args.work_dir,
        asset_name=args.asset_name,
        material_names=material_names_from_arg(args.materials),
    )

    print(f"success: {result.success}")
    print(f"work_dir: {result.work_dir}")
    print(f"rc: {result.rc_exe_path}")
    print(f"fbx: {result.copied_fbx_path or result.source_fbx_path}")
    print(f"mtl: {result.mtl_path}")
    print(f"json: {result.json_path}")
    print(f"expected_output: {result.expected_output_path}")
    print(f"material_report: {result.material_report_path}")
    if result.error:
        print(f"error: {result.error}")
    if result.rc_result and result.rc_result.stdout:
        print(result.rc_result.stdout)
    if result.rc_result and result.rc_result.stderr:
        print(result.rc_result.stderr)

    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
