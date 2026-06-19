#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Source-backed RC material-slot limits shared by request and MTL paths."""

RC_MAX_SUB_MATERIALS = 128


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
