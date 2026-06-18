#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for tracking source polygon usage by material slot."""


def empty_material_slot_usage(material_count):
    return {
        index: {
            "polygon_count": 0,
            "mesh_names": set(),
        }
        for index in range(material_count)
    }


def add_polygon_usage(usage_by_slot, material_slot, mesh_name, polygon_count=1):
    if material_slot is None:
        return usage_by_slot
    slot_usage = usage_by_slot.setdefault(
        material_slot,
        {
            "polygon_count": 0,
            "mesh_names": set(),
        },
    )
    slot_usage["polygon_count"] += polygon_count
    if mesh_name:
        slot_usage["mesh_names"].add(mesh_name)
    return usage_by_slot


def finalize_material_slot_usage(usage_by_slot):
    finalized = {}
    for slot, usage in sorted(usage_by_slot.items()):
        polygon_count = int(usage.get("polygon_count", 0))
        mesh_names = usage.get("mesh_names", set())
        finalized[slot] = {
            "polygon_count": polygon_count,
            "mesh_names": sorted(mesh_names),
            "used_by_polygons": polygon_count > 0,
        }
    return finalized


def build_material_slot_usage(meshes, material_count=0):
    usage_by_slot = empty_material_slot_usage(material_count)
    for mesh in meshes or []:
        mesh_name = mesh.get("name", "")
        for polygon in mesh.get("polygons", []):
            add_polygon_usage(
                usage_by_slot,
                polygon.get("material_slot"),
                mesh_name,
            )
    return finalize_material_slot_usage(usage_by_slot)
