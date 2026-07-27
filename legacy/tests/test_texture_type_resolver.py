from model_processing.texture_type_resolver import (
    infer_texture_type_from_path,
    infer_texture_type_from_text,
    normalize_texture_type,
)
from model_processing.texture_extractor import TextureExtractor


class ImageStub:
    filepath = "wall_normal.png"


class SocketStub:
    name = "Base Color"


class LinkStub:
    to_socket = SocketStub()


class OutputStub:
    links = [LinkStub()]


class NodeStub:
    image = ImageStub()
    outputs = [OutputStub()]
    label = ""
    name = "Image Texture"


def test_normalize_texture_type_handles_blender_socket_names_and_ce_maps():
    assert normalize_texture_type("Base Color") == "diffuse"
    assert normalize_texture_type("Diffuse Color") == "diffuse"
    assert normalize_texture_type("Normal Map") == "normal"
    assert normalize_texture_type("Bumpmap") == "normal"
    assert normalize_texture_type("Heightmap") == "displacement"
    assert normalize_texture_type("Emission Color") == "emissive"
    assert normalize_texture_type("Ambient Occlusion") == "ao"


def test_infer_texture_type_from_path_uses_shared_suffix_priority():
    assert infer_texture_type_from_path("wall_diff.tif") == "diffuse"
    assert infer_texture_type_from_path("wall_a.tif") == "diffuse"
    assert infer_texture_type_from_path("wall_ddna.tif") == "normal"
    assert infer_texture_type_from_path("wall_spec.tif") == "specular"
    assert infer_texture_type_from_path("wall_displ.tif") == "displacement"
    assert infer_texture_type_from_path("wall_emissive.tif") == "emissive"
    assert infer_texture_type_from_path("wall_opacity.tif") == "alpha"
    assert infer_texture_type_from_path("wall_ao.tif") == "ao"
    assert infer_texture_type_from_path("wall_rough.tif") == "roughness"
    assert infer_texture_type_from_path("wall_gloss.tif") == "glossiness"
    assert infer_texture_type_from_path("wall_metallic.tif") == "metallic"
    assert infer_texture_type_from_path("wall_unknown.tif") is None


def test_infer_texture_type_from_text_uses_socket_and_node_hints():
    assert infer_texture_type_from_text("Base Color") == "diffuse"
    assert infer_texture_type_from_text("Fancy Normal Input") == "normal"
    assert infer_texture_type_from_text("roughness value") == "roughness"
    assert infer_texture_type_from_text("Metallic Factor") == "metallic"
    assert infer_texture_type_from_text("Displace Height") == "displacement"
    assert infer_texture_type_from_text("unrelated") is None


def test_texture_extractor_prefers_filename_suffix_over_socket_hint():
    extractor = TextureExtractor.__new__(TextureExtractor)

    assert extractor._determine_texture_type(NodeStub(), material=None) == "normal"
