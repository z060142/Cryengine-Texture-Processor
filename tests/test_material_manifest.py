import json

from model_processing.material_manifest import (
    discover_material_manifest,
    load_material_manifest,
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
