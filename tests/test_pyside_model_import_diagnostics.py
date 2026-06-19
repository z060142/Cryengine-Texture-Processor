import json

from ui_pyside.model_import import (
    collect_model_material_diagnostics,
    default_rc_smoke_work_dir,
    generate_model_material_manifest,
    load_model_material_manifest,
    material_manifest_summary_text,
    model_load_state_text,
    model_display_name,
    rc_material_smoke_summary_text,
    run_model_material_rc_smoke,
    texture_source_mode_text,
    texture_source_summary_text,
)
from tools.rc_smoke_test import RCSmokeResult


def test_collect_model_material_diagnostics_reports_deleted_known_slot():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {"name": "Visible", "id": 1},
                {
                    "name": "Removed",
                    "id": 2,
                    "deleted": True,
                    "polygon_count": 2,
                    "used_by_polygons": True,
                    "mesh_names": ["ProbeMesh"],
                },
            ]
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["code"] == "deleted_known_fbx_slot_usage_unknown"
    assert diagnostics[0]["material"] == "Removed"
    assert diagnostics[0]["fbx_slot"] == 1
    assert diagnostics[0]["polygon_count"] == 2
    assert diagnostics[0]["used_by_polygons"] is True
    assert diagnostics[0]["mesh_names"] == ["ProbeMesh"]


def test_collect_model_material_diagnostics_is_empty_for_normal_slots():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {"name": "Bark", "id": 1},
                {"name": "Leaves", "id": 2},
            ]
        }
    )

    assert diagnostics == []


def test_collect_model_material_diagnostics_reports_slot_name_conflict_warning():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {
                    "name": "Wood",
                    "id": 1,
                    "material_names": ["Metal", "Wood"],
                    "slot_name_conflict": True,
                },
            ]
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["code"] == "material_slot_name_conflict"
    assert diagnostics[0]["material_names"] == ["Metal", "Wood"]


def test_collect_model_material_diagnostics_reports_manifest_omitted_material():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {"name": "Visible", "id": 1, "polygon_count": 2, "used_by_polygons": True},
                {"name": "Missing", "id": 2, "polygon_count": 3, "used_by_polygons": True},
            ],
            "material_manifest": {
                "manifest": {
                    "manifest_kind": "blender-fbx-material-inspection",
                    "materials": [{"slot": 0, "name": "Visible"}],
                }
            },
        }
    )

    assert diagnostics[0]["code"] == "rc_omitted_source_material_faces_deleted"
    assert diagnostics[0]["material"] == "Missing"
    assert diagnostics[0]["omitted_reason"] == "not_in_request_materials"


def test_collect_model_material_diagnostics_reports_manifest_duplicate_name():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "material_manifest": {
                "manifest": {
                    "manifest_kind": "blender-fbx-material-inspection",
                    "materials": [
                        {"slot": 0, "name": "Stone"},
                        {"slot": 1, "name": "Stone"},
                    ],
                }
            },
        }
    )

    assert diagnostics[0]["code"] == "material_manifest_duplicate_name"
    assert diagnostics[0]["material"] == "Stone"


def test_collect_model_material_diagnostics_reports_manifest_polygon_mismatch():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}, {"name": "Metal", "id": 2}],
            "material_manifest": {
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
        }
    )

    assert diagnostics[0]["code"] == "material_manifest_polygon_slot_name_mismatch"
    assert diagnostics[0]["polygon_material_name"] == "Stone"
    assert diagnostics[0]["table_material_name"] == "Metal"


def test_collect_model_material_diagnostics_reports_invalid_manifest_slots():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}, {"name": "Metal", "id": 2}],
            "material_manifest": {
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
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert "material_manifest_invalid_material_slot" in codes
    assert "material_manifest_invalid_polygon_slot" in codes


def test_collect_model_material_diagnostics_reports_invalid_manifest_polygon_indices():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "material_manifest": {
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
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert codes.count("material_manifest_invalid_polygon_index") == 2


def test_collect_model_material_diagnostics_reports_invalid_manifest_shape():
    root_diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "material_manifest": {
                "manifest": ["not", "an", "object"],
            },
        }
    )

    root_codes = [diagnostic["code"] for diagnostic in root_diagnostics]
    assert "material_manifest_invalid_root" in root_codes

    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "material_manifest": {
                "manifest": {
                    "manifest_kind": "blender-fbx-material-inspection",
                    "materials": ["bad-row", {"slot": 0, "name": "Stone"}],
                    "polygons": [False, {"polygon": 0, "material_name": "Stone", "material_table_slot": 0}],
                }
            },
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert "material_manifest_invalid_material_row" in codes
    assert "material_manifest_invalid_polygon_row" in codes


def test_collect_model_material_diagnostics_reports_invalid_manifest_names():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "material_manifest": {
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
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert "material_manifest_invalid_material_name" in codes
    assert "material_manifest_invalid_polygon_material_name" in codes


def test_collect_model_material_diagnostics_reports_out_of_range_manifest_slots():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "LastValid", "id": 128}, {"name": "TooHigh", "id": 129}],
            "material_manifest": {
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
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert "material_manifest_material_slot_out_of_rc_range" in codes
    assert "material_manifest_polygon_slot_out_of_rc_range" in codes


def test_collect_model_material_diagnostics_reports_degraded_model_load_status():
    diagnostics = collect_model_material_diagnostics(
        {
            "load_status": "import_only",
            "load_warning": "filesystem texture scan only",
            "materials": [{"name": "Asset", "id": 1}],
        }
    )

    assert diagnostics[0]["code"] == "degraded_model_load_status"
    assert diagnostics[0]["severity"] == "warning"
    assert diagnostics[0]["load_status"] == "import_only"


def test_collect_model_material_diagnostics_reports_degraded_texture_source():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {
                    "name": "Wall",
                    "id": 1,
                    "texture_ref_evidence": [
                        {
                            "path": "wall_diff.png",
                            "filename": "wall_diff.png",
                            "texture_type": "diffuse",
                            "source_mode": "filesystem_import_only",
                        }
                    ],
                }
            ]
        }
    )

    assert diagnostics[0]["code"] == "degraded_texture_reference_source"
    assert diagnostics[0]["source_modes"] == ["filesystem_import_only"]
    assert diagnostics[0]["texture_ref_evidence"][0]["filename"] == "wall_diff.png"


def test_collect_model_material_diagnostics_reports_mtl_texture_source_warnings():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {
                    "name": "Bush",
                    "id": 1,
                    "index": 0,
                    "textures": {
                        "diffuse": "rock_face_01_diff.tif",
                        "specular": "rock_face_01_diff.tif",
                        "displacement": "rock_face_01_diff.tif",
                        "opacity": "rock_face_01_diff.tif",
                    },
                }
            ]
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert codes == [
        "mismatch_ce_texture_suffix",
        "mismatch_ce_texture_suffix",
        "shared_texture_path_across_ce_maps",
    ]
    reuse = diagnostics[2]
    assert reuse["severity"] == "warning"
    assert reuse["material"] == "Bush"
    assert reuse["fbx_slot"] == 0
    assert reuse["sub_index"] == 0
    assert reuse["ce_map_types"] == ["Diffuse", "Heightmap", "Opacity", "Specular"]
    assert reuse["expected_suffixes"] == ["_diff", "_displ", "_spec"]


def test_collect_model_material_diagnostics_allows_diffuse_opacity_texture_sharing():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [
                {
                    "name": "Leaves",
                    "id": 1,
                    "textures": {
                        "diffuse": "leaves_diff.tif",
                        "opacity": "leaves_diff.tif",
                    },
                }
            ]
        }
    )

    assert diagnostics == []


def test_collect_model_material_diagnostics_reports_rc_unassigned_placeholders():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "rc_material_smoke": {
                "unassigned_slot_diagnostics": [
                    {
                        "ok": True,
                        "type": "trailing_unassigned_placeholder",
                        "slot": 3,
                        "request_name": "<unassigned>",
                        "mtl_slot_name": "<unassigned>",
                        "used_by_cgf": False,
                        "max_used_material_id": 2,
                    },
                    {
                        "ok": False,
                        "type": "used_unassigned_material",
                        "slot": 1,
                        "request_name": "unassigned",
                        "mtl_slot_name": "unassigned",
                        "used_by_cgf": True,
                        "max_used_material_id": 1,
                    },
                ]
            },
        }
    )

    assert diagnostics[0]["severity"] == "info"
    assert diagnostics[0]["code"] == "trailing_unassigned_placeholder"
    assert diagnostics[0]["sub_index"] == 3
    assert diagnostics[1]["severity"] == "hazard"
    assert diagnostics[1]["code"] == "used_unassigned_material"
    assert diagnostics[1]["used_by_cgf"] is True


def test_collect_model_material_diagnostics_reports_rc_cgf_material_id_mismatch():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "rc_material_smoke": {
                "cgf_material_id_alignment_checks": [
                    {
                        "ok": True,
                        "material_id": 0,
                        "in_request": True,
                        "in_mtl": True,
                        "request_name": "Stone",
                        "mtl_slot_name": "Stone",
                        "used_unassigned": False,
                    },
                    {
                        "ok": False,
                        "material_id": 2,
                        "in_request": False,
                        "in_mtl": False,
                        "request_name": "",
                        "mtl_slot_name": "",
                        "used_unassigned": False,
                    },
                ]
            },
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "hazard"
    assert diagnostics[0]["code"] == "cgf_material_id_alignment_mismatch"
    assert diagnostics[0]["material_id"] == 2
    assert diagnostics[0]["sub_index"] == 2
    assert diagnostics[0]["in_request"] is False
    assert diagnostics[0]["in_mtl"] is False
    assert diagnostics[0]["message"] == (
        "CGF material id is missing from both the RC request and generated MTL slot table."
    )


def test_collect_model_material_diagnostics_reports_material_slot_evidence_mismatch():
    diagnostics = collect_model_material_diagnostics(
        {
            "materials": [{"name": "Stone", "id": 1}],
            "rc_material_smoke": {
                "material_slot_evidence_rows": [
                    {
                        "ok": True,
                        "status": "matched_used_slot",
                        "slot": 0,
                        "request_names": ["Stone"],
                        "mtl_name": "Stone",
                        "cgf_mtl_name": "Stone",
                    },
                    {
                        "ok": False,
                        "status": "cgf_mtl_name_mismatch",
                        "slot": 1,
                        "manifest_names": ["Glass"],
                        "request_names": ["Glass"],
                        "mtl_name": "Glass",
                        "cgf_mtl_name": "WrongGlass",
                        "used_by_cgf": True,
                    },
                ]
            },
        }
    )

    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "hazard"
    assert diagnostics[0]["code"] == "cgf_mtl_name_mismatch"
    assert diagnostics[0]["material"] == "Glass"
    assert diagnostics[0]["sub_index"] == 1
    assert diagnostics[0]["cgf_mtl_name"] == "WrongGlass"


def test_model_display_name_marks_hazards():
    assert model_display_name({"filename": "tree.fbx", "material_diagnostics": []}) == "tree.fbx"
    assert (
        model_display_name(
            {
                "filename": "tree.fbx",
                "material_diagnostics": [{"severity": "warning"}],
            }
        )
        == "tree.fbx [diagnostics]"
    )
    assert (
        model_display_name(
            {
                "filename": "tree.fbx",
                "material_diagnostics": [{"severity": "hazard"}],
            }
        )
        == "tree.fbx [hazard]"
    )


def test_model_display_name_includes_degraded_load_state():
    assert (
        model_display_name(
            {
                "filename": "tree.fbx",
                "load_status": "import_only",
                "material_diagnostics": [{"severity": "warning"}],
            }
        )
        == "tree.fbx [import_only] [diagnostics]"
    )
    assert model_display_name({"filename": "tree.fbx", "load_status": "dummy"}) == "tree.fbx [dummy]"


def test_model_load_state_text_explains_degraded_state():
    assert model_load_state_text({"load_status": "loaded"}) == "loaded"
    assert model_load_state_text({"load_status": "import_only"}) == "import_only (filesystem texture scan)"
    assert model_load_state_text({"load_status": "dummy"}) == "dummy (model load failed)"


def test_texture_source_summary_text_explains_fallback_modes():
    assert texture_source_mode_text("filesystem_import_only") == (
        "filesystem scan (import_only) [filesystem_import_only]"
    )
    assert (
        texture_source_summary_text(
            [
                {"source_mode": "blender"},
                {"source_mode": "filesystem_no_bpy"},
                {"source_mode": "filesystem_no_bpy"},
            ]
        )
        == "blender material data [blender] x1, filesystem scan (no bpy) [filesystem_no_bpy] x2"
    )


def test_load_model_material_manifest_reads_fbx_material_sidecar(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "Stone", "first_object": "Mesh", "first_local_slot": 0}],
                "polygons": [{"polygon": 0}],
            }
        ),
        encoding="utf-8",
    )

    info = load_model_material_manifest(str(fbx_path))

    assert info["path"] == str(manifest_path)
    assert info["summary"]["material_count"] == 1
    assert info["materials"] == [{"slot": 0, "name": "Stone", "source": "Mesh", "local_slot": 0}]
    assert material_manifest_summary_text(info) == "1 slots / 1 polygons (blender-fbx-material-inspection)"


def test_material_manifest_summary_text_handles_missing_manifest():
    assert material_manifest_summary_text({}) == "not found"


def test_default_rc_smoke_work_dir_uses_model_stem(tmp_path):
    fbx_path = tmp_path / "asset.fbx"

    assert default_rc_smoke_work_dir(str(fbx_path)) == str(tmp_path / "asset_rc_smoke_work")


def test_rc_material_smoke_summary_text_handles_states():
    assert rc_material_smoke_summary_text({}) == "not run"
    assert rc_material_smoke_summary_text({"success": True}) == "passed"
    assert (
        rc_material_smoke_summary_text(
            {
                "success": True,
                "semantic_alignment_ok": True,
                "cgf_material_id_alignment_ok": False,
                "unassigned_slot_diagnostics_ok": False,
            }
        )
        == "passed / semantic ok / CGF ids mismatch / used unassigned"
    )
    assert (
        rc_material_smoke_summary_text(
            {
                "success": True,
                "semantic_alignment_ok": True,
                "cgf_material_id_alignment_ok": True,
                "unassigned_slot_diagnostics_ok": True,
                "material_report_summary": {
                    "unassigned_placeholder_count": 2,
                    "used_unassigned_material_count": 0,
                },
            }
        )
        == "passed / semantic ok / CGF ids ok / unassigned placeholders x2"
    )
    assert (
        rc_material_smoke_summary_text(
            {
                "success": False,
                "semantic_alignment_ok": True,
                "cgf_material_id_alignment_ok": False,
                "unassigned_slot_diagnostics_ok": False,
                "material_report_summary": {
                    "unassigned_placeholder_count": 0,
                    "used_unassigned_material_count": 1,
                },
            }
        )
        == "failed / semantic ok / CGF ids mismatch / used unassigned x1"
    )
    assert rc_material_smoke_summary_text({"error": "missing rc"}) == "failed: missing rc"


def test_generate_model_material_manifest_runs_inspector_and_reloads_sidecar(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fbx", encoding="utf-8")

    def fake_inspector(blender_path, model_path):
        assert blender_path == ""
        assert model_path == str(fbx_path)
        manifest_path.write_text(
            json.dumps(
                {
                    "manifest_kind": "blender-fbx-material-inspection",
                    "materials": [
                        {"slot": 0, "name": "Stone", "first_object": "MeshA", "first_local_slot": 0},
                        {"slot": 1, "name": "Stone.001", "first_object": "MeshB", "first_local_slot": 0},
                    ],
                    "polygons": [{"polygon": 0}, {"polygon": 1}],
                }
            ),
            encoding="utf-8",
        )
        return {"success": True, "manifest": str(manifest_path)}

    info = generate_model_material_manifest(str(fbx_path), inspector_func=fake_inspector)

    assert info["path"] == str(manifest_path)
    assert info["summary"]["material_count"] == 2
    assert info["materials"][1]["name"] == "Stone.001"


def test_run_model_material_rc_smoke_uses_manifest_material_specs(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
    report_path = tmp_path / "asset_rc_smoke_work" / "asset.material_report.json"
    fbx_path.write_text("fbx", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone", "first_object": "MeshA", "first_local_slot": 0},
                    {"slot": 1, "name": "Stone.001", "first_object": "MeshB", "first_local_slot": 0},
                ],
                "polygons": [{"material": "Stone"}, {"material": "Stone.001"}],
            }
        ),
        encoding="utf-8",
    )

    def fake_smoke_runner(rc_exe_path, source_fbx_path, work_dir, asset_name=None, material_specs=None):
        assert rc_exe_path == "S:/Tools/rc.exe"
        assert source_fbx_path == str(fbx_path)
        assert work_dir == str(tmp_path / "asset_rc_smoke_work")
        assert asset_name == "asset"
        assert [material["name"] for material in material_specs] == ["Stone", "Stone.001"]
        assert [material["sub_index"] for material in material_specs] == [0, 1]
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "summary": {
                        "unassigned_placeholder_count": 1,
                        "used_unassigned_material_count": 0,
                    },
                    "material_slot_evidence": {
                        "summary": {
                            "ok": True,
                            "row_count": 2,
                            "status_counts": {
                                "matched_used_slot": 1,
                                "trailing_unassigned_placeholder": 1,
                            },
                        },
                        "rows": [
                            {
                                "ok": True,
                                "status": "matched_used_slot",
                                "slot": 0,
                                "request_names": ["Stone"],
                                "mtl_name": "Stone",
                                "cgf_mtl_name": "Stone",
                                "used_by_cgf": True,
                            },
                            {
                                "ok": True,
                                "status": "trailing_unassigned_placeholder",
                                "slot": 2,
                                "request_names": ["<unassigned>"],
                                "mtl_name": "<unassigned>",
                                "cgf_mtl_name": "",
                                "used_by_cgf": False,
                            },
                        ],
                    },
                    "fixture_material_semantic_alignment": {"ok": True},
                    "cgf_material_id_alignment": {
                        "ok": True,
                        "checks": [
                            {
                                "ok": True,
                                "material_id": 0,
                                "in_request": True,
                                "in_mtl": True,
                                "request_name": "Stone",
                                "mtl_slot_name": "Stone",
                                "used_unassigned": False,
                            }
                        ],
                        "unassigned_slot_diagnostics_ok": True,
                        "unassigned_slot_diagnostics": [
                            {
                                "ok": True,
                                "type": "trailing_unassigned_placeholder",
                                "slot": 2,
                                "request_name": "<unassigned>",
                                "mtl_slot_name": "<unassigned>",
                                "used_by_cgf": False,
                                "max_used_material_id": 1,
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        return RCSmokeResult(
            True,
            work_dir,
            rc_exe_path,
            source_fbx_path,
            material_report_path=str(report_path),
        )

    smoke_info = run_model_material_rc_smoke(str(fbx_path), "S:/Tools/rc.exe", smoke_runner=fake_smoke_runner)

    assert smoke_info["success"] is True
    assert smoke_info["material_report_path"] == str(report_path)
    assert smoke_info["semantic_alignment_ok"] is True
    assert smoke_info["cgf_material_id_alignment_ok"] is True
    assert smoke_info["cgf_material_id_alignment_checks"] == [
        {
            "ok": True,
            "material_id": 0,
            "in_request": True,
            "in_mtl": True,
            "request_name": "Stone",
            "mtl_slot_name": "Stone",
            "used_unassigned": False,
        }
    ]
    assert smoke_info["unassigned_slot_diagnostics_ok"] is True
    assert smoke_info["material_report_summary"] == {
        "unassigned_placeholder_count": 1,
        "used_unassigned_material_count": 0,
    }
    assert smoke_info["material_slot_evidence_summary"]["row_count"] == 2
    assert smoke_info["material_slot_evidence_rows"][0]["status"] == "matched_used_slot"
    assert smoke_info["unassigned_slot_diagnostics"] == [
        {
            "ok": True,
            "type": "trailing_unassigned_placeholder",
            "slot": 2,
            "request_name": "<unassigned>",
            "mtl_slot_name": "<unassigned>",
            "used_by_cgf": False,
            "max_used_material_id": 1,
        }
    ]
