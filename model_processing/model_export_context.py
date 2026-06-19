#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared model export preparation for MTL, FBX, and RC request outputs."""

import os
from dataclasses import dataclass
from typing import Any

from model_processing.material_index_assigner import parse_mtl_submaterial_names
from model_processing.material_texture_resolver import (
    build_fbx_texture_data,
    build_mtl_material_data,
)


@dataclass(frozen=True)
class ModelExportContext:
    """Prepared model export data shared by the UI export paths."""

    model_data: dict[str, Any]
    model_filename: str
    base_filename: str
    model_output_dir: str
    texture_output_dir: str
    texture_rel_dir: str
    output_format: str
    mtl_filename: str
    fbx_filename: str
    fbx_output_path: str
    model_texture_dir: str
    existing_mtl_path: str
    existing_submaterial_names: list[str]
    texture_refs: list[Any]
    mtl_materials: list[dict[str, Any]]
    fbx_texture_data: dict[str, dict[str, str]]


def fbx_texture_export_diagnostics(export_context):
    """Return non-blocking diagnostics for FBX texture data availability."""
    if export_context.fbx_texture_data:
        return []

    material_count = len(export_context.mtl_materials)
    return [
        {
            "severity": "warning",
            "code": "fbx_export_no_processed_textures",
            "source_model": export_context.model_filename,
            "material_count": material_count,
            "message": (
                "No processed textures were resolved for FBX material nodes. "
                "FBX/JSON/RC export should still run so material slot mapping can be verified; "
                "FbxExporter will use diffuse fallback paths for material texture nodes."
            ),
        }
    ]


def attach_material_manifest(model_data, model_info):
    """Copy the loaded sidecar material manifest onto a model dict when present."""
    material_manifest = (model_info or {}).get("material_manifest")
    if material_manifest and model_data is not None:
        model_data["material_manifest"] = material_manifest
    return model_data


def build_model_export_context(
    model_data,
    model_filename,
    model_output_dir,
    texture_output_dir,
    texture_refs,
    texture_manager,
    output_format="tif",
    texture_rel_dir="textures",
):
    """
    Build the shared export data used by MTL, FBX, JSON, and diagnostics paths.

    This helper intentionally does not touch Blender or Qt. Callers decide where
    the model_data and texture_refs come from, then use this common context so
    all export artifacts see the same resolved material and texture data.
    """
    if model_data is None:
        raise ValueError("model_data is required")

    model_filename = model_filename or "unknown_model"
    base_filename = os.path.splitext(model_filename)[0]
    output_format = output_format or "tif"
    texture_refs = list(texture_refs or [])

    mtl_filename = f"{base_filename}.mtl"
    fbx_filename = f"{base_filename}.fbx"
    fbx_output_path = os.path.join(model_output_dir, fbx_filename)
    model_texture_dir = os.path.join(model_output_dir, texture_rel_dir)
    existing_mtl_path = os.path.join(model_output_dir, mtl_filename)
    existing_submaterial_names = parse_mtl_submaterial_names(existing_mtl_path)

    mtl_materials = build_mtl_material_data(
        model_data,
        texture_refs,
        texture_manager,
        texture_output_dir,
        output_format,
    )
    fbx_texture_data = build_fbx_texture_data(
        model_data,
        texture_refs,
        texture_manager,
        texture_output_dir,
        output_format,
    )

    return ModelExportContext(
        model_data=model_data,
        model_filename=model_filename,
        base_filename=base_filename,
        model_output_dir=model_output_dir,
        texture_output_dir=texture_output_dir,
        texture_rel_dir=texture_rel_dir,
        output_format=output_format,
        mtl_filename=mtl_filename,
        fbx_filename=fbx_filename,
        fbx_output_path=fbx_output_path,
        model_texture_dir=model_texture_dir,
        existing_mtl_path=existing_mtl_path,
        existing_submaterial_names=existing_submaterial_names,
        texture_refs=texture_refs,
        mtl_materials=mtl_materials,
        fbx_texture_data=fbx_texture_data,
    )
