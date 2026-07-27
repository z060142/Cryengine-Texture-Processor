#!/usr/bin/env python
"""Strict recursive JSON comparison with an explicit key-path whitelist."""

import argparse
import fnmatch
import json
import os
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def json_pointer(value, pointer):
    if not pointer:
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or start with '/'")
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(token)]
        else:
            value = value[token]
    return value


def parse_field_specs(specs):
    fields = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(
                f"field projection must use NAME=/json/pointer syntax: {spec!r}"
            )
        name, pointer = spec.split("=", 1)
        if not name or not pointer.startswith("/"):
            raise ValueError(
                f"field projection must use NAME=/json/pointer syntax: {spec!r}"
            )
        if name in fields:
            raise ValueError(f"duplicate projected field name: {name!r}")
        fields[name] = pointer
    return fields


def project_list_rows(value, fields, side):
    if not fields:
        return value
    if not isinstance(value, list):
        raise ValueError(f"{side} field projection requires the selected value to be a list")
    projected = []
    for index, row in enumerate(value):
        try:
            projected.append(
                {name: json_pointer(row, pointer) for name, pointer in fields.items()}
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError(
                f"{side} field projection failed at row {index}: {error}"
            ) from error
    return projected


def is_whitelisted(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def normalized_path(value):
    return os.path.normcase(value.replace("\\", "/"))


def compare(expected, actual, path, ignores, allow_path_separators, result):
    if is_whitelisted(path, ignores):
        result["whitelist_hits"].append(path)
        return

    if type(expected) is not type(actual):
        result["mismatches"].append(
            {
                "path": path,
                "kind": "type",
                "expected": type(expected).__name__,
                "actual": type(actual).__name__,
            }
        )
        return

    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            child = f"{path}.{key}"
            if is_whitelisted(child, ignores):
                result["whitelist_hits"].append(child)
            else:
                result["mismatches"].append({"path": child, "kind": "missing_key"})
        for key in sorted(actual_keys - expected_keys):
            child = f"{path}.{key}"
            if is_whitelisted(child, ignores):
                result["whitelist_hits"].append(child)
            else:
                result["mismatches"].append({"path": child, "kind": "extra_key"})
        for key in sorted(expected_keys & actual_keys):
            compare(
                expected[key],
                actual[key],
                f"{path}.{key}",
                ignores,
                allow_path_separators,
                result,
            )
        return

    if isinstance(expected, list):
        if len(expected) != len(actual):
            result["mismatches"].append(
                {
                    "path": path,
                    "kind": "length",
                    "expected": len(expected),
                    "actual": len(actual),
                }
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            compare(
                expected_item,
                actual_item,
                f"{path}[{index}]",
                ignores,
                allow_path_separators,
                result,
            )
        return

    if expected == actual:
        result["compared_value_count"] += 1
        return

    if (
        allow_path_separators
        and isinstance(expected, str)
        and normalized_path(expected) == normalized_path(actual)
    ):
        result["whitelist_hits"].append(path)
        return

    result["mismatches"].append(
        {
            "path": path,
            "kind": "value",
            "expected": expected,
            "actual": actual,
        }
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected")
    parser.add_argument("actual")
    parser.add_argument("--expected-pointer", default="")
    parser.add_argument("--actual-pointer", default="")
    parser.add_argument(
        "--expected-field",
        action="append",
        default=[],
        metavar="NAME=/POINTER",
        help="Project each expected list row to a named field. Repeat per field.",
    )
    parser.add_argument(
        "--actual-field",
        action="append",
        default=[],
        metavar="NAME=/POINTER",
        help="Project each actual list row to a named field. Repeat per field.",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Explicit fnmatch key path, for example '$.paths.*'. Repeat as needed.",
    )
    parser.add_argument(
        "--allow-path-separators",
        action="store_true",
        help="Treat slash-only string differences as whitelist hits.",
    )
    args = parser.parse_args(argv)

    expected_fields = parse_field_specs(args.expected_field)
    actual_fields = parse_field_specs(args.actual_field)
    if set(expected_fields) != set(actual_fields):
        parser.error(
            "--expected-field and --actual-field must define the same output names"
        )
    expected = project_list_rows(
        json_pointer(load_json(args.expected), args.expected_pointer),
        expected_fields,
        "expected",
    )
    actual = project_list_rows(
        json_pointer(load_json(args.actual), args.actual_pointer),
        actual_fields,
        "actual",
    )
    result = {
        "ok": False,
        "expected": args.expected,
        "actual": args.actual,
        "expected_pointer": args.expected_pointer,
        "actual_pointer": args.actual_pointer,
        "expected_fields": expected_fields,
        "actual_fields": actual_fields,
        "whitelist_patterns": args.ignore,
        "whitelist_hits": [],
        "compared_value_count": 0,
        "mismatches": [],
    }
    compare(
        expected,
        actual,
        "$",
        args.ignore,
        args.allow_path_separators,
        result,
    )
    result["ok"] = not result["mismatches"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
