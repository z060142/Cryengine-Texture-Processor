from model_processing.material_converter import MaterialConverter
from model_processing.texture_type_resolver import infer_texture_type_from_path, normalize_texture_type


def test_normalize_texture_type_accepts_common_aliases():
    assert normalize_texture_type("Diffuse") == "diffuse"
    assert normalize_texture_type("Base Color") == "diffuse"
    assert normalize_texture_type("DDNA") == "normal"
    assert normalize_texture_type("Bumpmap") == "normal"
    assert normalize_texture_type("Heightmap") == "displacement"


def test_infer_texture_type_from_filename_suffixes():
    assert infer_texture_type_from_path("wall_diff.tif") == "diffuse"
    assert infer_texture_type_from_path("wall_ddna.tif") == "normal"
    assert infer_texture_type_from_path("wall_spec.tif") == "specular"
    assert infer_texture_type_from_path("wall_displ.tif") == "displacement"
    assert infer_texture_type_from_path("wall_emissive.tif") == "emissive"
    assert infer_texture_type_from_path("wall_opacity.tif") == "alpha"
    assert infer_texture_type_from_path("wall_unknown.tif") is None


def test_convert_maps_classified_texture_keys_to_cryengine_fields():
    result = MaterialConverter().convert(
        {"name": "Wall"},
        {
            "diffuse": "wall_diff.tif",
            "normal": "wall_ddna.tif",
            "specular": "wall_spec.tif",
            "displacement": "wall_displ.tif",
            "emissive": "wall_emissive.tif",
            "alpha": "wall_opacity.tif",
        },
    )

    assert result["Name"] == "Wall"
    assert result["Textures"]["Diffuse"] == "wall_diff.tif"
    assert result["Textures"]["Bumpmap"] == "wall_ddna.tif"
    assert result["Textures"]["Specular"] == "wall_spec.tif"
    assert result["Textures"]["Heightmap"] == "wall_displ.tif"
    assert result["Textures"]["Emittance"] == "wall_emissive.tif"
    assert result["Textures"]["Opacity"] == "wall_opacity.tif"
    assert "%NORMAL_MAP" in result["StringGenMask"]
    assert "%SPECULAR_MAP" in result["StringGenMask"]
    assert "%DISPLACEMENT_MAPPING" in result["StringGenMask"]


def test_convert_skips_known_non_mtl_texture_channels():
    result = MaterialConverter().convert(
        {"name": "Wall"},
        {
            "diffuse": "wall_diff.tif",
            "ao": "wall_ao.tif",
            "glossiness": "wall_gloss.tif",
        },
    )

    assert result["Textures"]["Diffuse"] == "wall_diff.tif"
    assert "ao" not in result["Textures"]
    assert "glossiness" not in result["Textures"]
    assert "Occlusion" not in result["Textures"]


def test_convert_can_infer_original_to_processed_texture_map():
    result = MaterialConverter().convert(
        {"name": "Wall"},
        {
            "source/wall_albedo.png": "processed/wall_diff.tif",
            "source/wall_normal.png": "processed/wall_ddna.tif",
        },
    )

    assert result["Textures"]["Diffuse"] == "processed/wall_diff.tif"
    assert result["Textures"]["Bumpmap"] == "processed/wall_ddna.tif"


def test_convert_deep_copies_template_textures():
    converter = MaterialConverter()
    first = converter.convert({"name": "A"}, {"diffuse": "a_diff.tif"})
    second = converter.convert({"name": "B"}, {})

    assert first["Textures"]["Diffuse"] == "a_diff.tif"
    assert second["Textures"]["Diffuse"] == ""


def test_apply_to_material_records_converted_data_on_dict():
    material = {"name": "Wall"}
    converted = MaterialConverter().convert(material, {"diffuse": "wall_diff.tif"})

    result = MaterialConverter().apply_to_material(material, converted)

    assert result is material
    assert material["cryengine_material"]["Textures"]["Diffuse"] == "wall_diff.tif"


def test_set_texture_node_records_normalized_texture_type_on_dict():
    material = {"name": "Wall"}

    MaterialConverter()._set_texture_node(material, "Bumpmap", "wall_ddna.tif")

    assert material["textures"] == {"normal": "wall_ddna.tif"}


def test_set_texture_node_maps_alpha_to_mtl_opacity_key_on_dict():
    material = {"name": "Wall"}

    MaterialConverter()._set_texture_node(material, "Alpha", "wall_opacity.tif")

    assert material["textures"] == {"opacity": "wall_opacity.tif"}
