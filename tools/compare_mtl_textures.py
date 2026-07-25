#!/usr/bin/env python3
"""Compare reference MTL texture sections by material name."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET


def normalized_element(element):
    if element is None:
        return None
    return {
        "tag": element.tag,
        "attributes": dict(sorted(element.attrib.items())),
        "text": (element.text or "").strip(),
        "children": [normalized_element(child) for child in element],
    }


def textures_by_material(path):
    root = ET.parse(path).getroot()
    submaterials = root.find("SubMaterials")
    if submaterials is None:
        raise ValueError(f"MTL has no SubMaterials element: {path}")
    result = {}
    for material in submaterials.findall("Material"):
        name = material.attrib.get("Name", "")
        if name in result:
            raise ValueError(f"duplicate material name {name!r}: {path}")
        result[name] = normalized_element(material.find("Textures"))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected")
    parser.add_argument("actual")
    args = parser.parse_args(argv)

    try:
        expected = textures_by_material(args.expected)
        actual = textures_by_material(args.actual)
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    mismatches = []
    compared = 0
    for name, expected_textures in expected.items():
        if name not in actual:
            mismatches.append({"material": name, "kind": "missing_material"})
        elif actual[name] != expected_textures:
            mismatches.append(
                {
                    "material": name,
                    "kind": "textures_mismatch",
                    "expected": expected_textures,
                    "actual": actual[name],
                }
            )
        else:
            compared += 1
    report = {
        "ok": not mismatches,
        "expected": args.expected,
        "actual": args.actual,
        "reference_material_count": len(expected),
        "actual_material_count": len(actual),
        "compared_texture_sections": compared,
        "mismatches": mismatches,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
