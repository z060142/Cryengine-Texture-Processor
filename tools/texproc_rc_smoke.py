#!/usr/bin/env python3
"""Run texproc outputs through RC.exe and verify the resulting DDS headers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXPROC_EXE = REPO_ROOT / "rebuild" / "target" / "release" / "texproc.exe"

DDS_MAGIC = b"DDS "
DDS_PIXEL_FORMAT_OFFSET = 76
DDS_DX10_HEADER_OFFSET = 128
DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
CRY_TEXTURE_STAGE = b"FYRC"
CRY_EIF_ATTACHED_ALPHA = 0x400
ALPHA_FOURCC = {"DXT2", "DXT3", "DXT4", "DXT5", "BC2U", "BC2S", "BC3U", "BC3S"}
ALPHA_DXGI_FORMATS = {
    2,  # R32G32B32A32_FLOAT
    10,  # R16G16B16A16_FLOAT
    11,  # R16G16B16A16_UNORM
    24,  # R10G10B10A2_UNORM
    28,  # R8G8B8A8_UNORM
    29,  # R8G8B8A8_UNORM_SRGB
    30,  # R8G8B8A8_UINT
    31,  # R8G8B8A8_SNORM
    32,  # R8G8B8A8_SINT
    74,  # BC2_UNORM
    75,  # BC2_UNORM_SRGB
    77,  # BC3_UNORM
    78,  # BC3_UNORM_SRGB
    87,  # B8G8R8A8_UNORM
    91,  # B8G8R8A8_UNORM_SRGB
    98,  # BC7_UNORM
    99,  # BC7_UNORM_SRGB
}


def _run(command, cwd=None):
    return subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def build_rc_command(rc_exe, tif_path):
    return [str(rc_exe), str(tif_path), "/refresh", "/userdialog=0"]


def read_dds_header(path):
    path = Path(path)
    data = path.read_bytes()[:148]
    if len(data) < 128:
        raise ValueError(f"DDS header is truncated: {path}")
    if data[:4] != DDS_MAGIC:
        raise ValueError(f"DDS magic is invalid: {path}")

    header_size, flags, height, width = struct.unpack_from("<4I", data, 4)
    if header_size != 124:
        raise ValueError(f"DDS header size is {header_size}, expected 124: {path}")
    pixel_format_size, pixel_format_flags = struct.unpack_from(
        "<2I", data, DDS_PIXEL_FORMAT_OFFSET
    )
    if pixel_format_size != 32:
        raise ValueError(
            f"DDS pixel format size is {pixel_format_size}, expected 32: {path}"
        )
    fourcc_bytes = data[DDS_PIXEL_FORMAT_OFFSET + 8 : DDS_PIXEL_FORMAT_OFFSET + 12]
    fourcc = fourcc_bytes.rstrip(b"\0").decode("ascii", errors="replace")
    rgb_bit_count, red_mask, green_mask, blue_mask, alpha_mask = struct.unpack_from(
        "<5I", data, DDS_PIXEL_FORMAT_OFFSET + 12
    )
    cry_image_flags = struct.unpack_from("<I", data, 36)[0]
    cry_texture_stage_bytes = data[124:128]
    cry_texture_stage = cry_texture_stage_bytes.rstrip(b"\0").decode(
        "ascii", errors="replace"
    )
    cry_attached_alpha = (
        cry_texture_stage_bytes == CRY_TEXTURE_STAGE
        and bool(cry_image_flags & CRY_EIF_ATTACHED_ALPHA)
    )

    dxgi_format = None
    dx10_misc_flags2 = None
    if fourcc == "DX10":
        if len(data) < 148:
            raise ValueError(f"DDS DX10 header is truncated: {path}")
        dxgi_format, _, _, _, dx10_misc_flags2 = struct.unpack_from(
            "<5I", data, DDS_DX10_HEADER_OFFSET
        )

    alpha_reasons = []
    if pixel_format_flags & (DDPF_ALPHAPIXELS | DDPF_ALPHA):
        alpha_reasons.append("pixel_format_flags")
    if alpha_mask:
        alpha_reasons.append("alpha_mask")
    if fourcc in ALPHA_FOURCC:
        alpha_reasons.append(f"fourcc:{fourcc}")
    if dxgi_format in ALPHA_DXGI_FORMATS:
        alpha_reasons.append(f"dxgi_format:{dxgi_format}")
    if cry_attached_alpha:
        alpha_reasons.append("cry_eif_attached_alpha")

    return {
        "header_size": header_size,
        "flags": flags,
        "width": width,
        "height": height,
        "pixel_format_size": pixel_format_size,
        "pixel_format_flags": pixel_format_flags,
        "fourcc": fourcc,
        "rgb_bit_count": rgb_bit_count,
        "red_mask": red_mask,
        "green_mask": green_mask,
        "blue_mask": blue_mask,
        "alpha_mask": alpha_mask,
        "cry_image_flags": cry_image_flags,
        "cry_texture_stage": cry_texture_stage,
        "cry_attached_alpha": cry_attached_alpha,
        "dxgi_format": dxgi_format,
        "dx10_misc_flags2": dx10_misc_flags2,
        "alpha_capable": bool(alpha_reasons),
        "alpha_reasons": alpha_reasons,
    }


def write_visual_instructions(path, dds_paths):
    names = "\n".join(f"- `{Path(dds).name}`" for dds in dds_paths)
    text = f"""# T-013 CryEngine visual check

1. Copy the DDS files below into a test folder under the target GameSDK, for
   example `Assets/Textures/T013/`, preserving their filenames.
2. In Sandbox Material Editor, create one material for each basename. Assign
   `_diff` as Diffuse, `_spec` as Specular, `_ddna` as Normal, and `_displ` as
   Height/Displacement.
3. Apply each material to a lit test sphere or cube. Check that diffuse color,
   normal response, gloss variation from `_ddna` alpha, and displacement all
   remain readable. For `KB3D_ENC_GlassClean`, also check that the non-constant
   metallic input did not produce flat or corrupt output.
4. Record PASS/FAIL and the engine/project build in
   `rebuild/tickets/T-013-t5-rc-dds-e2e.md`.

DDS files:

{names}
"""
    path = Path(path)
    path.write_text(text, encoding="utf-8", newline="\n")


def run_smoke(
    *,
    rc_exe,
    texproc_exe,
    inputs,
    work_dir,
    output_path,
    settings_path=None,
    suffixes_path=None,
    allow_unknown=False,
):
    rc_exe = Path(rc_exe).resolve()
    texproc_exe = Path(texproc_exe).resolve()
    inputs = [Path(value).resolve() for value in inputs]
    work_dir = Path(work_dir).resolve()
    output_path = Path(output_path).resolve()
    settings_path = Path(settings_path).resolve() if settings_path else None
    suffixes_path = Path(suffixes_path).resolve() if suffixes_path else None

    for label, path in (
        ("RC executable", rc_exe),
        ("texproc executable", texproc_exe),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} not found: {path}")
    for input_path in inputs:
        if not input_path.exists():
            raise FileNotFoundError(f"texture input not found: {input_path}")
    if settings_path and not settings_path.is_file():
        raise FileNotFoundError(f"settings file not found: {settings_path}")
    if suffixes_path and not suffixes_path.is_file():
        raise FileNotFoundError(f"suffix table not found: {suffixes_path}")

    texture_dir = work_dir / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    stale = sorted(texture_dir.glob("*.tif")) + sorted(texture_dir.glob("*.dds"))
    if stale:
        raise RuntimeError(
            f"texture work directory must not contain existing TIFF/DDS files: {texture_dir}"
        )

    texproc_command = [str(texproc_exe), "process"]
    if settings_path:
        texproc_command.extend(["--settings", str(settings_path)])
    if suffixes_path:
        texproc_command.extend(["--suffixes", str(suffixes_path)])
    if allow_unknown:
        texproc_command.append("--allow-unknown")
    texproc_command.extend(["--out", str(texture_dir)])
    texproc_command.extend(str(path) for path in inputs)
    texproc_result = _run(texproc_command, cwd=REPO_ROOT / "rebuild")
    if texproc_result.returncode != 0:
        raise RuntimeError(
            f"texproc exited with {texproc_result.returncode}: "
            f"{texproc_result.stderr.strip()}"
        )

    tif_paths = sorted(texture_dir.glob("*.tif"), key=lambda path: path.name.casefold())
    if not tif_paths:
        raise RuntimeError("texproc succeeded but produced no TIFF files")

    texture_reports = []
    for tif_path in tif_paths:
        dds_path = tif_path.with_suffix(".dds")
        rc_command = build_rc_command(rc_exe, tif_path)
        rc_result = _run(rc_command, cwd=texture_dir)
        dds_exists = dds_path.is_file()
        dds_header = {}
        dds_header_error = ""
        if dds_exists:
            try:
                dds_header = read_dds_header(dds_path)
            except (OSError, ValueError) as error:
                dds_header_error = str(error)
        requires_alpha = tif_path.stem.casefold().endswith("_ddna")
        alpha_ok = (
            bool(dds_header.get("alpha_capable")) if requires_alpha else None
        )
        texture_reports.append(
            {
                "name": tif_path.name,
                "tif": str(tif_path),
                "tif_sha256": _sha256(tif_path),
                "dds": str(dds_path),
                "dds_exists": dds_exists,
                "dds_size_bytes": dds_path.stat().st_size if dds_exists else 0,
                "dds_sha256": _sha256(dds_path) if dds_exists else "",
                "dds_header": dds_header,
                "dds_header_error": dds_header_error,
                "requires_alpha": requires_alpha,
                "alpha_ok": alpha_ok,
                "rc": {
                    "command": rc_command,
                    "returncode": rc_result.returncode,
                    "stdout": rc_result.stdout,
                    "stderr": rc_result.stderr,
                },
                "ok": (
                    rc_result.returncode == 0
                    and dds_exists
                    and not dds_header_error
                    and (alpha_ok is not False)
                ),
            }
        )

    dds_paths = [
        Path(item["dds"]) for item in texture_reports if item["dds_exists"]
    ]
    visual_instructions = work_dir / "VISUAL_CHECK.md"
    write_visual_instructions(visual_instructions, dds_paths)
    ddna_reports = [item for item in texture_reports if item["requires_alpha"]]
    summary = {
        "ok": bool(texture_reports)
        and all(item["ok"] for item in texture_reports)
        and bool(ddna_reports),
        "input_count": len(inputs),
        "tif_count": len(texture_reports),
        "rc_success_count": sum(
            item["rc"]["returncode"] == 0 for item in texture_reports
        ),
        "dds_count": sum(item["dds_exists"] for item in texture_reports),
        "dds_header_ok_count": sum(
            item["dds_exists"] and not item["dds_header_error"]
            for item in texture_reports
        ),
        "ddna_count": len(ddna_reports),
        "ddna_alpha_ok_count": sum(item["alpha_ok"] is True for item in ddna_reports),
    }
    report = {
        "schema": "cryengine_rust_texproc_rc_smoke.v1",
        "summary": summary,
        "paths": {
            "rc_exe": str(rc_exe),
            "texproc_exe": str(texproc_exe),
            "inputs": [str(path) for path in inputs],
            "settings": str(settings_path) if settings_path else "",
            "suffixes": str(suffixes_path) if suffixes_path else "",
            "work_dir": str(work_dir),
            "texture_dir": str(texture_dir),
            "visual_instructions": str(visual_instructions),
            "report": str(output_path),
        },
        "texproc": {
            "command": texproc_command,
            "returncode": texproc_result.returncode,
            "stdout": texproc_result.stdout,
            "stderr": texproc_result.stderr,
        },
        "textures": texture_reports,
    }
    _write_json(output_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run texproc TIFF outputs through RC.exe and verify DDS headers."
    )
    parser.add_argument(
        "--rc", default=os.environ.get("CE_RC_EXE", ""), help="Path to RC.exe"
    )
    parser.add_argument(
        "--texproc",
        default=os.environ.get("CE_TEXPROC_EXE", str(DEFAULT_TEXPROC_EXE)),
        help="Path to the frozen Rust texproc executable",
    )
    parser.add_argument("--work-dir", required=True, help="Empty smoke artifact root")
    parser.add_argument("--output", default="", help="Smoke report JSON")
    parser.add_argument("--settings", default="", help="Optional texproc settings JSON")
    parser.add_argument("--suffixes", default="", help="Optional suffix table JSON")
    parser.add_argument("--allow-unknown", action="store_true")
    parser.add_argument("inputs", nargs="+", help="Texture files or directories")
    args = parser.parse_args(argv)
    if not args.rc:
        parser.error("--rc or CE_RC_EXE is required")

    output_path = (
        Path(args.output)
        if args.output
        else Path(args.work_dir) / "rust_texproc_rc_smoke.json"
    )
    try:
        report = run_smoke(
            rc_exe=args.rc,
            texproc_exe=args.texproc,
            inputs=args.inputs,
            work_dir=args.work_dir,
            output_path=output_path,
            settings_path=args.settings or None,
            suffixes_path=args.suffixes or None,
            allow_unknown=args.allow_unknown,
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    summary = report["summary"]
    print(f"ok: {summary['ok']}")
    print(f"tiff_to_dds: {summary['dds_count']}/{summary['tif_count']}")
    print(
        "ddna_alpha: "
        f"{summary['ddna_alpha_ok_count']}/{summary['ddna_count']}"
    )
    print(f"visual_package: {Path(args.work_dir).resolve()}")
    print(f"report: {output_path.resolve()}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
