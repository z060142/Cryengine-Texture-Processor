#!/usr/bin/env python
"""Compare legacy Python filename grouping with the signed Rust T-012 scan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from core.texture_manager import TextureManager


def _key(path: str | Path) -> str:
    value = str(path).replace("\\\\?\\", "")
    return str(Path(value).resolve()).casefold()


def _expected_def(filename: str, python_type: str, rust_type: str, python_base: str, rust_base: str) -> str | None:
    stem = Path(filename).stem.casefold()
    if stem.endswith(("_a", "_d")):
        return "DEF-14"
    if stem.endswith(("_arm", "_orm", "_rma", "_rm", "_ra")):
        return "DEF-16"
    if rust_type == "unknown" and python_type != "unknown":
        return "DEF-17"
    if python_type == "unknown" and rust_type != "unknown":
        return "DEF-17"
    if python_base.casefold() == rust_base.casefold() and python_base != rust_base:
        return "DEF-18"
    if python_base != rust_base:
        return "DEF-15/22"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rust_scan = json.loads(args.rust.read_text(encoding="utf-8"))
    rust_entries: dict[str, dict[str, object]] = {}
    for group in rust_scan["groups"]:
        for entry in list(group["slots"].values()) + group["unknown"]:
            rust_entries[_key(entry["path"])] = entry

    manager = TextureManager()
    differences: list[dict[str, object]] = []
    unexpected: list[dict[str, object]] = []
    files = sorted(
        (path for path in args.input.rglob("*") if path.is_file()),
        key=lambda path: str(path).casefold(),
    )
    for path in files:
        rust = rust_entries.get(_key(path))
        if rust is None:
            unexpected.append({"path": str(path), "reason": "missing from Rust scan"})
            continue
        python_type, python_base = manager.classify_texture(str(path))
        rust_type = str(rust["source_type"])
        rust_base = str(rust["base_name"])
        if python_type == rust_type and python_base == rust_base:
            continue
        defect = _expected_def(path.name, python_type, rust_type, python_base, rust_base)
        row = {
            "path": str(path),
            "python": {"source_type": python_type, "base_name": python_base},
            "rust": {"source_type": rust_type, "base_name": rust_base},
            "defect": defect,
        }
        differences.append(row)
        if defect is None:
            unexpected.append(row)

    report = {
        "version": 1,
        "input": str(args.input.resolve()),
        "file_count": len(files),
        "rust_group_count": len(rust_scan["groups"]),
        "difference_count": len(differences),
        "unexpected_count": len(unexpected),
        "differences": differences,
        "unexpected": unexpected,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("file_count", "rust_group_count", "difference_count", "unexpected_count")}))
    return 0 if not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
