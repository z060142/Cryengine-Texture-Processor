#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build asset-flow validator specs from folders of source FBX files."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


FBX_EXTENSIONS = {".fbx"}


def _safe_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "asset")).strip("._")
    return safe or "asset"


def _hash_path(path):
    return hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:8]


def iter_fbx_files(roots):
    for root in roots:
        if not root or not os.path.exists(root):
            continue
        if os.path.isfile(root):
            if Path(root).suffix.lower() in FBX_EXTENSIONS:
                yield os.path.abspath(root)
            continue
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if Path(filename).suffix.lower() in FBX_EXTENSIONS:
                    yield os.path.abspath(os.path.join(dirpath, filename))


def collect_fbx_candidates(roots, max_bytes=None):
    candidates = []
    seen = set()
    for path in iter_fbx_files(roots):
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if max_bytes is not None and size > max_bytes:
            continue
        candidates.append({"path": path, "size_bytes": size})
    return sorted(candidates, key=lambda item: (item["size_bytes"], item["path"].lower()))


def build_spec(roots, work_root, limit=10, max_bytes=None, texture_output_format="tif"):
    selected = collect_fbx_candidates(roots, max_bytes=max_bytes)
    if limit and limit > 0:
        selected = selected[:limit]

    cases = []
    used_names = set()
    for candidate in selected:
        path = candidate["path"]
        stem = _safe_name(Path(path).stem)
        name = f"{stem}_{_hash_path(path)}"
        while name in used_names:
            name = f"{name}_{len(used_names)}"
        used_names.add(name)
        cases.append(
            {
                "name": name,
                "type": "rc",
                "fbx": path,
                "source_size_bytes": candidate["size_bytes"],
            }
        )

    return {
        "work_root": work_root,
        "texture_output_format": texture_output_format,
        "metadata": {
            "builder": "tools.asset_flow_spec_builder",
            "roots": [os.path.abspath(root) for root in roots],
            "limit": limit,
            "max_bytes": max_bytes,
            "case_count": len(cases),
        },
        "cases": cases,
    }


def _parse_size_mb(value):
    if value is None:
        return None
    parsed = float(value)
    if parsed <= 0:
        return None
    return int(parsed * 1024 * 1024)


def write_spec(path, spec):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(spec, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an asset-flow validator spec from FBX folders.")
    parser.add_argument("roots", nargs="+", help="FBX files or folders to scan.")
    parser.add_argument("--output", required=True, help="Output JSON spec path.")
    parser.add_argument("--work-root", required=True, help="ASCII work root used by tools.asset_flow_validator.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of smallest FBX files to include.")
    parser.add_argument("--max-mb", default="10", help="Maximum FBX size in MB. Use 0 to disable.")
    parser.add_argument("--texture-output-format", default="tif", help="Texture output format passed through to the spec.")
    args = parser.parse_args(argv)

    max_bytes = _parse_size_mb(args.max_mb)
    spec = build_spec(
        args.roots,
        args.work_root,
        limit=args.limit,
        max_bytes=max_bytes,
        texture_output_format=args.texture_output_format,
    )
    write_spec(args.output, spec)
    print(args.output)
    print(f"case_count: {len(spec['cases'])}")
    for case in spec["cases"]:
        print(f"{case['name']}: {case['source_size_bytes']} bytes")


if __name__ == "__main__":
    main()
