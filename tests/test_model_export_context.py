import os

from model_processing.model_export_context import (
    attach_material_manifest,
    build_model_export_context,
    fbx_texture_export_diagnostics,
)


class TextureRef:
    def __init__(self, path, material_name):
        self.path = path
        self.material_name = material_name


class TextureManagerStub:
    def classify_texture(self, file_path):
        filename = os.path.splitext(os.path.basename(file_path))[0]
        return "diffuse", filename.removesuffix("_albedo")


def test_attach_material_manifest_copies_sidecar_info():
    model_data = {"materials": []}
    manifest_info = {"path": "asset.fbx_material_manifest.json", "manifest": {"materials": []}}

    result = attach_material_manifest(model_data, {"material_manifest": manifest_info})

    assert result is model_data
    assert model_data["material_manifest"] == manifest_info


def test_build_model_export_context_prepares_shared_paths_and_material_data(tmp_path):
    source = tmp_path / "chair_albedo.png"
    source.write_text("fake source")
    (tmp_path / "chair_diff.tif").write_text("fake diff")
    (tmp_path / "chair_ddna.tif").write_text("fake ddna")
    model_output_dir = tmp_path / "models"
    texture_output_dir = tmp_path
    model_data = {"materials": [{"name": "Chair"}]}

    context = build_model_export_context(
        model_data,
        "chair.fbx",
        str(model_output_dir),
        str(texture_output_dir),
        [TextureRef(str(source), "Chair")],
        TextureManagerStub(),
        "tif",
    )

    assert context.base_filename == "chair"
    assert context.mtl_filename == "chair.mtl"
    assert context.fbx_filename == "chair.fbx"
    assert context.fbx_output_path == os.path.join(str(model_output_dir), "chair.fbx")
    assert context.model_texture_dir == os.path.join(str(model_output_dir), "textures")
    assert context.existing_submaterial_names == []
    assert context.mtl_materials[0]["name"] == "Chair"
    assert set(context.mtl_materials[0]["textures"].keys()) == {"diffuse", "normal"}
    assert set(context.fbx_texture_data["Chair"].keys()) == {"diff", "ddna"}


def test_build_model_export_context_keeps_manifest_order_for_mtl_materials(tmp_path):
    model_data = {
        "materials": [{"name": "Stone.001"}, {"name": "Stone"}],
        "material_manifest": {
            "manifest": {
                "manifest_kind": "blender-fbx-material-inspection",
                "materials": [
                    {"slot": 0, "name": "Stone"},
                    {"slot": 1, "name": "Stone.001"},
                ],
            }
        },
    }

    context = build_model_export_context(
        model_data,
        "asset.fbx",
        str(tmp_path),
        str(tmp_path),
        [],
        TextureManagerStub(),
    )

    assert [material["name"] for material in context.mtl_materials] == ["Stone", "Stone.001"]
    assert [material["sub_index"] for material in context.mtl_materials] == [0, 1]
    assert context.fbx_texture_data == {}


def test_fbx_texture_export_diagnostics_warns_without_blocking_material_export(tmp_path):
    model_data = {"materials": [{"name": "SlotA"}, {"name": "SlotB"}]}
    context = build_model_export_context(
        model_data,
        "slots_only.fbx",
        str(tmp_path),
        str(tmp_path / "textures"),
        [],
        TextureManagerStub(),
    )

    diagnostics = fbx_texture_export_diagnostics(context)

    assert context.mtl_materials
    assert context.fbx_texture_data == {}
    assert diagnostics == [
        {
            "severity": "warning",
            "code": "fbx_export_no_processed_textures",
            "source_model": "slots_only.fbx",
            "material_count": 2,
            "message": (
                "No processed textures were resolved for FBX material nodes. "
                "FBX/JSON/RC export should still run so material slot mapping can be verified; "
                "FbxExporter will use diffuse fallback paths for material texture nodes."
            ),
        }
    ]
