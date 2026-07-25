use crate::model::ConverterModel;
use crate::request::ImportRequest;
use crate::texture_resolver::resolve_material_textures;
use quick_xml::events::{BytesEnd, BytesStart, Event};
use quick_xml::Writer;
use serde::Deserialize;
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

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
    material_overrides: BTreeMap<String, Value>,
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

impl MaterialOverridePayload {
    pub fn load(path: &Path) -> Result<Self, String> {
        let json = fs::read_to_string(path)
            .map_err(|error| format!("failed to read overrides {}: {error}", path.display()))?;
        let payload: Self = serde_json::from_str(&json)
            .map_err(|error| format!("failed to parse overrides {}: {error}", path.display()))?;
        if let Some(schema) = &payload.schema {
            if schema != "cryengine_material_overrides.v1" {
                return Err(format!(
                    "unsupported material override schema {schema:?} in {}",
                    path.display()
                ));
            }
        }
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
    texture_dir: &Path,
    out: &Path,
) -> Result<(), String> {
    let source_by_name: BTreeMap<_, _> = model
        .materials
        .iter()
        .map(|material| (material.name.as_str(), material))
        .collect();
    let mtl_dir = out.parent().unwrap_or_else(|| Path::new(""));

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
        let textures: Vec<TextureEntry> = source_by_name
            .get(material.name.as_str())
            .map(|source| {
                resolve_material_textures(source, texture_dir, mtl_dir)
                    .into_iter()
                    .map(|texture| TextureEntry {
                        map: texture.ce_map,
                        file: texture.mtl_file,
                        texmod: default_texmod(),
                    })
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();
        let fallback_policy = fallback_shader_policy(&textures);
        let override_state = overrides.and_then(|payload| payload.state(&material.name));
        let mut attrs = default_material_attrs();
        if let Some(state) = &override_state {
            attrs.extend(state.attrs.clone());
        }
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
    fn texture_modifier_defaults_are_loaded_from_ce_schema() {
        let texmod = default_texmod();
        assert_eq!(texmod["TexMod_RotateType"], "0");
        assert_eq!(texmod["TexMod_TexGenType"], "0");
        assert_eq!(texmod["TexMod_bTexGenProjected"], "0");
    }
}
