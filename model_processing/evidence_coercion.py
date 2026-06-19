#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared coercion helpers for material-mapping evidence."""

import math


def coerce_non_negative_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text or not all("0" <= char <= "9" for char in text):
            return None
        return int(text)
    return None


def coerce_request_sub_index(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= -1 else None
    if isinstance(value, str):
        text = value.strip()
        if text == "-1":
            return -1
        if not text or not all("0" <= char <= "9" for char in text):
            return None
        return int(text)
    return None


def coerce_center_x(center):
    if not isinstance(center, (list, tuple)) or not center:
        return None
    try:
        center_x = float(center[0])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(center_x):
        return None
    return round(center_x, 4)
