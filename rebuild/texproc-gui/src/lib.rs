use std::{
    fs,
    path::{Path, PathBuf},
};

use texproc::{ScanEntry, ScanResult, Severity};

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
