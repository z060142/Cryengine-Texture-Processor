use crate::diagnostic::Diagnostic;
use serde::Serialize;
use std::fmt;

pub const RC_MAX_SUB_MATERIALS: i32 = 128;
pub const PROXY_PHYSICALIZE_PATTERNS: &[&str] =
    &["proxy", "phys", "physics", "collision", "collider"];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Physicalize {
    No,
    Default,
    Obstruct,
    NoCollide,
    ProxyOnly,
}

impl Physicalize {
    pub fn parse(value: &str) -> Option<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "no" => Some(Self::No),
            "default" => Some(Self::Default),
            "obstruct" => Some(Self::Obstruct),
            "no_collide" => Some(Self::NoCollide),
            "proxy_only" => Some(Self::ProxyOnly),
            _ => None,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::No => "no",
            Self::Default => "default",
            Self::Obstruct => "obstruct",
            Self::NoCollide => "no_collide",
            Self::ProxyOnly => "proxy_only",
        }
    }
}

impl fmt::Display for Physicalize {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_str())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PhysicalizeResolution {
    pub value: Physicalize,
    pub source: String,
    pub source_key: String,
    pub raw_value: String,
    pub valid: bool,
}

pub fn normalize_sub_index(sub_index: Option<i32>) -> i32 {
    match sub_index {
        Some(value) if value < RC_MAX_SUB_MATERIALS => value,
        _ => -1,
    }
}

pub fn is_supported_sub_index(sub_index: Option<i32>) -> bool {
    matches!(sub_index, Some(0..RC_MAX_SUB_MATERIALS))
}

pub fn normalize_physicalize(value: &str) -> Physicalize {
    Physicalize::parse(value).unwrap_or(Physicalize::No)
}

pub fn infer_physicalize_from_name(material_name: &str) -> Physicalize {
    let name = material_name.to_ascii_lowercase();
    if PROXY_PHYSICALIZE_PATTERNS
        .iter()
        .any(|pattern| name.contains(pattern))
    {
        Physicalize::ProxyOnly
    } else {
        Physicalize::NoCollide
    }
}

pub fn resolve_physicalize(
    explicit: Option<(&str, &str)>,
    material_name: &str,
) -> PhysicalizeResolution {
    if let Some((key, raw_value)) = explicit.filter(|(_, value)| !value.is_empty()) {
        return PhysicalizeResolution {
            value: normalize_physicalize(raw_value),
            source: "explicit".to_owned(),
            source_key: key.to_owned(),
            raw_value: raw_value.to_owned(),
            valid: Physicalize::parse(raw_value).is_some(),
        };
    }

    PhysicalizeResolution {
        value: infer_physicalize_from_name(material_name),
        source: "name_heuristic".to_owned(),
        source_key: String::new(),
        raw_value: String::new(),
        valid: true,
    }
}

pub fn physicalize_diagnostics(
    material_name: &str,
    resolution: &PhysicalizeResolution,
) -> Vec<Diagnostic> {
    if resolution.valid {
        return Vec::new();
    }

    vec![Diagnostic::new(
        "warning",
        "rc_unknown_physicalize_defaults_to_no",
        material_name,
        "RC ImportRequest only recognizes no, default, obstruct, no_collide, and proxy_only. Unknown physicalize values fall back to the same behavior as 'no'.",
    )
    .detail("physicalize", resolution.value.as_str())
    .detail("requested_physicalize", resolution.raw_value.clone())
    .detail("source_key", resolution.source_key.clone())]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sub_index_limit_matches_rc() {
        assert_eq!(normalize_sub_index(None), -1);
        assert_eq!(normalize_sub_index(Some(-1)), -1);
        assert_eq!(normalize_sub_index(Some(0)), 0);
        assert_eq!(normalize_sub_index(Some(127)), 127);
        assert_eq!(normalize_sub_index(Some(128)), -1);
        assert!(is_supported_sub_index(Some(127)));
        assert!(!is_supported_sub_index(Some(128)));
    }

    #[test]
    fn physicalize_normalization_and_proxy_inference_match_python() {
        assert_eq!(normalize_physicalize(" DEFAULT "), Physicalize::Default);
        assert_eq!(normalize_physicalize("unknown"), Physicalize::No);
        assert_eq!(
            infer_physicalize_from_name("wheel_collision_proxy"),
            Physicalize::ProxyOnly
        );
        assert_eq!(
            infer_physicalize_from_name("render_mesh"),
            Physicalize::NoCollide
        );
    }

    #[test]
    fn unknown_explicit_physicalize_emits_warning() {
        let resolution = resolve_physicalize(Some(("physicalize", "wat")), "Body");
        assert_eq!(resolution.value, Physicalize::No);
        assert!(!resolution.valid);
        assert_eq!(
            physicalize_diagnostics("Body", &resolution)[0].code,
            "rc_unknown_physicalize_defaults_to_no"
        );
    }
}
