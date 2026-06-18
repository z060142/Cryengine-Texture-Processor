#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify a controlled Blender FBX fixture after RC conversion."""

import argparse
import json

DEFAULT_POLYGON_SPACING = 3.0


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_fixture_material_ids(manifest_path, report_path):
    manifest = load_json(manifest_path)
    report = load_json(report_path)

    expected = sorted(manifest.get("expect_cgf_material_ids", []))
    actual = sorted(report.get("cgf_material_summary", {}).get("material_ids", []))
    return {
        "ok": expected == actual and not report.get("cgf_read_error"),
        "expected": expected,
        "actual": actual,
        "cgf_read_error": report.get("cgf_read_error", ""),
        "cgf_material_id_alignment": report.get("cgf_material_id_alignment", {}),
        "manifest": manifest_path,
        "report": report_path,
    }


def _polygon_from_subset_center(subset, polygon_spacing=DEFAULT_POLYGON_SPACING):
    center = subset.get("center") or []
    if not center:
        raise ValueError("subset has no center")
    return int(round(float(center[0]) / polygon_spacing))


def _collect_subset_polygon_material_ids(report, polygon_spacing=DEFAULT_POLYGON_SPACING):
    actual_by_polygon = {}
    subset_entries = []
    duplicate_polygons = []
    meshes = report.get("cgf_material_summary", {}).get("meshes", [])
    for mesh in meshes:
        for subset in mesh.get("subsets", []):
            polygon = _polygon_from_subset_center(subset, polygon_spacing=polygon_spacing)
            material_id = int(subset.get("material_id"))
            if polygon in actual_by_polygon:
                duplicate_polygons.append(polygon)
            actual_by_polygon[polygon] = material_id
            subset_entries.append(
                {
                    "mesh_chunk_id": mesh.get("chunk_id"),
                    "subset": subset.get("subset"),
                    "polygon": polygon,
                    "center": subset.get("center"),
                    "material_id": material_id,
                    "num_indices": subset.get("num_indices"),
                }
            )
    return actual_by_polygon, subset_entries, duplicate_polygons


def verify_fixture_polygon_material_ids(manifest_path, report_path, polygon_spacing=DEFAULT_POLYGON_SPACING):
    manifest = load_json(manifest_path)
    report = load_json(report_path)

    expected_raw_by_polygon = {
        int(polygon["polygon"]): int(polygon["material_slot"])
        for polygon in manifest.get("polygons", [])
    }
    material_name_by_polygon = {
        int(polygon["polygon"]): polygon.get("material_name", "")
        for polygon in manifest.get("polygons", [])
    }
    request_name_to_sub_index = {
        material.get("name"): int(material.get("sub_index"))
        for material in report.get("request_materials", [])
        if material.get("name") is not None and material.get("sub_index") is not None
    }
    request_sub_index_by_polygon = {
        polygon: request_name_to_sub_index.get(material_name)
        for polygon, material_name in material_name_by_polygon.items()
    }
    actual_by_polygon, subset_entries, duplicate_polygons = _collect_subset_polygon_material_ids(
        report,
        polygon_spacing=polygon_spacing,
    )
    name_remap_mismatches = [
        {
            "polygon": polygon,
            "material_name": material_name_by_polygon.get(polygon, ""),
            "actual_material_id": actual_by_polygon.get(polygon),
            "request_sub_index_for_name": request_sub_index,
        }
        for polygon, request_sub_index in request_sub_index_by_polygon.items()
        if request_sub_index is not None and actual_by_polygon.get(polygon) != request_sub_index
    ]

    return {
        "ok": (
            expected_raw_by_polygon == actual_by_polygon
            and not duplicate_polygons
            and not report.get("cgf_read_error")
        ),
        "expected_raw_fbx_slot_by_polygon": expected_raw_by_polygon,
        "actual_cgf_material_id_by_polygon": actual_by_polygon,
        "request_sub_index_by_polygon_name": request_sub_index_by_polygon,
        "name_remap_mismatches": name_remap_mismatches,
        "duplicate_polygons": duplicate_polygons,
        "subset_entries": subset_entries,
        "cgf_read_error": report.get("cgf_read_error", ""),
        "manifest": manifest_path,
        "report": report_path,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify controlled fixture material ids in an RC material report.")
    parser.add_argument("--manifest", required=True, help="Path to *.fixture_manifest.json")
    parser.add_argument("--report", required=True, help="Path to *.material_report.json")
    parser.add_argument(
        "--check-polygons",
        action="store_true",
        help="Verify each generated polygon's CGF material id by subset center instead of only checking the id set",
    )
    args = parser.parse_args(argv)

    if args.check_polygons:
        result = verify_fixture_polygon_material_ids(args.manifest, args.report)
    else:
        result = verify_fixture_material_ids(args.manifest, args.report)
        try:
            result["polygon_material_check"] = verify_fixture_polygon_material_ids(args.manifest, args.report)
        except (KeyError, TypeError, ValueError):
            result["polygon_material_check"] = {"ok": None, "error": "polygon check unavailable"}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
