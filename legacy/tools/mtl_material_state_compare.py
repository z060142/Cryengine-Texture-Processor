#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compare high-value material state between two CryEngine .mtl files."""

import argparse
from collections import Counter
import json
import os
import xml.etree.ElementTree as ET

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()


COMPARE_ATTRS = (
    "Shader",
    "MtlFlags",
    "GenMask",
    "StringGenMask",
)


def _child_attributes(element, child_name):
    child = element.find(child_name)
    if child is None:
        return {}
    return {key: child.get(key, "") for key in sorted(child.attrib)}


def _sub_material_elements(mtl_path):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    if sub_materials is None:
        return []
    return [child for child in list(sub_materials) if child.tag == "Material"]


def _counter_dict(values):
    return {key: count for key, count in sorted(Counter(values).items())}


def load_material_states(mtl_path):
    states = []
    for slot, element in enumerate(_sub_material_elements(mtl_path)):
        public_params = _child_attributes(element, "PublicParams")
        states.append(
            {
                "slot": slot,
                "name": element.get("Name", ""),
                "attrs": {name: element.get(name, "") for name in COMPARE_ATTRS},
                "public_params": public_params,
            }
        )
    return states


def summarize_material_states(states):
    return {
        "material_count": len(states),
        "shader_counts": _counter_dict(state["attrs"].get("Shader", "") for state in states),
        "mtl_flags_counts": _counter_dict(state["attrs"].get("MtlFlags", "") for state in states),
        "string_gen_mask_counts": _counter_dict(state["attrs"].get("StringGenMask", "") for state in states),
        "public_param_name_counts": _counter_dict(
            name
            for state in states
            for name in state["public_params"]
        ),
    }


def _states_by_name(states):
    grouped = {}
    duplicate_names = []
    for state in states:
        name = state["name"]
        if name in grouped:
            duplicate_names.append(name)
        grouped[name] = state
    return grouped, sorted(set(duplicate_names))


def _dict_mismatches(reference, candidate, path):
    mismatches = []
    all_keys = sorted(set(reference) | set(candidate))
    for key in all_keys:
        reference_value = reference.get(key)
        candidate_value = candidate.get(key)
        if reference_value != candidate_value:
            mismatches.append(
                {
                    "path": f"{path}.{key}",
                    "reference": reference_value,
                    "candidate": candidate_value,
                }
            )
    return mismatches


def compare_material_states(reference_states, candidate_states):
    reference_by_name, reference_duplicates = _states_by_name(reference_states)
    candidate_by_name, candidate_duplicates = _states_by_name(candidate_states)
    reference_names = set(reference_by_name)
    candidate_names = set(candidate_by_name)
    material_mismatches = []

    for name in sorted(reference_names & candidate_names):
        reference = reference_by_name[name]
        candidate = candidate_by_name[name]
        differences = [
            *_dict_mismatches(reference["attrs"], candidate["attrs"], "attrs"),
            *_dict_mismatches(reference["public_params"], candidate["public_params"], "public_params"),
        ]
        if differences:
            material_mismatches.append(
                {
                    "name": name,
                    "reference_slot": reference["slot"],
                    "candidate_slot": candidate["slot"],
                    "differences": differences,
                }
            )

    summary_mismatches = _dict_mismatches(
        summarize_material_states(reference_states),
        summarize_material_states(candidate_states),
        "summary",
    )
    return {
        "ok": not (
            reference_duplicates
            or candidate_duplicates
            or (reference_names - candidate_names)
            or (candidate_names - reference_names)
            or summary_mismatches
            or material_mismatches
        ),
        "missing_materials": sorted(reference_names - candidate_names),
        "extra_materials": sorted(candidate_names - reference_names),
        "reference_duplicate_names": reference_duplicates,
        "candidate_duplicate_names": candidate_duplicates,
        "summary_mismatches": summary_mismatches,
        "material_mismatches": material_mismatches,
    }


def build_material_state_compare_report(reference_mtl, candidate_mtl):
    reference_states = load_material_states(reference_mtl)
    candidate_states = load_material_states(candidate_mtl)
    comparison = compare_material_states(reference_states, candidate_states)
    return {
        "schema": "cryengine_mtl_material_state_compare.v1",
        "reference_mtl": os.path.abspath(reference_mtl),
        "candidate_mtl": os.path.abspath(candidate_mtl),
        "reference_summary": summarize_material_states(reference_states),
        "candidate_summary": summarize_material_states(candidate_states),
        "comparison": comparison,
    }


def write_material_state_compare_report(reference_mtl, candidate_mtl, output_path):
    report = build_material_state_compare_report(reference_mtl, candidate_mtl)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare high-value material state between two .mtl files.")
    parser.add_argument("--reference", required=True, help="Reference/native .mtl path")
    parser.add_argument("--candidate", required=True, help="Generated/candidate .mtl path")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    args = parser.parse_args(argv)

    report = write_material_state_compare_report(args.reference, args.candidate, args.output)
    print(args.output)
    print(f"ok: {report['comparison']['ok']}")
    return 0 if report["comparison"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
