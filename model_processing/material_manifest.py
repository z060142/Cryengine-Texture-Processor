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


def _manifest_payload(material_manifest_info):
    if not material_manifest_info:
        return {}
    if "manifest" in material_manifest_info:
        return material_manifest_info.get("manifest") or {}
    return material_manifest_info


def material_manifest_materials(source_materials, material_manifest_info=None):
    manifest = _manifest_payload(material_manifest_info)
    manifest_materials = manifest.get("materials", [])
    if not manifest_materials:
        return list(source_materials or [])

    source_by_name = {
        material.get("name"): material
        for material in source_materials or []
        if material.get("name") is not None
    }
    polygon_count_by_slot = {}
    mesh_names_by_slot = {}
    for polygon in manifest.get("polygons", []):
        slot = polygon.get("expected_cgf_material_id", polygon.get("material_table_slot", polygon.get("material_slot")))
        if slot is None:
            continue
        slot = int(slot)
        polygon_count_by_slot[slot] = polygon_count_by_slot.get(slot, 0) + 1
        mesh_name = polygon.get("object")
        if mesh_name:
            mesh_names_by_slot.setdefault(slot, set()).add(mesh_name)

    materials = []
    for material in sorted(manifest_materials, key=lambda item: int(item.get("slot", 0))):
        slot = int(material.get("slot", 0))
        name = material.get("name", "")
        merged = dict(source_by_name.get(name, {}))
        merged.update(
            {
                "name": name,
                "id": slot + 1,
                "index": slot,
                "sub_index": slot,
                "auto_assigned": False,
                "material_table_slot": slot,
                "material_manifest_name": name,
                "material_manifest_kind": material_manifest_kind(manifest),
                "polygon_count": merged.get("polygon_count", polygon_count_by_slot.get(slot, 0)),
                "used_by_polygons": merged.get("used_by_polygons", polygon_count_by_slot.get(slot, 0) > 0),
                "mesh_names": merged.get("mesh_names", sorted(mesh_names_by_slot.get(slot, set()))),
                "material_names": merged.get("material_names", [name]),
                "textures": merged.get("textures", {}),
                "physicalize": merged.get("physicalize", material.get("physicalize")),
            }
        )
        materials.append(merged)
    return materials
