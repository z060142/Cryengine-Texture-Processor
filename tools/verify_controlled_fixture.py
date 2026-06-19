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


def _coerce_non_negative_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text or not all("0" <= char <= "9" for char in text):
            return None
        return int(text)
    return None


def _coerce_request_sub_index(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= -1 else None
    if isinstance(value, str):
        text = value.strip()
        if text == "-1":
            return -1
        if not text or not all("0" <= char <= "9" for char in text):
            return None
        return int(text)
    return None


def _coerce_center_x(center):
    if not isinstance(center, (list, tuple)) or not center:
        return None
    try:
        return round(float(center[0]), 4)
    except (TypeError, ValueError):
        return None


def _iter_manifest_polygon_evidence(manifest):
    polygons = manifest.get("polygons", []) if isinstance(manifest, dict) else []
    invalid_entries = []
    if not isinstance(polygons, list):
        return [], [
            {
                "ok": False,
                "order": None,
                "error": "invalid_manifest_polygons_collection",
                "collection_type": type(polygons).__name__,
            }
        ]

    rows = []
    for order, polygon in enumerate(polygons):
        if not isinstance(polygon, dict):
            invalid_entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_manifest_polygon_row",
                    "row_type": type(polygon).__name__,
                }
            )
            continue

        polygon_index = _coerce_non_negative_int(polygon.get("polygon"))
        if polygon_index is None:
            invalid_entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_manifest_polygon_index",
                    "polygon": polygon.get("polygon"),
                    "index_type": type(polygon.get("polygon")).__name__,
                }
            )
            continue

        material_slot = _coerce_non_negative_int(polygon.get("material_slot"))
        raw_expected = polygon.get("expected_cgf_material_id", polygon.get("material_slot"))
        expected_cgf_material_id = _coerce_non_negative_int(raw_expected)
        if material_slot is None:
            invalid_entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_manifest_polygon_slot",
                    "polygon": polygon_index,
                    "slot": polygon.get("material_slot"),
                    "slot_type": type(polygon.get("material_slot")).__name__,
                }
            )
        if expected_cgf_material_id is None:
            invalid_entries.append(
                {
                    "ok": False,
                    "order": order,
                    "error": "invalid_manifest_expected_cgf_material_id",
                    "polygon": polygon_index,
                    "expected_cgf_material_id": raw_expected,
                    "slot_type": type(raw_expected).__name__,
                }
            )
            continue

        rows.append(
            {
                "polygon": polygon_index,
                "material_slot": material_slot,
                "expected_cgf_material_id": expected_cgf_material_id,
                "material_name": polygon.get("material_name", ""),
                "center_x": polygon.get("center_x"),
            }
        )
    return rows, invalid_entries


def _polygon_from_subset_center(subset, polygon_spacing=DEFAULT_POLYGON_SPACING):
    center_x = _coerce_center_x(subset.get("center") if isinstance(subset, dict) else None)
    if center_x is None:
        raise ValueError("subset has no center")
    return int(round(center_x / polygon_spacing))


def _build_center_polygon_lookup(manifest):
    lookup = {}
    polygons, _ = _iter_manifest_polygon_evidence(manifest)
    for polygon in polygons:
        if polygon.get("center_x") is None:
            continue
        center_x = _coerce_center_x([polygon.get("center_x")])
        if center_x is None:
            continue
        lookup[center_x] = polygon["polygon"]
    return lookup


def _polygon_from_subset(subset, center_polygon_lookup=None, polygon_spacing=DEFAULT_POLYGON_SPACING):
    center_x = _coerce_center_x(subset.get("center") if isinstance(subset, dict) else None)
    if center_x is None:
        raise ValueError("subset has no center")
    if center_polygon_lookup and center_x in center_polygon_lookup:
        return center_polygon_lookup[center_x]
    return _polygon_from_subset_center(subset, polygon_spacing=polygon_spacing)


def _collect_subset_polygon_material_ids(report, center_polygon_lookup=None, polygon_spacing=DEFAULT_POLYGON_SPACING):
    actual_by_polygon = {}
    subset_entries = []
    invalid_subset_entries = []
    duplicate_polygons = []
    cgf_summary = report.get("cgf_material_summary", {}) if isinstance(report, dict) else {}
    meshes = cgf_summary.get("meshes", []) if isinstance(cgf_summary, dict) else []
    if not isinstance(meshes, list):
        return actual_by_polygon, subset_entries, duplicate_polygons, [
            {"ok": False, "error": "invalid_cgf_meshes_collection", "collection_type": type(meshes).__name__}
        ]
    for mesh_order, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            invalid_subset_entries.append(
                {"ok": False, "error": "invalid_cgf_mesh_row", "mesh_order": mesh_order, "row_type": type(mesh).__name__}
            )
            continue
        subsets = mesh.get("subsets", [])
        if subsets is None:
            subsets = []
        if not isinstance(subsets, list):
            invalid_subset_entries.append(
                {
                    "ok": False,
                    "error": "invalid_cgf_mesh_subsets_collection",
                    "mesh_chunk_id": mesh.get("chunk_id"),
                    "collection_type": type(subsets).__name__,
                }
            )
            continue
        for subset_order, subset in enumerate(subsets):
            if not isinstance(subset, dict):
                invalid_subset_entries.append(
                    {
                        "ok": False,
                        "error": "invalid_cgf_subset_row",
                        "mesh_chunk_id": mesh.get("chunk_id"),
                        "subset_order": subset_order,
                        "row_type": type(subset).__name__,
                    }
                )
                continue
            try:
                polygon = _polygon_from_subset(
                    subset,
                    center_polygon_lookup=center_polygon_lookup,
                    polygon_spacing=polygon_spacing,
                )
            except ValueError as e:
                invalid_subset_entries.append(
                    {
                        "ok": False,
                        "error": "invalid_cgf_subset_center",
                        "mesh_chunk_id": mesh.get("chunk_id"),
                        "subset": subset.get("subset"),
                        "center": subset.get("center"),
                        "message": str(e),
                    }
                )
                continue
            material_id = _coerce_non_negative_int(subset.get("material_id"))
            if material_id is None:
                invalid_subset_entries.append(
                    {
                        "ok": False,
                        "error": "invalid_cgf_subset_material_id",
                        "mesh_chunk_id": mesh.get("chunk_id"),
                        "subset": subset.get("subset"),
                        "material_id": subset.get("material_id"),
                        "material_id_type": type(subset.get("material_id")).__name__,
                    }
                )
                continue
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
    return actual_by_polygon, subset_entries, duplicate_polygons, invalid_subset_entries


def verify_fixture_polygon_material_ids(manifest_path, report_path, polygon_spacing=DEFAULT_POLYGON_SPACING):
    manifest = load_json(manifest_path)
    report = load_json(report_path)

    polygon_rows, invalid_manifest_entries = _iter_manifest_polygon_evidence(manifest)
    raw_fbx_slot_by_polygon = {
        polygon["polygon"]: polygon["material_slot"]
        for polygon in polygon_rows
        if polygon["material_slot"] is not None
    }
    expected_cgf_by_polygon = {
        polygon["polygon"]: polygon["expected_cgf_material_id"]
        for polygon in polygon_rows
    }
    material_name_by_polygon = {
        polygon["polygon"]: polygon.get("material_name", "")
        for polygon in polygon_rows
    }
    invalid_request_entries = []
    request_name_to_sub_index = {}
    request_name_counts = {}
    request_materials = report.get("request_materials", []) if isinstance(report, dict) else []
    if not isinstance(request_materials, list):
        invalid_request_entries.append(
            {
                "ok": False,
                "error": "invalid_request_materials_collection",
                "collection_type": type(request_materials).__name__,
            }
        )
        request_materials = []
    for order, material in enumerate(request_materials):
        if not isinstance(material, dict):
            invalid_request_entries.append(
                {"ok": False, "error": "invalid_request_material_row", "order": order, "row_type": type(material).__name__}
            )
            continue
        name = material.get("name")
        sub_index = _coerce_request_sub_index(material.get("sub_index"))
        if name is None or sub_index is None:
            invalid_request_entries.append(
                {
                    "ok": False,
                    "error": "invalid_request_material_mapping",
                    "order": order,
                    "name": name,
                    "sub_index": material.get("sub_index"),
                }
            )
            continue
        request_name_counts[name] = request_name_counts.get(name, 0) + 1
        request_name_to_sub_index[name] = sub_index
    duplicate_request_names = sorted(name for name, count in request_name_counts.items() if count > 1)
    request_sub_index_by_polygon = {
        polygon: request_name_to_sub_index.get(material_name)
        for polygon, material_name in material_name_by_polygon.items()
    }
    center_polygon_lookup = _build_center_polygon_lookup(manifest)
    actual_by_polygon, subset_entries, duplicate_polygons, invalid_subset_entries = _collect_subset_polygon_material_ids(
        report,
        center_polygon_lookup=center_polygon_lookup,
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
        if request_sub_index is None or actual_by_polygon.get(polygon) != request_sub_index
    ]

    return {
        "ok": (
            expected_cgf_by_polygon == actual_by_polygon
            and not duplicate_polygons
            and not invalid_manifest_entries
            and not invalid_request_entries
            and not invalid_subset_entries
            and not report.get("cgf_read_error")
        ),
        "expected_cgf_material_id_by_polygon": expected_cgf_by_polygon,
        "raw_fbx_slot_by_polygon": raw_fbx_slot_by_polygon,
        "actual_cgf_material_id_by_polygon": actual_by_polygon,
        "request_sub_index_by_polygon_name": request_sub_index_by_polygon,
        "request_name_mapping_ok": not name_remap_mismatches and not duplicate_request_names,
        "duplicate_request_material_names": duplicate_request_names,
        "name_remap_mismatches": name_remap_mismatches,
        "invalid_manifest_entries": invalid_manifest_entries,
        "invalid_request_entries": invalid_request_entries,
        "invalid_subset_entries": invalid_subset_entries,
        "center_polygon_lookup": center_polygon_lookup,
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
