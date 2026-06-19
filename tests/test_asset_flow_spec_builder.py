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


def test_texture_paths_from_obj_mtl_finds_ancestor_textures_folder(tmp_path):
    obj_dir = tmp_path / "Pack" / "Models" / "OBJ"
    texture_dir = tmp_path / "Pack" / "Textures"
    obj_dir.mkdir(parents=True)
    texture_dir.mkdir()
    mtl = obj_dir / "Weed_b.mtl"
    diff = texture_dir / "Weed_B_a.tga"
    normal = texture_dir / "Weed_B_n.tga"
    diff.write_bytes(b"diff")
    normal.write_bytes(b"normal")
    mtl.write_text(
        "newmtl Weed_B_mat\nmap_Kd Weed_B_a.tga\nbump Weed_B_n.tga -bm 1\n",
        encoding="utf-8",
    )

    assert asset_flow_spec_builder.texture_paths_from_obj_mtl(str(mtl)) == [
        str(diff.resolve()),
        str(normal.resolve()),
    ]


def test_texture_paths_from_obj_mtl_can_filter_by_name_hint(tmp_path):
    obj_dir = tmp_path / "Pack" / "Models" / "OBJ"
    texture_dir = tmp_path / "Pack" / "Textures"
    obj_dir.mkdir(parents=True)
    texture_dir.mkdir()
    mtl = obj_dir / "Weed_b.mtl"
    weed = texture_dir / "Weed_B_a.tga"
    bark = texture_dir / "Bark_a.tga"
    weed.write_bytes(b"weed")
    bark.write_bytes(b"bark")
    mtl.write_text(
        "\n".join(
            [
                "newmtl BarkSG",
                "map_Kd Bark_a.tga",
                "newmtl Weed_bSG",
                "map_Kd Weed_B_a.tga",
            ]
        ),
        encoding="utf-8",
    )

    assert asset_flow_spec_builder.texture_paths_from_obj_mtl(str(mtl), name_hint="Weed_b") == [
        str(weed.resolve())
    ]


def test_texture_paths_from_obj_mtl_expands_related_normal(tmp_path):
    obj_dir = tmp_path / "Pack" / "Models" / "OBJ"
    texture_dir = tmp_path / "Pack" / "Textures"
    obj_dir.mkdir(parents=True)
    texture_dir.mkdir()
    mtl = obj_dir / "Weed_b.mtl"
    diff = texture_dir / "Weed_B_a.tga"
    normal = texture_dir / "Weed_B_n.tga"
    diff.write_bytes(b"diff")
    normal.write_bytes(b"normal")
    mtl.write_text("newmtl Weed_bSG\nmap_Kd Weed_B_a.tga\n", encoding="utf-8")

    assert asset_flow_spec_builder.texture_paths_from_obj_mtl(str(mtl), name_hint="Weed_b") == [
        str(diff.resolve()),
        str(normal.resolve()),
    ]


def test_build_spec_can_add_texture_process_case_from_obj_mtl(tmp_path):
    pack = tmp_path / "Pack"
    fbx_dir = pack / "Models" / "FBX"
    obj_dir = pack / "Models" / "OBJ"
    texture_dir = pack / "Textures"
    fbx_dir.mkdir(parents=True)
    obj_dir.mkdir()
    texture_dir.mkdir()
    fbx = fbx_dir / "Weed_b.fbx"
    mtl = obj_dir / "Weed_b.mtl"
    diff = texture_dir / "Weed_B_a.tga"
    fbx.write_bytes(b"fbx")
    diff.write_bytes(b"diff")
    mtl.write_text("newmtl Weed_B_mat\nmap_Kd Weed_B_a.tga\n", encoding="utf-8")

    spec = asset_flow_spec_builder.build_spec(
        [str(fbx)],
        str(tmp_path / "work"),
        obj_mtl_roots=[str(obj_dir)],
        include_texture_process=True,
    )

    assert [case["type"] for case in spec["cases"]] == ["texture_process", "rc"]
    assert spec["cases"][0]["textures"] == [str(diff.resolve())]
    assert spec["cases"][1]["texture_output_dir"] == spec["cases"][0]["output_dir"]
    assert spec["cases"][1]["obj_mtl_evidence"] == str(mtl.resolve())


def test_main_prints_texture_process_cases(tmp_path, capsys):
    pack = tmp_path / "Pack"
    fbx_dir = pack / "Models" / "FBX"
    obj_dir = pack / "Models" / "OBJ"
    texture_dir = pack / "Textures"
    fbx_dir.mkdir(parents=True)
    obj_dir.mkdir()
    texture_dir.mkdir()
    fbx = fbx_dir / "Weed_b.fbx"
    mtl = obj_dir / "Weed_b.mtl"
    texture = texture_dir / "Weed_B_a.tga"
    fbx.write_bytes(b"fbx")
    texture.write_bytes(b"diff")
    mtl.write_text("newmtl Weed_B_mat\nmap_Kd Weed_B_a.tga\n", encoding="utf-8")
    output = tmp_path / "spec.json"

    asset_flow_spec_builder.main(
        [
            str(fbx),
            "--obj-mtl-root",
            str(obj_dir),
            "--include-texture-process",
            "--output",
            str(output),
            "--work-root",
            str(tmp_path / "work"),
            "--max-mb",
            "0",
        ]
    )

    assert "texture_process textures=1" in capsys.readouterr().out
