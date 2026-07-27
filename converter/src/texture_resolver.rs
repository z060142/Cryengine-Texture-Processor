use crate::model::MaterialRecord;
use std::fs;
use std::path::{Component, Path, PathBuf};

const KNOWN_TEXTURE_SUFFIXES: &[&str] = &[
    "_basecolor",
    "_albedo",
    "_diffuse",
    "_diff",
    "_color",
    "_col",
    "_a",
    "_d",
    "_ddna",
    "_ddn",
    "_normal",
    "_norm",
    "_nrm",
    "_nor_dx",
    "_nor_gl",
    "_nor",
    "_n",
    "_specular",
    "_spec",
    "_refl",
    "_s",
    "_displacement",
    "_displ",
    "_height",
    "_disp",
    "_bump",
    "_h",
    "_emissive",
    "_emission",
    "_glow",
    "_em",
    "_e",
    "_opacity",
    "_alpha",
    "_transparency",
    "_mask",
    "_ao",
    "_ambient",
    "_occlusion",
    "_roughness",
    "_rough",
    "_r",
    "_glossiness",
    "_glossy",
    "_gloss",
    "_g",
    "_smoothness",
    "_metalness",
    "_metallic",
    "_metal",
    "_m",
    "_sss",
    "_subsurface",
];

const OUTPUT_EXTENSIONS: &[&str] = &["dds", "hdr", "tif"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedTexture {
    pub texture_type: String,
    pub ce_map: String,
    pub path: PathBuf,
    pub mtl_file: String,
}

struct OutputRule {
    texture_type: &'static str,
    output_keys: &'static [(&'static str, bool)],
    explicit_suffix: Option<&'static str>,
    ce_map_alias: Option<&'static str>,
}

const OUTPUT_RULES: &[OutputRule] = &[
    OutputRule {
        texture_type: "diffuse",
        output_keys: &[("diff", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "normal",
        output_keys: &[("ddna", true), ("ddna", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "specular",
        output_keys: &[("spec", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "displacement",
        output_keys: &[("displ", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "emissive",
        output_keys: &[("emissive", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "opacity",
        output_keys: &[],
        explicit_suffix: Some("_opacity"),
        ce_map_alias: None,
    },
    OutputRule {
        texture_type: "roughness",
        output_keys: &[],
        explicit_suffix: Some("_roughness"),
        ce_map_alias: Some("Opacity"),
    },
    OutputRule {
        texture_type: "subsurface",
        output_keys: &[("sss", false)],
        explicit_suffix: None,
        ce_map_alias: None,
    },
];

pub fn strip_known_texture_suffix(stem: &str) -> &str {
    let lower = stem.to_ascii_lowercase();
    for suffix in KNOWN_TEXTURE_SUFFIXES {
        if lower.ends_with(suffix) {
            return &stem[..stem.len() - suffix.len()];
        }
    }
    stem
}

pub fn resolve_base_name(material: &MaterialRecord) -> Option<String> {
    material.textures.iter().find_map(|texture| {
        let path = [
            texture.relative_filename.as_str(),
            texture.filename.as_str(),
            texture.absolute_filename.as_str(),
        ]
        .into_iter()
        .find(|value| !value.trim().is_empty())?;
        let filename = path.rsplit(['\\', '/']).next().unwrap_or(path);
        let stem = filename.rsplit_once('.').map_or(filename, |(stem, _)| stem);
        let base_name = strip_known_texture_suffix(stem);
        (!base_name.is_empty()).then(|| base_name.to_owned())
    })
}

pub fn resolve_material_textures(
    material: &MaterialRecord,
    texture_dir: &Path,
    mtl_dir: &Path,
) -> Vec<ResolvedTexture> {
    let Some(base_name) = resolve_base_name(material) else {
        return Vec::new();
    };

    OUTPUT_RULES
        .iter()
        .filter_map(|rule| {
            let suffixes: Vec<_> = rule.explicit_suffix.map_or_else(
                || {
                    rule.output_keys
                        .iter()
                        .map(|(key, normal_alpha)| {
                            ce_schema::texture_suffix(key, *normal_alpha).to_owned()
                        })
                        .collect()
                },
                |suffix| vec![suffix.to_owned()],
            );
            let path = find_processed_texture(texture_dir, &base_name, &suffixes)?;
            let ce_map = rule.ce_map_alias.map(str::to_owned).or_else(|| {
                ce_schema::ce_texture_map(rule.texture_type)
                    .filter(|policy| policy.exported)
                    .map(|policy| policy.ce_map_type.clone())
            })?;
            Some(ResolvedTexture {
                texture_type: rule.texture_type.to_owned(),
                ce_map,
                mtl_file: relative_mtl_path(&path, mtl_dir),
                path,
            })
        })
        .collect()
}

fn find_processed_texture(
    texture_dir: &Path,
    base_name: &str,
    suffixes: &[String],
) -> Option<PathBuf> {
    for extension in OUTPUT_EXTENSIONS {
        for suffix in suffixes {
            let filename = format!("{base_name}{suffix}.{extension}");
            if let Some(path) = find_case_preserved_file(texture_dir, &filename) {
                return Some(path);
            }
        }
    }
    None
}

fn find_case_preserved_file(directory: &Path, filename: &str) -> Option<PathBuf> {
    fs::read_dir(directory)
        .ok()?
        .filter_map(Result::ok)
        .find(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .eq_ignore_ascii_case(filename)
                && entry.path().is_file()
        })
        .map(|entry| entry.path())
}

pub fn relative_mtl_path(target: &Path, start_dir: &Path) -> String {
    let target_text = target.to_string_lossy();
    if target_text.starts_with('%') {
        return target_text.replace('\\', "/");
    }
    if !target.is_absolute() {
        return with_local_prefix(target_text.replace('\\', "/"));
    }

    let target_components: Vec<_> = target.components().collect();
    let start_components: Vec<_> = start_dir.components().collect();
    let common = target_components
        .iter()
        .zip(&start_components)
        .take_while(|(left, right)| component_eq(left, right))
        .count();
    if common == 0 {
        return target_text.replace('\\', "/");
    }

    let mut parts = Vec::new();
    for component in &start_components[common..] {
        if matches!(component, Component::Normal(_)) {
            parts.push("..".to_owned());
        }
    }
    for component in &target_components[common..] {
        if let Component::Normal(value) = component {
            parts.push(value.to_string_lossy().into_owned());
        }
    }
    with_local_prefix(parts.join("/"))
}

fn component_eq(left: &Component<'_>, right: &Component<'_>) -> bool {
    left.as_os_str()
        .to_string_lossy()
        .eq_ignore_ascii_case(&right.as_os_str().to_string_lossy())
}

fn with_local_prefix(path: String) -> String {
    if path.is_empty()
        || path.starts_with("../")
        || path.starts_with('/')
        || path.starts_with('.')
        || path.starts_with('%')
    {
        path
    } else {
        format!("./{path}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::TextureRef;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn texture_ref(filename: &str) -> TextureRef {
        TextureRef {
            material_prop: String::new(),
            shader_prop: String::new(),
            filename: filename.to_owned(),
            absolute_filename: String::new(),
            relative_filename: filename.to_owned(),
            embedded: false,
            content_size: 0,
            content: Vec::new(),
        }
    }

    fn material(filenames: &[&str]) -> MaterialRecord {
        MaterialRecord {
            name: "Wall".to_owned(),
            typed_id: 0,
            element_id: 0,
            textures: filenames
                .iter()
                .map(|filename| texture_ref(filename))
                .collect(),
        }
    }

    fn temp_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("converter-texture-resolver-{label}-{unique}"));
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn known_suffixes_include_ddn_alias_and_source_names() {
        assert_eq!(strip_known_texture_suffix("wall_diff"), "wall");
        assert_eq!(strip_known_texture_suffix("wall_ddna"), "wall");
        assert_eq!(strip_known_texture_suffix("wall_ddn"), "wall");
        assert_eq!(strip_known_texture_suffix("wall_basecolor"), "wall");
        assert_eq!(strip_known_texture_suffix("wall_roughness"), "wall");
        assert_eq!(strip_known_texture_suffix("wall"), "wall");
    }

    #[test]
    fn multiple_refs_use_first_filename_as_base_name_fallback() {
        let material = material(&["Stone_basecolor.png", "Ignored_normal.png"]);
        assert_eq!(resolve_base_name(&material).as_deref(), Some("Stone"));
    }

    #[test]
    fn ddna_is_preferred_but_ddn_is_accepted() {
        let root = temp_dir("ddn");
        let texture_dir = root.join("textures");
        let mtl_dir = root.join("models");
        fs::create_dir_all(&texture_dir).unwrap();
        fs::create_dir_all(&mtl_dir).unwrap();
        fs::write(texture_dir.join("wall_ddn.tif"), b"ddn").unwrap();

        let material = material(&["wall_normal.png"]);
        let ddn = resolve_material_textures(&material, &texture_dir, &mtl_dir);
        assert_eq!(ddn[0].ce_map, "Bumpmap");
        assert_eq!(ddn[0].path.file_name().unwrap(), "wall_ddn.tif");

        fs::write(texture_dir.join("wall_ddna.tif"), b"ddna").unwrap();
        let ddna = resolve_material_textures(&material, &texture_dir, &mtl_dir);
        assert_eq!(ddna[0].path.file_name().unwrap(), "wall_ddna.tif");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn output_paths_are_relative_to_mtl_directory() {
        let root = temp_dir("relative");
        let texture_dir = root.join("example").join("car");
        let mtl_dir = root.join("phase").join("rc_work");
        fs::create_dir_all(&texture_dir).unwrap();
        fs::create_dir_all(&mtl_dir).unwrap();
        let target = texture_dir.join("wall_diff.dds");
        fs::write(&target, b"diff").unwrap();

        assert_eq!(
            relative_mtl_path(&target, &mtl_dir),
            "../../example/car/wall_diff.dds"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn roughness_uses_observed_opacity_alias_and_preserves_real_case() {
        let root = temp_dir("roughness");
        fs::write(root.join("wall_Roughness.tif"), b"roughness").unwrap();
        let material = material(&["wall_basecolor.png"]);
        let textures = resolve_material_textures(&material, &root, &root);
        let roughness = textures
            .iter()
            .find(|texture| texture.texture_type == "roughness")
            .unwrap();
        assert_eq!(roughness.ce_map, "Opacity");
        assert_eq!(roughness.mtl_file, "./wall_Roughness.tif");
        fs::remove_dir_all(root).unwrap();
    }
}
