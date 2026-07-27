#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Source-backed RC material policies shared by request, MTL, and diagnostics paths."""

RC_MAX_SUB_MATERIALS = 128
RC_UNKNOWN_PHYSICALIZE_FALLBACK = "no"

RC_PHYSICALIZE_VALUES = {
    "no": "PHYS_GEOM_TYPE_NONE",
    "default": "PHYS_GEOM_TYPE_DEFAULT",
    "obstruct": "PHYS_GEOM_TYPE_OBSTRUCT",
    "no_collide": "PHYS_GEOM_TYPE_NO_COLLIDE",
    "proxy_only": "PHYS_GEOM_TYPE_DEFAULT_PROXY",
}

RC_PHYSICALIZE_DISPLAY = {
    "no": "render",
    "default": "render, collide, raytest",
    "obstruct": "render, collide",
    "no_collide": "render, raytest",
    "proxy_only": "collide, raytest; no draw",
}

EXPLICIT_PHYSICALIZE_KEYS = ("physicalize", "physicalization", "physicalize_setting")
PROXY_PHYSICALIZE_PATTERNS = (
    "proxy",
    "phys",
    "physics",
    "collision",
    "collider",
)


def normalize_rc_sub_index(sub_index):
    """Match RC ImportRequest handling of material `sub_index` values."""
    if sub_index is None:
        return -1
    sub_index = int(sub_index)
    if sub_index >= RC_MAX_SUB_MATERIALS:
        return -1
    return sub_index


def is_supported_rc_sub_index(sub_index):
    if sub_index is None:
        return False
    normalized = normalize_rc_sub_index(sub_index)
    return normalized >= 0 and normalized == int(sub_index)


def normalize_rc_physicalize(value):
    """Match ImportRequest handling: unknown strings fall back to PHYS_GEOM_TYPE_NONE."""
    normalized = str(value or "").strip().lower()
    if normalized in RC_PHYSICALIZE_VALUES:
        return normalized
    return RC_UNKNOWN_PHYSICALIZE_FALLBACK


def _explicit_physicalize(material):
    for key in EXPLICIT_PHYSICALIZE_KEYS:
        if key not in material:
            continue
        value = material.get(key)
        if value is None or value == "":
            continue
        return key, value
    return "", None


def infer_rc_physicalize_from_name(material_name):
    name_lower = (material_name or "").lower()
    if any(pattern in name_lower for pattern in PROXY_PHYSICALIZE_PATTERNS):
        return "proxy_only"
    return "no_collide"


def resolve_rc_physicalize(material, fallback_name=""):
    """Resolve request `physicalize` with explicit material metadata before name heuristics."""
    material = material or {}
    key, raw_value = _explicit_physicalize(material)
    if raw_value is not None:
        value = normalize_rc_physicalize(raw_value)
        return {
            "value": value,
            "source": "explicit",
            "source_key": key,
            "raw_value": raw_value,
            "valid": str(raw_value).strip().lower() in RC_PHYSICALIZE_VALUES,
        }

    material_name = material.get("name", fallback_name)
    return {
        "value": infer_rc_physicalize_from_name(material_name),
        "source": "name_heuristic",
        "source_key": "",
        "raw_value": "",
        "valid": True,
    }


def rc_physicalize_diagnostics(material_name, physicalize_resolution):
    if physicalize_resolution.get("valid", True):
        return []

    return [
        {
            "severity": "warning",
            "code": "rc_unknown_physicalize_defaults_to_no",
            "material": material_name,
            "physicalize": physicalize_resolution["value"],
            "requested_physicalize": physicalize_resolution.get("raw_value", ""),
            "source_key": physicalize_resolution.get("source_key", ""),
            "message": (
                "RC ImportRequest only recognizes no, default, obstruct, no_collide, and proxy_only. "
                "Unknown physicalize values fall back to the same behavior as 'no'."
            ),
        }
    ]
