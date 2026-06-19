#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gate asset-flow validator reports against practical acceptance coverage."""

import argparse
import json
import os

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()


DEFAULT_REQUIREMENTS = {
    "raw_textures_found": 1,
    "texture_processing_started": 1,
    "texture_format_ok": 1,
    "manifest_generated": 1,
    "model_format_ok": 1,
    "material_slots_ok": 1,
    "mtl_format_ok": 1,
    "material_texture_ok": 1,
}


def load_report(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_requirement(value):
    if ":" not in value:
        return value, 1
    name, count = value.split(":", 1)
    return name, int(count)


def build_requirements(values=None, use_defaults=True):
    requirements = dict(DEFAULT_REQUIREMENTS) if use_defaults else {}
    for value in values or []:
        name, count = parse_requirement(value)
        requirements[name] = count
    return requirements


def evaluate_report(report, requirements=None, require_overall_ok=True):
    requirements = requirements or DEFAULT_REQUIREMENTS
    summary = report.get("summary", {})
    check_counts = summary.get("check_counts", {})
    failures = []
    records = []

    if require_overall_ok and summary.get("ok") is not True:
        failures.append("report summary ok is not true")

    for name, min_pass in requirements.items():
        counts = check_counts.get(name, {})
        passed = int(counts.get("pass", 0))
        failed = int(counts.get("fail", 0))
        na = int(counts.get("na", 0))
        ok = passed >= int(min_pass) and failed == 0
        if passed < int(min_pass):
            failures.append(f"{name} pass count {passed} < required {min_pass}")
        if failed:
            failures.append(f"{name} has {failed} failed checks")
        records.append(
            {
                "check": name,
                "required_pass": int(min_pass),
                "pass": passed,
                "fail": failed,
                "na": na,
                "ok": ok,
            }
        )

    return {
        "schema": "cryengine_asset_flow_acceptance_gate.v1",
        "ok": not failures,
        "summary_ok": summary.get("ok") is True,
        "requirements": records,
        "failures": failures,
    }


def write_report(path, report):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gate an asset-flow validator report against acceptance coverage.")
    parser.add_argument("--report", required=True, help="Asset-flow validator JSON report")
    parser.add_argument("--output", default="", help="Optional JSON gate report path")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="Required check coverage as name:min_pass. Can be passed more than once.",
    )
    parser.add_argument(
        "--no-defaults",
        action="store_true",
        help="Only enforce --require entries instead of the default practical acceptance checks.",
    )
    args = parser.parse_args(argv)

    gate = evaluate_report(
        load_report(args.report),
        requirements=build_requirements(args.require, use_defaults=not args.no_defaults),
    )
    if args.output:
        write_report(args.output, gate)
        print(args.output)
    print(f"ok: {gate['ok']}")
    for record in gate["requirements"]:
        print(
            "{check}: pass={passed} fail={failed} na={na} required={required} ok={ok}".format(
                check=record["check"],
                passed=record["pass"],
                failed=record["fail"],
                na=record["na"],
                required=record["required_pass"],
                ok=record["ok"],
            )
        )
    for failure in gate["failures"]:
        print(f"failure: {failure}")
    return 0 if gate["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
