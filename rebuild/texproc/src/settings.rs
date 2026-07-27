use std::{
    fs,
    path::{Path, PathBuf},
};

use serde_json::{json, Value};

use crate::{
    ArmOrder, DiffFormat, OutputResolution, Result, TexprocError, TextureSettings,
    TextureTypeSettings,
};

pub fn load_texture_settings(path: &Path) -> Result<TextureSettings> {
    let text = fs::read_to_string(path).map_err(|error| {
        TexprocError::new(format!(
            "failed to read settings {}: {error}",
            path.display()
        ))
    })?;
    let value: Value = serde_json::from_str(&text)
        .map_err(|error| TexprocError::new(format!("invalid settings JSON: {error}")))?;
    texture_settings_from_value(&value)
}

pub fn save_texture_settings(path: &Path, settings: &TextureSettings) -> Result<()> {
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent)?;
    }
    let json = serde_json::to_string_pretty(&texture_settings_to_value(settings))
        .expect("texture settings JSON values are serializable");
    fs::write(path, format!("{json}\n")).map_err(|error| {
        TexprocError::new(format!(
            "failed to write settings {}: {error}",
            path.display()
        ))
    })
}

pub fn texture_settings_from_value(value: &Value) -> Result<TextureSettings> {
    let object = value
        .as_object()
        .ok_or_else(|| TexprocError::new("settings JSON must be an object"))?;
    let mut settings = TextureSettings::default();
    for (key, value) in object {
        match key.as_str() {
            "output_resolution" => {
                let text = value.as_str().ok_or_else(|| {
                    TexprocError::new("output_resolution must be `original` or a numeric string")
                })?;
                settings.output_resolution = if text.eq_ignore_ascii_case("original") {
                    OutputResolution::Original
                } else {
                    let maximum: u32 = text.parse().map_err(|_| {
                        TexprocError::new(
                            "output_resolution must be `original` or a positive integer",
                        )
                    })?;
                    if maximum == 0 {
                        return Err(TexprocError::new(
                            "output_resolution must be `original` or a positive integer",
                        ));
                    }
                    OutputResolution::Max(maximum)
                };
            }
            "diff_format" => {
                settings.diff_format = match required_string(value, key)?.as_str() {
                    "albedo" => DiffFormat::Albedo,
                    "diffuse_ao" => DiffFormat::DiffuseAo,
                    other => {
                        return Err(TexprocError::new(format!("invalid diff_format `{other}`")))
                    }
                }
            }
            "normal_flip_green" => settings.normal_flip_green = required_bool(value, key)?,
            "normalize_height" => settings.normalize_height = required_bool(value, key)?,
            "process_metallic" => settings.process_metallic = required_bool(value, key)?,
            "metal_gate" => settings.metal_gate = required_bool(value, key)?,
            "metal_gate_metallic_cut" => {
                settings.metal_gate_metallic_cut = required_f32(value, key)?
            }
            "metal_gate_spec_min" => settings.metal_gate_spec_min = required_f32(value, key)?,
            "metal_gate_gloss_cut" => settings.metal_gate_gloss_cut = required_f32(value, key)?,
            "metal_gate_transition" => settings.metal_gate_transition = required_f32(value, key)?,
            "normal_from_height_strength" => {
                settings.normal_from_height_strength = required_f32(value, key)?
            }
            "generate_missing_spec" => settings.generate_missing_spec = required_bool(value, key)?,
            "generate_missing_emissive" => {
                settings.generate_missing_emissive = required_bool(value, key)?
            }
            "generate_missing_sss" => settings.generate_missing_sss = required_bool(value, key)?,
            "generate_sss_from_diffuse" => {
                settings.generate_sss_from_diffuse = required_bool(value, key)?
            }
            "emissive_brightness" => settings.emissive_brightness = required_f32(value, key)?,
            "sss_intensity" => settings.sss_intensity = required_f32(value, key)?,
            "sss_contrast" => settings.sss_contrast = required_f32(value, key)?,
            "dither" => settings.dither = required_bool(value, key)?,
            "arm_order" => {
                settings.arm_order = match required_string(value, key)?.to_uppercase().as_str() {
                    "ARM" => ArmOrder::Arm,
                    "ORM" => ArmOrder::Orm,
                    "RMA" => ArmOrder::Rma,
                    other => return Err(TexprocError::new(format!("invalid arm_order `{other}`"))),
                }
            }
            "texture_types" => settings.texture_types = parse_texture_types(value)?,
            other => return Err(TexprocError::new(format!("unknown settings key `{other}`"))),
        }
    }
    Ok(settings)
}

pub fn texture_settings_to_value(settings: &TextureSettings) -> Value {
    let output_resolution = match settings.output_resolution {
        OutputResolution::Original => "original".to_owned(),
        OutputResolution::Max(maximum) => maximum.to_string(),
    };
    let diff_format = match settings.diff_format {
        DiffFormat::Albedo => "albedo",
        DiffFormat::DiffuseAo => "diffuse_ao",
    };
    let arm_order = match settings.arm_order {
        ArmOrder::Arm => "ARM",
        ArmOrder::Orm => "ORM",
        ArmOrder::Rma => "RMA",
    };
    json!({
        "output_resolution": output_resolution,
        "diff_format": diff_format,
        "normal_flip_green": settings.normal_flip_green,
        "normalize_height": settings.normalize_height,
        "process_metallic": settings.process_metallic,
        "metal_gate": settings.metal_gate,
        "metal_gate_metallic_cut": settings.metal_gate_metallic_cut,
        "metal_gate_spec_min": settings.metal_gate_spec_min,
        "metal_gate_gloss_cut": settings.metal_gate_gloss_cut,
        "metal_gate_transition": settings.metal_gate_transition,
        "normal_from_height_strength": settings.normal_from_height_strength,
        "generate_missing_spec": settings.generate_missing_spec,
        "generate_missing_emissive": settings.generate_missing_emissive,
        "generate_missing_sss": settings.generate_missing_sss,
        "generate_sss_from_diffuse": settings.generate_sss_from_diffuse,
        "emissive_brightness": settings.emissive_brightness,
        "sss_intensity": settings.sss_intensity,
        "sss_contrast": settings.sss_contrast,
        "arm_order": arm_order,
        "dither": settings.dither,
        "texture_types": {
            "diff": settings.texture_types.diff,
            "spec": settings.texture_types.spec,
            "ddna": settings.texture_types.ddna,
            "displ": settings.texture_types.displ,
            "emissive": settings.texture_types.emissive,
            "sss": settings.texture_types.sss,
        }
    })
}

pub fn default_settings_path() -> PathBuf {
    PathBuf::from("texproc-settings.json")
}

fn parse_texture_types(value: &Value) -> Result<TextureTypeSettings> {
    let object = value
        .as_object()
        .ok_or_else(|| TexprocError::new("texture_types must be an object"))?;
    let mut settings = TextureTypeSettings::default();
    for (key, value) in object {
        let enabled = required_bool(value, key)?;
        match key.as_str() {
            "diff" => settings.diff = enabled,
            "spec" => settings.spec = enabled,
            "ddna" => settings.ddna = enabled,
            "displ" => settings.displ = enabled,
            "emissive" => settings.emissive = enabled,
            "sss" => settings.sss = enabled,
            other => {
                return Err(TexprocError::new(format!(
                    "unknown texture_types key `{other}`"
                )))
            }
        }
    }
    Ok(settings)
}

fn required_string(value: &Value, key: &str) -> Result<String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be a string")))
}

fn required_bool(value: &Value, key: &str) -> Result<bool> {
    value
        .as_bool()
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be boolean")))
}

fn required_f32(value: &Value, key: &str) -> Result<f32> {
    value
        .as_f64()
        .map(|value| value as f32)
        .filter(|value| value.is_finite())
        .ok_or_else(|| TexprocError::new(format!("settings `{key}` must be finite numeric")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cli_settings_shape_round_trips() {
        let settings = TextureSettings {
            output_resolution: OutputResolution::Max(2048),
            diff_format: DiffFormat::DiffuseAo,
            arm_order: ArmOrder::Rma,
            normal_flip_green: true,
            ..TextureSettings::default()
        };
        assert_eq!(
            texture_settings_from_value(&texture_settings_to_value(&settings)).unwrap(),
            settings
        );
    }
}
