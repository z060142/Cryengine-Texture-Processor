use crate::model::{ConverterModel, MaterialRecord};
use crate::request::ImportRequest;
use quick_xml::events::{BytesEnd, BytesStart, Event};
use quick_xml::{Reader, Writer};
use serde::Deserialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

const ROOT_MTL_FLAGS: &str = "524544";
const SUB_MTL_FLAGS: &str = "524416";
const MATERIAL_ATTR_KEYS: &[&str] = &[
    "AlphaTest",
    "CloakAmount",
    "Diffuse",
    "Emittance",
    "LayerAct",
    "MatTemplate",
    "MtlFlags",
    "Opacity",
    "Shader",
    "Shininess",
    "Specular",
    "SurfaceType",
    "vertModifType",
];

#[derive(Debug, Deserialize)]
pub struct MaterialOverridePayload {
    #[serde(default)]
    pub schema: Option<String>,
    #[serde(default)]
    source_mtl: Option<String>,
    #[serde(default)]
    material_overrides: BTreeMap<String, Value>,
    #[serde(skip)]
    payload_dir: PathBuf,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct MaterialState {
    attrs: BTreeMap<String, String>,
    public_params: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct TextureEntry {
    map: String,
    file: String,
    texmod: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct NativeMaterial {
    name: String,
    textures: Vec<TextureEntry>,
}

impl MaterialOverridePayload {
    pub fn load(path: &Path) -> Result<Self, String> {
        let json = fs::read_to_string(path)
            .map_err(|error| format!("failed to read overrides {}: {error}", path.display()))?;
        let mut payload: Self = serde_json::from_str(&json)
            .map_err(|error| format!("failed to parse overrides {}: {error}", path.display()))?;
        if let Some(schema) = &payload.schema {
            if schema != "cryengine_material_overrides.v1" {
                return Err(format!(
                    "unsupported material override schema {schema:?} in {}",
                    path.display()
                ));
            }
        }
        payload.payload_dir = path.parent().unwrap_or_else(|| Path::new("")).to_owned();
        Ok(payload)
    }

    fn state(&self, material_name: &str) -> Option<MaterialState> {
        let row = self.material_overrides.get(material_name)?.as_object()?;
        let mut state = MaterialState::default();
        for source in override_sources(row) {
            for alias in ["material_attrs", "mtl_attrs", "attributes"] {
                if let Some(attrs) = source.get(alias).and_then(Value::as_object) {
                    extend_string_values(&mut state.attrs, attrs);
                }
            }
            for key in MATERIAL_ATTR_KEYS {
                if let Some(value) = source.get(*key).and_then(xml_value) {
                    state.attrs.insert((*key).to_owned(), value);
                }
            }
            if let Some(value) = source.get("shader").and_then(xml_value) {
                state.attrs.insert("Shader".to_owned(), value);
            }
            for (canonical, aliases) in [
                ("GenMask", ["GenMask", "gen_mask"]),
                ("StringGenMask", ["StringGenMask", "string_gen_mask"]),
            ] {
                for alias in aliases {
                    if let Some(value) = source.get(alias).and_then(xml_value) {
                        state.attrs.insert(canonical.to_owned(), value);
                        break;
                    }
                }
            }
            for alias in ["PublicParams", "public_params"] {
                if let Some(params) = source.get(alias).and_then(Value::as_object) {
                    extend_string_values(&mut state.public_params, params);
                }
            }
        }
        state.attrs.remove("Name");
        Some(state)
    }

    fn source_mtl_path(&self) -> Option<PathBuf> {
        let path = PathBuf::from(self.source_mtl.as_deref()?);
        Some(if path.is_absolute() {
            path
        } else {
            self.payload_dir.join(path)
        })
    }
}

fn override_sources(row: &Map<String, Value>) -> Vec<&Map<String, Value>> {
    let mut sources = Vec::new();
    for key in ["cryengine_material", "ce_material", "mtl_overrides"] {
        if let Some(source) = row.get(key).and_then(Value::as_object) {
            sources.push(source);
        }
    }
    sources.push(row);
    sources
}

fn xml_value(value: &Value) -> Option<String> {
    match value {
        Value::String(value) => Some(value.clone()),
        Value::Number(value) => Some(value.to_string()),
        Value::Bool(value) => Some(if *value { "true" } else { "false" }.to_owned()),
        _ => None,
    }
}

fn extend_string_values(target: &mut BTreeMap<String, String>, source: &Map<String, Value>) {
    for (name, value) in source {
        if !name.is_empty() {
            if let Some(value) = xml_value(value) {
                target.insert(name.clone(), value);
            }
        }
    }
}

pub fn write_mtl(
    model: &ConverterModel,
    request: &ImportRequest,
    overrides: Option<&MaterialOverridePayload>,
    out: &Path,
) -> Result<(), String> {
    let native_materials = overrides
        .and_then(MaterialOverridePayload::source_mtl_path)
        .filter(|path| path.is_file())
        .map(|path| parse_native_materials(&path))
        .transpose()?
        .unwrap_or_default();
    let native_by_name: BTreeMap<_, _> = native_materials
        .into_iter()
        .map(|material| (material.name.clone(), material))
        .collect();
    let source_by_name: BTreeMap<_, _> = model
        .materials
        .iter()
        .map(|material| (material.name.as_str(), material))
        .collect();

    let mut writer = Writer::new(Vec::new());
    write_start(
        &mut writer,
        "Material",
        &[
            ("MtlFlags".to_owned(), ROOT_MTL_FLAGS.to_owned()),
            ("vertModifType".to_owned(), "0".to_owned()),
        ],
    )?;
    write_start(&mut writer, "SubMaterials", &[])?;

    for material in &request.materials {
        let textures = native_by_name
            .get(&material.name)
            .map(|native| native.textures.clone())
            .unwrap_or_else(|| {
                source_by_name.get(material.name.as_str()).map_or_else(
                    || fallback_placeholder_textures(&material.name),
                    |source| fallback_source_textures(source),
                )
            });
        let fallback_policy = fallback_shader_policy(&textures);
        let override_state = overrides.and_then(|payload| payload.state(&material.name));
        let mut attrs = override_state
            .as_ref()
            .map(|state| state.attrs.clone())
            .unwrap_or_else(default_material_attrs);
        if !attrs.contains_key("GenMask") || !attrs.contains_key("StringGenMask") {
            attrs
                .entry("GenMask".to_owned())
                .or_insert_with(|| fallback_policy.0.clone());
            attrs
                .entry("StringGenMask".to_owned())
                .or_insert_with(|| fallback_policy.1.clone());
        }

        let mut ordered_attrs = vec![("Name".to_owned(), material.name.clone())];
        ordered_attrs.extend(attrs);
        write_start(&mut writer, "Material", &ordered_attrs)?;
        write_start(&mut writer, "Textures", &[])?;

        for texture in textures {
            write_start(
                &mut writer,
                "Texture",
                &[
                    ("Map".to_owned(), texture.map),
                    ("File".to_owned(), texture.file),
                ],
            )?;
            write_empty(
                &mut writer,
                "TexMod",
                &texture.texmod.into_iter().collect::<Vec<_>>(),
            )?;
            write_end(&mut writer, "Texture")?;
        }
        write_end(&mut writer, "Textures")?;

        let public_params = override_state
            .map(|state| state.public_params)
            .filter(|params| !params.is_empty())
            .unwrap_or(fallback_policy.2);
        write_empty(
            &mut writer,
            "PublicParams",
            &public_params.into_iter().collect::<Vec<_>>(),
        )?;
        write_end(&mut writer, "Material")?;
    }

    write_end(&mut writer, "SubMaterials")?;
    write_empty(
        &mut writer,
        "PublicParams",
        &[
            ("EmittanceMapGamma".to_owned(), "1".to_owned()),
            ("SSSIndex".to_owned(), "0".to_owned()),
        ],
    )?;
    write_end(&mut writer, "Material")?;

    let xml = String::from_utf8(writer.into_inner())
        .map_err(|error| format!("MTL writer produced invalid UTF-8: {error}"))?;
    fs::write(out, xml).map_err(|error| format!("failed to write {}: {error}", out.display()))
}

fn default_material_attrs() -> BTreeMap<String, String> {
    [
        ("MtlFlags", SUB_MTL_FLAGS),
        ("Shader", "Illum"),
        ("SurfaceType", ""),
        ("MatTemplate", ""),
        ("Diffuse", "1,1,1"),
        ("Specular", "1,1,1"),
        ("Emittance", "0,0,0,0"),
        ("Opacity", "1"),
        ("Shininess", "255"),
    ]
    .into_iter()
    .map(|(key, value)| (key.to_owned(), value.to_owned()))
    .collect()
}

fn fallback_shader_policy(textures: &[TextureEntry]) -> (String, String, BTreeMap<String, String>) {
    let has_normal = textures.iter().any(|texture| texture.map == "Bumpmap");
    let has_specular = textures.iter().any(|texture| texture.map == "Specular");
    let policy_name = if has_normal && has_specular {
        "normal_specular_displacement"
    } else {
        "empty_material"
    };
    let policy = &ce_schema::genmask_table()[policy_name];
    let gen_mask = policy["gen_mask"].as_u64().unwrap_or(32).to_string();
    let string_gen_mask = policy["string_gen_mask"]
        .as_str()
        .unwrap_or("%SUBSURFACE_SCATTERING")
        .to_owned();
    let public_params = policy["public_params"]
        .as_object()
        .map(|params| {
            params
                .iter()
                .filter_map(|(name, value)| {
                    value.as_str().map(|value| (name.clone(), value.to_owned()))
                })
                .collect()
        })
        .unwrap_or_else(|| {
            [
                ("EmittanceMapGamma".to_owned(), "1".to_owned()),
                ("SSSIndex".to_owned(), "0".to_owned()),
            ]
            .into_iter()
            .collect()
        });
    (gen_mask, string_gen_mask, public_params)
}

fn fallback_source_textures(material: &MaterialRecord) -> Vec<TextureEntry> {
    let props: Vec<_> = material
        .textures
        .iter()
        .map(|texture| texture.material_prop.to_ascii_lowercase())
        .collect();
    let channels = [
        (
            "diffuse",
            "diff",
            props.iter().any(|prop| prop == "diffusecolor"),
        ),
        (
            "normal",
            "ddna",
            props.iter().any(|prop| prop == "normalmap"),
        ),
        (
            "specular",
            "spec",
            props
                .iter()
                .any(|prop| prop == "reflectionfactor" || prop == "shininessexponent"),
        ),
        (
            "displacement",
            "displ",
            props.iter().any(|prop| prop == "shininessexponent"),
        ),
        (
            "opacity",
            "opacity",
            props.iter().any(|prop| prop == "transparencyfactor"),
        ),
        (
            "emissive",
            "emissive",
            props.iter().any(|prop| prop == "emissivecolor"),
        ),
    ];
    channels
        .into_iter()
        .filter(|(_, _, present)| *present)
        .filter_map(|(texture_type, output_key, _)| {
            let policy = ce_schema::ce_texture_map(texture_type)?;
            policy.exported.then(|| TextureEntry {
                map: policy.ce_map_type.clone(),
                file: format!(
                    "./{}{}.dds",
                    material.name,
                    ce_schema::texture_suffix(output_key, output_key == "ddna")
                ),
                texmod: default_texmod(),
            })
        })
        .collect()
}

fn fallback_placeholder_textures(name: &str) -> Vec<TextureEntry> {
    if !matches!(
        name.to_ascii_lowercase().as_str(),
        "unassigned" | "<unassigned>"
    ) {
        return Vec::new();
    }
    vec![
        TextureEntry {
            map: "Diffuse".to_owned(),
            file: "%ENGINE%/EngineAssets/Textures/white.dds".to_owned(),
            texmod: default_texmod(),
        },
        TextureEntry {
            map: "Bumpmap".to_owned(),
            file: "%ENGINE%/EngineAssets/Textures/white_ddn.dds".to_owned(),
            texmod: default_texmod(),
        },
    ]
}

fn default_texmod() -> BTreeMap<String, String> {
    ce_schema::texmod_table()["attributes"]
        .as_object()
        .map(|attrs| {
            attrs
                .iter()
                .filter_map(|(name, value)| {
                    value.as_str().map(|value| (name.clone(), value.to_owned()))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn parse_native_materials(path: &Path) -> Result<Vec<NativeMaterial>, String> {
    let mut reader = Reader::from_file(path)
        .map_err(|error| format!("failed to read source MTL {}: {error}", path.display()))?;
    reader.config_mut().trim_text(true);
    let mut buffer = Vec::new();
    let mut in_submaterials = false;
    let mut current_material: Option<NativeMaterial> = None;
    let mut current_texture: Option<TextureEntry> = None;
    let mut materials = Vec::new();

    loop {
        match reader.read_event_into(&mut buffer) {
            Ok(Event::Start(event)) if event.name().as_ref() == b"SubMaterials" => {
                in_submaterials = true;
            }
            Ok(Event::End(event)) if event.name().as_ref() == b"SubMaterials" => {
                in_submaterials = false;
            }
            Ok(Event::Start(event)) if in_submaterials && event.name().as_ref() == b"Material" => {
                let attrs = read_attrs(&event)?;
                current_material = Some(NativeMaterial {
                    name: attrs.get("Name").cloned().unwrap_or_default(),
                    textures: Vec::new(),
                });
            }
            Ok(Event::End(event)) if in_submaterials && event.name().as_ref() == b"Material" => {
                if let Some(material) = current_material.take() {
                    materials.push(material);
                }
            }
            Ok(Event::Start(event))
                if current_material.is_some() && event.name().as_ref() == b"Texture" =>
            {
                let attrs = read_attrs(&event)?;
                current_texture = Some(TextureEntry {
                    map: attrs.get("Map").cloned().unwrap_or_default(),
                    file: attrs.get("File").cloned().unwrap_or_default(),
                    texmod: BTreeMap::new(),
                });
            }
            Ok(Event::Empty(event))
                if current_texture.is_some() && event.name().as_ref() == b"TexMod" =>
            {
                if let Some(texture) = &mut current_texture {
                    texture.texmod = read_attrs(&event)?;
                }
            }
            Ok(Event::End(event))
                if current_material.is_some() && event.name().as_ref() == b"Texture" =>
            {
                if let (Some(material), Some(texture)) =
                    (&mut current_material, current_texture.take())
                {
                    material.textures.push(texture);
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(error) => {
                return Err(format!(
                    "failed to parse source MTL {}: {error}",
                    path.display()
                ));
            }
        }
        buffer.clear();
    }
    Ok(materials)
}

fn read_attrs(event: &BytesStart<'_>) -> Result<BTreeMap<String, String>, String> {
    event
        .attributes()
        .map(|attribute| {
            let attribute = attribute.map_err(|error| format!("invalid XML attribute: {error}"))?;
            let key = String::from_utf8_lossy(attribute.key.as_ref()).into_owned();
            let value = attribute
                .normalized_value(quick_xml::XmlVersion::Implicit1_0)
                .map_err(|error| format!("invalid XML attribute value: {error}"))?
                .into_owned();
            Ok((key, value))
        })
        .collect()
}

fn write_start(
    writer: &mut Writer<Vec<u8>>,
    name: &str,
    attrs: &[(String, String)],
) -> Result<(), String> {
    let mut event = BytesStart::new(name);
    for (key, value) in attrs {
        event.push_attribute((key.as_str(), value.as_str()));
    }
    writer
        .write_event(Event::Start(event))
        .map_err(|error| format!("failed to write MTL XML: {error}"))
}

fn write_empty(
    writer: &mut Writer<Vec<u8>>,
    name: &str,
    attrs: &[(String, String)],
) -> Result<(), String> {
    let mut event = BytesStart::new(name);
    for (key, value) in attrs {
        event.push_attribute((key.as_str(), value.as_str()));
    }
    writer
        .write_event(Event::Empty(event))
        .map_err(|error| format!("failed to write MTL XML: {error}"))
}

fn write_end(writer: &mut Writer<Vec<u8>>, name: &str) -> Result<(), String> {
    writer
        .write_event(Event::End(BytesEnd::new(name)))
        .map_err(|error| format!("failed to write MTL XML: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn payload(json: &str) -> MaterialOverridePayload {
        serde_json::from_str(json).unwrap()
    }

    #[test]
    fn all_three_override_channels_are_supported_in_precedence_order() {
        let payload = payload(
            r#"{
                "material_overrides": {
                    "Glass": {
                        "cryengine_material": {"Shader":"Glass","MtlFlags":"1"},
                        "ce_material": {"MtlFlags":"2","public_params":{"Tint":"0.1"}},
                        "mtl_overrides": {"MtlFlags":"3","string_gen_mask":"%TINT_MAP"},
                        "shader":"Illum"
                    }
                }
            }"#,
        );
        let state = payload.state("Glass").unwrap();
        assert_eq!(state.attrs["Shader"], "Illum");
        assert_eq!(state.attrs["MtlFlags"], "3");
        assert_eq!(state.attrs["StringGenMask"], "%TINT_MAP");
        assert_eq!(state.public_params["Tint"], "0.1");
    }

    #[test]
    fn shader_fallback_is_loaded_from_ce_schema() {
        let textures = [
            TextureEntry {
                map: "Bumpmap".to_owned(),
                ..TextureEntry::default()
            },
            TextureEntry {
                map: "Specular".to_owned(),
                ..TextureEntry::default()
            },
        ];
        let (gen_mask, string_gen_mask, public_params) = fallback_shader_policy(&textures);
        assert_eq!(gen_mask, "1125899907366944");
        assert_eq!(
            string_gen_mask,
            "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
        );
        assert_eq!(public_params["SSSIndex"], "0");

        let (gen_mask, string_gen_mask, _) = fallback_shader_policy(&[]);
        assert_eq!(gen_mask, "32");
        assert_eq!(string_gen_mask, "%SUBSURFACE_SCATTERING");
    }

    #[test]
    fn fallback_paths_use_ce_schema_suffix_and_map_tables() {
        let material = MaterialRecord {
            name: "Stone".to_owned(),
            typed_id: 0,
            element_id: 0,
            textures: vec![crate::model::TextureRef {
                material_prop: "NormalMap".to_owned(),
                shader_prop: "NormalMap".to_owned(),
                filename: "stone_normal.png".to_owned(),
                absolute_filename: String::new(),
                relative_filename: String::new(),
                embedded: false,
                content_size: 0,
            }],
        };
        let textures = fallback_source_textures(&material);
        assert_eq!(textures[0].map, "Bumpmap");
        assert_eq!(textures[0].file, "./Stone_ddna.dds");
        assert_eq!(textures[0].texmod["TexMod_RotateType"], "0");
    }
}
