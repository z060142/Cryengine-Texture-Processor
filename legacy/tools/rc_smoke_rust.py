#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run a narrow RC.exe smoke test against Rust converter outputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERTER_EXE = REPO_ROOT.parent / "target" / "release" / "converter.exe"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mtl_schema_report import (  # noqa: E402
    build_mtl_schema_report,
    load_material_overrides,
    write_mtl_schema_report,
)
from utils.cgf_material_reader import read_cgf_material_summary  # noqa: E402


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _run(command, cwd=None):
    return subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )


def _mtl_material_names(mtl_path):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return []
    return [material.attrib.get("Name", "") for material in sub_materials.findall("Material")]


def build_rc_command(rc_exe, request_path, copied_fbx_path, cgf_path):
    return [
        str(rc_exe),
        str(request_path),
        "/overwriteextension=fbx",
        f"/overwritesourcefile={copied_fbx_path}",
        f"/overwritefilename={Path(cgf_path).name}",
    ]


def build_material_alignment(manifest, request, mtl_names, cgf_summary):
    expected_ids = [int(value) for value in manifest.get("expect_cgf_material_ids", [])]
    expected_id_set = set(expected_ids)
    manifest_rows = sorted(
        (
            {
                "slot": int(row["slot"]),
                "name": str(row.get("name", "")),
                "physicalize": str(row.get("physicalize", "")),
            }
            for row in manifest.get("materials", [])
            if row.get("slot") is not None and int(row["slot"]) in expected_id_set
        ),
        key=lambda row: row["slot"],
    )
    material_tables = cgf_summary.get("materials", [])
    primary_table = max(
        material_tables,
        key=lambda table: len(table.get("sub_materials", [])),
        default={},
    )
    actual_rows = primary_table.get("sub_materials", [])
    actual_by_slot = {
        int(row["slot"]): row
        for row in actual_rows
        if row.get("slot") is not None
    }
    checks = []
    for expected in manifest_rows:
        actual = actual_by_slot.get(expected["slot"])
        checks.append(
            {
                "slot": expected["slot"],
                "expected_name": expected["name"],
                "actual_name": actual.get("name", "") if actual else "",
                "physicalize_type": actual.get("physicalize_type") if actual else None,
                "ok": bool(actual) and actual.get("name") == expected["name"],
            }
        )

    request_materials = request.get("materials", [])
    placeholder_request = next(
        (
            row
            for row in request_materials
            if str(row.get("name", "")).strip().casefold() == "<unassigned>"
        ),
        None,
    )
    placeholder_slot = (
        int(placeholder_request["sub_index"])
        if placeholder_request and placeholder_request.get("sub_index") is not None
        else None
    )
    placeholder_mtl_slots = [
        index
        for index, name in enumerate(mtl_names)
        if str(name).strip().casefold() == "<unassigned>"
    ]
    placeholder_cgf_slots = [
        int(row["slot"])
        for row in actual_rows
        if str(row.get("name", "")).strip().casefold() == "<unassigned>"
    ]
    placeholder_expected_in_cgf = (
        placeholder_slot is not None and placeholder_slot in expected_id_set
    )
    placeholder_cgf_present = bool(placeholder_cgf_slots)
    placeholder = {
        "name": "<unassigned>",
        "request_present": placeholder_request is not None,
        "request_slot": placeholder_slot,
        "mtl_present": bool(placeholder_mtl_slots),
        "mtl_slots": placeholder_mtl_slots,
        "expected_in_cgf": placeholder_expected_in_cgf,
        "cgf_present": placeholder_cgf_present,
        "cgf_slots": placeholder_cgf_slots,
        "classification": (
            "manifest_expected_cgf_material"
            if placeholder_expected_in_cgf
            else "trailing_unassigned_not_expected_in_cgf"
        ),
    }
    placeholder["ok"] = (
        placeholder["request_present"]
        and placeholder["mtl_present"]
        and placeholder_cgf_present == placeholder_expected_in_cgf
    )

    actual_ids = [int(value) for value in cgf_summary.get("material_ids", [])]
    ids_ok = actual_ids == expected_ids
    names_ok = (
        len(checks) == len(expected_ids)
        and len(actual_rows) == len(expected_ids)
        and all(row["ok"] for row in checks)
    )
    return {
        "ok": ids_ok and names_ok and placeholder["ok"],
        "expected_count": len(expected_ids),
        "matched_count": sum(1 for row in checks if row["ok"]),
        "actual_sub_material_count": len(actual_rows),
        "expected_cgf_material_ids": expected_ids,
        "actual_cgf_material_ids": actual_ids,
        "material_ids_ok": ids_ok,
        "material_names_ok": names_ok,
        "material_table_name": primary_table.get("name", ""),
        "checks": checks,
        "placeholder": placeholder,
    }


def _compact_cgf_summary(summary):
    return {
        "path": summary.get("path", ""),
        "file_version": summary.get("file_version", ""),
        "chunk_count": summary.get("chunk_count", 0),
        "material_ids": summary.get("material_ids", []),
        "materials": summary.get("materials", []),
    }


def run_smoke(
    *,
    rc_exe,
    converter_exe,
    fbx_path,
    manifest_path,
    work_dir,
    output_path,
    overrides_path=None,
    texture_dir=None,
):
    rc_exe = Path(rc_exe).resolve()
    converter_exe = Path(converter_exe).resolve()
    fbx_path = Path(fbx_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    work_dir = Path(work_dir).resolve()
    output_path = Path(output_path).resolve()
    overrides_path = Path(overrides_path).resolve() if overrides_path else None
    texture_dir = Path(texture_dir).resolve() if texture_dir else None

    for label, path in (
        ("RC executable", rc_exe),
        ("converter executable", converter_exe),
        ("FBX input", fbx_path),
        ("material manifest", manifest_path),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    if overrides_path and not overrides_path.is_file():
        raise FileNotFoundError(f"material overrides not found: {overrides_path}")
    if texture_dir and not texture_dir.is_dir():
        raise FileNotFoundError(f"texture directory not found: {texture_dir}")

    rc_work = work_dir / "rc_work"
    rc_work.mkdir(parents=True, exist_ok=True)
    copied_fbx_path = rc_work / fbx_path.name
    if copied_fbx_path != fbx_path:
        shutil.copy2(fbx_path, copied_fbx_path)

    converter_command = [
        str(converter_exe),
        "convert",
        str(copied_fbx_path),
        "--manifest",
        str(manifest_path),
        "--out-dir",
        str(rc_work),
    ]
    if overrides_path:
        converter_command.extend(["--overrides", str(overrides_path)])
    if texture_dir:
        converter_command.extend(["--texture-dir", str(texture_dir)])
    converter_result = _run(converter_command, cwd=REPO_ROOT.parent)
    if converter_result.returncode != 0:
        raise RuntimeError(
            f"Rust converter exited with {converter_result.returncode}: "
            f"{converter_result.stderr.strip()}"
        )
    converter_outputs = json.loads(converter_result.stdout)
    request_path = Path(converter_outputs["request"]).resolve()
    mtl_path = Path(converter_outputs["mtl"]).resolve()
    request = _load_json(request_path)
    manifest = _load_json(manifest_path)

    cgf_path = request_path.with_suffix(f".{str(request.get('output_ext') or 'cgf').lstrip('.')}")
    if cgf_path.exists():
        cgf_path.unlink()
    rc_command = build_rc_command(rc_exe, request_path, copied_fbx_path, cgf_path)
    rc_result = _run(rc_command, cwd=REPO_ROOT.parent)
    cgf_exists = cgf_path.is_file()

    cgf_summary = {}
    cgf_read_error = ""
    if cgf_exists:
        try:
            cgf_summary = read_cgf_material_summary(str(cgf_path))
        except Exception as error:  # The report must preserve reader failures.
            cgf_read_error = str(error)

    mtl_overrides = load_material_overrides(str(overrides_path)) if overrides_path else {}
    mtl_schema_report = build_mtl_schema_report(
        [str(mtl_path)],
        material_overrides=mtl_overrides,
    )
    mtl_schema_gate_path = rc_work / f"{request_path.stem}.mtl_schema_gate.json"
    write_mtl_schema_report(mtl_schema_report, str(mtl_schema_gate_path))

    material_alignment = (
        build_material_alignment(
            manifest,
            request,
            _mtl_material_names(mtl_path),
            cgf_summary,
        )
        if cgf_summary
        else {
            "ok": False,
            "expected_count": len(manifest.get("expect_cgf_material_ids", [])),
            "matched_count": 0,
            "checks": [],
            "placeholder": {"ok": False, "classification": "cgf_unavailable"},
        }
    )
    rc_exit_ok = rc_result.returncode == 0
    mtl_schema_gate_ok = bool(mtl_schema_report.get("gate", {}).get("summary", {}).get("ok"))
    summary = {
        "ok": (
            rc_exit_ok
            and cgf_exists
            and not cgf_read_error
            and material_alignment["ok"]
            and mtl_schema_gate_ok
        ),
        "rc_exit_ok": rc_exit_ok,
        "rc_returncode": rc_result.returncode,
        "cgf_exists": cgf_exists,
        "cgf_read_ok": bool(cgf_summary) and not cgf_read_error,
        "material_alignment_ok": material_alignment["ok"],
        "material_match_count": material_alignment.get("matched_count", 0),
        "material_expected_count": material_alignment.get("expected_count", 0),
        "placeholder_ok": material_alignment.get("placeholder", {}).get("ok", False),
        "mtl_schema_gate_ok": mtl_schema_gate_ok,
    }
    report = {
        "schema": "cryengine_rust_rc_smoke.v1",
        "summary": summary,
        "paths": {
            "rc_exe": str(rc_exe),
            "converter_exe": str(converter_exe),
            "source_fbx": str(fbx_path),
            "copied_fbx": str(copied_fbx_path),
            "manifest": str(manifest_path),
            "overrides": str(overrides_path) if overrides_path else "",
            "texture_dir": str(texture_dir) if texture_dir else "",
            "request": str(request_path),
            "mtl": str(mtl_path),
            "cgf": str(cgf_path),
            "mtl_schema_gate": str(mtl_schema_gate_path),
            "report": str(output_path),
        },
        "converter": {
            "command": converter_command,
            "returncode": converter_result.returncode,
            "stdout": converter_result.stdout,
            "stderr": converter_result.stderr,
        },
        "rc": {
            "command": rc_command,
            "returncode": rc_result.returncode,
            "stdout": rc_result.stdout,
            "stderr": rc_result.stderr,
        },
        "artifacts": {
            "request_sha256": _sha256(request_path),
            "mtl_sha256": _sha256(mtl_path),
            "cgf_sha256": _sha256(cgf_path) if cgf_exists else "",
            "cgf_size_bytes": cgf_path.stat().st_size if cgf_exists else 0,
        },
        "cgf_material_summary": _compact_cgf_summary(cgf_summary) if cgf_summary else {},
        "cgf_read_error": cgf_read_error,
        "material_alignment": material_alignment,
        "mtl_schema_report": {
            "summary": mtl_schema_report.get("summary", {}),
            "gate": mtl_schema_report.get("gate", {}),
        },
    }
    _write_json(output_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run RC.exe against Rust converter request + MTL outputs."
    )
    parser.add_argument("--rc", default=os.environ.get("CE_RC_EXE", ""), help="Path to rc.exe")
    parser.add_argument(
        "--converter",
        default=os.environ.get("CE_CONVERTER_EXE", str(DEFAULT_CONVERTER_EXE)),
        help="Path to the frozen Rust converter executable",
    )
    parser.add_argument("--fbx", required=True, help="Source FBX")
    parser.add_argument(
        "--manifest",
        default="",
        help="Material manifest (default: <fbx>.fbx_material_manifest.json)",
    )
    parser.add_argument("--overrides", default="", help="Optional material overrides JSON")
    parser.add_argument("--texture-dir", default="", help="Optional processed texture directory")
    parser.add_argument("--work-dir", required=True, help="Smoke root; artifacts use work-dir/rc_work")
    parser.add_argument("--output", default="", help="Smoke report JSON")
    args = parser.parse_args(argv)

    fbx_path = Path(args.fbx)
    manifest_path = Path(args.manifest) if args.manifest else Path(f"{fbx_path}_material_manifest.json")
    output_path = Path(args.output) if args.output else Path(args.work_dir) / "rust_rc_smoke.json"
    if not args.rc:
        parser.error("--rc or CE_RC_EXE is required")

    try:
        report = run_smoke(
            rc_exe=args.rc,
            converter_exe=args.converter,
            fbx_path=fbx_path,
            manifest_path=manifest_path,
            work_dir=args.work_dir,
            output_path=output_path,
            overrides_path=args.overrides or None,
            texture_dir=args.texture_dir or None,
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    summary = report["summary"]
    print(f"ok: {summary['ok']}")
    print(f"rc_returncode: {summary['rc_returncode']}")
    print(f"cgf_exists: {summary['cgf_exists']}")
    print(
        "material_alignment: "
        f"{summary['material_match_count']}/{summary['material_expected_count']}"
    )
    print(f"placeholder_ok: {summary['placeholder_ok']}")
    print(f"mtl_schema_gate_ok: {summary['mtl_schema_gate_ok']}")
    print(f"report: {Path(output_path).resolve()}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
