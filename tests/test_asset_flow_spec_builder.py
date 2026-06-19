import json

from tools import asset_flow_spec_builder


def test_build_spec_selects_smallest_fbx_cases(tmp_path):
    root = tmp_path / "assets"
    nested = root / "nested"
    nested.mkdir(parents=True)
    large = root / "Large.fbx"
    small = nested / "Small.fbx"
    ignored = root / "Ignored.obj"
    large.write_bytes(b"1" * 20)
    small.write_bytes(b"1" * 5)
    ignored.write_bytes(b"1")

    spec = asset_flow_spec_builder.build_spec(
        [str(root)],
        str(tmp_path / "work"),
        limit=1,
        max_bytes=10,
    )

    assert spec["work_root"] == str(tmp_path / "work")
    assert spec["metadata"]["case_count"] == 1
    assert spec["cases"] == [
        {
            "name": f"Small_{asset_flow_spec_builder._hash_path(str(small))}",
            "type": "rc",
            "fbx": str(small.resolve()),
            "source_size_bytes": 5,
        }
    ]


def test_main_writes_validator_spec(tmp_path, capsys):
    fbx = tmp_path / "Mesh.fbx"
    fbx.write_bytes(b"fbx")
    output = tmp_path / "spec.json"

    asset_flow_spec_builder.main(
        [
            str(fbx),
            "--output",
            str(output),
            "--work-root",
            str(tmp_path / "work"),
            "--limit",
            "5",
            "--max-mb",
            "0",
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["cases"][0]["type"] == "rc"
    assert payload["cases"][0]["fbx"] == str(fbx.resolve())
    assert "case_count: 1" in capsys.readouterr().out


def test_build_spec_attaches_sibling_obj_mtl_evidence(tmp_path):
    model_root = tmp_path / "Models"
    fbx_dir = model_root / "FBX"
    obj_dir = model_root / "OBJ"
    fbx_dir.mkdir(parents=True)
    obj_dir.mkdir()
    fbx = fbx_dir / "Weed_b.fbx"
    obj_mtl = obj_dir / "Weed_b.mtl"
    fbx.write_bytes(b"fbx")
    obj_mtl.write_text("newmtl Weed_B_mat\nmap_Kd ../Textures/Weed_B_a.tga\n", encoding="utf-8")

    spec = asset_flow_spec_builder.build_spec(
        [str(fbx_dir)],
        str(tmp_path / "work"),
        obj_mtl_roots=[str(obj_dir)],
    )

    assert spec["cases"][0]["obj_mtl_evidence"] == str(obj_mtl.resolve())


def test_build_spec_can_disable_obj_mtl_evidence(tmp_path):
    fbx = tmp_path / "Mesh.fbx"
    mtl = tmp_path / "Mesh.mtl"
    fbx.write_bytes(b"fbx")
    mtl.write_text("newmtl Mesh\n", encoding="utf-8")

    spec = asset_flow_spec_builder.build_spec(
        [str(tmp_path)],
        str(tmp_path / "work"),
        include_obj_mtl_evidence=False,
    )

    assert "obj_mtl_evidence" not in spec["cases"][0]


def test_build_spec_attaches_texture_output_dir(tmp_path):
    fbx = tmp_path / "Mesh.fbx"
    fbx.write_bytes(b"fbx")

    spec = asset_flow_spec_builder.build_spec(
        [str(fbx)],
        str(tmp_path / "work"),
        texture_output_dir=str(tmp_path / "textures"),
    )

    assert spec["cases"][0]["texture_output_dir"] == str(tmp_path / "textures")
    assert spec["metadata"]["texture_output_dir"] == str(tmp_path / "textures")
