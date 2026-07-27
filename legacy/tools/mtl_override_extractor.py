#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract reusable per-material MTL overrides from a reference CryEngine .mtl."""

import argparse
import json
import os
import xml.etree.ElementTree as ET

try:
    from _repo_path import add_repo_root
except ModuleNotFoundError:
    from tools._repo_path import add_repo_root

add_repo_root()


MATERIAL_NAME_ATTR = "Name"


def extract_material_overrides(mtl_path):
    root = ET.parse(mtl_path).getroot()
    sub_materials = root.find("SubMaterials")
    overrides = {}
    if sub_materials is None:
        return overrides

    for material in list(sub_materials):
        if material.tag != "Material":
            continue
        name = material.get(MATERIAL_NAME_ATTR, "")
        if not name:
            continue
        public_params = material.find("PublicParams")
        cryengine_material = {
            key: value
            for key, value in material.attrib.items()
            if key != MATERIAL_NAME_ATTR
        }
        if public_params is not None:
            cryengine_material["PublicParams"] = dict(public_params.attrib)
        overrides[name] = {
            "cryengine_material": cryengine_material,
        }

    return overrides


def build_override_payload(mtl_path):
    return {
        "schema": "cryengine_material_overrides.v1",
        "source_mtl": os.path.abspath(mtl_path),
        "material_overrides": extract_material_overrides(mtl_path),
    }


def write_override_payload(mtl_path, output_path):
    payload = build_override_payload(mtl_path)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract material override JSON from a CryEngine .mtl file.")
    parser.add_argument("mtl", help="Reference .mtl file")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    payload = write_override_payload(args.mtl, args.output)
    print(args.output)
    print(f"material_overrides: {len(payload['material_overrides'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
