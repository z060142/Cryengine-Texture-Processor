import json

from output_formats.material_diagnostics_exporter import (
    build_material_diagnostics_report,
    export_material_diagnostics,
)


def test_build_material_diagnostics_report_summarizes_hazards():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1},
            {
                "name": "Removed",
                "id": 2,
                "deleted": True,
                "polygon_count": 3,
                "used_by_polygons": True,
                "mesh_names": ["ProbeMesh"],
                "material_names": ["Removed"],
                "slot_name_conflict": False,
            },
        ],
        source_model="probe.fbx",
        artifact_kind="fbx",
    )

    assert report["source_model"] == "probe.fbx"
    assert report["artifact_kind"] == "fbx"
    assert report["summary"] == {
        "material_count": 2,
        "diagnostic_count": 1,
        "hazard_count": 1,
    }
    assert report["materials"][1]["name"] == "Removed"
    assert report["materials"][1]["fbx_slot"] == 1
    assert report["materials"][1]["polygon_count"] == 3
    assert report["materials"][1]["used_by_polygons"] is True
    assert report["materials"][1]["mesh_names"] == ["ProbeMesh"]
    assert report["materials"][1]["material_names"] == ["Removed"]
    assert report["materials"][1]["slot_name_conflict"] is False
    assert report["diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert report["diagnostics"][0]["polygon_count"] == 3
    assert report["diagnostics"][0]["used_by_polygons"] is True
    assert report["diagnostics"][0]["mesh_names"] == ["ProbeMesh"]


def test_build_material_diagnostics_report_includes_slot_name_conflict_warning():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wood",
                "id": 1,
                "polygon_count": 2,
                "used_by_polygons": True,
                "mesh_names": ["MeshA", "MeshB"],
                "material_names": ["Metal", "Wood"],
                "slot_name_conflict": True,
            }
        ],
        source_model="conflict.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["slot_name_conflict"] is True
    assert report["materials"][0]["material_names"] == ["Metal", "Wood"]
    assert report["diagnostics"][0]["severity"] == "warning"
    assert report["diagnostics"][0]["code"] == "material_slot_name_conflict"
    assert report["diagnostics"][0]["material_names"] == ["Metal", "Wood"]


def test_build_material_diagnostics_report_includes_case_insensitive_name_collision():
    report = build_material_diagnostics_report(
        [
            {"name": "Wood", "id": 1},
            {"name": "wood", "id": 2},
        ],
        source_model="case.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 2
    assert report["summary"]["hazard_count"] == 2
    assert report["materials"][0]["case_insensitive_name_conflict"] is True
    assert report["materials"][0]["case_insensitive_material_names"] == ["Wood", "wood"]
    assert report["diagnostics"][0]["code"] == "rc_case_insensitive_material_name_collision"
    assert report["diagnostics"][0]["case_insensitive_material_names"] == ["Wood", "wood"]


def test_build_material_diagnostics_report_includes_texture_ref_evidence_warning():
    evidence = [
        {
            "path": "textures/wall_diff.png",
            "filename": "wall_diff.png",
            "texture_type": "diffuse",
            "source_mode": "filesystem_no_bpy",
        }
    ]
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wall",
                "id": 1,
                "texture_ref_evidence": evidence,
            }
        ],
        source_model="wall.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["texture_ref_evidence"] == evidence
    assert report["materials"][0]["diagnostics"][0]["code"] == "degraded_texture_reference_source"
    assert report["diagnostics"][0]["source_modes"] == ["filesystem_no_bpy"]
    assert report["diagnostics"][0]["texture_ref_evidence"] == evidence


def test_build_material_diagnostics_report_does_not_warn_for_blender_texture_evidence():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Wall",
                "id": 1,
                "texture_ref_evidence": [
                    {
                        "path": "textures/wall_diff.png",
                        "filename": "wall_diff.png",
                        "texture_type": "diffuse",
                        "source_mode": "blender",
                    }
                ],
            }
        ]
    )

    assert report["summary"]["diagnostic_count"] == 0
    assert report["diagnostics"] == []


def test_build_material_diagnostics_report_allows_deleted_known_unused_slot():
    report = build_material_diagnostics_report(
        [
            {"name": "Removed", "id": 2, "deleted": True, "polygon_count": 0},
        ],
        source_model="probe.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 0
    assert report["summary"]["hazard_count"] == 0


def test_build_material_diagnostics_report_flags_deleted_known_used_slot():
    report = build_material_diagnostics_report(
        [
            {"name": "Removed", "id": 2, "deleted": True, "polygon_count": 4},
        ],
        source_model="probe.fbx",
    )

    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["fbx_slot"] == 1


def test_build_material_diagnostics_report_keeps_clean_material_records_without_hazards():
    report = build_material_diagnostics_report(
        [
            {"name": "Bark", "id": 1},
            {"name": "Leaves", "id": 2},
        ],
        source_model="tree.fbx",
    )

    assert report["summary"]["hazard_count"] == 0
    assert report["diagnostics"] == []
    assert [item["sub_index"] for item in report["materials"]] == [0, 1]


def test_build_material_diagnostics_report_includes_mtl_shader_policy():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Stone",
                "id": 1,
                "textures": {
                    "normal": "stone_ddn.dds",
                    "specular": "stone_spec.dds",
                    "displacement": "stone_displ.dds",
                },
            }
        ],
        source_model="stone.fbx",
    )

    policy = report["materials"][0]["mtl_shader_policy"]

    assert policy["tokens"] == [
        "%DISPLACEMENT_MAPPING",
        "%NORMAL_MAP",
        "%PHONG_TESSELLATION",
        "%SPECULAR_MAP",
        "%SUBSURFACE_SCATTERING",
    ]
    assert policy["gen_mask_policy"] == "compatibility_preserved_until_roundtrip_evidence"
    assert policy["string_gen_mask_source"] == "source_backed_token_names"
    assert policy["token_reasons"]["%NORMAL_MAP"] == {
        "source": "texture_presence",
        "texture_type": "normal",
    }
    assert policy["public_params"]["TessellationFactorMax"] == "32"
    assert policy["public_param_reasons"]["TessellationFactorMax"] == {
        "source": "displacement_texture_compatibility",
        "texture_type": "displacement",
    }


def test_build_material_diagnostics_report_includes_mtl_flags_policy():
    report = build_material_diagnostics_report(
        [
            {"name": "Stone", "id": 1},
            {"name": "Leaves", "id": 2},
        ],
        source_model="flags.fbx",
    )

    material_policy = report["materials"][0]["mtl_flags_policy"]
    summary = report["mtl_flags_policy_summary"]

    assert material_policy["mtl_flags"] == "524416"
    assert material_policy["analysis"]["names"] == [
        "MTL_FLAG_PURE_CHILD",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert material_policy["usage"] == "exported_sub_material"
    assert summary["material_count"] == 2
    assert summary["root_material"]["mtl_flags"] == "524544"
    assert summary["root_material"]["analysis"]["names"] == [
        "MTL_FLAG_MULTI_SUBMTL",
        "MTL_64BIT_SHADERGENMASK",
    ]
    assert summary["sub_material_flag_counts"] == {"524416": 2}
    assert summary["sub_material_flag_name_counts"] == {
        "MTL_64BIT_SHADERGENMASK": 2,
        "MTL_FLAG_PURE_CHILD": 2,
    }
    assert summary["source_evidence"]["source"].endswith("IMaterial.h")


def test_build_material_diagnostics_report_summarizes_mtl_shader_policy():
    report = build_material_diagnostics_report(
        [
            {
                "name": "Stone",
                "id": 1,
                "textures": {
                    "normal": "stone_ddn.dds",
                    "specular": "stone_spec.dds",
                    "displacement": "stone_displ.dds",
                },
            },
            {
                "name": "Leaves",
                "id": 2,
                "textures": {
                    "normal": "leaves_ddn.dds",
                },
            },
        ],
        source_model="foliage.fbx",
    )

    summary = report["mtl_shader_policy_summary"]

    assert summary["material_count"] == 2
    assert summary["token_counts"] == {
        "%DISPLACEMENT_MAPPING": 1,
        "%NORMAL_MAP": 2,
        "%PHONG_TESSELLATION": 1,
        "%SPECULAR_MAP": 1,
        "%SUBSURFACE_SCATTERING": 2,
    }
    assert summary["gen_mask_policy_counts"] == {
        "compatibility_preserved_until_roundtrip_evidence": 2,
    }
    assert summary["string_gen_mask_source_counts"] == {
        "source_backed_token_names": 2,
    }
    assert summary["public_params_policy_counts"] == {
        "compatibility_preserved_until_roundtrip_evidence": 2,
    }
    assert summary["public_param_counts"]["EmittanceMapGamma"] == 2
    assert summary["public_param_counts"]["TessellationFactorMax"] == 1


def test_build_material_diagnostics_report_flags_used_ignored_source_material():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1},
            {"name": "Material", "id": 2, "polygon_count": 4, "used_by_polygons": True},
        ],
        source_model="default_material.fbx",
    )

    assert report["summary"]["material_count"] == 1
    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["code"] == "rc_omitted_source_material_faces_deleted"
    assert report["diagnostics"][0]["material"] == "Material"
    assert report["diagnostics"][0]["polygon_count"] == 4
    assert report["diagnostics"][0]["omitted_reason"] == "default_name_filter"


def test_build_material_diagnostics_report_flags_manifest_omitted_source_material():
    report = build_material_diagnostics_report(
        [
            {"name": "Visible", "id": 1, "polygon_count": 2, "used_by_polygons": True},
            {"name": "Missing", "id": 2, "polygon_count": 3, "used_by_polygons": True},
        ],
        source_model="manifest_missing.fbx",
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Visible"}],
            }
        },
    )

    assert report["summary"]["material_count"] == 1
    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["code"] == "rc_omitted_source_material_faces_deleted"
    assert report["diagnostics"][0]["material"] == "Missing"
    assert report["diagnostics"][0]["omitted_reason"] == "not_in_request_materials"


def test_build_material_diagnostics_report_includes_manifest_table_diagnostics():
    report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}, {"name": "Metal", "id": 2}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 0, "name": "Metal"},
                    {"slot": 2, "name": "Stone"},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert "material_manifest_duplicate_slot" in codes
    assert "material_manifest_duplicate_name" in codes


def test_build_material_diagnostics_report_includes_manifest_polygon_diagnostics():
    report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}, {"name": "Metal", "id": 2}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Metal"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "Stone", "material_table_slot": 0},
                    {"polygon": 1, "material_name": "Stone", "material_table_slot": 1},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert "material_manifest_polygon_slot_name_mismatch" in codes
    assert "material_manifest_polygon_name_multiple_slots" in codes


def test_build_material_diagnostics_report_includes_invalid_manifest_slot_diagnostics():
    report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}, {"name": "Metal", "id": 2}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": "bad-slot", "name": "Stone"},
                    {"slot": 1, "name": "Metal"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "Stone", "material_table_slot": "bad-polygon-slot"},
                    {"polygon": 1, "material_name": "Metal", "material_table_slot": 1},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert "material_manifest_invalid_material_slot" in codes
    assert "material_manifest_invalid_polygon_slot" in codes
    assert report["summary"]["hazard_count"] >= 2


def test_build_material_diagnostics_report_includes_invalid_manifest_polygon_indices():
    report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Stone"}],
                "polygons": [
                    {"material_name": "Stone", "material_table_slot": 0},
                    {"polygon": True, "material_name": "Stone", "material_table_slot": 0},
                    {"polygon": "2", "material_name": "Stone", "material_table_slot": 0},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert codes.count("material_manifest_invalid_polygon_index") == 2
    assert report["summary"]["hazard_count"] >= 2


def test_build_material_diagnostics_report_includes_invalid_manifest_shape_diagnostics():
    root_report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}],
        material_manifest_info={
            "manifest": ["not", "an", "object"],
        },
    )

    root_codes = [diagnostic["code"] for diagnostic in root_report["diagnostics"]]
    assert "material_manifest_invalid_root" in root_codes

    collection_report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": {"slot": 0, "name": "Stone"},
                "polygons": "not-a-list",
            }
        },
    )

    collection_codes = [diagnostic["code"] for diagnostic in collection_report["diagnostics"]]
    assert "material_manifest_invalid_materials_collection" in collection_codes
    assert "material_manifest_invalid_polygons_collection" in collection_codes

    row_report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": ["bad-row", {"slot": 0, "name": "Stone"}],
                "polygons": [False, {"polygon": 0, "material_name": "Stone", "material_table_slot": 0}],
            }
        },
    )

    row_codes = [diagnostic["code"] for diagnostic in row_report["diagnostics"]]
    assert "material_manifest_invalid_material_row" in row_codes
    assert "material_manifest_invalid_polygon_row" in row_codes


def test_build_material_diagnostics_report_includes_invalid_manifest_name_diagnostics():
    report = build_material_diagnostics_report(
        [{"name": "Stone", "id": 1}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": ""},
                    {"slot": 1, "name": 123},
                    {"slot": 2, "name": "Stone"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "", "material_table_slot": 0},
                    {"polygon": 1, "material_name": 123, "material_table_slot": 1},
                    {"polygon": 2, "material_name": "Stone", "material_table_slot": 2},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert "material_manifest_invalid_material_name" in codes
    assert "material_manifest_invalid_polygon_material_name" in codes


def test_build_material_diagnostics_report_includes_out_of_range_manifest_slot_diagnostics():
    report = build_material_diagnostics_report(
        [{"name": "LastValid", "id": 128}, {"name": "TooHigh", "id": 129}],
        material_manifest_info={
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 127, "name": "LastValid"},
                    {"slot": 128, "name": "TooHigh"},
                ],
                "polygons": [
                    {"polygon": 0, "material_name": "LastValid", "material_table_slot": 127},
                    {"polygon": 1, "material_name": "TooHigh", "material_table_slot": 128},
                ],
            }
        },
    )

    codes = [diagnostic["code"] for diagnostic in report["diagnostics"]]
    assert "material_manifest_material_slot_out_of_rc_range" in codes
    assert "material_manifest_polygon_slot_out_of_rc_range" in codes
    assert "rc_sub_index_out_of_range_deleted" in codes


def test_build_material_diagnostics_report_checks_source_materials_separately_from_output_materials():
    report = build_material_diagnostics_report(
        [{"name": "Visible", "id": 1}],
        source_materials=[
            {"name": "Visible", "id": 1},
            {"name": "Missing", "id": 2, "polygon_count": 3, "used_by_polygons": True},
        ],
    )

    assert report["summary"]["material_count"] == 1
    assert report["summary"]["hazard_count"] == 1
    assert report["diagnostics"][0]["material"] == "Missing"


def test_build_material_diagnostics_report_does_not_warn_when_only_ignored_materials_are_present():
    report = build_material_diagnostics_report(
        [{"name": "Material", "id": 1, "polygon_count": 4, "used_by_polygons": True}],
        source_model="default_only.fbx",
    )

    assert report["summary"]["material_count"] == 0
    assert report["summary"]["diagnostic_count"] == 0
    assert report["diagnostics"] == []


def test_build_material_diagnostics_report_uses_existing_mtl_fallback_when_provided():
    report = build_material_diagnostics_report(
        [
            {"name": "Reserved", "sub_index": 0, "auto_assigned": False},
            {"name": "Moved", "id": 1},
        ],
        existing_submaterial_names=["Reserved", "Moved"],
    )

    assert report["materials"][1]["name"] == "Moved"
    assert report["materials"][1]["sub_index"] == 1
    assert report["diagnostics"][0]["code"] == "sub_index_differs_from_fbx_slot_usage_unknown"


def test_build_material_diagnostics_report_flags_duplicate_sub_index():
    report = build_material_diagnostics_report(
        [
            {"name": "Wood", "id": 1, "sub_index": 0, "auto_assigned": False},
            {"name": "Metal", "id": 2, "sub_index": 0, "auto_assigned": False},
        ],
        source_model="duplicate.fbx",
    )

    assert report["summary"]["hazard_count"] == 3
    assert report["materials"][0]["duplicate_sub_index_conflict"] is True
    assert report["materials"][0]["duplicate_sub_index_material_names"] == ["Wood", "Metal"]
    assert report["diagnostics"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"
    assert report["diagnostics"][0]["duplicate_sub_index_material_names"] == ["Wood", "Metal"]


def test_build_material_diagnostics_report_flags_rc_sub_index_limit():
    report = build_material_diagnostics_report(
        [{"name": "TooHigh", "sub_index": 128, "auto_assigned": False}],
        source_model="too_high.fbx",
    )

    assert report["summary"]["hazard_count"] == 1
    assert report["materials"][0]["sub_index"] == -1
    assert report["materials"][0]["requested_sub_index"] == 128
    assert report["diagnostics"][0]["code"] == "rc_sub_index_out_of_range_deleted"


def test_build_material_diagnostics_report_flags_unknown_physicalize():
    report = build_material_diagnostics_report(
        [{"name": "Odd", "physicalize": "render_only"}],
        source_model="odd.fbx",
    )

    assert report["summary"]["diagnostic_count"] == 1
    assert report["summary"]["hazard_count"] == 0
    assert report["materials"][0]["physicalize"] == "no"
    assert report["materials"][0]["requested_physicalize"] == "render_only"
    assert report["diagnostics"][0]["code"] == "rc_unknown_physicalize_defaults_to_no"


def test_export_material_diagnostics_writes_json(tmp_path):
    output_path = export_material_diagnostics(
        [{"name": "Removed", "id": 1, "deleted": True}],
        str(tmp_path),
        "asset.material_diagnostics.json",
        source_model="asset.fbx",
    )

    payload = json.loads((tmp_path / "asset.material_diagnostics.json").read_text(encoding="utf-8"))

    assert output_path.endswith("asset.material_diagnostics.json")
    assert payload["source_model"] == "asset.fbx"
    assert payload["summary"]["hazard_count"] == 1
    assert payload["materials"][0]["mtl_flags_policy"]["mtl_flags"] == "524416"
    assert payload["mtl_flags_policy_summary"]["sub_material_flag_counts"] == {"524416": 1}
    assert payload["materials"][0]["mtl_shader_policy"]["string_gen_mask"] == "%SUBSURFACE_SCATTERING"
    assert payload["mtl_shader_policy_summary"]["token_counts"] == {"%SUBSURFACE_SCATTERING": 1}
