from tools import rc_smoke_rust


def _manifest():
    return {
        "expect_cgf_material_ids": [0, 1],
        "materials": [
            {"slot": 0, "name": "Body", "physicalize": "no"},
            {"slot": 1, "name": "Glass", "physicalize": "no"},
        ],
    }


def _request():
    return {
        "materials": [
            {"sub_index": 0, "name": "Body", "physicalize": "no"},
            {"sub_index": 1, "name": "Glass", "physicalize": "no"},
            {"sub_index": 2, "name": "<unassigned>", "physicalize": "no"},
        ]
    }


def _cgf_summary(include_placeholder=False):
    sub_materials = [
        {"slot": 0, "name": "Body", "physicalize_type": -1},
        {"slot": 1, "name": "Glass", "physicalize_type": -1},
    ]
    if include_placeholder:
        sub_materials.append(
            {"slot": 2, "name": "<unassigned>", "physicalize_type": -1}
        )
    return {
        "material_ids": [0, 1],
        "materials": [
            {
                "name": "car",
                "sub_material_count": len(sub_materials),
                "sub_materials": sub_materials,
            }
        ],
    }


def test_material_alignment_accepts_omitted_trailing_placeholder():
    alignment = rc_smoke_rust.build_material_alignment(
        _manifest(),
        _request(),
        ["Body", "Glass", "<unassigned>"],
        _cgf_summary(),
    )

    assert alignment["ok"] is True
    assert alignment["matched_count"] == 2
    assert alignment["placeholder"] == {
        "name": "<unassigned>",
        "request_present": True,
        "request_slot": 2,
        "mtl_present": True,
        "mtl_slots": [2],
        "expected_in_cgf": False,
        "cgf_present": False,
        "cgf_slots": [],
        "classification": "trailing_unassigned_not_expected_in_cgf",
        "ok": True,
    }


def test_material_alignment_rejects_unexpected_cgf_placeholder():
    alignment = rc_smoke_rust.build_material_alignment(
        _manifest(),
        _request(),
        ["Body", "Glass", "<unassigned>"],
        _cgf_summary(include_placeholder=True),
    )

    assert alignment["ok"] is False
    assert alignment["placeholder"]["cgf_present"] is True
    assert alignment["placeholder"]["ok"] is False


def test_rc_command_uses_frozen_import_overrides():
    command = rc_smoke_rust.build_rc_command(
        "S:/Tools/rc/rc.exe",
        "C:/work/car.json",
        "C:/work/car.fbx",
        "C:/work/car.cgf",
    )

    assert command == [
        "S:/Tools/rc/rc.exe",
        "C:/work/car.json",
        "/overwriteextension=fbx",
        "/overwritesourcefile=C:/work/car.fbx",
        "/overwritefilename=car.cgf",
    ]
