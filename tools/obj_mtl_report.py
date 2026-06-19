#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Report material and texture references from Wavefront OBJ .mtl files."""

import argparse
import json
import os
import shlex


TEXTURE_STATEMENTS = {
    "map_Ka": "ambient",
    "map_Kd": "diffuse",
    "map_Ks": "specular",
    "map_bump": "normal",
    "bump": "normal",
    "map_Bump": "normal",
    "disp": "displacement",
    "map_d": "opacity",
    "map_refl": "reflection",
    "refl": "reflection",
    "map_Ke": "emissive",
}


def _split_mtl_line(line):
    try:
        return shlex.split(line, posix=False)
    except ValueError:
        return line.split()


def _texture_filename(tokens):
    if len(tokens) < 2:
        return ""

    # OBJ MTL texture lines may include options before the filename. The Dark
    # Fantasy pack also has unquoted filenames with spaces, so join the payload
    # after a small best-effort option skip instead of taking only the last token.
    payload = tokens[1:]
    while payload and payload[0].startswith("-"):
        option = payload.pop(0)
        arg_count = 0
        if option in {"-s", "-o", "-t"}:
            arg_count = min(3, len(payload))
        elif option in {"-bm", "-boost", "-mm", "-clamp", "-blendu", "-blendv"}:
            arg_count = min(1, len(payload))
        for _ in range(arg_count):
            payload.pop(0)

    return " ".join(payload).strip().strip('"')


def parse_obj_mtl(path):
    materials = []
    current = None
    diagnostics = []

    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            tokens = _split_mtl_line(line)
            if not tokens:
                continue

            statement = tokens[0]
            if statement == "newmtl":
                name = " ".join(tokens[1:]).strip() or f"Material_{len(materials)}"
                current = {
                    "name": name,
                    "line": line_number,
                    "textures": [],
                    "properties": {},
                }
                materials.append(current)
                continue

            if current is None:
                diagnostics.append(
                    {
                        "severity": "warning",
                        "line": line_number,
                        "message": f"Statement before first newmtl ignored: {statement}",
                    }
                )
                continue

            if statement in TEXTURE_STATEMENTS:
                filename = _texture_filename(tokens)
                current["textures"].append(
                    {
                        "statement": statement,
                        "texture_type": TEXTURE_STATEMENTS[statement],
                        "file": filename,
                        "filename": os.path.basename(filename),
                        "line": line_number,
                    }
                )
            else:
                current["properties"][statement] = " ".join(tokens[1:])

    texture_count = sum(len(material["textures"]) for material in materials)
    return {
        "schema": "wavefront_obj_mtl_report.v1",
        "source": os.path.abspath(path),
        "summary": {
            "material_count": len(materials),
            "texture_reference_count": texture_count,
            "diagnostic_count": len(diagnostics),
            "ok": len(materials) > 0 and len(diagnostics) == 0,
        },
        "materials": materials,
        "diagnostics": diagnostics,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report Wavefront OBJ .mtl material texture references.")
    parser.add_argument("mtl", help="Path to a Wavefront OBJ .mtl file")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args(argv)

    report = parse_obj_mtl(args.mtl)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    else:
        print(text)

    return 0 if report["summary"]["material_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
