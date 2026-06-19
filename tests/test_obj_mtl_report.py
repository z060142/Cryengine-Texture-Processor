from pathlib import Path

from tools.obj_mtl_report import parse_obj_mtl


def test_parse_obj_mtl_texture_refs_with_spaces(tmp_path):
    mtl = tmp_path / "sample.mtl"
    mtl.write_text(
        "\n".join(
            [
                "newmtl metalA",
                "map_Kd KB3D_DKF_metalA_Diffuse.jpg",
                "map_bump Map__99_Normal Bump.tga",
            ]
        ),
        encoding="utf-8",
    )

    report = parse_obj_mtl(str(mtl))

    assert report["summary"]["ok"] is True
    assert report["summary"]["material_count"] == 1
    assert report["materials"][0]["name"] == "metalA"
    assert report["materials"][0]["textures"][1]["file"] == "Map__99_Normal Bump.tga"
    assert report["materials"][0]["textures"][1]["texture_type"] == "normal"


def test_parse_obj_mtl_texture_refs_with_simple_option(tmp_path):
    mtl = tmp_path / "sample.mtl"
    mtl.write_text(
        "\n".join(
            [
                "newmtl planksA",
                "map_Kd -s 1 1 1 KB3D_DKF_planksA_Diffuse.jpg",
            ]
        ),
        encoding="utf-8",
    )

    report = parse_obj_mtl(str(mtl))

    assert report["materials"][0]["textures"][0]["file"] == "KB3D_DKF_planksA_Diffuse.jpg"
