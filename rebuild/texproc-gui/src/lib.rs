use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};

use texproc::{parse_base_name, ScanEntry, ScanResult, Severity, SuffixTable};

/// Image extensions the scanner accepts — mirrors texproc's supported set. Used
/// to skip non-image files in a directory listing without touching the file.
const RELATED_IMAGE_EXTENSIONS: [&str; 6] = ["png", "jpg", "jpeg", "tif", "tiff", "exr"];

/// Reduce a texture selection to the unique `(directory, lowercase base-name)`
/// pairs whose siblings we want to pull in. Base names come from texproc's
/// filename-only parser — **no image is opened**. This is the "one listing per
/// directory" guarantee for Add Related: each returned directory is scanned once.
pub fn related_wanted_bases(
    selected: &[PathBuf],
    suffixes: &SuffixTable,
) -> BTreeMap<PathBuf, BTreeSet<String>> {
    let mut wanted: BTreeMap<PathBuf, BTreeSet<String>> = BTreeMap::new();
    for path in selected {
        let (Some(directory), Some(filename)) = (
            path.parent(),
            path.file_name().and_then(|name| name.to_str()),
        ) else {
            continue;
        };
        let base = parse_base_name(filename, suffixes).to_lowercase();
        wanted
            .entry(directory.to_path_buf())
            .or_default()
            .insert(base);
    }
    wanted
}

/// From one directory's raw filenames, pick the image files whose parsed base
/// name matches a wanted base and that are not already imported. Pure string
/// work — filenames only, no filesystem, no decode, no header probe — so it
/// stays O(listing) regardless of selection size. `already` holds lowercased
/// absolute paths of the current import set.
pub fn related_matches_in_dir(
    directory: &Path,
    filenames: &[String],
    wanted_bases: &BTreeSet<String>,
    already: &BTreeSet<String>,
    suffixes: &SuffixTable,
) -> Vec<PathBuf> {
    let mut matches = Vec::new();
    for filename in filenames {
        if !is_related_image(filename) {
            continue;
        }
        let base = parse_base_name(filename, suffixes).to_lowercase();
        if !wanted_bases.contains(&base) {
            continue;
        }
        let full = directory.join(filename);
        if already.contains(&full.to_string_lossy().to_lowercase()) {
            continue;
        }
        matches.push(full);
    }
    matches
}

fn is_related_image(filename: &str) -> bool {
    Path::new(filename)
        .extension()
        .and_then(|value| value.to_str())
        .is_some_and(|extension| {
            RELATED_IMAGE_EXTENSIONS
                .iter()
                .any(|candidate| extension.eq_ignore_ascii_case(candidate))
        })
}

/// Signed axis tokens for the Conversion Settings Forward/Up dropdowns, in the
/// `<sign><axis>` shape RC uses in `forward_up_axes`.
pub const AXIS_TOKENS: [&str; 6] = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"];

/// Join a Forward and an Up axis token into an RC `forward_up_axes` string
/// (`<forward><up>`, e.g. `"-Z"` + `"+Y"` → `"-Z+Y"`).
pub fn compose_forward_up(forward: &str, up: &str) -> String {
    format!("{forward}{up}")
}

/// Split an RC `forward_up_axes` string back into `(forward, up)` tokens.
/// Returns `None` unless it is exactly two `<sign><axis>` tokens.
pub fn parse_forward_up(value: &str) -> Option<(String, String)> {
    if value.len() != 4 {
        return None;
    }
    let (forward, up) = value.split_at(2);
    (AXIS_TOKENS.contains(&forward) && AXIS_TOKENS.contains(&up))
        .then(|| (forward.to_owned(), up.to_owned()))
}

/// A Forward/Up combination is illegal when both name the same axis (parallel),
/// regardless of sign — RC cannot build a basis from it. The last char is the
/// axis letter (`X`/`Y`/`Z`).
pub fn axes_parallel(forward: &str, up: &str) -> bool {
    forward.chars().last() == up.chars().last()
}

pub const ASSIGNABLE_SOURCE_TYPES: [&str; 12] = [
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

#[derive(Clone, Debug)]
pub struct ReviewDocument {
    path: PathBuf,
    scan: ScanResult,
    dirty: bool,
}

impl ReviewDocument {
    pub fn load(path: &Path) -> Result<Self, String> {
        let text = fs::read_to_string(path)
            .map_err(|error| format!("failed to read {}: {error}", path.display()))?;
        let scan: ScanResult = serde_json::from_str(&text)
            .map_err(|error| format!("invalid groups JSON {}: {error}", path.display()))?;
        Self::from_scan(path.to_owned(), scan)
    }

    pub fn from_scan(path: PathBuf, scan: ScanResult) -> Result<Self, String> {
        if scan.version != 1 {
            return Err(format!(
                "unsupported groups JSON version {}; expected 1",
                scan.version
            ));
        }
        for group in &scan.groups {
            for source_type in group.slots.keys() {
                if !ASSIGNABLE_SOURCE_TYPES.contains(&source_type.as_str()) {
                    return Err(format!(
                        "group `{}` contains unsupported source type `{source_type}`",
                        group.base_name
                    ));
                }
            }
        }
        Ok(Self {
            path,
            scan,
            dirty: false,
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn scan(&self) -> &ScanResult {
        &self.scan
    }

    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    pub fn unresolved_unknown_count(&self) -> usize {
        self.scan
            .groups
            .iter()
            .map(|group| group.unknown.len())
            .sum()
    }

    pub fn conflict_warning_count(&self) -> usize {
        self.scan
            .groups
            .iter()
            .flat_map(|group| &group.diagnostics)
            .filter(|diagnostic| {
                diagnostic.severity == Severity::Warning && diagnostic.code == "DEF-19"
            })
            .count()
    }

    pub fn target_occupant(&self, group_index: usize, source_type: &str) -> Option<&ScanEntry> {
        self.scan.groups.get(group_index)?.slots.get(source_type)
    }

    pub fn assign_unknown(
        &mut self,
        group_index: usize,
        unknown_index: usize,
        source_type: &str,
    ) -> Result<(), String> {
        if !ASSIGNABLE_SOURCE_TYPES.contains(&source_type) {
            return Err(format!("unsupported source type `{source_type}`"));
        }
        let group = self
            .scan
            .groups
            .get_mut(group_index)
            .ok_or_else(|| format!("group index {group_index} is out of range"))?;
        if let Some(existing) = group.slots.get(source_type) {
            return Err(format!(
                "DEF-19 conflict: `{source_type}` is already occupied by {}",
                existing.filename
            ));
        }
        if unknown_index >= group.unknown.len() {
            return Err(format!(
                "unknown index {unknown_index} is out of range for group `{}`",
                group.base_name
            ));
        }
        let mut entry = group.unknown.remove(unknown_index);
        entry.source_type = source_type.to_owned();
        group.slots.insert(source_type.to_owned(), entry);
        self.dirty = true;
        Ok(())
    }

    pub fn save(&mut self) -> Result<(), String> {
        let json = serde_json::to_string_pretty(&self.scan)
            .map_err(|error| format!("failed to serialize groups JSON: {error}"))?;
        fs::write(&self.path, format!("{json}\n"))
            .map_err(|error| format!("failed to write {}: {error}", self.path.display()))?;
        self.dirty = false;
        Ok(())
    }

    pub fn save_as(&mut self, path: PathBuf) -> Result<(), String> {
        self.path = path;
        self.save()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        collections::BTreeMap,
        time::{SystemTime, UNIX_EPOCH},
    };
    use texproc::{Diagnostic, ScanGroup};

    fn entry(filename: &str, source_type: &str) -> ScanEntry {
        ScanEntry {
            path: format!("C:\\textures\\{filename}"),
            filename: filename.to_owned(),
            source_type: source_type.to_owned(),
            base_name: "Stone".to_owned(),
            header: None,
            arm_order: None,
        }
    }

    fn scan() -> ScanResult {
        let mut slots = BTreeMap::new();
        slots.insert("normal".to_owned(), entry("Stone_normal.png", "normal"));
        ScanResult {
            version: 1,
            groups: vec![ScanGroup {
                key: "stone".to_owned(),
                base_name: "Stone".to_owned(),
                slots,
                unknown: vec![
                    entry("Stone_refraction.png", "unknown"),
                    entry("Stone_extra.png", "unknown"),
                ],
                diagnostics: vec![Diagnostic {
                    severity: Severity::Warning,
                    code: "DEF-19".to_owned(),
                    message: "existing conflict".to_owned(),
                    path: None,
                    group: Some("Stone".to_owned()),
                }],
            }],
            diagnostics: Vec::new(),
        }
    }

    fn temp_file(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!(
            "texproc-gui-{label}-{}-{nonce}.json",
            std::process::id()
        ))
    }

    #[test]
    fn assignment_moves_unknown_into_a_process_slot() {
        let mut document = ReviewDocument::from_scan(PathBuf::from("groups.json"), scan()).unwrap();
        document.assign_unknown(0, 0, "glossiness").unwrap();

        assert_eq!(document.unresolved_unknown_count(), 1);
        assert!(document.is_dirty());
        let assigned = &document.scan().groups[0].slots["glossiness"];
        assert_eq!(assigned.filename, "Stone_refraction.png");
        assert_eq!(assigned.source_type, "glossiness");
    }

    #[test]
    fn assigning_every_unknown_clears_the_diagnostics_count() {
        let mut document = ReviewDocument::from_scan(PathBuf::from("groups.json"), scan()).unwrap();
        assert_eq!(document.unresolved_unknown_count(), 2);

        document.assign_unknown(0, 0, "glossiness").unwrap();
        assert_eq!(document.unresolved_unknown_count(), 1);
        document.assign_unknown(0, 0, "roughness").unwrap();
        assert_eq!(document.unresolved_unknown_count(), 0);
    }

    #[test]
    fn occupied_target_reports_def19_without_mutating_the_group() {
        let mut document = ReviewDocument::from_scan(PathBuf::from("groups.json"), scan()).unwrap();
        let error = document.assign_unknown(0, 0, "normal").unwrap_err();

        assert!(error.contains("DEF-19 conflict"));
        assert_eq!(document.unresolved_unknown_count(), 2);
        assert!(!document.is_dirty());
        assert_eq!(document.conflict_warning_count(), 1);
    }

    #[test]
    fn save_round_trip_remains_scanresult_compatible() {
        let path = temp_file("round-trip");
        let mut document = ReviewDocument::from_scan(path.clone(), scan()).unwrap();
        document.assign_unknown(0, 0, "roughness").unwrap();
        document.save().unwrap();

        let saved: ScanResult = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert!(saved.groups[0].slots.contains_key("roughness"));
        assert_eq!(saved.groups[0].unknown.len(), 1);
        assert!(!document.is_dirty());
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn related_bases_dedup_pairs_across_a_selection() {
        let table = SuffixTable::embedded().unwrap();
        // Two different maps of the same group in one dir + a second group in
        // another dir → two unique (dir, base) pairs, one base each.
        let selected = vec![
            PathBuf::from(r"Z:\tex\4k\KB3D_ENC_AtlasA_basecolor.png"),
            PathBuf::from(r"Z:\tex\4k\KB3D_ENC_AtlasA_normal.png"),
            PathBuf::from(r"Z:\tex\props\Crate_orm.png"),
        ];
        let wanted = related_wanted_bases(&selected, &table);
        assert_eq!(wanted.len(), 2, "two directories");
        assert_eq!(
            wanted[Path::new(r"Z:\tex\4k")],
            BTreeSet::from(["kb3d_enc_atlasa".to_owned()]),
            "both selected files collapse to one base"
        );
        assert_eq!(
            wanted[Path::new(r"Z:\tex\props")],
            BTreeSet::from(["crate".to_owned()])
        );
    }

    /// Performance red-line evidence for Add Related on the real KB3D 4k set:
    /// import only `KB3D_ENC_AtlasA_basecolor.png`, then match siblings via a
    /// single directory listing of ~793 entries — no image decode. Ignored by
    /// default (needs Z:); run with:
    ///   cargo test -p texproc-gui -- --ignored --nocapture add_related_timing
    #[test]
    #[ignore = "requires the real Z:\\enchanted\\KB3DTextures\\4k dataset"]
    fn add_related_timing_on_real_kb3d_directory() {
        use std::time::Instant;

        let dir = Path::new(r"Z:\enchanted\KB3DTextures\4k");
        let selected = vec![dir.join("KB3D_ENC_AtlasA_basecolor.png")];
        assert!(
            selected[0].is_file(),
            "dataset not present at {}",
            dir.display()
        );
        let table = SuffixTable::embedded().unwrap();
        let already = selected
            .iter()
            .map(|path| path.to_string_lossy().to_lowercase())
            .collect::<BTreeSet<_>>();

        let started = Instant::now();
        let wanted = related_wanted_bases(&selected, &table);
        let mut added = Vec::new();
        let mut dirs_scanned = 0;
        let mut listing_entries = 0;
        for (directory, bases) in &wanted {
            let entries = std::fs::read_dir(directory).unwrap();
            dirs_scanned += 1;
            let filenames = entries
                .filter_map(|entry| entry.ok())
                .filter_map(|entry| entry.file_name().to_str().map(str::to_owned))
                .collect::<Vec<_>>();
            listing_entries += filenames.len();
            added.extend(related_matches_in_dir(
                directory, &filenames, bases, &already, &table,
            ));
        }
        let elapsed = started.elapsed();

        let names = added
            .iter()
            .filter_map(|path| path.file_name().and_then(|name| name.to_str()))
            .collect::<Vec<_>>();
        eprintln!(
            "Add Related: {} files added, {dirs_scanned} dir(s), {listing_entries} entries listed, {:.1} ms",
            added.len(),
            elapsed.as_secs_f64() * 1000.0
        );
        eprintln!("added = {names:?}");
        assert_eq!(added.len(), 6, "expected the 6 AtlasA siblings: {names:?}");
        assert!(
            names.iter().all(|name| !name.contains("SignAtlasA")),
            "must not pull the distinct SignAtlasA group: {names:?}"
        );
        assert!(
            elapsed.as_secs_f64() < 1.0,
            "Add Related must stay well under a second (was {elapsed:?})"
        );
    }

    #[test]
    fn related_matches_base_and_skips_imported_and_non_images() {
        let table = SuffixTable::embedded().unwrap();
        let dir = Path::new(r"Z:\tex\4k");
        let wanted = BTreeSet::from(["kb3d_enc_atlasa".to_owned()]);
        // basecolor is already imported → excluded; readme.txt is not an image;
        // OtherGroup does not match the wanted base.
        let already = BTreeSet::from([r"z:\tex\4k\kb3d_enc_atlasa_basecolor.png".to_owned()]);
        let filenames = vec![
            "KB3D_ENC_AtlasA_basecolor.png".to_owned(),
            "KB3D_ENC_AtlasA_normal.png".to_owned(),
            "KB3D_ENC_AtlasA_roughness.png".to_owned(),
            "KB3D_ENC_OtherGroup_normal.png".to_owned(),
            "readme.txt".to_owned(),
        ];
        let matches = related_matches_in_dir(dir, &filenames, &wanted, &already, &table);
        let names = matches
            .iter()
            .filter_map(|path| path.file_name().and_then(|name| name.to_str()))
            .collect::<Vec<_>>();
        assert_eq!(
            names,
            vec![
                "KB3D_ENC_AtlasA_normal.png",
                "KB3D_ENC_AtlasA_roughness.png"
            ]
        );
    }

    #[test]
    fn forward_up_composes_and_round_trips() {
        assert_eq!(compose_forward_up("-Z", "+Y"), "-Z+Y");
        assert_eq!(
            parse_forward_up("-Z+Y"),
            Some(("-Z".to_owned(), "+Y".to_owned()))
        );
        // Every legal combination round-trips.
        for forward in AXIS_TOKENS {
            for up in AXIS_TOKENS {
                let joined = compose_forward_up(forward, up);
                assert_eq!(
                    parse_forward_up(&joined),
                    Some((forward.to_owned(), up.to_owned()))
                );
            }
        }
        assert_eq!(
            parse_forward_up("-Y+Z"),
            Some(("-Y".to_owned(), "+Z".to_owned()))
        );
        assert_eq!(parse_forward_up("bogus"), None);
        assert_eq!(parse_forward_up("-Z+Q"), None);
    }

    #[test]
    fn manual_axes_win_over_detection() {
        // Detected Y-up "-Z+Y"; the artist overrides Up to +Z. The request string
        // is built from the dropdowns, so the manual value wins — this is the
        // whole point of the override panel.
        let (detected_forward, detected_up) = parse_forward_up("-Z+Y").unwrap();
        assert_eq!(
            (detected_forward.as_str(), detected_up.as_str()),
            ("-Z", "+Y")
        );
        let manual = compose_forward_up("-Z", "+Z");
        assert_eq!(manual, "-Z+Z");
        assert_ne!(manual, "-Z+Y", "override differs from detection");
    }

    #[test]
    fn parallel_forward_and_up_are_rejected() {
        // Same axis letter (any sign) is illegal — RC cannot form a basis.
        assert!(axes_parallel("+Z", "-Z"));
        assert!(axes_parallel("-Y", "+Y"));
        assert!(axes_parallel("+X", "+X"));
        // Orthogonal combinations are legal.
        assert!(!axes_parallel("-Z", "+Y"));
        assert!(!axes_parallel("+X", "+Y"));
    }

    #[test]
    fn unsupported_version_and_slot_are_rejected() {
        let mut unsupported_version = scan();
        unsupported_version.version = 2;
        assert!(
            ReviewDocument::from_scan(PathBuf::from("groups.json"), unsupported_version)
                .unwrap_err()
                .contains("version 2")
        );

        let mut unsupported_slot = scan();
        unsupported_slot.groups[0]
            .slots
            .insert("invented".to_owned(), entry("Stone_bad.png", "invented"));
        assert!(
            ReviewDocument::from_scan(PathBuf::from("groups.json"), unsupported_slot)
                .unwrap_err()
                .contains("unsupported source type")
        );
    }
}
