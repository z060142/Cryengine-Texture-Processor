use std::{
    collections::{BTreeMap, HashMap, HashSet},
    fs,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::{
    error::{Result, TexprocError},
    io::{probe_header, HeaderInfo},
};

const DEFAULT_SUFFIXES: &str = include_str!("../data/suffix_settings.json");
// `hdr`/`exr` are HDR passthrough formats (T-015): accepted by the scanner so
// they never trip DEF-20, then staged straight to RC instead of the TIF pipeline.
const SUPPORTED_EXTENSIONS: &[&str] =
    &["png", "jpg", "jpeg", "tif", "tiff", "exr", "hdr", "tga", "bmp", "webp"];
const SOURCE_TYPES: &[&str] = &[
    "diffuse",
    "normal",
    "specular",
    "glossiness",
    "roughness",
    "displacement",
    "metallic",
    "ao",
    "alpha",
    "emissive",
    "sss",
    "arm",
];
const CE_SUFFIXES: &[(&str, &str)] = &[
    ("diff", "diffuse"),
    ("ddna", "normal"),
    ("ddn", "normal"),
    ("displ", "displacement"),
    ("spec", "specular"),
    ("em", "emissive"),
    ("emissive", "emissive"),
    ("sss", "sss"),
];

#[derive(Clone, Debug)]
pub struct SuffixTable {
    entries: Vec<(String, String)>,
    removable: HashSet<String>,
}

impl SuffixTable {
    pub fn embedded() -> Result<Self> {
        Self::from_json(DEFAULT_SUFFIXES)
    }

    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let text = fs::read_to_string(path.as_ref()).map_err(|error| {
            TexprocError::new(format!(
                "failed to read suffix table {}: {error}",
                path.as_ref().display()
            ))
        })?;
        Self::from_json(&text)
    }

    pub fn from_json(text: &str) -> Result<Self> {
        let value: serde_json::Value = serde_json::from_str(text)
            .map_err(|error| TexprocError::new(format!("invalid suffix JSON: {error}")))?;
        let object = value
            .as_object()
            .ok_or_else(|| TexprocError::new("suffix JSON must be an object"))?;
        let mut entries = Vec::new();
        let mut owners = HashMap::<String, String>::new();
        let mut removable = ["dx", "gl", "directx", "opengl", "2k", "4k", "8k"]
            .into_iter()
            .map(str::to_owned)
            .collect::<HashSet<_>>();

        for (source_type, suffixes) in object {
            if source_type == "removable_suffixes" {
                for suffix in string_array(suffixes, source_type)? {
                    removable.insert(normalize_suffix(suffix));
                }
                continue;
            }
            if !SOURCE_TYPES.contains(&source_type.as_str()) {
                return Err(TexprocError::new(format!(
                    "unknown source type `{source_type}` in suffix table"
                )));
            }
            for raw_suffix in string_array(suffixes, source_type)? {
                let suffix = normalize_suffix(raw_suffix);
                if suffix.is_empty() {
                    return Err(TexprocError::new(format!(
                        "empty suffix for source type `{source_type}`"
                    )));
                }
                if let Some(owner) = owners.get(&suffix) {
                    if owner != source_type {
                        return Err(TexprocError::new(format!(
                            "suffix `{suffix}` is assigned to both `{owner}` and `{source_type}`"
                        )));
                    }
                    continue;
                }
                if let Some((_, ce_type)) = CE_SUFFIXES
                    .iter()
                    .find(|(ce_suffix, _)| *ce_suffix == suffix)
                {
                    if ce_type != source_type {
                        return Err(TexprocError::new(format!(
                            "suffix `{suffix}` conflicts with frozen CE type `{ce_type}`"
                        )));
                    }
                }
                owners.insert(suffix.clone(), source_type.clone());
                entries.push((suffix, source_type.clone()));
            }
        }
        Ok(Self { entries, removable })
    }
}

impl Default for SuffixTable {
    fn default() -> Self {
        Self::embedded().expect("embedded suffix table must be valid")
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Warning,
    Error,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Diagnostic {
    pub severity: Severity,
    pub code: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct HeaderRecord {
    pub channels: u8,
    pub bit_depth: u8,
    pub width: u32,
    pub height: u32,
}

impl From<HeaderInfo> for HeaderRecord {
    fn from(header: HeaderInfo) -> Self {
        Self {
            channels: header.channels,
            bit_depth: header.bit_depth,
            width: header.width,
            height: header.height,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ScanEntry {
    pub path: String,
    pub filename: String,
    pub source_type: String,
    pub base_name: String,
    pub header: Option<HeaderRecord>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arm_order: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ScanGroup {
    pub key: String,
    pub base_name: String,
    pub slots: BTreeMap<String, ScanEntry>,
    pub unknown: Vec<ScanEntry>,
    pub diagnostics: Vec<Diagnostic>,
}

#[derive(Clone, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
pub struct ScanResult {
    pub version: u32,
    pub groups: Vec<ScanGroup>,
    pub diagnostics: Vec<Diagnostic>,
}

impl ScanResult {
    pub fn unknown_only_groups(&self) -> impl Iterator<Item = &ScanGroup> {
        // HDR passthrough entries (`.hdr`/`.exr`, T-015) are unclassified by
        // design but are handled by the process stage, so a group that is only
        // passthrough files must not trip the exit-3 grouping gate.
        self.groups.iter().filter(|group| {
            group.slots.is_empty()
                && group
                    .unknown
                    .iter()
                    .any(|entry| !crate::passthrough::is_passthrough_path(Path::new(&entry.path)))
        })
    }
}

pub fn scan_inputs(inputs: &[PathBuf], suffixes: &SuffixTable) -> Result<ScanResult> {
    let paths = expand_inputs(inputs)?;
    let mut builders = BTreeMap::<String, ScanGroup>::new();
    let mut diagnostics = Vec::new();
    let mut seen = HashSet::new();

    for path in paths {
        let absolute = fs::canonicalize(&path).unwrap_or(path.clone());
        let dedup = absolute.to_string_lossy().to_lowercase();
        if !seen.insert(dedup) {
            diagnostics.push(diagnostic(
                Severity::Warning,
                "DEF-18",
                "duplicate Windows-equivalent path ignored",
                Some(&absolute),
                None,
            ));
            continue;
        }
        let mut entry_diagnostics = Vec::new();
        let entry = classify_path(&absolute, suffixes, &mut entry_diagnostics);
        let key = entry.base_name.to_lowercase();
        let group = builders.entry(key.clone()).or_insert_with(|| ScanGroup {
            key,
            base_name: entry.base_name.clone(),
            slots: BTreeMap::new(),
            unknown: Vec::new(),
            diagnostics: Vec::new(),
        });
        group.diagnostics.extend(entry_diagnostics);

        if entry.source_type == "unknown" {
            group.unknown.push(entry);
            continue;
        }
        if let Some(existing) = group.slots.get(&entry.source_type) {
            let existing_area = area(existing.header.as_ref());
            let incoming_area = area(entry.header.as_ref());
            let winner = if incoming_area >= existing_area {
                "later input"
            } else {
                "existing input"
            };
            group.diagnostics.push(diagnostic(
                Severity::Warning,
                "DEF-19",
                &format!(
                    "slot `{}` conflict: {} px versus {} px; {winner} wins",
                    entry.source_type, incoming_area, existing_area
                ),
                Some(Path::new(&entry.path)),
                Some(&group.base_name),
            ));
            if incoming_area < existing_area {
                continue;
            }
        }
        group.slots.insert(entry.source_type.clone(), entry);
    }
    let groups = builders.into_values().collect::<Vec<_>>();
    for group in &groups {
        diagnostics.extend(group.diagnostics.clone());
    }
    Ok(ScanResult {
        version: 1,
        groups,
        diagnostics,
    })
}

/// Parse a filename down to its group base name using suffix rules only —
/// **no header probe, no image decode**. Mirrors `classify_path`'s base-name
/// derivation (qualifier peeling → ARM alias → CE suffix → ambiguous a/d →
/// configured suffixes → fallback). String ops only, so it is safe to run over
/// every candidate in a directory listing (the Add Related performance red
/// line). The source type is intentionally not resolved here, since that is the
/// only part of classification that needs the header.
pub fn parse_base_name(filename: &str, suffixes: &SuffixTable) -> String {
    let stem = Path::new(filename)
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or(filename);
    let (candidate, _qualifiers) = peel_qualifiers(stem, &suffixes.removable);
    if let Some((base, _alias)) = match_arm_alias(&candidate) {
        return base;
    }
    for (suffix, _source_type) in CE_SUFFIXES {
        if let Some(base) = strip_terminal(&candidate, suffix) {
            return base;
        }
    }
    for ambiguous in ["a", "d"] {
        if let Some(base) = strip_terminal(&candidate, ambiguous) {
            return base;
        }
    }
    for (suffix, _source_type) in &suffixes.entries {
        if matches!(suffix.as_str(), "a" | "d") {
            continue;
        }
        if let Some(base) = strip_terminal(&candidate, suffix) {
            return base;
        }
    }
    candidate
}

fn classify_path(
    path: &Path,
    suffixes: &SuffixTable,
    diagnostics: &mut Vec<Diagnostic>,
) -> ScanEntry {
    let filename = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or_default()
        .to_owned();
    let raw_stem = path
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or(&filename);
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_lowercase();

    if !SUPPORTED_EXTENSIONS.contains(&extension.as_str()) {
        diagnostics.push(diagnostic(
            Severity::Error,
            "DEF-20",
            &format!("unsupported decoder extension `.{extension}`"),
            Some(path),
            None,
        ));
        return unknown_entry(path, &filename, raw_stem, None);
    }

    // T-015: `.hdr`/`.exr` are HDR passthrough formats. Branch on extension
    // *before* any header probe or type classification: they carry no type
    // suffix (env maps), Radiance HDR is not a probe-able format here, and the
    // owner's ruling routes every `.exr` to RC rather than the TIF pipeline
    // regardless of suffix. They land as `unknown` and the process stage stages
    // them to RC (see `passthrough` / `batch::process_scan_group`).
    if crate::passthrough::is_passthrough_ext(&extension) {
        return unknown_entry(path, &filename, raw_stem, None);
    }

    let header = match probe_header(path) {
        Ok(header) => Some(HeaderRecord::from(header)),
        Err(error) => {
            diagnostics.push(diagnostic(
                Severity::Error,
                "DEF-20",
                &format!("header probe failed: {error}"),
                Some(path),
                None,
            ));
            return unknown_entry(path, &filename, raw_stem, None);
        }
    };
    let (candidate, _qualifiers) = peel_qualifiers(raw_stem, &suffixes.removable);

    if let Some((base, alias)) = match_arm_alias(&candidate) {
        let (arm_order, ambiguous) = match alias.as_str() {
            "arm"
            | "occlusion-roughness-metallic"
            | "occlusion_roughness_metallic"
            | "ao-rough-metal"
            | "ao_rough_metal" => (Some("ARM".to_owned()), false),
            "orm" => (Some("ORM".to_owned()), false),
            "rma" => (Some("RMA".to_owned()), false),
            "rm" | "ra" => (Some("configured".to_owned()), true),
            _ => unreachable!(),
        };
        if ambiguous {
            diagnostics.push(diagnostic(
                Severity::Warning,
                "DEF-16",
                &format!("ambiguous ARM alias `_{alias}` uses configured arm_order"),
                Some(path),
                Some(&base),
            ));
        }
        return entry(path, &filename, "arm", &base, header, arm_order);
    }

    for (suffix, source_type) in CE_SUFFIXES {
        if let Some(base) = strip_terminal(&candidate, suffix) {
            return entry(path, &filename, source_type, &base, header, None);
        }
    }
    for ambiguous in ["a", "d"] {
        if let Some(base) = strip_terminal(&candidate, ambiguous) {
            let source_type = match (ambiguous, header.as_ref().map(|value| value.channels)) {
                (_, Some(3 | 4)) => "diffuse",
                ("a", Some(1 | 2)) => "alpha",
                ("d", Some(1 | 2)) => "displacement",
                _ => "unknown",
            };
            if source_type == "unknown" {
                diagnostics.push(diagnostic(
                    Severity::Error,
                    "DEF-14",
                    "ambiguous single-letter suffix could not be resolved from header channels",
                    Some(path),
                    Some(&base),
                ));
            }
            return entry(path, &filename, source_type, &base, header, None);
        }
    }
    for (suffix, source_type) in &suffixes.entries {
        if matches!(suffix.as_str(), "a" | "d") {
            continue;
        }
        if let Some(base) = strip_terminal(&candidate, suffix) {
            return entry(path, &filename, source_type, &base, header, None);
        }
    }

    diagnostics.push(diagnostic(
        Severity::Warning,
        "DEF-17",
        "no deterministic filename suffix matched; pixel guessing is disabled",
        Some(path),
        None,
    ));
    unknown_entry(path, &filename, &candidate, header)
}

fn expand_inputs(inputs: &[PathBuf]) -> Result<Vec<PathBuf>> {
    let mut output = Vec::new();
    for input in inputs {
        if input.is_file() {
            output.push(input.clone());
        } else if input.is_dir() {
            visit_directory(input, &mut output)?;
        } else {
            return Err(TexprocError::new(format!(
                "input does not exist: {}",
                input.display()
            )));
        }
    }
    output.sort_by_key(|path| path.to_string_lossy().to_lowercase());
    Ok(output)
}

fn visit_directory(directory: &Path, output: &mut Vec<PathBuf>) -> Result<()> {
    let mut entries = fs::read_dir(directory)?.collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name().to_string_lossy().to_lowercase());
    for entry in entries {
        let path = entry.path();
        if path.is_dir() {
            visit_directory(&path, output)?;
        } else if path.is_file() {
            output.push(path);
        }
    }
    Ok(())
}

fn peel_qualifiers(stem: &str, removable: &HashSet<String>) -> (String, Vec<String>) {
    let mut value = stem.to_owned();
    let mut removed = Vec::new();
    loop {
        let Some((prefix, token)) = value.rsplit_once(['_', '-']) else {
            break;
        };
        let token_lower = token.to_lowercase();
        let resolution = token_lower
            .strip_suffix('k')
            .is_some_and(|digits| !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit()));
        if !resolution && !removable.contains(&token_lower) {
            break;
        }
        removed.push(token_lower);
        value = prefix.to_owned();
    }
    (value, removed)
}

fn match_arm_alias(stem: &str) -> Option<(String, String)> {
    for alias in [
        "occlusion-roughness-metallic",
        "occlusion_roughness_metallic",
        "ao-rough-metal",
        "ao_rough_metal",
        "arm",
        "orm",
        "rma",
        "rm",
        "ra",
    ] {
        if let Some(base) = strip_terminal(stem, alias) {
            return Some((base, alias.to_owned()));
        }
    }
    None
}

fn strip_terminal(stem: &str, suffix: &str) -> Option<String> {
    if stem.eq_ignore_ascii_case(suffix) {
        return Some(stem.to_owned());
    }
    let prefix = stem.get(..stem.len().checked_sub(suffix.len())?)?;
    let tail = stem.get(stem.len() - suffix.len()..)?;
    if tail.eq_ignore_ascii_case(suffix) && (prefix.ends_with('_') || prefix.ends_with('-')) {
        Some(prefix.trim_end_matches(['_', '-']).to_owned())
    } else {
        None
    }
}

fn normalize_suffix(value: &str) -> String {
    value.trim().trim_start_matches(['_', '-']).to_lowercase()
}

fn string_array<'a>(value: &'a serde_json::Value, key: &str) -> Result<Vec<&'a str>> {
    value
        .as_array()
        .ok_or_else(|| TexprocError::new(format!("suffix key `{key}` must be an array")))?
        .iter()
        .map(|value| {
            value.as_str().ok_or_else(|| {
                TexprocError::new(format!("suffix key `{key}` must contain strings"))
            })
        })
        .collect()
}

fn entry(
    path: &Path,
    filename: &str,
    source_type: &str,
    base_name: &str,
    header: Option<HeaderRecord>,
    arm_order: Option<String>,
) -> ScanEntry {
    ScanEntry {
        path: path.to_string_lossy().into_owned(),
        filename: filename.to_owned(),
        source_type: source_type.to_owned(),
        base_name: base_name.to_owned(),
        header,
        arm_order,
    }
}

fn unknown_entry(
    path: &Path,
    filename: &str,
    base_name: &str,
    header: Option<HeaderRecord>,
) -> ScanEntry {
    entry(path, filename, "unknown", base_name, header, None)
}

fn area(header: Option<&HeaderRecord>) -> u64 {
    header.map_or(0, |header| {
        u64::from(header.width) * u64::from(header.height)
    })
}

fn diagnostic(
    severity: Severity,
    code: &str,
    message: &str,
    path: Option<&Path>,
    group: Option<&str>,
) -> Diagnostic {
    Diagnostic {
        severity,
        code: code.to_owned(),
        message: message.to_owned(),
        path: path.map(|path| path.to_string_lossy().into_owned()),
        group: group.map(str::to_owned),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suffix_normalization_and_conflicts_are_deterministic() {
        let table = SuffixTable::from_json(
            r#"{"normal":["_n","normal"],"roughness":["_r"],"removable_suffixes":["gl"]}"#,
        )
        .unwrap();
        assert!(table
            .entries
            .contains(&("n".to_owned(), "normal".to_owned())));
        assert!(table.removable.contains("directx"));
        assert!(SuffixTable::from_json(r#"{"normal":["x"],"roughness":["_x"]}"#).is_err());
    }

    #[test]
    fn terminal_cleanup_does_not_remove_internal_tokens() {
        let removable = ["dx", "gl"].into_iter().map(str::to_owned).collect();
        assert_eq!(
            peel_qualifiers("stone_normal_dx", &removable).0,
            "stone_normal"
        );
        assert_eq!(
            peel_qualifiers("dx_stone_normal", &removable).0,
            "dx_stone_normal"
        );
        assert_eq!(
            strip_terminal("normal_wall_normal", "normal"),
            Some("normal_wall".to_owned())
        );
    }

    #[test]
    fn parse_base_name_is_header_free_and_matches_grouping() {
        let table = SuffixTable::embedded().unwrap();
        // Configured suffix (basecolor → diffuse) and a plain map suffix.
        assert_eq!(
            parse_base_name("KB3D_ENC_AtlasA_basecolor.png", &table),
            "KB3D_ENC_AtlasA"
        );
        assert_eq!(
            parse_base_name("KB3D_ENC_AtlasA_normal.png", &table),
            "KB3D_ENC_AtlasA"
        );
        // Trailing resolution qualifier is peeled before the suffix is matched.
        assert_eq!(parse_base_name("Wall_roughness_4k.png", &table), "Wall");
        // ARM alias collapses to the base.
        assert_eq!(parse_base_name("Crate_orm.png", &table), "Crate");
        // Ambiguous single-letter suffix strips regardless of header.
        assert_eq!(parse_base_name("Panel_d.png", &table), "Panel");
        // No recognized suffix → the peeled stem is the base.
        assert_eq!(
            parse_base_name("loose_texture.png", &table),
            "loose_texture"
        );
    }

    #[test]
    fn arm_aliases_encode_order_and_ambiguity() {
        assert_eq!(
            match_arm_alias("packed_orm"),
            Some(("packed".to_owned(), "orm".to_owned()))
        );
        assert_eq!(
            match_arm_alias("packed_rm"),
            Some(("packed".to_owned(), "rm".to_owned()))
        );
        assert_eq!(
            match_arm_alias("packed_occlusion-roughness-metallic"),
            Some((
                "packed".to_owned(),
                "occlusion-roughness-metallic".to_owned()
            ))
        );
    }
}
