from core.texture_manager import TextureGroup
from output_formats.emissive_exporter import EmissiveExporter


def test_emissive_exporter_generates_ce_em_suffix(tmp_path):
    group = TextureGroup("lamp")
    exporter = EmissiveExporter()

    output_path = exporter.export(
        group,
        {"generate_missing_emissive": True, "output_resolution": "16"},
        str(tmp_path),
    )

    assert output_path == str(tmp_path / "lamp_em.tif")
    assert (tmp_path / "lamp_em.tif").exists()
