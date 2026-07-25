#!/usr/bin/env python
"""Compare two XML documents as normalized ordered trees."""

import argparse
import fnmatch
import json
import sys
import xml.etree.ElementTree as ET


def normalized_element(element):
    return {
        "tag": element.tag,
        "attributes": dict(sorted(element.attrib.items())),
        "text": (element.text or "").strip(),
        "children": [normalized_element(child) for child in element],
    }


def is_whitelisted(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def compare(expected, actual, path, ignores, result):
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
            compare(expected[key], actual[key], f"{path}.{key}", ignores, result)
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
            compare(expected_item, actual_item, f"{path}[{index}]", ignores, result)
        return

    if expected == actual:
        result["compared_value_count"] += 1
    else:
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
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Explicit fnmatch tree path. Repeat as needed.",
    )
    args = parser.parse_args(argv)

    expected = normalized_element(ET.parse(args.expected).getroot())
    actual = normalized_element(ET.parse(args.actual).getroot())
    result = {
        "ok": False,
        "expected": args.expected,
        "actual": args.actual,
        "whitelist_patterns": args.ignore,
        "whitelist_hits": [],
        "compared_value_count": 0,
        "mismatches": [],
    }
    compare(expected, actual, "$", args.ignore, result)
    result["ok"] = not result["mismatches"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
