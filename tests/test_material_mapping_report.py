import json
import xml.etree.ElementTree as ET

from tools.material_mapping_report import (
    build_material_mapping_report,
    discover_fixture_manifest,
    evaluate_cgf_material_ids,
    evaluate_fixture_material_semantics,
    evaluate_material_slot_alignment,
    load_cryasset_details,
    load_fixture_manifest,
    load_mtl_slots,
    load_request_materials,
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


def test_evaluate_cgf_material_ids_checks_request_and_mtl_presence():
    result = evaluate_cgf_material_ids(
        {"material_ids": [0, 2]},
        [{"name": "Bark", "sub_index": 0}, {"name": "Leaves", "sub_index": 1}],
        [{"slot": 0, "name": "Bark"}, {"slot": 2, "name": "Proxy"}],
    )

    assert not result["ok"]
    assert result["checks"] == [
        {"ok": True, "material_id": 0, "in_request": True, "in_mtl": True, "mtl_slot_name": "Bark"},
        {"ok": False, "material_id": 2, "in_request": False, "in_mtl": True, "mtl_slot_name": "Proxy"},
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
    assert report["rc"]["output_exists"]
    assert report["rc"]["output_size"] == 3
    assert report["mtl_cryasset_details"]["subMaterialCount"] == "1"
    assert report["cgf_material_id_alignment"]["material_ids"] == []

    report_path = tmp_path / "asset.material_report.json"
    write_material_mapping_report(report, str(report_path))
    assert json.loads(report_path.read_text(encoding="utf-8"))["alignment"]["ok"]
