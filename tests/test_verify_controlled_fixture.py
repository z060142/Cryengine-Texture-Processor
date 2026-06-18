import json

from tools.verify_controlled_fixture import verify_fixture_material_ids, verify_fixture_polygon_material_ids


def test_verify_fixture_material_ids_passes_when_expected_matches_actual(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [1, 0]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "", "cgf_material_summary": {"material_ids": [0, 1]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert result["ok"]
    assert result["expected"] == [0, 1]
    assert result["actual"] == [0, 1]


def test_verify_fixture_material_ids_fails_when_ids_differ(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [0, 2]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "", "cgf_material_summary": {"material_ids": [0, 1]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert not result["ok"]
    assert result["expected"] == [0, 2]
    assert result["actual"] == [0, 1]


def test_verify_fixture_material_ids_fails_on_cgf_read_error(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(json.dumps({"expect_cgf_material_ids": [0]}), encoding="utf-8")
    report_path.write_text(
        json.dumps({"cgf_read_error": "bad cgf", "cgf_material_summary": {"material_ids": [0]}}),
        encoding="utf-8",
    )

    result = verify_fixture_material_ids(str(manifest_path), str(report_path))

    assert not result["ok"]
    assert result["cgf_read_error"] == "bad cgf"


def test_verify_fixture_polygon_material_ids_matches_raw_fbx_slots(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(
        json.dumps(
            {
                "polygons": [
                    {"polygon": 0, "material_slot": 0, "material_name": "Slot_0_Red"},
                    {"polygon": 1, "material_slot": 1, "material_name": "Slot_1_Green"},
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "cgf_read_error": "",
                "request_materials": [
                    {"name": "Slot_1_Green", "sub_index": 0},
                    {"name": "Slot_0_Red", "sub_index": 1},
                ],
                "cgf_material_summary": {
                    "meshes": [
                        {
                            "chunk_id": 10,
                            "subsets": [
                                {"subset": 0, "center": [3.0, 0.0, 0.0], "material_id": 1, "num_indices": 3},
                                {"subset": 1, "center": [0.0, 0.0, 0.0], "material_id": 0, "num_indices": 3},
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = verify_fixture_polygon_material_ids(str(manifest_path), str(report_path))

    assert result["ok"]
    assert result["expected_cgf_material_id_by_polygon"] == {0: 0, 1: 1}
    assert result["raw_fbx_slot_by_polygon"] == {0: 0, 1: 1}
    assert result["actual_cgf_material_id_by_polygon"] == {0: 0, 1: 1}
    assert result["request_sub_index_by_polygon_name"] == {0: 1, 1: 0}
    assert result["name_remap_mismatches"] == [
        {
            "polygon": 0,
            "material_name": "Slot_0_Red",
            "actual_material_id": 0,
            "request_sub_index_for_name": 1,
        },
        {
            "polygon": 1,
            "material_name": "Slot_1_Green",
            "actual_material_id": 1,
            "request_sub_index_for_name": 0,
        },
    ]


def test_verify_fixture_polygon_material_ids_fails_when_polygon_id_differs(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(
        json.dumps(
            {
                "polygons": [
                    {"polygon": 0, "material_slot": 0, "material_name": "Slot_0_Red"},
                    {"polygon": 1, "material_slot": 1, "material_name": "Slot_1_Green"},
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "cgf_read_error": "",
                "cgf_material_summary": {
                    "meshes": [
                        {
                            "chunk_id": 10,
                            "subsets": [
                                {"subset": 0, "center": [0.0, 0.0, 0.0], "material_id": 1, "num_indices": 3},
                                {"subset": 1, "center": [3.0, 0.0, 0.0], "material_id": 0, "num_indices": 3},
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = verify_fixture_polygon_material_ids(str(manifest_path), str(report_path))

    assert not result["ok"]
    assert result["expected_cgf_material_id_by_polygon"] == {0: 0, 1: 1}
    assert result["raw_fbx_slot_by_polygon"] == {0: 0, 1: 1}
    assert result["actual_cgf_material_id_by_polygon"] == {0: 1, 1: 0}


def test_verify_fixture_polygon_material_ids_accepts_explicit_expected_cgf_ids(tmp_path):
    manifest_path = tmp_path / "asset.fixture_manifest.json"
    report_path = tmp_path / "asset.material_report.json"
    manifest_path.write_text(
        json.dumps(
            {
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
                ]
            }
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            {
                "cgf_read_error": "",
                "request_materials": [
                    {"name": "LocalSlot0_Wood", "sub_index": 0},
                    {"name": "LocalSlot0_Metal", "sub_index": 1},
                ],
                "cgf_material_summary": {
                    "meshes": [
                        {
                            "chunk_id": 10,
                            "subsets": [
                                {"subset": 0, "center": [0.00001, 0.0, 0.0], "material_id": 0, "num_indices": 3},
                                {"subset": 0, "center": [3.0, 0.0, 0.0], "material_id": 1, "num_indices": 3},
                            ],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    result = verify_fixture_polygon_material_ids(str(manifest_path), str(report_path))

    assert result["ok"]
    assert result["expected_cgf_material_id_by_polygon"] == {0: 0, 1: 1}
    assert result["raw_fbx_slot_by_polygon"] == {0: 0, 1: 0}
    assert result["actual_cgf_material_id_by_polygon"] == {0: 0, 1: 1}
