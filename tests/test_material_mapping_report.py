import json
import xml.etree.ElementTree as ET

from tools.material_mapping_report import (
    build_existing_output_material_report,
    build_material_mapping_report,
    discover_fixture_manifest,
    evaluate_cgf_import_settings_roundtrip,
    evaluate_cgf_material_ids,
    evaluate_fixture_material_semantics,
    evaluate_material_slot_alignment,
    load_cryasset_details,
    load_fixture_manifest,
    load_mtl_slots,
    load_request_materials,
    summarize_material_mapping_report,
    write_material_mapping_report,
)


def test_load_request_materials_reads_rc_request(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps(
            {
                "request": {
                    "materials": [
                        {"name": "Bark", "physicalize": "no_collide", "sub_index": 0},
                        {"name": "proxy", "physicalize": "proxy_only", "sub_index": 2},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_request_materials(str(json_path)) == [
        {"order": 0, "name": "Bark", "sub_index": 0, "physicalize": "no_collide"},
        {"order": 1, "name": "proxy", "sub_index": 2, "physicalize": "proxy_only"},
    ]


def test_load_request_materials_surfaces_malformed_request_rows(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps(
            {
                "request": {
                    "materials": [
                        "bad-row",
                        {"name": "", "sub_index": 0},
                        {"name": "BadSub", "sub_index": True},
                        {"name": "StringSub", "sub_index": "2"},
                        {"name": "Deleted", "sub_index": "-1"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_request_materials(str(json_path)) == [
        {
            "order": 0,
            "name": "",
            "sub_index": None,
            "physicalize": "",
            "ok": False,
            "errors": ["invalid_request_material_row"],
            "row_type": "str",
        },
        {
            "order": 1,
            "name": "",
            "sub_index": 0,
            "physicalize": "",
            "raw_name": "",
            "name_type": "str",
            "ok": False,
            "errors": ["invalid_request_material_name"],
        },
        {
            "order": 2,
            "name": "BadSub",
            "sub_index": None,
            "physicalize": "",
            "raw_sub_index": True,
            "sub_index_type": "bool",
            "ok": False,
            "errors": ["invalid_request_sub_index"],
        },
        {"order": 3, "name": "StringSub", "sub_index": 2, "physicalize": ""},
        {"order": 4, "name": "Deleted", "sub_index": -1, "physicalize": ""},
    ]


def test_load_request_materials_surfaces_malformed_materials_collection(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(json.dumps({"request": {"materials": {"name": "Stone"}}}), encoding="utf-8")

    assert load_request_materials(str(json_path)) == [
        {
            "order": None,
            "name": "",
            "sub_index": None,
            "physicalize": "",
            "ok": False,
            "errors": ["invalid_request_materials_collection"],
            "collection_type": "dict",
        }
    ]


def test_load_mtl_slots_reads_submaterial_order(tmp_path):
    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark", Shader="Illum", SurfaceType="")
    ET.SubElement(sub_materials, "Material", Name="Leaves", Shader="Illum", SurfaceType="mat_leaves")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    assert load_mtl_slots(str(mtl_path)) == [
        {"slot": 0, "name": "Bark", "shader": "Illum", "surface_type": ""},
        {"slot": 1, "name": "Leaves", "shader": "Illum", "surface_type": "mat_leaves"},
    ]


def test_load_cryasset_details_reads_detail_values(tmp_path):
    cryasset_path = tmp_path / "asset.mtl.cryasset"
    root = ET.Element("AssetMetadata")
    details = ET.SubElement(root, "Details")
    ET.SubElement(details, "Detail", name="subMaterialCount").text = "2"
    ET.SubElement(details, "Detail", name="textureCount").text = "0"
    ET.ElementTree(root).write(cryasset_path, encoding="utf-8", xml_declaration=True)

    assert load_cryasset_details(str(cryasset_path)) == {
        "subMaterialCount": "2",
        "textureCount": "0",
    }


def test_evaluate_material_slot_alignment_reports_mismatch():
    result = evaluate_material_slot_alignment(
        [{"name": "Bark", "sub_index": 1}],
        [{"slot": 1, "name": "Leaves"}],
    )

    assert not result["ok"]
    assert result["checks"][0]["type"] == "slot_name_mismatch"


def test_evaluate_material_slot_alignment_reports_invalid_request_materials():
    result = evaluate_material_slot_alignment(
        [
            "bad-row",
            {"order": 1, "name": "", "sub_index": 0, "errors": ["invalid_request_material_name"], "name_type": "str"},
            {
                "order": 2,
                "name": "BadSub",
                "sub_index": None,
                "raw_sub_index": True,
                "errors": ["invalid_request_sub_index"],
                "sub_index_type": "bool",
            },
            {"order": 3, "name": 123, "sub_index": 0},
            {"order": 4, "name": "RawBadSub", "sub_index": 1.5},
            {"order": 5, "name": "Stone", "sub_index": 0},
        ],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not result["ok"]
    assert [check["type"] for check in result["checks"]] == [
        "invalid_request_material_row",
        "invalid_request_material_name",
        "invalid_request_sub_index",
        "invalid_request_material_name",
        "invalid_request_sub_index",
        "slot_name_match",
    ]
    assert result["checks"][2]["sub_index"] is True
    assert result["checks"][4]["sub_index"] == 1.5


def test_evaluate_material_slot_alignment_reports_invalid_mtl_slots():
    result = evaluate_material_slot_alignment(
        [{"name": "Stone", "sub_index": 0}],
        [
            "bad-row",
            {"name": "MissingSlot"},
            {"slot": True, "name": "BoolSlot"},
            {"slot": "0", "name": "Stone"},
        ],
    )

    assert not result["ok"]
    assert [check["type"] for check in result["checks"]] == [
        "invalid_mtl_slot_row",
        "invalid_mtl_slot_index",
        "invalid_mtl_slot_index",
        "slot_name_match",
    ]
    assert result["checks"][1]["slot"] is None
    assert result["checks"][2]["slot"] is True


def test_evaluate_material_slot_alignment_reports_invalid_mtl_slots_collection():
    result = evaluate_material_slot_alignment(
        [{"name": "Stone", "sub_index": 0}],
        {"slot": 0, "name": "Stone"},
    )

    assert not result["ok"]
    assert result["checks"][0]["type"] == "invalid_mtl_slots_collection"
    assert result["checks"][0]["collection_type"] == "dict"
    assert result["checks"][1]["type"] == "missing_mtl_slot"


def test_evaluate_cgf_material_ids_checks_request_and_mtl_presence():
    result = evaluate_cgf_material_ids(
        {"material_ids": [0, 2]},
        [{"name": "Bark", "sub_index": 0}, {"name": "Leaves", "sub_index": 1}],
        [{"slot": 0, "name": "Bark"}, {"slot": 2, "name": "Proxy"}],
    )

    assert not result["ok"]
    assert result["checks"] == [
        {
            "ok": True,
            "material_id": 0,
            "in_request": True,
            "in_mtl": True,
            "mtl_slot_name": "Bark",
            "used_unassigned": False,
        },
        {
            "ok": False,
            "material_id": 2,
            "in_request": False,
            "in_mtl": True,
            "mtl_slot_name": "Proxy",
            "used_unassigned": False,
        },
    ]


def test_evaluate_cgf_material_ids_ignores_invalid_mtl_slots():
    result = evaluate_cgf_material_ids(
        {"material_ids": [0]},
        [{"name": "Stone", "sub_index": 0}],
        ["bad-row", {"slot": True, "name": "BoolSlot"}, {"slot": "0", "name": "Stone"}],
    )

    assert result["ok"]
    assert result["checks"] == [
        {
            "ok": True,
            "material_id": 0,
            "in_request": True,
            "in_mtl": True,
            "mtl_slot_name": "Stone",
            "used_unassigned": False,
        },
    ]


def test_evaluate_cgf_material_ids_classifies_unassigned_placeholders():
    result = evaluate_cgf_material_ids(
        {"material_ids": [0, 2]},
        [
            {"name": "Bark", "sub_index": 0},
            {"name": "unassigned", "sub_index": 1},
            {"name": "Leaves", "sub_index": 2},
            {"name": "<unassigned>", "sub_index": 3},
        ],
        [
            {"slot": 0, "name": "Bark"},
            {"slot": 1, "name": "unassigned"},
            {"slot": 2, "name": "Leaves"},
            {"slot": 3, "name": "<unassigned>"},
        ],
    )

    assert result["ok"]
    assert result["unassigned_slot_diagnostics_ok"]
    assert result["unassigned_slot_diagnostics"] == [
        {
            "ok": True,
            "type": "gap_unassigned_placeholder",
            "slot": 1,
            "request_name": "unassigned",
            "mtl_slot_name": "unassigned",
            "source": ["request", "mtl"],
            "used_by_cgf": False,
            "max_used_material_id": 2,
        },
        {
            "ok": True,
            "type": "trailing_unassigned_placeholder",
            "slot": 3,
            "request_name": "<unassigned>",
            "mtl_slot_name": "<unassigned>",
            "source": ["request", "mtl"],
            "used_by_cgf": False,
            "max_used_material_id": 2,
        },
    ]


def test_evaluate_cgf_material_ids_rejects_used_unassigned_material():
    result = evaluate_cgf_material_ids(
        {"material_ids": [0, 1]},
        [{"name": "Stone", "sub_index": 0}, {"name": "unassigned", "sub_index": 1}],
        [{"slot": 0, "name": "Stone"}, {"slot": 1, "name": "unassigned"}],
    )

    assert not result["ok"]
    assert not result["unassigned_slot_diagnostics_ok"]
    assert result["checks"][1] == {
        "ok": False,
        "material_id": 1,
        "in_request": True,
        "in_mtl": True,
        "mtl_slot_name": "unassigned",
        "used_unassigned": True,
    }
    assert result["unassigned_slot_diagnostics"] == [
        {
            "ok": False,
            "type": "used_unassigned_material",
            "slot": 1,
            "request_name": "unassigned",
            "mtl_slot_name": "unassigned",
            "source": ["request", "mtl"],
            "used_by_cgf": True,
            "max_used_material_id": 1,
        }
    ]


def test_summarize_material_mapping_report_counts_unassigned_placeholders_and_hazards():
    placeholder_report = {
        "rc": {"returncode": 0, "output_exists": True},
        "request_materials": [{"name": "Stone", "sub_index": 0}, {"name": "<unassigned>", "sub_index": 1}],
        "mtl_slots": [{"slot": 0, "name": "Stone"}, {"slot": 1, "name": "<unassigned>"}],
        "alignment": {"ok": True},
        "cgf_import_settings_alignment": {"ok": True},
        "fixture_material_semantic_alignment": {"ok": True},
        "cgf_material_id_alignment": {
            "ok": True,
            "material_ids": [0],
            "checks": [{"ok": True, "material_id": 0}],
            "unassigned_slot_diagnostics_ok": True,
            "unassigned_slot_diagnostics": [
                {"ok": True, "type": "trailing_unassigned_placeholder", "slot": 1}
            ],
        },
    }
    used_report = {
        **placeholder_report,
        "cgf_material_id_alignment": {
            "ok": False,
            "material_ids": [0, 1],
            "checks": [{"ok": True, "material_id": 0}, {"ok": False, "material_id": 1}],
            "unassigned_slot_diagnostics_ok": False,
            "unassigned_slot_diagnostics": [
                {"ok": False, "type": "used_unassigned_material", "slot": 1}
            ],
        },
    }

    placeholder_summary = summarize_material_mapping_report(placeholder_report)
    used_summary = summarize_material_mapping_report(used_report)

    assert placeholder_summary["unassigned_slot_counts"] == {"trailing_unassigned_placeholder": 1}
    assert placeholder_summary["unassigned_placeholder_count"] == 1
    assert placeholder_summary["used_unassigned_material_count"] == 0
    assert placeholder_summary["failed_material_id_check_count"] == 0
    assert placeholder_summary["action_required"] is False
    assert used_summary["unassigned_slot_counts"] == {"used_unassigned_material": 1}
    assert used_summary["used_unassigned_material_count"] == 1
    assert used_summary["failed_material_id_check_count"] == 1
    assert used_summary["action_required"] is True


def test_evaluate_cgf_import_settings_roundtrip_matches_request_mtl_and_cgf_mtl_name():
    request_materials = [
        {"order": 0, "name": "Bark", "sub_index": 0, "physicalize": "no"},
        {"order": 1, "name": "Leaves", "sub_index": 1, "physicalize": "no"},
        {"order": 2, "name": "<unassigned>", "sub_index": 2, "physicalize": "no"},
    ]
    cgf_summary = {
        "import_settings": [
            {
                "chunk_id": 23,
                "version": 0,
                "json_error": "",
                "json": {
                    "materials": [
                        {"name": "Bark", "physicalize": "no", "sub_index": 0},
                        {"name": "Leaves", "physicalize": "no", "sub_index": 1},
                        {"name": "<unassigned>", "physicalize": "no", "sub_index": 2},
                    ]
                },
            }
        ],
        "materials": [
            {
                "chunk_id": 2,
                "name": "asset",
                "sub_materials": [
                    {"slot": 0, "name": "Bark", "physicalize_type": -1},
                    {"slot": 1, "name": "Leaves", "physicalize_type": -1},
                ],
            }
        ],
        "material_ids": [0, 1],
    }

    result = evaluate_cgf_import_settings_roundtrip(
        cgf_summary,
        request_materials,
        [
            {"slot": 0, "name": "Bark"},
            {"slot": 1, "name": "Leaves"},
            {"slot": 2, "name": "<unassigned>"},
        ],
    )

    assert result["ok"]
    assert result["import_settings_present"]
    assert result["import_settings_meta"] == {"chunk_id": 23, "version": 0, "material_count": 3}
    assert result["request_vs_import_settings"]["ok"]
    assert result["import_settings_vs_mtl"]["ok"]
    assert result["import_settings_vs_cgf_mtl_name"]["ok"]
    assert result["import_settings_vs_cgf_mtl_name"]["extra_import_settings_slots_ok"]
    assert result["import_settings_vs_cgf_mtl_name"]["extra_import_settings_slots"] == [
        {
            "ok": True,
            "type": "trailing_unassigned_slot_omitted_from_cgf",
            "sub_index": 2,
            "name": "<unassigned>",
            "physicalize": "no",
            "trailing": True,
            "unassigned": True,
            "cgf_mtl_name_sub_material_count": 2,
        }
    ]


def test_evaluate_cgf_import_settings_roundtrip_rejects_real_extra_cgf_mtl_name_slot():
    result = evaluate_cgf_import_settings_roundtrip(
        {
            "import_settings": [
                {
                    "chunk_id": 23,
                    "version": 0,
                    "json_error": "",
                    "json": {
                        "materials": [
                            {"name": "Bark", "physicalize": "no", "sub_index": 0},
                            {"name": "Leaves", "physicalize": "no", "sub_index": 1},
                            {"name": "Proxy", "physicalize": "proxy_only", "sub_index": 2},
                        ]
                    },
                }
            ],
            "materials": [{"sub_materials": [{"slot": 0, "name": "Bark"}, {"slot": 1, "name": "Leaves"}]}],
            "material_ids": [0, 1],
        },
        [
            {"order": 0, "name": "Bark", "sub_index": 0, "physicalize": "no"},
            {"order": 1, "name": "Leaves", "sub_index": 1, "physicalize": "no"},
            {"order": 2, "name": "Proxy", "sub_index": 2, "physicalize": "proxy_only"},
        ],
        [{"slot": 0, "name": "Bark"}, {"slot": 1, "name": "Leaves"}, {"slot": 2, "name": "Proxy"}],
    )

    assert not result["ok"]
    assert not result["import_settings_vs_cgf_mtl_name"]["ok"]
    assert not result["import_settings_vs_cgf_mtl_name"]["extra_import_settings_slots_ok"]
    assert result["import_settings_vs_cgf_mtl_name"]["extra_import_settings_slots"] == [
        {
            "ok": False,
            "type": "missing_cgf_mtl_name_slot",
            "sub_index": 2,
            "name": "Proxy",
            "physicalize": "proxy_only",
            "trailing": True,
            "unassigned": False,
            "cgf_mtl_name_sub_material_count": 2,
        }
    ]


def test_evaluate_cgf_import_settings_roundtrip_accepts_request_wrapped_import_settings():
    result = evaluate_cgf_import_settings_roundtrip(
        {
            "import_settings": [
                {
                    "chunk_id": 23,
                    "version": 0,
                    "json_error": "",
                    "json": {
                        "request": {
                            "materials": [
                                {"name": "Stone", "physicalize": "no", "sub_index": 0},
                            ]
                        }
                    },
                }
            ],
            "materials": [{"sub_materials": [{"slot": 0, "name": "Stone"}]}],
            "material_ids": [0],
        },
        [{"order": 0, "name": "Stone", "sub_index": 0, "physicalize": "no"}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert result["ok"]
    assert result["import_settings_meta"] == {"chunk_id": 23, "version": 0, "material_count": 1}


def test_evaluate_cgf_import_settings_roundtrip_reports_material_mismatches():
    result = evaluate_cgf_import_settings_roundtrip(
        {
            "import_settings": [
                {
                    "chunk_id": 23,
                    "version": 0,
                    "json_error": "",
                    "json": {"materials": [{"name": "Wrong", "physicalize": "proxy_only", "sub_index": 1}]},
                }
            ],
            "materials": [
                {
                    "chunk_id": 2,
                    "name": "asset",
                    "sub_materials": [{"slot": 1, "name": "WrongInCgf"}],
                }
            ],
            "material_ids": [1, 2],
        },
        [{"order": 0, "name": "Bark", "sub_index": 0, "physicalize": "no"}],
        [{"slot": 0, "name": "Bark"}, {"slot": 1, "name": "Wrong"}],
    )

    assert not result["ok"]
    assert result["request_vs_import_settings"]["checks"][0]["type"] == "request_import_settings_mismatch"
    assert result["import_settings_vs_mtl"]["ok"]
    assert result["import_settings_vs_cgf_mtl_name"]["checks"][0] == {
        "ok": False,
        "type": "cgf_mtl_name_mismatch",
        "sub_index": 1,
        "import_settings_name": "Wrong",
        "cgf_mtl_name": "WrongInCgf",
    }
    assert result["import_settings_material_id_alignment"]["checks"][-1] == {
        "ok": False,
        "material_id": 2,
        "in_request": False,
        "in_mtl": False,
        "mtl_slot_name": "",
        "used_unassigned": False,
    }


def test_evaluate_cgf_import_settings_roundtrip_reports_missing_or_invalid_import_settings():
    missing_result = evaluate_cgf_import_settings_roundtrip(
        {},
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not missing_result["ok"]
    assert not missing_result["import_settings_present"]
    assert missing_result["import_settings_error"] == "missing_cgf_import_settings"

    invalid_result = evaluate_cgf_import_settings_roundtrip(
        {"import_settings": [{"json_error": "bad-json", "json": None}]},
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not invalid_result["ok"]
    assert invalid_result["import_settings_error"] == "invalid_cgf_import_settings_json"


def test_evaluate_cgf_import_settings_roundtrip_reports_invalid_request_rows():
    result = evaluate_cgf_import_settings_roundtrip(
        {
            "import_settings": [
                {
                    "chunk_id": 23,
                    "version": 0,
                    "json_error": "",
                    "json": {"materials": [{"name": "Stone", "physicalize": "no", "sub_index": 0}]},
                }
            ],
            "materials": [{"sub_materials": [{"slot": 0, "name": "Stone"}]}],
            "material_ids": [0],
        },
        [{"name": "", "sub_index": 0, "errors": ["invalid_request_material_name"], "name_type": "str"}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not result["ok"]
    assert result["invalid_request_entries"] == [
        {
            "ok": False,
            "order": 0,
            "error": "invalid_request_material_name",
            "name": "",
            "sub_index": 0,
            "row_type": None,
            "collection_type": None,
            "name_type": "str",
            "sub_index_type": None,
            "path": None,
            "read_error": None,
        }
    ]


def test_discover_fixture_manifest_checks_source_before_copied(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    copied_fbx = tmp_path / "copied.fbx"
    source_manifest = tmp_path / "source.fixture_manifest.json"
    copied_manifest = tmp_path / "copied.fixture_manifest.json"
    source_fbx.write_text("fbx", encoding="utf-8")
    copied_fbx.write_text("fbx", encoding="utf-8")
    source_manifest.write_text(json.dumps({"fixture_kind": "source"}), encoding="utf-8")
    copied_manifest.write_text(json.dumps({"fixture_kind": "copied"}), encoding="utf-8")

    manifest_path = discover_fixture_manifest(str(source_fbx), str(copied_fbx))

    assert manifest_path == str(source_manifest)
    assert load_fixture_manifest(manifest_path)["fixture_kind"] == "source"


def test_discover_fixture_manifest_falls_back_to_fbx_material_manifest(tmp_path):
    source_fbx = tmp_path / "source.fbx"
    source_manifest = tmp_path / "source.fbx_material_manifest.json"
    source_fbx.write_text("fbx", encoding="utf-8")
    source_manifest.write_text(json.dumps({"manifest_kind": "blender-fbx-material-inspection"}), encoding="utf-8")

    manifest_path = discover_fixture_manifest(str(source_fbx))

    assert manifest_path == str(source_manifest)
    assert load_fixture_manifest(manifest_path)["manifest_kind"] == "blender-fbx-material-inspection"


def test_evaluate_fixture_material_semantics_flags_swapped_request_names():
    manifest = {
        "fixture_kind": "multi-mesh-name-conflict",
        "materials": [
            {"slot": 0, "name": "LocalSlot0_Wood"},
            {"slot": 1, "name": "LocalSlot0_Metal"},
        ],
        "polygons": [
            {
                "polygon": 0,
                "material_slot": 0,
                "material_name": "LocalSlot0_Wood",
                "expected_cgf_material_id": 0,
                "center_x": 0.0,
            },
            {
                "polygon": 1,
                "material_slot": 0,
                "material_name": "LocalSlot0_Metal",
                "expected_cgf_material_id": 1,
                "center_x": 3.0,
            },
        ],
    }
    cgf_summary = {
        "meshes": [
            {
                "chunk_id": 10,
                "subsets": [
                    {"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 0},
                    {"subset": 0, "center": [3.0, 0.0, 0.0], "material_id": 1},
                ],
            }
        ]
    }
    result = evaluate_fixture_material_semantics(
        manifest,
        cgf_summary,
        [
            {"name": "LocalSlot0_Metal", "sub_index": 0},
            {"name": "LocalSlot0_Wood", "sub_index": 1},
        ],
        [
            {"slot": 0, "name": "LocalSlot0_Metal"},
            {"slot": 1, "name": "LocalSlot0_Wood"},
        ],
    )

    assert not result["ok"]
    assert result["manifest_kind"] == "multi-mesh-name-conflict"
    assert result["material_checks"][0]["expected_name"] == "LocalSlot0_Wood"
    assert result["material_checks"][0]["request_names"] == ["LocalSlot0_Metal"]
    assert result["polygon_checks"][0]["cgf_id_ok"]
    assert not result["polygon_checks"][0]["ok"]


def test_evaluate_fixture_material_semantics_accepts_preserved_suffix_names():
    manifest = {
        "fixture_kind": "multi-mesh-name-conflict",
        "materials": [
            {"slot": 0, "name": "DuplicateSurface"},
            {"slot": 1, "name": "DuplicateSurface.001"},
        ],
        "polygons": [
            {
                "polygon": 0,
                "material_slot": 0,
                "material_name": "DuplicateSurface",
                "expected_cgf_material_id": 0,
                "center_x": 0.0,
            },
            {
                "polygon": 1,
                "material_slot": 0,
                "material_name": "DuplicateSurface.001",
                "expected_cgf_material_id": 1,
                "center_x": 3.0,
            },
        ],
    }
    cgf_summary = {
        "meshes": [
            {
                "chunk_id": 10,
                "subsets": [
                    {"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 0},
                    {"subset": 0, "center": [3.0, 0.0, 0.0], "material_id": 1},
                ],
            }
        ]
    }
    result = evaluate_fixture_material_semantics(
        manifest,
        cgf_summary,
        [
            {"name": "DuplicateSurface", "sub_index": 0},
            {"name": "DuplicateSurface.001", "sub_index": 1},
        ],
        [
            {"slot": 0, "name": "DuplicateSurface"},
            {"slot": 1, "name": "DuplicateSurface.001"},
        ],
    )

    assert result["ok"]
    assert result["manifest_kind"] == "multi-mesh-name-conflict"
    assert result["duplicate_request_material_names"] == []
    assert result["polygon_checks"][1]["request_names_for_actual_id"] == ["DuplicateSurface.001"]


def test_evaluate_fixture_material_semantics_skips_generic_polygon_center_checks():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "polygon_verification": "material_table_only",
            "materials": [{"slot": 0, "name": "Stone"}],
            "polygons": [
                {
                    "polygon": 0,
                    "material_name": "Stone",
                    "expected_cgf_material_id": 0,
                    "center_x": 999.0,
                }
            ],
        },
        {
            "meshes": [
                {
                    "chunk_id": 10,
                    "subsets": [{"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 0}],
                }
            ]
        },
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert result["ok"]
    assert result["polygon_verification"] == "material_table_only"
    assert result["polygon_checks_skipped"]
    assert result["polygon_count"] == 1
    assert result["polygon_checks"] == []
    assert result["subset_entries"] == []


def test_evaluate_fixture_material_semantics_reports_invalid_manifest_slots():
    manifest = {
        "manifest_kind": "blender-fbx-material-inspection",
        "materials": [
            {"slot": "bad-slot", "name": "Broken"},
            {"slot": -1, "name": "DeletedLooking"},
            {"slot": True, "name": "BooleanSlot"},
            {"slot": 1.5, "name": "FloatSlot"},
            {"slot": 1, "name": "Visible"},
        ],
        "polygons": [
            {
                "polygon": 0,
                "material_slot": "bad-polygon-slot",
                "material_name": "Broken",
                "expected_cgf_material_id": "bad-polygon-slot",
            },
            {
                "polygon": 1,
                "material_slot": -1,
                "material_name": "DeletedLooking",
                "expected_cgf_material_id": -1,
            },
            {
                "polygon": 2,
                "material_slot": True,
                "material_name": "BooleanSlot",
                "expected_cgf_material_id": True,
            },
            {
                "polygon": 3,
                "material_slot": 1.5,
                "material_name": "FloatSlot",
                "expected_cgf_material_id": 1.5,
            },
            {
                "polygon": 4,
                "material_slot": 1,
                "material_name": "Visible",
                "expected_cgf_material_id": 1,
            },
        ],
    }

    result = evaluate_fixture_material_semantics(
        manifest,
        {"material_ids": []},
        [{"name": "Visible", "sub_index": 1}],
        [{"slot": 1, "name": "Visible"}],
    )

    assert not result["ok"]
    assert result["material_checks"][0]["error"] == "invalid_manifest_material_slot"
    assert result["material_checks"][0]["slot"] == "bad-slot"
    assert result["material_checks"][1]["error"] == "invalid_manifest_material_slot"
    assert result["material_checks"][1]["slot"] == -1
    assert result["material_checks"][2]["error"] == "invalid_manifest_material_slot"
    assert result["material_checks"][2]["slot"] is True
    assert result["material_checks"][3]["error"] == "invalid_manifest_material_slot"
    assert result["material_checks"][3]["slot"] == 1.5
    assert result["polygon_checks"][0]["error"] == "invalid_manifest_polygon_slot"
    assert result["polygon_checks"][0]["expected_cgf_material_id"] == "bad-polygon-slot"
    assert result["polygon_checks"][1]["error"] == "invalid_manifest_polygon_slot"
    assert result["polygon_checks"][1]["expected_cgf_material_id"] == -1
    assert result["polygon_checks"][2]["error"] == "invalid_manifest_polygon_slot"
    assert result["polygon_checks"][2]["expected_cgf_material_id"] is True
    assert result["polygon_checks"][3]["error"] == "invalid_manifest_polygon_slot"
    assert result["polygon_checks"][3]["expected_cgf_material_id"] == 1.5


def test_evaluate_fixture_material_semantics_reports_invalid_manifest_shape():
    root_result = evaluate_fixture_material_semantics(
        ["not", "an", "object"],
        {"material_ids": []},
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not root_result["ok"]
    assert root_result["material_checks"][0]["error"] == "invalid_manifest_root"
    assert root_result["material_checks"][0]["root_type"] == "list"

    collection_result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": {"slot": 0, "name": "Stone"},
            "polygons": "not-a-list",
        },
        {"material_ids": []},
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not collection_result["ok"]
    assert collection_result["material_checks"][0]["error"] == "invalid_manifest_materials_collection"
    assert collection_result["material_checks"][0]["collection_type"] == "dict"
    assert collection_result["polygon_checks"][0]["error"] == "invalid_manifest_polygons_collection"
    assert collection_result["polygon_checks"][0]["collection_type"] == "str"

    row_result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": ["bad-row", {"slot": 0, "name": "Stone"}],
            "polygons": [False, {"polygon": 0, "material_name": "Stone", "material_table_slot": 0}],
        },
        {"material_ids": []},
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not row_result["ok"]
    assert row_result["material_checks"][0]["error"] == "invalid_manifest_material_row"
    assert row_result["material_checks"][0]["manifest_order"] == 0
    assert row_result["polygon_checks"][0]["error"] == "invalid_manifest_polygon_row"
    assert row_result["polygon_checks"][0]["polygon_order"] == 0


def test_evaluate_fixture_material_semantics_reports_invalid_manifest_names():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [
                {"slot": 0, "name": ""},
                {"slot": 1, "name": 123},
                {"slot": 2, "name": "Stone"},
            ],
            "polygons": [
                {"polygon": 0, "material_name": "", "expected_cgf_material_id": 0},
                {"polygon": 1, "material_name": 123, "expected_cgf_material_id": 1},
                {"polygon": 2, "material_name": "Stone", "expected_cgf_material_id": 2},
            ],
        },
        {"material_ids": []},
        [{"name": "Stone", "sub_index": 2}],
        [{"slot": 2, "name": "Stone"}],
    )

    assert not result["ok"]
    assert result["material_checks"][0]["error"] == "invalid_manifest_material_name"
    assert result["material_checks"][0]["name_type"] == "str"
    assert result["material_checks"][1]["error"] == "invalid_manifest_material_name"
    assert result["material_checks"][1]["name_type"] == "int"
    assert result["polygon_checks"][0]["error"] == "invalid_manifest_polygon_material_name"
    assert result["polygon_checks"][0]["name_type"] == "str"
    assert result["polygon_checks"][1]["error"] == "invalid_manifest_polygon_material_name"
    assert result["polygon_checks"][1]["name_type"] == "int"


def test_evaluate_fixture_material_semantics_reports_invalid_polygon_indices():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [{"slot": 0, "name": "Stone"}],
            "polygons": [
                {"material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 0.0},
                {"polygon": -1, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 3.0},
                {"polygon": True, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 6.0},
                {"polygon": 1.5, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 9.0},
                {"polygon": "4", "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": "bad-center"},
            ],
        },
        {
            "meshes": [
                {
                    "chunk_id": 10,
                    "subsets": [{"subset": 0, "center": [12.0, 0.0, 0.0], "material_id": 0}],
                }
            ]
        },
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not result["ok"]
    invalid_checks = [check for check in result["polygon_checks"] if check.get("error") == "invalid_manifest_polygon_index"]
    assert [check["polygon"] for check in invalid_checks] == [None, -1, True, 1.5]
    assert [check["polygon_order"] for check in invalid_checks] == [0, 1, 2, 3]
    assert result["polygon_checks"][-1]["polygon"] == 4
    assert result["polygon_checks"][-1]["ok"]


def test_evaluate_fixture_material_semantics_reports_invalid_cgf_subset_evidence():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [{"slot": 0, "name": "Stone"}],
            "polygons": [
                {"polygon": 0, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 0.0},
            ],
        },
        {
            "meshes": [
                "bad-mesh-row",
                {"chunk_id": 10, "subsets": "bad-subsets"},
                {
                    "chunk_id": 11,
                    "subsets": [
                        "bad-subset-row",
                        {"subset": 1, "center": [], "material_id": 0},
                        {"subset": 2, "center": ["bad-center"], "material_id": 0},
                        {"subset": 3, "center": [3.0, 0.0, 0.0], "material_id": True},
                        {"subset": 4, "center": [0.0, 0.0, 0.0], "material_id": "0"},
                    ],
                },
            ]
        },
        [{"name": "Stone", "sub_index": 0}],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not result["ok"]
    assert result["polygon_checks"][-1]["ok"]
    assert result["subset_entries"] == [
        {
            "mesh_chunk_id": 11,
            "subset": 4,
            "polygon": 0,
            "center": [0.0, 0.0, 0.0],
            "material_id": 0,
        }
    ]
    assert [entry["error"] for entry in result["invalid_subset_entries"]] == [
        "invalid_cgf_mesh_row",
        "invalid_cgf_mesh_subsets_collection",
        "invalid_cgf_subset_row",
        "invalid_cgf_subset_center",
        "invalid_cgf_subset_center",
        "invalid_cgf_subset_material_id",
    ]


def test_evaluate_fixture_material_semantics_reports_invalid_request_material_evidence():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [{"slot": 0, "name": "Stone"}],
            "polygons": [{"polygon": 0, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 0.0}],
        },
        {
            "meshes": [
                {
                    "chunk_id": 10,
                    "subsets": [{"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 0}],
                }
            ]
        },
        [
            "bad-row",
            {"order": 1, "name": "", "sub_index": 0, "errors": ["invalid_request_material_name"], "name_type": "str"},
            {
                "order": 2,
                "name": "BadSub",
                "sub_index": None,
                "raw_sub_index": True,
                "errors": ["invalid_request_sub_index"],
                "sub_index_type": "bool",
            },
            {"order": 3, "name": 123, "sub_index": 0},
            {"order": 4, "name": "RawBadSub", "sub_index": 1.5},
            {"order": 5, "name": "Stone", "sub_index": 0},
        ],
        [{"slot": 0, "name": "Stone"}],
    )

    assert not result["ok"]
    assert result["polygon_checks"][-1]["ok"]
    assert result["duplicate_request_material_names"] == []
    assert result["duplicate_request_sub_indices"] == []
    assert [entry["error"] for entry in result["invalid_request_entries"]] == [
        "invalid_request_material_row",
        "invalid_request_material_name",
        "invalid_request_sub_index",
        "invalid_request_material_name",
        "invalid_request_sub_index",
    ]
    assert result["invalid_request_entries"][2]["sub_index"] is True
    assert result["invalid_request_entries"][4]["sub_index"] == 1.5


def test_evaluate_fixture_material_semantics_reports_invalid_mtl_slot_evidence():
    result = evaluate_fixture_material_semantics(
        {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [{"slot": 0, "name": "Stone"}],
            "polygons": [{"polygon": 0, "material_name": "Stone", "expected_cgf_material_id": 0, "center_x": 0.0}],
        },
        {
            "meshes": [
                {
                    "chunk_id": 10,
                    "subsets": [{"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 0}],
                }
            ]
        },
        [{"name": "Stone", "sub_index": 0}],
        [
            "bad-row",
            {"name": "MissingSlot"},
            {"slot": True, "name": "BoolSlot"},
            {"slot": "0", "name": "Stone"},
        ],
    )

    assert not result["ok"]
    assert result["material_checks"][0]["ok"]
    assert result["polygon_checks"][-1]["ok"]
    assert [entry["error"] for entry in result["invalid_mtl_entries"]] == [
        "invalid_mtl_slot_row",
        "invalid_mtl_slot_index",
        "invalid_mtl_slot_index",
    ]
    assert result["invalid_mtl_entries"][2]["slot"] is True


def test_evaluate_fixture_material_semantics_reports_out_of_range_manifest_slots():
    manifest = {
        "manifest_kind": "blender-fbx-material-inspection",
        "materials": [
            {"slot": 127, "name": "LastValid"},
            {"slot": 128, "name": "TooHigh"},
        ],
        "polygons": [
            {
                "polygon": 0,
                "material_slot": 127,
                "material_name": "LastValid",
                "expected_cgf_material_id": 127,
            },
            {
                "polygon": 1,
                "material_slot": 128,
                "material_name": "TooHigh",
                "expected_cgf_material_id": 128,
            },
        ],
    }

    result = evaluate_fixture_material_semantics(
        manifest,
        {"material_ids": []},
        [{"name": "LastValid", "sub_index": 127}, {"name": "TooHigh", "sub_index": -1}],
        [{"slot": 127, "name": "LastValid"}],
    )

    assert not result["ok"]
    assert result["material_checks"][1]["error"] == "manifest_material_slot_out_of_rc_range"
    assert result["material_checks"][1]["slot"] == 128
    assert result["material_checks"][1]["max_sub_materials"] == 128
    assert result["polygon_checks"][1]["error"] == "manifest_polygon_slot_out_of_rc_range"
    assert result["polygon_checks"][1]["expected_cgf_material_id"] == 128


def test_build_and_write_material_mapping_report(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps({"request": {"materials": [{"name": "Bark", "sub_index": 0, "physicalize": "no_collide"}]}}),
        encoding="utf-8",
    )

    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Bark", Shader="Illum", SurfaceType="")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    cryasset_path = tmp_path / "asset.mtl.cryasset"
    cryasset_root = ET.Element("AssetMetadata")
    details = ET.SubElement(cryasset_root, "Details")
    ET.SubElement(details, "Detail", name="subMaterialCount").text = "1"
    ET.ElementTree(cryasset_root).write(cryasset_path, encoding="utf-8", xml_declaration=True)

    cgf_path = tmp_path / "asset.cgf"
    cgf_path.write_bytes(b"cgf")

    report = build_material_mapping_report(
        str(json_path),
        str(mtl_path),
        expected_output_path=str(cgf_path),
        rc_exe_path="rc.exe",
        source_fbx_path="source.fbx",
        copied_fbx_path="asset.fbx",
        rc_returncode=0,
    )

    assert report["alignment"]["ok"]
    assert report["summary"]["slot_alignment_ok"] is True
    assert report["summary"]["request_material_count"] == 1
    assert report["summary"]["mtl_slot_count"] == 1
    assert report["summary"]["unassigned_placeholder_count"] == 0
    assert report["request_read_error"] == ""
    assert report["rc"]["output_exists"]
    assert report["rc"]["output_size"] == 3
    assert report["mtl_cryasset_details"]["subMaterialCount"] == "1"
    assert report["mtl_read_error"] == ""
    assert report["mtl_cryasset_read_error"] == ""
    assert report["cgf_material_id_alignment"]["material_ids"] == []
    assert report["cgf_import_settings_alignment"]["import_settings_error"] == "missing_cgf_import_settings"

    report_path = tmp_path / "asset.material_report.json"
    write_material_mapping_report(report, str(report_path))
    assert json.loads(report_path.read_text(encoding="utf-8"))["alignment"]["ok"]


def test_build_existing_output_material_report_uses_cgf_import_settings_when_json_missing(monkeypatch, tmp_path):
    cgf_path = tmp_path / "asset.cgf"
    cgf_path.write_bytes(b"cgf")
    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="Stone", Shader="Illum")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    monkeypatch.setattr(
        "tools.material_mapping_report.read_cgf_material_summary",
        lambda path: {
            "path": path,
            "import_settings": [
                {
                    "chunk_id": 9,
                    "version": 0,
                    "json_error": "",
                    "json": {"request": {"materials": [{"name": "Stone", "physicalize": "no", "sub_index": 0}]}},
                }
            ],
            "materials": [{"sub_materials": [{"slot": 0, "name": "Stone"}]}],
            "material_ids": [0],
        },
    )

    report = build_existing_output_material_report(str(cgf_path), str(mtl_path))

    assert report["request_source"]["type"] == "cgf_import_settings"
    assert report["request_source"]["import_settings_meta"] == {"chunk_id": 9, "version": 0, "material_count": 1}
    assert report["alignment"]["ok"]
    assert report["cgf_import_settings_alignment"]["ok"]
    assert report["cgf_material_id_alignment"]["ok"]


def test_build_material_mapping_report_surfaces_malformed_mtl_and_cryasset_xml(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text(
        json.dumps({"request": {"materials": [{"name": "Bark", "sub_index": 0, "physicalize": "no_collide"}]}}),
        encoding="utf-8",
    )

    mtl_path = tmp_path / "asset.mtl"
    mtl_path.write_text("<Material><SubMaterials>", encoding="utf-8")
    cryasset_path = tmp_path / "asset.mtl.cryasset"
    cryasset_path.write_text("<AssetMetadata><Details>", encoding="utf-8")

    report = build_material_mapping_report(
        str(json_path),
        str(mtl_path),
        expected_output_path="",
        rc_exe_path="rc.exe",
        source_fbx_path="source.fbx",
        copied_fbx_path="asset.fbx",
        rc_returncode=0,
    )

    assert report["mtl_slots"] == []
    assert report["mtl_read_error"]
    assert report["mtl_cryasset_details"] == {}
    assert report["mtl_cryasset_read_error"]
    assert not report["alignment"]["ok"]
    assert report["alignment"]["checks"][0]["type"] == "missing_mtl_slot"


def test_build_material_mapping_report_surfaces_malformed_request_json(tmp_path):
    json_path = tmp_path / "asset.json"
    json_path.write_text('{"request": {"materials": [', encoding="utf-8")

    mtl_path = tmp_path / "asset.mtl"
    root = ET.Element("Material")
    ET.SubElement(root, "SubMaterials")
    ET.ElementTree(root).write(mtl_path, encoding="utf-8", xml_declaration=True)

    report = build_material_mapping_report(
        str(json_path),
        str(mtl_path),
        expected_output_path="",
        rc_exe_path="rc.exe",
        source_fbx_path="source.fbx",
        copied_fbx_path="asset.fbx",
        rc_returncode=0,
    )

    assert report["request_read_error"]
    assert report["request_materials"][0]["errors"] == ["invalid_request_json"]
    assert report["request_materials"][0]["path"] == str(json_path)
    assert not report["alignment"]["ok"]
    assert report["alignment"]["checks"][0]["type"] == "invalid_request_json"
    assert report["alignment"]["checks"][0]["read_error"]
