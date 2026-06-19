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
