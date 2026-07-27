from model_processing.material_slot_usage import build_material_slot_usage


def test_build_material_slot_usage_counts_polygons_by_slot():
    usage = build_material_slot_usage(
        [
            {
                "name": "MeshA",
                "polygons": [
                    {"material_slot": 0},
                    {"material_slot": 2},
                    {"material_slot": 2},
                ],
            },
            {
                "name": "MeshB",
                "polygons": [
                    {"material_slot": 2},
                ],
            },
        ],
        material_count=4,
    )

    assert usage[0] == {
        "polygon_count": 1,
        "mesh_names": ["MeshA"],
        "material_names": [],
        "slot_name_conflict": False,
        "used_by_polygons": True,
    }
    assert usage[1] == {
        "polygon_count": 0,
        "mesh_names": [],
        "material_names": [],
        "slot_name_conflict": False,
        "used_by_polygons": False,
    }
    assert usage[2] == {
        "polygon_count": 3,
        "mesh_names": ["MeshA", "MeshB"],
        "material_names": [],
        "slot_name_conflict": False,
        "used_by_polygons": True,
    }
    assert usage[3] == {
        "polygon_count": 0,
        "mesh_names": [],
        "material_names": [],
        "slot_name_conflict": False,
        "used_by_polygons": False,
    }


def test_build_material_slot_usage_keeps_slots_beyond_declared_material_count():
    usage = build_material_slot_usage(
        [{"name": "MeshA", "polygons": [{"material_slot": 5}]}],
        material_count=1,
    )

    assert usage[0]["polygon_count"] == 0
    assert usage[5] == {
        "polygon_count": 1,
        "mesh_names": ["MeshA"],
        "material_names": [],
        "slot_name_conflict": False,
        "used_by_polygons": True,
    }


def test_build_material_slot_usage_detects_name_conflict_for_same_slot():
    usage = build_material_slot_usage(
        [
            {
                "name": "MeshA",
                "material_slots": [{"slot": 0, "name": "Wood"}],
                "polygons": [{"material_slot": 0, "material_name": "Wood"}],
            },
            {
                "name": "MeshB",
                "material_slots": [{"slot": 0, "name": "Metal"}],
                "polygons": [{"material_slot": 0, "material_name": "Metal"}],
            },
        ],
        material_count=1,
    )

    assert usage[0]["polygon_count"] == 2
    assert usage[0]["material_names"] == ["Metal", "Wood"]
    assert usage[0]["slot_name_conflict"] is True
