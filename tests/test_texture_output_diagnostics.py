from core.batch_processor import BatchProcessor
from core.texture_manager import TextureGroup
from output_formats.texture_output_diagnostics import build_texture_output_policy


class ExporterStub:
    def __init__(self, path):
        self.path = path

    def export(self, group, settings, output_dir):
        del group, settings, output_dir
        return self.path


def test_build_texture_output_policy_accepts_ce_suffixes_and_rc_source_extensions():
    policy = build_texture_output_policy(
        {
            "diff": "wall_diff.tif",
            "spec": "wall_spec.tif",
            "ddna": "wall_ddna.tif",
            "displ": "wall_displ.tif",
            "emissive": "wall_em.tif",
            "sss": "wall_sss.tif",
        }
    )

    assert policy["ok"] is True
    assert policy["diagnostics"] == []
    ce_map_by_key = {entry["output_key"]: entry["policy"]["ce_map_type"] for entry in policy["entries"]}
    assert ce_map_by_key == {
        "ddna": "Bumpmap",
        "diff": "Diffuse",
        "displ": "Heightmap",
        "emissive": "Emittance",
        "spec": "Specular",
        "sss": "SubSurface",
    }


def test_build_texture_output_policy_warns_for_non_rc_extension_and_suffix_mismatch():
    policy = build_texture_output_policy(
        {
            "diff": "wall_basecolor.png",
            "spec": "wall_s.tif",
            "unknown": "wall_custom.tif",
        }
    )

    assert policy["ok"] is False
    assert [diagnostic["code"] for diagnostic in policy["diagnostics"]] == [
        "unsupported_rc_texture_output_extension",
        "mismatch_texture_output_suffix",
        "mismatch_texture_output_suffix",
        "unknown_texture_output_key",
    ]
    assert policy["diagnostics"][0]["supported_extensions"] == ["dds", "hdr", "tif"]
    assert policy["diagnostics"][1]["expected_suffix"] == "_diff"
    assert policy["diagnostics"][2]["expected_suffix"] == "_spec"


def test_batch_processor_records_texture_output_policy(tmp_path):
    group = TextureGroup("wall")
    processor = BatchProcessor(texture_manager=None)
    processor.set_output_dir(str(tmp_path))
    processor.set_settings({"texture_types": {"diff": True, "spec": False, "ddna": True, "displ": False}})
    processor.diff_exporter = ExporterStub(str(tmp_path / "wall_basecolor.png"))
    processor.ddna_exporter = ExporterStub(str(tmp_path / "wall_ddna.tif"))

    processor._generate_output_formats(group)

    assert group.output["diff"] == str(tmp_path / "wall_basecolor.png")
    assert group.output["ddna"] == str(tmp_path / "wall_ddna.tif")
    assert group.output_policy["ok"] is False
    assert [diagnostic["code"] for diagnostic in group.output_diagnostics] == [
        "unsupported_rc_texture_output_extension",
        "mismatch_texture_output_suffix",
    ]
