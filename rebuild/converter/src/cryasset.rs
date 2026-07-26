//! Port of Python `output_formats/mtl_exporter.py:export_mtl_cryasset`.
//!
//! A `.mtl.cryasset` is a small XML sidecar that CryEngine's asset system reads
//! alongside every `.mtl`. It is written right after a successful `.mtl` write so
//! both the CLI `convert` and the GUI emit it.

use std::collections::hash_map::RandomState;
use std::collections::BTreeSet;
use std::ffi::OsString;
use std::fs;
use std::hash::{BuildHasher, Hash, Hasher};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Materials Python skips when counting sub-materials and textures.
const IGNORED_MATERIALS: &[&str] = &["Material", "Dots Stroke"];

/// Engine white placeholders emitted first in `Dependencies`, matching Python.
const ENGINE_TEXTURES: &[&str] = &[
    "%ENGINE%/EngineAssets/Textures/white.dds",
    "%ENGINE%/EngineAssets/Textures/white_ddna.dds",
    "%ENGINE%/EngineAssets/Textures/white_displ.dds",
];

/// Write `<mtl_path>.cryasset` next to a freshly written `.mtl`.
///
/// `materials` is `(material name, texture files already relative to the mtl
/// directory)` — exactly the entries written into each material's `<Textures>`.
pub fn write_cryasset(
    mtl_path: &Path,
    materials: &[(String, Vec<String>)],
) -> Result<PathBuf, String> {
    let mut cryasset = OsString::from(mtl_path);
    cryasset.push(".cryasset");
    let cryasset = PathBuf::from(cryasset);

    let mtl_filename = mtl_path
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_default();

    let xml = build_cryasset_xml(&mtl_filename, materials, &new_guid(), epoch_seconds());
    fs::write(&cryasset, xml)
        .map_err(|error| format!("failed to write {}: {error}", cryasset.display()))?;
    Ok(cryasset)
}

fn build_cryasset_xml(
    mtl_filename: &str,
    materials: &[(String, Vec<String>)],
    guid: &str,
    timestamp: u64,
) -> String {
    let valid: Vec<&(String, Vec<String>)> = materials
        .iter()
        .filter(|(name, _)| !IGNORED_MATERIALS.contains(&name.as_str()))
        .collect();
    let sub_material_count = valid.len();

    // Unique texture paths across valid materials (all extensions count here,
    // matching Python's textureCount; sorted for a stable Dependencies order).
    let mut texture_paths: BTreeSet<&str> = BTreeSet::new();
    for (_, files) in &valid {
        for file in files {
            if !file.is_empty() {
                texture_paths.insert(file.as_str());
            }
        }
    }
    let texture_count = texture_paths.len();

    // Only `.dds` paths become project dependencies (Python's filter), prefixed
    // with `./` unless already relative or an engine path.
    let project_deps: Vec<String> = texture_paths
        .iter()
        .filter(|path| path.to_ascii_lowercase().ends_with(".dds"))
        .map(|path| with_local_prefix(path))
        .collect();

    let mut xml = String::new();
    xml.push_str(&format!(
        "<AssetMetadata version=\"0\" type=\"Material\" guid=\"{}\" timestamp=\"{timestamp}\">\n",
        escape_attr(guid)
    ));
    xml.push_str(" <Files>\n");
    xml.push_str(&format!(
        "  <File path=\"{}\"/>\n",
        escape_attr(mtl_filename)
    ));
    xml.push_str(" </Files>\n");
    xml.push_str(" <Details>\n");
    xml.push_str(&format!(
        "  <Detail name=\"subMaterialCount\">{sub_material_count}</Detail>\n"
    ));
    xml.push_str(&format!(
        "  <Detail name=\"textureCount\">{texture_count}</Detail>\n"
    ));
    xml.push_str(" </Details>\n");
    xml.push_str(" <Dependencies>\n");
    for engine in ENGINE_TEXTURES {
        xml.push_str(&format!("  <Path usageCount=\"1\">{engine}</Path>\n"));
    }
    for dep in &project_deps {
        xml.push_str(&format!(
            "  <Path usageCount=\"1\">{}</Path>\n",
            escape_text(dep)
        ));
    }
    xml.push_str(" </Dependencies>\n");
    xml.push_str("</AssetMetadata>\n");
    xml
}

fn with_local_prefix(path: &str) -> String {
    if path.starts_with("./") || path.starts_with("../") || path.starts_with('%') {
        path.to_owned()
    } else {
        format!("./{path}")
    }
}

fn escape_attr(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn escape_text(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn epoch_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|delta| delta.as_secs())
        .unwrap_or(0)
}

/// A uuid-v4-*shaped* string from std entropy only (no uuid/rand crates).
///
/// Not cryptographic: two independent `RandomState` seeds plus wall-clock nanos
/// give ample entropy for a unique asset guid. Version/variant nibbles are set
/// so the shape matches `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`.
fn new_guid() -> String {
    let mut bytes = [0u8; 16];
    bytes[..8].copy_from_slice(&entropy(0).to_be_bytes());
    bytes[8..].copy_from_slice(&entropy(1).to_be_bytes());
    bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC 4122 variant
    let hex = |slice: &[u8]| {
        slice
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>()
    };
    format!(
        "{}-{}-{}-{}-{}",
        hex(&bytes[0..4]),
        hex(&bytes[4..6]),
        hex(&bytes[6..8]),
        hex(&bytes[8..10]),
        hex(&bytes[10..16]),
    )
}

fn entropy(salt: u64) -> u64 {
    // A fresh RandomState carries a random per-instance seed; two instances plus
    // the timestamp give 64 well-mixed bits per call.
    let mut hasher = RandomState::new().build_hasher();
    salt.hash(&mut hasher);
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|delta| delta.as_nanos())
        .unwrap_or(0)
        .hash(&mut hasher);
    hasher.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn materials() -> Vec<(String, Vec<String>)> {
        vec![
            // Ignored: must not count toward sub-materials or textures.
            ("Material".to_owned(), vec!["./ignored_diff.dds".to_owned()]),
            (
                "Wall".to_owned(),
                vec![
                    "./wall_diff.dds".to_owned(),
                    "./wall_ddna.dds".to_owned(),
                    "./wall_rough.tif".to_owned(), // non-dds: counts, but no dependency
                ],
            ),
            (
                "Rock".to_owned(),
                vec![
                    "./rock_diff.dds".to_owned(),
                    "./wall_diff.dds".to_owned(), // duplicate across materials
                ],
            ),
        ]
    }

    fn dependency_paths(xml: &str) -> Vec<String> {
        xml.lines()
            .filter_map(|line| {
                let line = line.trim();
                line.strip_prefix("<Path usageCount=\"1\">")?
                    .strip_suffix("</Path>")
                    .map(str::to_owned)
            })
            .collect()
    }

    #[test]
    fn counts_exclude_ignored_and_dedup_textures() {
        let xml = build_cryasset_xml("car.mtl", &materials(), "guid", 123);
        assert!(xml.contains("<Detail name=\"subMaterialCount\">2</Detail>"));
        // {wall_diff, wall_ddna, wall_rough.tif, rock_diff} = 4 unique paths.
        assert!(xml.contains("<Detail name=\"textureCount\">4</Detail>"));
    }

    #[test]
    fn engine_deps_first_then_sorted_dds_only() {
        let xml = build_cryasset_xml("car.mtl", &materials(), "guid", 123);
        assert_eq!(
            dependency_paths(&xml),
            vec![
                "%ENGINE%/EngineAssets/Textures/white.dds".to_owned(),
                "%ENGINE%/EngineAssets/Textures/white_ddna.dds".to_owned(),
                "%ENGINE%/EngineAssets/Textures/white_displ.dds".to_owned(),
                "./rock_diff.dds".to_owned(),
                "./wall_ddna.dds".to_owned(),
                "./wall_diff.dds".to_owned(),
            ]
        );
    }

    #[test]
    fn header_and_file_and_root_shape() {
        let xml = build_cryasset_xml("car.mtl", &materials(), "abc", 1_740_928_082);
        assert!(xml.starts_with(
            "<AssetMetadata version=\"0\" type=\"Material\" guid=\"abc\" timestamp=\"1740928082\">\n"
        ));
        assert!(xml.contains("<File path=\"car.mtl\"/>"));
        assert!(xml.trim_end().ends_with("</AssetMetadata>"));
    }

    #[test]
    fn relative_prefix_added_only_when_missing() {
        let mats = vec![(
            "M".to_owned(),
            vec![
                "bare.dds".to_owned(),
                "../up.dds".to_owned(),
                "%ENGINE%/x.dds".to_owned(),
            ],
        )];
        let xml = build_cryasset_xml("m.mtl", &mats, "g", 1);
        let deps = dependency_paths(&xml);
        assert!(deps.contains(&"./bare.dds".to_owned()));
        assert!(deps.contains(&"../up.dds".to_owned()));
        assert!(deps.contains(&"%ENGINE%/x.dds".to_owned()));
    }

    fn is_uuid4_shaped(guid: &str) -> bool {
        let parts: Vec<&str> = guid.split('-').collect();
        if parts.len() != 5 {
            return false;
        }
        for (part, len) in parts.iter().zip([8, 4, 4, 4, 12]) {
            if part.len() != len
                || !part
                    .bytes()
                    .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
            {
                return false;
            }
        }
        parts[2].starts_with('4') && matches!(parts[3].as_bytes()[0], b'8' | b'9' | b'a' | b'b')
    }

    #[test]
    fn guid_has_uuid4_shape_across_many_draws() {
        for _ in 0..256 {
            let guid = new_guid();
            assert!(is_uuid4_shaped(&guid), "bad guid: {guid}");
        }
    }
}
