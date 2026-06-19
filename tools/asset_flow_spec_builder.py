#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Build asset-flow validator specs from folders of source FBX files."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from tools.obj_mtl_report import parse_obj_mtl


FBX_EXTENSIONS = {".fbx"}
MTL_EXTENSIONS = {".mtl"}


def _safe_name(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "asset")).strip("._")
    return safe or "asset"


def _match_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _matches_hint(value, hint):
    hint_key = _match_key(hint)
    if not hint_key:
        return True
    value_key = _match_key(value)
    return bool(value_key) and (value_key.startswith(hint_key) or hint_key.startswith(value_key))


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


def iter_mtl_files(roots):
    for root in roots:
        if not root or not os.path.exists(root):
            continue
        if os.path.isfile(root):
            if Path(root).suffix.lower() in MTL_EXTENSIONS:
                yield os.path.abspath(root)
            continue
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if Path(filename).suffix.lower() in MTL_EXTENSIONS:
                    yield os.path.abspath(os.path.join(dirpath, filename))


def build_mtl_index(roots):
    index = {}
    for path in iter_mtl_files(roots):
        stem = Path(path).stem.lower()
        index.setdefault(stem, []).append(path)
    for paths in index.values():
        paths.sort(key=lambda item: (len(item), item.lower()))
    return index


def _sibling_obj_dir_candidates(fbx_path):
    path = Path(fbx_path)
    parts = list(path.parts)
    candidates = []
    for index, part in enumerate(parts[:-1]):
        if part.lower() == "fbx":
            replaced = parts[:]
            replaced[index] = "OBJ"
            candidates.append(str(Path(*replaced).with_suffix(".mtl")))
            replaced[index] = "Obj"
            candidates.append(str(Path(*replaced).with_suffix(".mtl")))
            replaced[index] = "obj"
            candidates.append(str(Path(*replaced).with_suffix(".mtl")))
    return candidates


def find_obj_mtl_evidence(fbx_path, mtl_index=None):
    stem = Path(fbx_path).stem
    direct_candidates = [
        str(Path(fbx_path).with_suffix(".mtl")),
        *(_sibling_obj_dir_candidates(fbx_path)),
    ]
    for candidate in direct_candidates:
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

    for candidate in (mtl_index or {}).get(stem.lower(), []):
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return ""


def resolve_texture_path_from_obj_mtl(texture_file, mtl_path):
    if not texture_file:
        return ""
    if os.path.isabs(texture_file) and os.path.exists(texture_file):
        return os.path.abspath(texture_file)

    base_dir = os.path.dirname(os.path.abspath(mtl_path))
    direct = os.path.abspath(os.path.join(base_dir, texture_file))
    if os.path.exists(direct):
        return direct

    filename = os.path.basename(texture_file)
    current = Path(base_dir)
    for directory in [current, *current.parents]:
        candidate = directory / "Textures" / filename
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def _related_texture_filenames(texture_path):
    path = Path(texture_path)
    stem = path.stem
    suffix = path.suffix
    lower_stem = stem.lower()
    replacements = []
    for source_suffix in ("_a", "_d", "_diff", "_diffuse", "_albedo"):
        if lower_stem.endswith(source_suffix):
            base = stem[: -len(source_suffix)]
            replacements.extend([f"{base}_n{suffix}", f"{base}_normal{suffix}", f"{base}_s{suffix}", f"{base}_spec{suffix}"])
            break
    return replacements


def expand_related_texture_paths(paths, mtl_path):
    expanded = []
    seen = set()
    for path in paths:
        for candidate in [path, *(_related_texture_filenames(path))]:
            resolved = candidate if os.path.isabs(candidate) and os.path.exists(candidate) else resolve_texture_path_from_obj_mtl(candidate, mtl_path)
            if not resolved:
                continue
            normalized = os.path.normcase(os.path.abspath(resolved))
            if normalized in seen:
                continue
            seen.add(normalized)
            expanded.append(os.path.abspath(resolved))
    return expanded


def texture_paths_from_obj_mtl(mtl_path, name_hint=""):
    if not mtl_path or not os.path.exists(mtl_path):
        return []
    report = parse_obj_mtl(mtl_path)
    paths = []
    seen = set()
    for material in report.get("materials", []):
        material_matches = _matches_hint(material.get("name", ""), name_hint)
        for texture in material.get("textures", []):
            if name_hint and not material_matches and not _matches_hint(texture.get("file", ""), name_hint):
                continue
            candidate = resolve_texture_path_from_obj_mtl(texture.get("file", ""), mtl_path)
            if not candidate:
                continue
            normalized = os.path.normcase(os.path.abspath(candidate))
            if normalized in seen or not os.path.exists(candidate):
                continue
            seen.add(normalized)
            paths.append(os.path.abspath(candidate))
    return expand_related_texture_paths(paths, mtl_path)


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


def build_spec(
    roots,
    work_root,
    limit=10,
    max_bytes=None,
    texture_output_format="tif",
    texture_output_dir="",
    obj_mtl_roots=None,
    include_obj_mtl_evidence=True,
    include_texture_process=False,
    max_textures_per_case=8,
):
    selected = collect_fbx_candidates(roots, max_bytes=max_bytes)
    if limit and limit > 0:
        selected = selected[:limit]

    mtl_roots = list(obj_mtl_roots or roots)
    mtl_index = build_mtl_index(mtl_roots) if include_obj_mtl_evidence else {}
    cases = []
    used_names = set()
    for candidate in selected:
        path = candidate["path"]
        stem = _safe_name(Path(path).stem)
        name = f"{stem}_{_hash_path(path)}"
        while name in used_names:
            name = f"{name}_{len(used_names)}"
        used_names.add(name)
        case_texture_output_dir = texture_output_dir
        texture_paths = []
        case = {
            "name": name,
            "type": "rc",
            "fbx": path,
            "source_size_bytes": candidate["size_bytes"],
        }
        obj_mtl_evidence = find_obj_mtl_evidence(path, mtl_index) if include_obj_mtl_evidence else ""
        if obj_mtl_evidence:
            case["obj_mtl_evidence"] = obj_mtl_evidence
            if include_texture_process:
                texture_paths = texture_paths_from_obj_mtl(obj_mtl_evidence, name_hint=Path(path).stem)
        source_texture_count = len(texture_paths)
        texture_limit_applied = False
        if max_textures_per_case and max_textures_per_case > 0 and len(texture_paths) > max_textures_per_case:
            texture_paths = texture_paths[:max_textures_per_case]
            texture_limit_applied = True
        if include_texture_process and texture_paths and not case_texture_output_dir:
            case_texture_output_dir = os.path.join(work_root, f"{name}_textures")
            cases.append(
                {
                    "name": f"{name}_raw_textures",
                    "type": "texture_process",
                    "textures": texture_paths,
                    "output_dir": case_texture_output_dir,
                    "source_obj_mtl_evidence": obj_mtl_evidence,
                    "source_texture_count": source_texture_count,
                    "texture_limit_applied": texture_limit_applied,
                }
            )
        if case_texture_output_dir:
            case["texture_output_dir"] = case_texture_output_dir
        cases.append(case)

    return {
        "work_root": work_root,
        "texture_output_format": texture_output_format,
        "metadata": {
            "builder": "tools.asset_flow_spec_builder",
            "roots": [os.path.abspath(root) for root in roots],
            "limit": limit,
            "max_bytes": max_bytes,
            "obj_mtl_roots": [os.path.abspath(root) for root in mtl_roots],
            "include_obj_mtl_evidence": include_obj_mtl_evidence,
            "texture_output_dir": texture_output_dir,
            "include_texture_process": include_texture_process,
            "max_textures_per_case": max_textures_per_case,
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
    parser.add_argument(
        "--texture-output-dir",
        default="",
        help="Optional processed texture directory to attach to generated rc cases.",
    )
    parser.add_argument(
        "--obj-mtl-root",
        action="append",
        default=[],
        help="Optional root to scan for Wavefront OBJ .mtl evidence. Can be passed more than once.",
    )
    parser.add_argument(
        "--no-obj-mtl-evidence",
        action="store_true",
        help="Do not try to attach OBJ .mtl evidence to generated rc cases.",
    )
    parser.add_argument(
        "--include-texture-process",
        action="store_true",
        help="Add texture_process cases from OBJ .mtl texture references when possible.",
    )
    parser.add_argument(
        "--max-textures-per-case",
        type=int,
        default=8,
        help="Maximum raw textures to add to each generated texture_process case. Use 0 to disable.",
    )
    args = parser.parse_args(argv)

    max_bytes = _parse_size_mb(args.max_mb)
    spec = build_spec(
        args.roots,
        args.work_root,
        limit=args.limit,
        max_bytes=max_bytes,
        texture_output_format=args.texture_output_format,
        texture_output_dir=args.texture_output_dir,
        obj_mtl_roots=args.obj_mtl_root or args.roots,
        include_obj_mtl_evidence=not args.no_obj_mtl_evidence,
        include_texture_process=args.include_texture_process,
        max_textures_per_case=args.max_textures_per_case,
    )
    write_spec(args.output, spec)
    print(args.output)
    print(f"case_count: {len(spec['cases'])}")
    for case in spec["cases"]:
        evidence = f" obj_mtl={case['obj_mtl_evidence']}" if case.get("obj_mtl_evidence") else ""
        if case.get("type") == "rc":
            print(f"{case['name']}: {case['source_size_bytes']} bytes{evidence}")
        else:
            print(f"{case['name']}: {case['type']} textures={len(case.get('textures', []))}")


if __name__ == "__main__":
    main()
