#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rebuild CryEngine common global shader flag tables from .ext files."""

import os
import re

from output_formats.cryengine_mtl_schema import COMMON_GLOBAL_LEGACY_FIX_MASKS


USES_COMMON_GLOBAL_FLAGS = "UsesCommonGlobalFlags"
EXT_NAME_PATTERN = re.compile(r"\bName\s*=\s*(%[A-Za-z0-9_]+)")
GLOBALS_LINE_PATTERN = re.compile(r"^\s*(%[A-Za-z0-9_]+)\s+(0x[0-9a-fA-F]+|[0-9a-fA-F]+)\b")


def extract_common_global_tokens_from_ext(ext_text):
    if USES_COMMON_GLOBAL_FLAGS not in ext_text:
        return []
    return sorted({match.group(1).upper() for match in EXT_NAME_PATTERN.finditer(ext_text)})


def iter_ext_files(shader_ext_dir):
    for filename in sorted(os.listdir(shader_ext_dir)):
        if filename.lower().endswith(".ext"):
            yield os.path.join(shader_ext_dir, filename)


def collect_common_global_tokens(shader_ext_dir):
    tokens = set()
    for ext_path in iter_ext_files(shader_ext_dir):
        with open(ext_path, encoding="utf-8", errors="ignore") as f:
            tokens.update(extract_common_global_tokens_from_ext(f.read()))
    return sorted(tokens)


def build_common_global_flag_table(tokens, legacy_fix_masks=COMMON_GLOBAL_LEGACY_FIX_MASKS):
    table = {token: 1 << index for index, token in enumerate(sorted(set(tokens)))}
    for token, replacement_mask in sorted(legacy_fix_masks.items()):
        if token not in table:
            continue
        old_mask = table[token]
        table[token] = replacement_mask
        for other_token, other_mask in list(table.items()):
            if other_token != token and other_mask == replacement_mask:
                table[other_token] = old_mask
                break
    return table


def build_common_global_flag_table_from_dir(shader_ext_dir):
    return build_common_global_flag_table(collect_common_global_tokens(shader_ext_dir))


def parse_common_global_flags_text(globals_text):
    table = {}
    for line in globals_text.splitlines():
        match = GLOBALS_LINE_PATTERN.match(line)
        if not match:
            continue
        token, mask = match.groups()
        table[token.upper()] = int(mask, 16)
    return table


def load_common_global_flag_table(globals_path):
    with open(globals_path, encoding="utf-8", errors="ignore") as f:
        return parse_common_global_flags_text(f.read())
