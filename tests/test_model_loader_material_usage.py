from model_processing.material_slot_usage import build_material_slot_usage
from model_processing.model_loader import ModelLoader


def test_extract_materials_uses_mesh_slot_order_not_global_materials():
    loader = ModelLoader.__new__(ModelLoader)
    loader.bpy = True
    meshes = [
        {
            "name": "ProbeMesh",
            "material_slots": [
                {"slot": 0, "name": "Slot_0_Red", "nodes": True},
                {"slot": 1, "name": "Slot_1_Green", "nodes": False},
                {"slot": 2, "name": "Slot_2_Blue", "nodes": False},
            ],
            "polygons": [
                {"material_slot": 0},
                {"material_slot": 2},
            ],
        }
    ]

    materials = loader._extract_materials(
        meshes,
        build_material_slot_usage(meshes, material_count=3),
    )

    assert [material["name"] for material in materials] == [
        "Slot_0_Red",
        "Slot_1_Green",
        "Slot_2_Blue",
    ]
    assert [material["index"] for material in materials] == [0, 1, 2]
    assert [material["polygon_count"] for material in materials] == [1, 0, 1]
    assert [material["used_by_polygons"] for material in materials] == [True, False, True]


def test_extract_materials_keeps_first_name_for_shared_slot_across_meshes():
    loader = ModelLoader.__new__(ModelLoader)
    loader.bpy = True
    meshes = [
        {
            "name": "MeshA",
            "material_slots": [{"slot": 0, "name": "Slot_A", "nodes": False}],
            "polygons": [{"material_slot": 0}],
        },
        {
            "name": "MeshB",
            "material_slots": [{"slot": 0, "name": "Slot_B", "nodes": False}],
            "polygons": [{"material_slot": 0}],
        },
    ]

    materials = loader._extract_materials(
        meshes,
        build_material_slot_usage(meshes, material_count=1),
    )

    assert materials[0]["name"] == "Slot_A"
    assert materials[0]["polygon_count"] == 2
    assert materials[0]["mesh_names"] == ["MeshA", "MeshB"]
