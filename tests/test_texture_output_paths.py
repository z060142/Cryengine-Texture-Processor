from output_formats.texture_output_paths import (
    OUTPUT_TEXTURE_TYPE_BY_KEY,
    texture_output_filename,
    texture_output_path,
    texture_output_suffix,
)


def test_texture_output_suffixes_follow_ce_policy():
    assert OUTPUT_TEXTURE_TYPE_BY_KEY == {
        "diff": "diffuse",
        "spec": "specular",
        "ddna": "normal",
        "displ": "displacement",
        "emissive": "emissive",
        "opacity": "opacity",
        "roughness": "roughness",
        "sss": "subsurface",
    }
    assert texture_output_suffix("diff") == "_diff"
    assert texture_output_suffix("spec") == "_spec"
    assert texture_output_suffix("ddna") == "_ddn"
    assert texture_output_suffix("ddna", normal_alpha=True) == "_ddna"
    assert texture_output_suffix("displ") == "_displ"
    assert texture_output_suffix("emissive") == "_em"
    assert texture_output_suffix("roughness") == "_roughness"
    assert texture_output_suffix("sss") == "_sss"


def test_texture_output_filename_and_path_use_tif_by_default(tmp_path):
    assert texture_output_filename("emissive", "wall") == "wall_em.tif"
    assert texture_output_filename("ddna", "wall", normal_alpha=True) == "wall_ddna.tif"
    assert texture_output_path("diff", "wall", str(tmp_path)) == str(tmp_path / "wall_diff.tif")
