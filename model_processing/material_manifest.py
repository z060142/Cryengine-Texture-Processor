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


def coerce_material_slot(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def material_manifest_table_diagnostics(material_manifest_info=None):
    manifest = _manifest_payload(material_manifest_info)
    manifest_materials = manifest.get("materials", [])
    manifest_polygons = manifest.get("polygons", [])
    diagnostics = []
    if not manifest_materials and not manifest_polygons:
        return diagnostics

    by_slot = {}
    by_name = {}
    for order, material in enumerate(manifest_materials):
        raw_slot = material.get("slot")
        slot = coerce_material_slot(raw_slot)
        name = material.get("name", "")
        if raw_slot is not None and slot is None:
            diagnostics.append(
                {
                    "severity": "hazard",
                    "code": "material_manifest_invalid_material_slot",
                    "manifest_order": order,
                    "material": name,
                    "slot": raw_slot,
                    "message": (
                        "The material manifest has a material row with a non-integer slot. "
                        "Request JSON and MTL generation cannot map this source material to a stable RC sub-index."
                    ),
                }
            )
        if slot is not None:
            by_slot.setdefault(slot, []).append({"order": order, "name": name})
        if name:
            by_name.setdefault(name, []).append({"order": order, "slot": slot})

    for slot, rows in sorted(by_slot.items()):
        if len(rows) <= 1:
            continue
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "material_manifest_duplicate_slot",
                "slot": slot,
                "material_names": [row["name"] for row in rows],
                "manifest_orders": [row["order"] for row in rows],
                "message": (
                    "The material manifest maps multiple material rows to the same slot. "
                    "The generated request will target the same final RC sub_index more than once."
                ),
            }
        )

    for name, rows in sorted(by_name.items()):
        if len(rows) <= 1:
            continue
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "material_manifest_duplicate_name",
                "material": name,
                "slots": [row["slot"] for row in rows],
                "manifest_orders": [row["order"] for row in rows],
                "message": (
                    "The material manifest lists the same material name multiple times. "
                    "The converter collapses exact duplicate request names, so one manifest row can disappear."
                ),
            }
        )

    table_name_by_slot = {
        slot: rows[0]["name"]
        for slot, rows in by_slot.items()
        if len(rows) == 1 and rows[0]["name"]
    }
    polygon_slots_by_name = {}
    polygon_mismatches = []
    for order, polygon in enumerate(manifest_polygons):
        name = polygon.get("material_name", "")
        raw_slot = polygon.get("material_table_slot", polygon.get("expected_cgf_material_id", polygon.get("material_slot")))
        if raw_slot is None or not name:
            continue
        slot = coerce_material_slot(raw_slot)
        if slot is None:
            diagnostics.append(
                {
                    "severity": "hazard",
                    "code": "material_manifest_invalid_polygon_slot",
                    "polygon_order": order,
                    "polygon_material_name": name,
                    "slot": raw_slot,
                    "message": (
                        "The material manifest has polygon evidence with a non-integer material slot. "
                        "The converter cannot prove which RC material id this polygon should use."
                    ),
                }
            )
            continue
        polygon_slots_by_name.setdefault(name, set()).add(slot)
        table_name = table_name_by_slot.get(slot)
        if table_name and table_name != name:
            polygon_mismatches.append(
                {
                    "polygon_order": order,
                    "slot": slot,
                    "polygon_material_name": name,
                    "table_material_name": table_name,
                }
            )

    for mismatch in polygon_mismatches:
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "material_manifest_polygon_slot_name_mismatch",
                **mismatch,
                "message": (
                    "A manifest polygon references a material name that does not match the material table row "
                    "for the same slot. Request/MTL generation follows the material table, while polygon evidence "
                    "says the source geometry uses a different material."
                ),
            }
        )

    for name, slots in sorted(polygon_slots_by_name.items()):
        if len(slots) <= 1:
            continue
        diagnostics.append(
            {
                "severity": "hazard",
                "code": "material_manifest_polygon_name_multiple_slots",
                "material": name,
                "slots": sorted(slots),
                "message": (
                    "Manifest polygon evidence maps the same material name to multiple table slots. "
                    "RC request materials are matched by material name, so this source material cannot "
                    "reliably target multiple final sub-indices."
                ),
            }
        )

    return diagnostics


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
        slot = coerce_material_slot(slot)
        if slot is None:
            continue
        polygon_count_by_slot[slot] = polygon_count_by_slot.get(slot, 0) + 1
        mesh_name = polygon.get("object")
        if mesh_name:
            mesh_names_by_slot.setdefault(slot, set()).add(mesh_name)

    materials = []
    sorted_materials = sorted(
        manifest_materials,
        key=lambda item: (
            coerce_material_slot(item.get("slot")) is None,
            coerce_material_slot(item.get("slot")) or 0,
        ),
    )
    for material in sorted_materials:
        slot = coerce_material_slot(material.get("slot"))
        if slot is None:
            continue
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
