#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gate processed texture outputs against CryEngine/RC texture rules."""

import argparse

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()

from output_formats.texture_output_diagnostics import (
    build_texture_output_report_from_paths,
    write_texture_output_report,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate processed texture outputs for CryEngine RC use.")
    parser.add_argument("paths", nargs="+", help="Output texture files or directories to scan")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    args = parser.parse_args(argv)

    report = build_texture_output_report_from_paths(args.paths)
    write_texture_output_report(report, args.output)
    print(args.output)
    print(f"ok: {report['summary']['ok']}")
    print(f"group_count: {report['summary']['group_count']}")
    print(f"output_count: {report['summary']['output_count']}")
    print(f"diagnostic_count: {report['summary']['diagnostic_count']}")
    return 0 if report["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
