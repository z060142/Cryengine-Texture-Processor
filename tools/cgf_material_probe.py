#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inspect material subset ids from CryEngine CGF files."""

import argparse
import json

from utils.cgf_material_reader import read_cgf_material_summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read CGF MeshSubsets material ids.")
    parser.add_argument("cgf", nargs="+", help="Path to one or more .cgf files")
    args = parser.parse_args(argv)

    summaries = [read_cgf_material_summary(path) for path in args.cgf]
    payload = summaries[0] if len(summaries) == 1 else summaries
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
