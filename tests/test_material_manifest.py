import json

from model_processing.material_manifest import (
    discover_material_manifest,
    load_material_manifest,
    material_manifest_materials,
    material_manifest_table_diagnostics,
    material_manifest_kind,
    material_manifest_summary,
    material_manifest_table_rows,
)


def test_discover_material_manifest_prefers_fixture_manifest(tmp_path):
    fbx_path = tmp_path / "asset.fbx"
    fixture_manifest = tmp_path / "asset.fixture_manifest.json"
    inspector_manifest = tmp_path / "asset.fbx_material_manifest.json"
    fbx_path.write_text("fbx", encoding="utf-8")
    fixture_manifest.write_text(json.dumps({"fixture_kind": "fixture"}), encoding="utf-8")
    inspector_manifest.write_text(json.dumps({"manifest_kind": "inspector"}), encoding="utf-8")

    assert discover_material_manifest(str(fbx_path)) == str(fixture_manifest)


def test_material_manifest_helpers_summarize_table_rows(tmp_path):
    manifest_path = tmp_path / "asset.fbx_material_manifest.json"
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

    manifest = load_material_manifest(str(manifest_path))

    assert material_manifest_kind(manifest) == "blender-fbx-material-inspection"
    assert material_manifest_summary(manifest, str(manifest_path)) == {
        "path": str(manifest_path),
        "kind": "blender-fbx-material-inspection",
        "material_count": 2,
        "polygon_count": 2,
    }
    assert material_manifest_table_rows(manifest) == [
        {"slot": 0, "name": "Stone", "source": "MeshA", "local_slot": 0},
        {"slot": 1, "name": "Stone.001", "source": "MeshB", "local_slot": 0},
    ]


def test_material_manifest_materials_reorders_and_pins_sub_indices():
    manifest_info = {
        "manifest": {
            "manifest_kind": "blender-fbx-material-inspection",
            "materials": [
                {"slot": 0, "name": "Stone"},
                {"slot": 1, "name": "Stone.001"},
            ],
            "polygons": [
                {"polygon": 0, "object": "MeshA", "expected_cgf_material_id": 0},
                {"polygon": 1, "object": "MeshB", "expected_cgf_material_id": 1},
            ],
        }
    }

    materials = material_manifest_materials(
        [
            {"name": "Stone.001", "textures": {"diffuse": "stone2_diff.tif"}},
            {"name": "Stone", "textures": {"diffuse": "stone_diff.tif"}},
        ],
        manifest_info,
    )

    assert [material["name"] for material in materials] == ["Stone", "Stone.001"]
    assert [material["id"] for material in materials] == [1, 2]
    assert [material["sub_index"] for material in materials] == [0, 1]
    assert [material["auto_assigned"] for material in materials] == [False, False]
    assert materials[0]["textures"] == {"diffuse": "stone_diff.tif"}
    assert materials[1]["mesh_names"] == ["MeshB"]


def test_material_manifest_table_diagnostics_reports_duplicate_slots_and_names():
    diagnostics = material_manifest_table_diagnostics(
        {
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 0, "name": "Metal"},
                    {"slot": 2, "name": "Stone"},
                ],
            }
        }
    )

    assert [diagnostic["code"] for diagnostic in diagnostics] == [
        "material_manifest_duplicate_slot",
        "material_manifest_duplicate_name",
    ]
    assert diagnostics[0]["slot"] == 0
    assert diagnostics[0]["material_names"] == ["Stone", "Metal"]
    assert diagnostics[1]["material"] == "Stone"
    assert diagnostics[1]["slots"] == [0, 2]


def test_material_manifest_table_diagnostics_reports_polygon_slot_name_mismatch():
    diagnostics = material_manifest_table_diagnostics(
        {
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
        }
    )

    codes = [diagnostic["code"] for diagnostic in diagnostics]
    assert "material_manifest_polygon_slot_name_mismatch" in codes
    assert "material_manifest_polygon_name_multiple_slots" in codes
    mismatch = next(diagnostic for diagnostic in diagnostics if diagnostic["code"] == "material_manifest_polygon_slot_name_mismatch")
    assert mismatch["slot"] == 1
    assert mismatch["polygon_material_name"] == "Stone"
    assert mismatch["table_material_name"] == "Metal"
