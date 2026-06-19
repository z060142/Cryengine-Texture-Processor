import json
import xml.etree.ElementTree as ET

import pytest

from output_formats.rc_import_schema import (
    RC_IMPORT_OUTPUT_EXTENSIONS,
    RC_IMPORT_PHYSICALIZE_VALUES,
    collect_request_schema_diagnostics,
    collect_unknown_request_fields,
    normalize_rc_sub_index,
)
from output_formats.json_exporter import export_json
from output_formats.rc_request_builder import build_import_request, build_material_requests, wrap_import_request


def sample_model():
    return {
        "path": "chair_source.obj",
        "materials": [
            {"name": "Chair"},
            {"name": "Chair.001"},
            {"name": "collision_proxy"},
            {"name": "Material"},
        ],
        "scene_hierarchy": [
            {
                "name": "Root",
                "children": [
                    {"name": "ChairMesh", "children": []},
                    {"name": "Chair_proxy", "children": []},
                ],
            }
        ],
    }


def test_build_import_request_matches_rc_root_payload_shape():
    request = build_import_request(sample_model(), "chair.fbx")

    assert request["source_filename"] == "chair.fbx"
    assert request["output_ext"] == "cgf"
    assert request["material_filename"] == "chair"
    assert request["unit_size"] == "cm"
    assert request["forward_up_axes"] == "-Y+Z"
    assert "use_32_bit_positions" not in request
    assert "cgf" in RC_IMPORT_OUTPUT_EXTENSIONS


def test_build_import_request_uses_source_backed_schema_fields_only():
    request = build_import_request(sample_model(), "chair.fbx")

    assert collect_unknown_request_fields(request) == {}
    assert collect_request_schema_diagnostics(request) == []
    assert "proxy_only" in RC_IMPORT_PHYSICALIZE_VALUES
    assert request["nodes"][0] == {
        "name": "Root",
        "path": ["Root"],
        "nodes": [
            {"name": "ChairMesh", "path": ["Root", "ChairMesh"]},
            {"name": "Chair_proxy", "path": ["Root", "Chair_proxy"]},
        ],
    }


def test_request_schema_diagnostics_report_internal_field_contamination():
    request = build_import_request(sample_model(), "chair.fbx")
    request["diagnostics"] = []
    request["materials"][0]["diagnostics"] = []
    request["nodes"][0]["_is_proxy"] = False
    request["jointPhysicsData"][0]["debug"] = True
    request["jointPhysicsData"][0]["jointLimits"] = {"min_x": 0, "debug_min": -1}

    diagnostics = collect_request_schema_diagnostics(request)

    assert [diagnostic["code"] for diagnostic in diagnostics] == [
        "rc_request_unknown_root_field",
        "rc_request_unknown_node_field",
        "rc_request_unknown_material_field",
        "rc_request_unknown_joint_physics_field",
        "rc_request_unknown_joint_limit_field",
    ]
    assert [diagnostic["location"] for diagnostic in diagnostics] == [
        "diagnostics",
        "nodes[0]._is_proxy",
        "materials[0].diagnostics",
        "jointPhysicsData[0].debug",
        "jointPhysicsData[0].jointLimits.debug_min",
    ]


def test_request_schema_diagnostics_report_invalid_rc_values():
    request = build_import_request(sample_model(), "chair.fbx")
    request["output_ext"] = "abc"
    request["materials"][0]["name"] = ""
    request["materials"][0]["physicalize"] = "render_only"
    request["materials"][0]["sub_index"] = True
    request["materials"][1]["sub_index"] = 128

    diagnostics = collect_request_schema_diagnostics(request)

    assert [diagnostic["code"] for diagnostic in diagnostics] == [
        "rc_request_invalid_output_ext",
        "rc_request_invalid_material_name",
        "rc_request_invalid_material_physicalize",
        "rc_request_invalid_material_sub_index",
        "rc_request_invalid_material_sub_index",
    ]
    assert [diagnostic["location"] for diagnostic in diagnostics] == [
        "output_ext",
        "materials[0].name",
        "materials[0].physicalize",
        "materials[0].sub_index",
        "materials[1].sub_index",
    ]
    assert diagnostics[0]["allowed_values"] == sorted(RC_IMPORT_OUTPUT_EXTENSIONS)
    assert diagnostics[2]["allowed_values"] == sorted(RC_IMPORT_PHYSICALIZE_VALUES)
    assert diagnostics[4]["max_value"] == 127


def test_request_schema_diagnostics_report_invalid_collections_and_rows():
    request = build_import_request(sample_model(), "chair.fbx")
    request["materials"] = ["bad-material-row"]
    request["nodes"] = "bad-node-collection"
    request["jointPhysicsData"] = [False]

    diagnostics = collect_request_schema_diagnostics(request)

    assert [diagnostic["code"] for diagnostic in diagnostics] == [
        "rc_request_invalid_collection",
        "rc_request_invalid_material_row",
        "rc_request_invalid_joint_physics_row",
    ]
    assert [diagnostic["location"] for diagnostic in diagnostics] == [
        "nodes",
        "materials[0]",
        "jointPhysicsData[0]",
    ]


def test_material_requests_use_rc_fields_only_and_preserve_blender_suffixes():
    request = build_import_request(sample_model(), "chair.fbx")

    assert request["materials"] == [
        {"name": "Chair", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Chair.001", "physicalize": "no_collide", "sub_index": 1},
        {"name": "collision_proxy", "physicalize": "proxy_only", "sub_index": 2},
    ]
    assert all("file" not in material for material in request["materials"])
    assert all("ui_name" not in material for material in request["materials"])
    assert all("diagnostics" not in material for material in request["materials"])


def test_material_requests_follow_material_manifest_table_order():
    model = sample_model()
    model["materials"] = [
        {"name": "Stone.001"},
        {"name": "Stone"},
    ]
    model["material_manifest"] = {
        "manifest": {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [
                {"slot": 0, "name": "Stone"},
                {"slot": 1, "name": "Stone.001"},
            ],
        }
    }

    request = build_import_request(model, "stone.fbx")

    assert request["materials"] == [
        {"name": "Stone", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Stone.001", "physicalize": "no_collide", "sub_index": 1},
    ]


def test_material_requests_preserve_explicit_physicalize_metadata():
    request = build_import_request(
        {
            "path": "wall.fbx",
            "materials": [
                {"name": "Visible", "physicalize": "no"},
                {"name": "Solid", "physicalize": "default"},
            ],
        },
        "wall.fbx",
    )

    assert request["materials"] == [
        {"name": "Visible", "physicalize": "no", "sub_index": 0},
        {"name": "Solid", "physicalize": "default", "sub_index": 1},
    ]


def test_material_requests_normalize_unknown_physicalize_like_rc():
    materials = build_material_requests(
        [{"name": "Odd", "physicalize": "render_only"}],
        include_diagnostics=True,
    )

    assert materials[0]["physicalize"] == "no"
    assert materials[0]["diagnostics"][0]["code"] == "rc_unknown_physicalize_defaults_to_no"
    assert materials[0]["diagnostics"][0]["requested_physicalize"] == "render_only"


def test_manifest_physicalize_metadata_overrides_name_heuristic():
    model = {
        "path": "proxy.fbx",
        "materials": [],
        "material_manifest": {
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [{"slot": 0, "name": "collision_proxy", "physicalize": "no"}],
            }
        },
    }

    request = build_import_request(model, "proxy.fbx")

    assert request["materials"] == [{"name": "collision_proxy", "physicalize": "no", "sub_index": 0}]


def test_material_requests_can_include_slot_diagnostics():
    materials = build_material_requests(
        [{"name": "Visible", "id": 1}, {"name": "Removed", "id": 2, "deleted": True}],
        include_diagnostics=True,
    )

    assert "diagnostics" not in materials[0]
    assert materials[1]["diagnostics"][0]["code"] == "deleted_known_fbx_slot_usage_unknown"


def test_material_requests_can_include_case_insensitive_collision_diagnostics():
    materials = build_material_requests(
        [{"name": "Wood", "id": 1}, {"name": "wood", "id": 2}],
        include_diagnostics=True,
    )

    assert materials[0]["diagnostics"][0]["code"] == "rc_case_insensitive_material_name_collision"
    assert materials[1]["diagnostics"][0]["code"] == "rc_case_insensitive_material_name_collision"


def test_material_requests_can_include_duplicate_sub_index_diagnostics():
    materials = build_material_requests(
        [
            {"name": "Wood", "id": 1, "sub_index": 0, "auto_assigned": False},
            {"name": "Metal", "id": 2, "sub_index": 0, "auto_assigned": False},
        ],
        include_diagnostics=True,
    )

    assert materials[0]["diagnostics"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"
    assert materials[1]["diagnostics"][0]["code"] == "rc_duplicate_sub_index_overwrites_material"


def test_nodes_and_joint_physics_use_path_arrays():
    request = build_import_request(sample_model(), "chair.fbx")
    root = request["nodes"][0]

    assert root["path"] == ["Root"]
    assert root["nodes"][1]["path"] == ["Root", "Chair_proxy"]
    assert "bIsProxy" not in root["nodes"][1]
    assert "helper" not in root["nodes"][1]
    assert "lod" not in root["nodes"][1]
    assert request["jointPhysicsData"] == [
        {
            "jointNodePath": ["Root"],
            "proxyNodePath": ["Root", "Chair_proxy"],
            "snapToJoint": True,
        }
    ]


def test_normalize_rc_sub_index_matches_import_request_bounds():
    assert normalize_rc_sub_index(0) == 0
    assert normalize_rc_sub_index(127) == 127
    assert normalize_rc_sub_index(128) == -1
    assert normalize_rc_sub_index(-1) == -1


def test_material_request_normalizes_out_of_range_sub_index_like_rc():
    materials = build_material_requests(
        [{"name": "TooHigh", "sub_index": 128, "auto_assigned": False}],
        include_diagnostics=True,
    )

    assert materials[0]["sub_index"] == -1
    assert materials[0]["diagnostics"][0]["code"] == "rc_sub_index_out_of_range_deleted"


def test_wrap_import_request_defaults_to_rc_request_name():
    request = build_import_request(sample_model(), "chair.fbx")

    assert set(wrap_import_request(request).keys()) == {"request"}
    assert set(wrap_import_request(request, "metadata").keys()) == {"metadata"}


def test_wrap_import_request_rejects_unknown_rc_fields():
    request = build_import_request(sample_model(), "chair.fbx")
    request["materials"][0]["diagnostics"] = [{"code": "internal"}]

    with pytest.raises(ValueError, match=r"materials\[0\]\.diagnostics"):
        wrap_import_request(request)


def test_wrap_import_request_rejects_invalid_rc_values():
    request = build_import_request(sample_model(), "chair.fbx", output_ext="abc")

    with pytest.raises(ValueError, match="output_ext"):
        wrap_import_request(request)


def test_export_json_writes_request_wrapper_by_default(tmp_path):
    success, output_file = export_json(sample_model(), "chair.fbx", str(tmp_path))

    assert success
    payload = json.loads((tmp_path / "chair.json").read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"request"}
    assert payload["request"]["source_filename"] == "chair.fbx"
    assert output_file.endswith("chair.json")


def test_export_json_rejects_invalid_rc_request_values(tmp_path):
    success, message = export_json(sample_model(), "chair.fbx", str(tmp_path), output_ext="abc")

    assert not success
    assert "source-unsupported fields: output_ext" in message
    assert not (tmp_path / "chair.json").exists()


def test_export_json_preserves_fbx_slot_order_over_existing_mtl_name_order(tmp_path):
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    ET.SubElement(sub_materials, "Material", Name="collision_proxy")
    ET.SubElement(sub_materials, "Material", Name="Chair")
    ET.ElementTree(root).write(tmp_path / "chair.mtl", encoding="utf-8")

    success, _ = export_json(sample_model(), "chair.fbx", str(tmp_path))

    assert success
    payload = json.loads((tmp_path / "chair.json").read_text(encoding="utf-8"))
    assert payload["request"]["materials"] == [
        {"name": "Chair", "physicalize": "no_collide", "sub_index": 0},
        {"name": "Chair.001", "physicalize": "no_collide", "sub_index": 1},
        {"name": "collision_proxy", "physicalize": "proxy_only", "sub_index": 2},
    ]
