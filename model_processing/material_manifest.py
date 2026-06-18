#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for FBX material-table sidecar manifests."""

import json
import os


MATERIAL_MANIFEST_SUFFIXES = (".fixture_manifest.json", ".fbx_material_manifest.json")


def discover_material_manifest(source_path="", copied_path=""):
    for fbx_path in (source_path, copied_path):
        if not fbx_path:
            continue
        stem = os.path.splitext(fbx_path)[0]
        for suffix in MATERIAL_MANIFEST_SUFFIXES:
            candidate = stem + suffix
            if os.path.exists(candidate):
                return candidate
    return ""


def load_material_manifest(manifest_path):
    if not manifest_path or not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def material_manifest_kind(manifest):
    return (manifest or {}).get("fixture_kind", (manifest or {}).get("manifest_kind", ""))


def material_manifest_summary(manifest, manifest_path=""):
    manifest = manifest or {}
    return {
        "path": manifest_path,
        "kind": material_manifest_kind(manifest),
        "material_count": len(manifest.get("materials", [])),
        "polygon_count": len(manifest.get("polygons", [])),
    }


def material_manifest_table_rows(manifest):
    rows = []
    for material in (manifest or {}).get("materials", []):
        rows.append(
            {
                "slot": material.get("slot"),
                "name": material.get("name", ""),
                "source": material.get("first_object", material.get("requested_name", "")),
                "local_slot": material.get("first_local_slot"),
            }
        )
    return rows
