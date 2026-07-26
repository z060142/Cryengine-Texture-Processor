use crate::model::ConverterModel;
use crate::request::ImportRequest;
use crate::texture_resolver::resolve_material_textures;
use quick_xml::events::{BytesEnd, BytesStart, Event};
use quick_xml::{Reader, Writer};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};
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
    texmod: Option<BTreeMap<String, String>>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct PreservedMaterial {
    name: String,
    textures: Option<Vec<TextureEntry>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MaterialTextureDiagnostic {
    pub severity: String,
    pub code: String,
    pub material: String,
    pub texture_source: Option<String>,
    pub message: String,
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
    preserve_mtl_textures: Option<&Path>,
    out: &Path,
) -> Result<Vec<MaterialTextureDiagnostic>, String> {
    let preserved_materials = preserve_mtl_textures
        .map(parse_preserved_materials)
        .transpose()?
        .unwrap_or_default();
    let preserved_by_name: BTreeMap<_, _> = preserved_materials
        .iter()
        .map(|material| (material.name.as_str(), material))
        .collect();
    let mut matched_preserved_names = BTreeSet::new();
    let source_by_name: BTreeMap<_, _> = model
        .materials
        .iter()
        .map(|material| (material.name.as_str(), material))
        .collect();
    let mtl_dir = out.parent().unwrap_or_else(|| Path::new(""));
    let mut diagnostics = Vec::new();
    // (material name, texture files) captured for the sibling .mtl.cryasset.
    let mut cryasset_materials: Vec<(String, Vec<String>)> = Vec::new();

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
        let synthesized = || {
            source_by_name
                .get(material.name.as_str())
                .map(|source| synthesized_textures(source, texture_dir, mtl_dir))
                .unwrap_or_default()
        };
        let (textures, diagnostic) = match preserved_by_name.get(material.name.as_str()) {
            Some(preserved) => {
                matched_preserved_names.insert(material.name.as_str());
                match &preserved.textures {
                    Some(textures) => (
                        textures.clone(),
                        texture_diagnostic(
                            "info",
                            "mtl_textures_preserved",
                            &material.name,
                            Some("preserved_from_ref"),
                            "Textures were preserved from the explicit reference MTL.",
                        ),
                    ),
                    None => (
                        synthesized(),
                        texture_diagnostic(
                            "warning",
                            "preserve_mtl_textures_missing",
                            &material.name,
                            Some("synthesized"),
                            "Matched reference material has no Textures element; synthesized textures were used.",
                        ),
                    ),
                }
            }
            None => (
                synthesized(),
                texture_diagnostic(
                    "info",
                    "mtl_textures_synthesized",
                    &material.name,
                    Some("synthesized"),
                    "No matching reference texture layout was applied.",
                ),
            ),
        };
        diagnostics.push(diagnostic);
        cryasset_materials.push((
            material.name.clone(),
            textures
                .iter()
                .map(|texture| texture.file.clone())
                .collect(),
        ));
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
            if let Some(texmod) = texture.texmod {
                write_empty(
                    &mut writer,
                    "TexMod",
                    &texmod.into_iter().collect::<Vec<_>>(),
                )?;
            }
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
    fs::write(out, xml).map_err(|error| format!("failed to write {}: {error}", out.display()))?;
    crate::cryasset::write_cryasset(out, &cryasset_materials)?;

    for preserved in &preserved_materials {
        if !matched_preserved_names.contains(preserved.name.as_str()) {
            diagnostics.push(texture_diagnostic(
                "warning",
                "preserve_mtl_material_unmatched",
                &preserved.name,
                None,
                "Reference MTL material did not match any output material.",
            ));
        }
    }
    Ok(diagnostics)
}

fn synthesized_textures(
    source: &crate::model::MaterialRecord,
    texture_dir: &Path,
    mtl_dir: &Path,
) -> Vec<TextureEntry> {
    resolve_material_textures(source, texture_dir, mtl_dir)
        .into_iter()
        .map(|texture| TextureEntry {
            map: texture.ce_map,
            file: texture.mtl_file,
            texmod: Some(default_texmod()),
        })
        .collect()
}

fn texture_diagnostic(
    severity: &str,
    code: &str,
    material: &str,
    texture_source: Option<&str>,
    message: &str,
) -> MaterialTextureDiagnostic {
    MaterialTextureDiagnostic {
        severity: severity.to_owned(),
        code: code.to_owned(),
        material: material.to_owned(),
        texture_source: texture_source.map(str::to_owned),
        message: message.to_owned(),
    }
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

fn parse_preserved_materials(path: &Path) -> Result<Vec<PreservedMaterial>, String> {
    let mut reader = Reader::from_file(path)
        .map_err(|error| format!("failed to read reference MTL {}: {error}", path.display()))?;
    reader.config_mut().trim_text(true);
    let mut buffer = Vec::new();
    let mut in_submaterials = false;
    let mut current_material: Option<PreservedMaterial> = None;
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
                current_material = Some(PreservedMaterial {
                    name: attrs.get("Name").cloned().unwrap_or_default(),
                    textures: None,
                });
            }
            Ok(Event::End(event)) if in_submaterials && event.name().as_ref() == b"Material" => {
                if let Some(material) = current_material.take() {
                    materials.push(material);
                }
            }
            Ok(Event::Start(event))
                if current_material.is_some() && event.name().as_ref() == b"Textures" =>
            {
                if let Some(material) = &mut current_material {
                    material.textures = Some(Vec::new());
                }
            }
            Ok(Event::Empty(event))
                if current_material.is_some() && event.name().as_ref() == b"Textures" =>
            {
                if let Some(material) = &mut current_material {
                    material.textures = Some(Vec::new());
                }
            }
            Ok(Event::Start(event))
                if current_material
                    .as_ref()
                    .is_some_and(|material| material.textures.is_some())
                    && event.name().as_ref() == b"Texture" =>
            {
                current_texture = Some(texture_from_attrs(read_attrs(&event)?));
            }
            Ok(Event::Empty(event))
                if current_material
                    .as_ref()
                    .is_some_and(|material| material.textures.is_some())
                    && event.name().as_ref() == b"Texture" =>
            {
                if let Some(textures) = current_material
                    .as_mut()
                    .and_then(|material| material.textures.as_mut())
                {
                    textures.push(texture_from_attrs(read_attrs(&event)?));
                }
            }
            Ok(Event::Start(event))
                if current_texture.is_some() && event.name().as_ref() == b"TexMod" =>
            {
                if let Some(texture) = &mut current_texture {
                    texture.texmod = Some(read_attrs(&event)?);
                }
            }
            Ok(Event::Empty(event))
                if current_texture.is_some() && event.name().as_ref() == b"TexMod" =>
            {
                if let Some(texture) = &mut current_texture {
                    texture.texmod = Some(read_attrs(&event)?);
                }
            }
            Ok(Event::End(event))
                if current_material.is_some() && event.name().as_ref() == b"Texture" =>
            {
                if let (Some(textures), Some(texture)) = (
                    current_material
                        .as_mut()
                        .and_then(|material| material.textures.as_mut()),
                    current_texture.take(),
                ) {
                    textures.push(texture);
                }
            }
            Ok(Event::Eof) => break,
            Ok(_) => {}
            Err(error) => {
                return Err(format!(
                    "failed to parse reference MTL {}: {error}",
                    path.display()
                ));
            }
        }
        buffer.clear();
    }
    Ok(materials)
}

fn texture_from_attrs(attrs: BTreeMap<String, String>) -> TextureEntry {
    TextureEntry {
        map: attrs.get("Map").cloned().unwrap_or_default(),
        file: attrs.get("File").cloned().unwrap_or_default(),
        texmod: None,
    }
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
    use crate::model::{MaterialRecord, NodeRecord, TextureRef};
    use crate::request::{ImportRequest, RequestMaterial};
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn payload(json: &str) -> MaterialOverridePayload {
        serde_json::from_str(json).unwrap()
    }

    fn temp_dir(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "converter-mtl-{label}-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir_all(&path).unwrap();
        path
    }

    fn model(names: &[&str]) -> ConverterModel {
        ConverterModel {
            source_fbx: "fixture.fbx".to_owned(),
            materials: names
                .iter()
                .enumerate()
                .map(|(index, name)| MaterialRecord {
                    name: (*name).to_owned(),
                    typed_id: index as u32,
                    element_id: index as u32,
                    textures: vec![TextureRef {
                        material_prop: "DiffuseColor".to_owned(),
                        shader_prop: "DiffuseColor".to_owned(),
                        filename: format!("{name}_basecolor.png"),
                        absolute_filename: String::new(),
                        relative_filename: String::new(),
                        embedded: false,
                        content_size: 0,
                        content: Vec::new(),
                    }],
                })
                .collect(),
            meshes: Vec::new(),
            scene_tree: NodeRecord {
                name: "Root".to_owned(),
                element_id: 0,
                typed_id: 0,
                children: Vec::new(),
            },
            node_count: 1,
            axes: crate::model::AxisDetection::fallback(),
        }
    }

    fn request(names: &[&str]) -> ImportRequest {
        ImportRequest {
            source_filename: "fixture.fbx".to_owned(),
            output_ext: "cgf".to_owned(),
            material_filename: Some("fixture".to_owned()),
            forward_up_axes: Some("-Y+Z".to_owned()),
            unit_size: Some("cm".to_owned()),
            scale: Some(1.0),
            physics_primitive: None,
            merge_all_nodes: Some(false),
            scene_origin: Some(false),
            ignore_custom_normals: Some(false),
            ignore_uv: Some(false),
            materials: names
                .iter()
                .enumerate()
                .map(|(index, name)| RequestMaterial {
                    name: (*name).to_owned(),
                    physicalize: "no".to_owned(),
                    sub_index: index as i32,
                })
                .collect(),
            nodes: Vec::new(),
            autolodsettings: None,
            animation: None,
            joint_physics_data: Vec::new(),
        }
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

    #[test]
    fn preserve_layout_handles_empty_missing_and_unmatched_materials() {
        let root = temp_dir("preserve-boundaries");
        let reference = root.join("reference.mtl");
        let output = root.join("output.mtl");
        fs::write(
            &reference,
            r#"<Material><SubMaterials>
                <Material Name="Exact"><Textures>
                    <Texture Map="Bumpmap" File="./shared_normal.dds"><TexMod Custom="yes"/></Texture>
                </Textures></Material>
                <Material Name="Empty"><Textures/></Material>
                <Material Name="Missing"></Material>
                <Material Name="Extra"><Textures><Texture Map="Diffuse" File="./unused.dds"/></Textures></Material>
            </SubMaterials></Material>"#,
        )
        .unwrap();
        for name in ["Exact", "Empty", "Missing"] {
            fs::write(root.join(format!("{name}_diff.tif")), b"fixture").unwrap();
        }

        let diagnostics = write_mtl(
            &model(&["Exact", "Empty", "Missing"]),
            &request(&["Exact", "Empty", "Missing"]),
            None,
            &root,
            Some(&reference),
            &output,
        )
        .unwrap();
        let parsed = parse_preserved_materials(&output).unwrap();
        let by_name: BTreeMap<_, _> = parsed
            .iter()
            .map(|material| (material.name.as_str(), material))
            .collect();

        let exact = by_name["Exact"].textures.as_ref().unwrap();
        assert_eq!(exact.len(), 1);
        assert_eq!(exact[0].map, "Bumpmap");
        assert_eq!(exact[0].file, "./shared_normal.dds");
        assert_eq!(exact[0].texmod.as_ref().unwrap()["Custom"], "yes");
        assert!(by_name["Empty"].textures.as_ref().unwrap().is_empty());
        assert_eq!(
            by_name["Missing"].textures.as_ref().unwrap()[0].file,
            "./Missing_diff.tif"
        );

        let diagnostic_by_material: BTreeMap<_, _> = diagnostics
            .iter()
            .map(|diagnostic| (diagnostic.material.as_str(), diagnostic))
            .collect();
        assert_eq!(
            diagnostic_by_material["Exact"].texture_source.as_deref(),
            Some("preserved_from_ref")
        );
        assert_eq!(
            diagnostic_by_material["Empty"].texture_source.as_deref(),
            Some("preserved_from_ref")
        );
        assert_eq!(
            diagnostic_by_material["Missing"].code,
            "preserve_mtl_textures_missing"
        );
        assert_eq!(
            diagnostic_by_material["Missing"].texture_source.as_deref(),
            Some("synthesized")
        );
        assert_eq!(
            diagnostic_by_material["Extra"].code,
            "preserve_mtl_material_unmatched"
        );
        assert_eq!(diagnostic_by_material["Extra"].severity, "warning");
        let extra_json = serde_json::to_value(diagnostic_by_material["Extra"]).unwrap();
        assert!(extra_json
            .as_object()
            .unwrap()
            .contains_key("texture_source"));
        assert!(extra_json["texture_source"].is_null());

        fs::remove_dir_all(root).unwrap();
    }
}
