#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for tracking source polygon usage by material slot."""


def empty_material_slot_usage(material_count):
    return {
        index: {
            "polygon_count": 0,
            "mesh_names": set(),
            "material_names": set(),
        }
        for index in range(material_count)
    }


def add_polygon_usage(usage_by_slot, material_slot, mesh_name, polygon_count=1, material_name=""):
    if material_slot is None:
        return usage_by_slot
    slot_usage = usage_by_slot.setdefault(
        material_slot,
        {
            "polygon_count": 0,
            "mesh_names": set(),
            "material_names": set(),
        },
    )
    slot_usage["polygon_count"] += polygon_count
    if mesh_name:
        slot_usage["mesh_names"].add(mesh_name)
    if material_name:
        slot_usage["material_names"].add(material_name)
    return usage_by_slot


def add_slot_material_name(usage_by_slot, material_slot, material_name):
    if material_slot is None or not material_name:
        return usage_by_slot
    slot_usage = usage_by_slot.setdefault(
        material_slot,
        {
            "polygon_count": 0,
            "mesh_names": set(),
            "material_names": set(),
        },
    )
    slot_usage["material_names"].add(material_name)
    return usage_by_slot


def finalize_material_slot_usage(usage_by_slot):
    finalized = {}
    for slot, usage in sorted(usage_by_slot.items()):
        polygon_count = int(usage.get("polygon_count", 0))
        mesh_names = usage.get("mesh_names", set())
        material_names = usage.get("material_names", set())
        finalized[slot] = {
            "polygon_count": polygon_count,
            "mesh_names": sorted(mesh_names),
            "material_names": sorted(material_names),
            "slot_name_conflict": len(material_names) > 1,
            "used_by_polygons": polygon_count > 0,
        }
    return finalized


def build_material_slot_usage(meshes, material_count=0):
    usage_by_slot = empty_material_slot_usage(material_count)
    for mesh in meshes or []:
        mesh_name = mesh.get("name", "")
        for slot in mesh.get("material_slots", []):
            add_slot_material_name(
                usage_by_slot,
                slot.get("slot"),
                slot.get("name", ""),
            )
        for polygon in mesh.get("polygons", []):
            add_polygon_usage(
                usage_by_slot,
                polygon.get("material_slot"),
                mesh_name,
                material_name=polygon.get("material_name", ""),
            )
    return finalize_material_slot_usage(usage_by_slot)
