#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export CryEngine Resource Compiler FBX import request JSON files."""

import json
import os
import traceback

from model_processing.material_index_assigner import parse_mtl_submaterial_names
from output_formats.rc_import_schema import assert_rc_import_request_schema
from output_formats.rc_request_builder import build_import_request, wrap_import_request


def export_json(
    model_data,
    source_filename,
    output_path,
    texture_output_dir=None,
    wrapper_name="direct",
    output_ext="cgf",
    material_filename=None,
):
    """
    Export a CryEngine Resource Compiler FBX import request.

    RC-side `CImportRequest::LoadFromFile()` reads the import fields from the
    JSON root object. Wrapper output is only for legacy/report fixtures.

    Args:
        model_data: Loaded model dict containing materials, meshes, and hierarchy.
        source_filename: FBX file referenced by RC. Relative paths are resolved
            by RC relative to the JSON file.
        output_path: Directory where the JSON file should be written.
        texture_output_dir: Kept for legacy call compatibility; unused here.
        wrapper_name: `direct` for RC, or a legacy wrapper such as `metadata`.
        output_ext: Target model extension, usually `cgf`, `chr`, `skin`, `caf`.
        material_filename: CryEngine material filename without extension.

    Returns:
        tuple: (success, result_path_or_message)
    """
    del texture_output_dir

    try:
        base_name = os.path.splitext(os.path.basename(source_filename))[0]
        json_filename = f"{base_name}.json"
        json_file_path = os.path.join(output_path, json_filename)
        resolved_material_filename = material_filename or base_name
        existing_submaterial_names = []

        if resolved_material_filename and not resolved_material_filename.startswith("%"):
            mtl_basename = resolved_material_filename
            if not mtl_basename.lower().endswith(".mtl"):
                mtl_basename = f"{mtl_basename}.mtl"
            existing_submaterial_names = parse_mtl_submaterial_names(
                os.path.join(output_path, mtl_basename)
            )

        request = build_import_request(
            model_data,
            source_filename=source_filename,
            material_filename=resolved_material_filename,
            output_ext=output_ext,
            existing_submaterial_names=existing_submaterial_names,
        )
        if wrapper_name in (None, "", "direct"):
            assert_rc_import_request_schema(request)
            json_data = request
        else:
            json_data = wrap_import_request(request, wrapper_name=wrapper_name)

        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        with open(json_file_path, "w", encoding="utf-8") as file:
            json.dump(json_data, file, ensure_ascii=False, indent=2)

        print(f"Successfully exported RC import request to: {json_file_path}")
        return True, json_file_path

    except Exception as e:
        error_msg = f"Failed to export RC import request '{source_filename}': {e}"
        print(error_msg)
        traceback.print_exc()
        return False, error_msg


if __name__ == "__main__":
    dummy_model_data = {
        "materials": [
            {"name": "Trunk_Material"},
            {"name": "Leaves_Material"},
            {"name": "Material"},
        ],
        "scene_hierarchy": [
            {
                "name": "Tree",
                "children": [
                    {"name": "Tree_LOD1", "children": []},
                    {"name": "Tree_Proxy", "children": []},
                ],
            }
        ],
    }
    success, result = export_json(
        dummy_model_data,
        "Tree.fbx",
        "Z:/mcp/dandan/output/model_export",
    )
    print(result if success else f"JSON export failed: {result}")
