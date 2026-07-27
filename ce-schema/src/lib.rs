use serde::Deserialize;
use serde_json::Value;
use std::sync::LazyLock;

const SCHEMA_JSON: &str = include_str!("../data/converter_schema.json");

const OUTPUT_TEXTURE_TYPES: &[(&str, &str)] = &[
    ("diff", "diffuse"),
    ("spec", "specular"),
    ("ddna", "normal"),
    ("displ", "displacement"),
    ("emissive", "emissive"),
    ("opacity", "opacity"),
    ("roughness", "roughness"),
    ("sss", "subsurface"),
];

static SCHEMA: LazyLock<ConverterSchema> = LazyLock::new(|| {
    serde_json::from_str(SCHEMA_JSON).expect("embedded converter schema must be valid JSON")
});

#[derive(Debug, Deserialize)]
struct ConverterSchema {
    texture_outputs: TextureOutputs,
    mtl: MtlSchema,
}

#[derive(Debug, Deserialize)]
struct TextureOutputs {
    supported_source_extensions: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct MtlSchema {
    texture_maps: TextureMapSchema,
    texture_modifier: Value,
    shader_policy: Value,
}

#[derive(Debug, Deserialize)]
struct TextureMapSchema {
    entries: Vec<CeTextureMap>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
pub struct CeTextureMap {
    pub texture_type: String,
    pub ce_map_type: String,
    pub exported: bool,
    pub expected_suffix: String,
    pub accepted_suffixes: Vec<String>,
}

/// Returns the output suffix for a supported texture pipeline output key.
///
/// Unknown keys return an empty string.
pub fn texture_suffix(output_key: &str, normal_has_alpha: bool) -> &'static str {
    if output_key == "ddna" && normal_has_alpha {
        return "_ddna";
    }

    if let Some((_, texture_type)) = OUTPUT_TEXTURE_TYPES
        .iter()
        .find(|(key, _)| *key == output_key)
    {
        if let Some(texture_map) = ce_texture_map(texture_type) {
            if !texture_map.expected_suffix.is_empty() {
                return texture_map.expected_suffix.as_str();
            }
        }
    }

    match output_key {
        "ddn" | "ddna" => "_ddn",
        "diff" => "_diff",
        "displ" => "_displ",
        "em" | "emissive" => "_em",
        "opacity" => "_opacity",
        "roughness" => "_roughness",
        "spec" => "_spec",
        "sss" => "_sss",
        _ => "",
    }
}

/// Looks up the CryEngine material texture-map policy for a texture type.
pub fn ce_texture_map(texture_type: &str) -> Option<&'static CeTextureMap> {
    SCHEMA
        .mtl
        .texture_maps
        .entries
        .iter()
        .find(|entry| entry.texture_type.eq_ignore_ascii_case(texture_type))
}

/// Returns the RC-supported texture source extensions.
pub fn supported_rc_source_extensions() -> &'static [String] {
    &SCHEMA.texture_outputs.supported_source_extensions
}

/// Returns the embedded texture-modifier policy table.
pub fn texmod_table() -> &'static Value {
    &SCHEMA.mtl.texture_modifier
}

/// Returns the embedded shader/genmask policy table.
pub fn genmask_table() -> &'static Value {
    &SCHEMA.mtl.shader_policy
}

#[cfg(test)]
mod tests {
    use super::{
        ce_texture_map, genmask_table, supported_rc_source_extensions, texmod_table,
        texture_suffix, SCHEMA_JSON,
    };
    use std::{fs, path::Path};

    #[test]
    fn embedded_schema_matches_repository_snapshot() {
        let workspace_root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("ce-schema must be inside the workspace");
        let repository_schema =
            fs::read_to_string(workspace_root.join("legacy/docs/converter_schema.json"))
                .expect("repository converter schema must be available");

        assert_eq!(SCHEMA_JSON, repository_schema);
    }

    #[test]
    fn texture_suffix_covers_all_pipeline_output_keys() {
        assert_eq!(texture_suffix("diff", false), "_diff");
        assert_eq!(texture_suffix("spec", false), "_spec");
        assert_eq!(texture_suffix("ddna", false), "_ddn");
        assert_eq!(texture_suffix("ddna", true), "_ddna");
        assert_eq!(texture_suffix("ddn", false), "_ddn");
        assert_eq!(texture_suffix("displ", false), "_displ");
        assert_eq!(texture_suffix("em", false), "_em");
        assert_eq!(texture_suffix("emissive", false), "_em");
        assert_eq!(texture_suffix("opacity", false), "_opacity");
        assert_eq!(texture_suffix("roughness", false), "_roughness");
        assert_eq!(texture_suffix("sss", false), "_sss");
    }

    #[test]
    fn texture_map_lookup_exposes_ce_policy_fields() {
        let cases = [
            ("diffuse", "Diffuse", true, "_diff"),
            ("normal", "Bumpmap", true, "_ddn"),
            ("bumpmap", "Bumpmap", true, "_ddn"),
            ("specular", "Specular", true, "_spec"),
            ("displacement", "Heightmap", true, "_displ"),
            ("heightmap", "Heightmap", true, "_displ"),
            ("smoothness", "Smoothness", true, "_ddna"),
            ("opacity", "Opacity", true, ""),
            ("emissive", "Emittance", true, "_em"),
            ("ao", "", false, ""),
        ];

        for (texture_type, ce_map_type, exported, expected_suffix) in cases {
            let policy = ce_texture_map(texture_type).expect("known texture-map policy");
            assert_eq!(policy.ce_map_type, ce_map_type);
            assert_eq!(policy.exported, exported);
            assert_eq!(policy.expected_suffix, expected_suffix);
        }

        let normal = ce_texture_map("normal").expect("normal policy");
        assert_eq!(normal.accepted_suffixes, ["_ddn", "_ddna"]);

        let emissive = ce_texture_map("EMISSIVE").expect("case-insensitive emissive policy");
        assert_eq!(emissive.accepted_suffixes, ["_em", "_emissive"]);
    }

    #[test]
    fn supported_extensions_follow_texture_compiler_table() {
        assert_eq!(supported_rc_source_extensions(), ["dds", "hdr", "tif"]);
    }

    #[test]
    fn texmod_and_genmask_tables_are_available_read_only() {
        let texmod = texmod_table();
        assert_eq!(texmod["attributes"]["TexMod_RotateType"], "0");
        assert_eq!(texmod["attributes"]["TexMod_TexGenType"], "0");
        assert_eq!(texmod["attributes"]["TexMod_bTexGenProjected"], "0");
        assert_eq!(
            texmod["emission_policy"],
            "compatibility_preserved_emits_minimal_texmod"
        );

        let genmask = genmask_table();
        assert_eq!(genmask["empty_material"]["gen_mask"], 32);
        assert_eq!(
            genmask["normal_specular_displacement"]["string_gen_mask"],
            "%NORMAL_MAP%SPECULAR_MAP%SUBSURFACE_SCATTERING"
        );
    }
}
