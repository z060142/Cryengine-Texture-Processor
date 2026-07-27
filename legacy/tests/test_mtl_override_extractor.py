import json
import xml.etree.ElementTree as ET

from tools.mtl_override_extractor import build_override_payload, extract_material_overrides, write_override_payload


def write_reference_mtl(path):
    root = ET.Element("Material")
    sub_materials = ET.SubElement(root, "SubMaterials")
    glass = ET.SubElement(
        sub_materials,
        "Material",
        Name="Glass",
        Shader="Glass",
        MtlFlags="526466",
        GenMask="524288",
        StringGenMask="%SPECULAR_MAP%TINT_MAP",
    )
    ET.SubElement(
        glass,
        "PublicParams",
        TintCloudiness="0.050000001",
        TintColor="0.16078432,0.16078432,0.16078432",
    )
    paint = ET.SubElement(
        sub_materials,
        "Material",
        Name="Paint",
        Shader="Multilayeredmaterials",
        GenMask="0",
        StringGenMask="",
    )
    ET.SubElement(paint, "PublicParams", Layer0ReflectivityScale="1.5")
    ET.ElementTree(root).write(path, encoding="utf-8")


def test_extract_material_overrides_preserves_shader_masks_and_public_params(tmp_path):
    mtl_path = tmp_path / "reference.mtl"
    write_reference_mtl(mtl_path)

    overrides = extract_material_overrides(mtl_path)

    assert overrides["Glass"]["cryengine_material"]["Shader"] == "Glass"
    assert overrides["Glass"]["cryengine_material"]["StringGenMask"] == "%SPECULAR_MAP%TINT_MAP"
    assert overrides["Glass"]["cryengine_material"]["PublicParams"]["TintCloudiness"] == "0.050000001"
    assert overrides["Paint"]["cryengine_material"]["Shader"] == "Multilayeredmaterials"
    assert overrides["Paint"]["cryengine_material"]["StringGenMask"] == ""
    assert overrides["Paint"]["cryengine_material"]["PublicParams"]["Layer0ReflectivityScale"] == "1.5"


def test_write_override_payload_writes_material_overrides_schema(tmp_path):
    mtl_path = tmp_path / "reference.mtl"
    output_path = tmp_path / "overrides.json"
    write_reference_mtl(mtl_path)

    payload = write_override_payload(mtl_path, output_path)

    assert payload["schema"] == "cryengine_material_overrides.v1"
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["material_overrides"]["Glass"]["cryengine_material"]["Shader"] == "Glass"
    assert build_override_payload(mtl_path)["material_overrides"]["Paint"]["cryengine_material"]["StringGenMask"] == ""
