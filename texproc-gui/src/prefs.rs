use std::{
    env, fs,
    path::{Path, PathBuf},
};

use serde_json::{json, Value};

#[derive(Clone, Debug)]
pub struct AppPreferences {
    pub texture_output_directory: String,
    pub model_output_directory: String,
    pub settings_path: String,
    pub import_path: String,
    pub model_path: String,
    pub manifest_path: String,
    pub overrides_path: String,
    pub rc_path: String,
    pub generate_dds: bool,
    pub delete_request_json: bool,
    pub delete_tif_after_dds: bool,
    pub export_associated_textures: bool,
    /// Conversion Settings (R9): unit_size dropdown, persisted. Forward/Up are
    /// re-detected per FBX and deliberately not persisted.
    pub conversion_unit: String,
    pub conversion_scale: f64,
    /// GUI language code ("en" / "zh-cn"). Unknown values load back as "en".
    pub language: String,
}

impl Default for AppPreferences {
    fn default() -> Self {
        Self {
            texture_output_directory: String::new(),
            model_output_directory: String::new(),
            settings_path: "texproc-settings.json".to_owned(),
            import_path: String::new(),
            model_path: String::new(),
            manifest_path: String::new(),
            overrides_path: String::new(),
            rc_path: String::new(),
            generate_dds: false,
            delete_request_json: false,
            delete_tif_after_dds: false,
            export_associated_textures: false,
            conversion_unit: "file".to_owned(),
            conversion_scale: 1.0,
            language: "en".to_owned(),
        }
    }
}

impl AppPreferences {
    pub fn load() -> Self {
        let path = preferences_path();
        let Ok(text) = fs::read_to_string(path) else {
            return Self::default();
        };
        let Ok(value) = serde_json::from_str::<Value>(&text) else {
            return Self::default();
        };
        let mut preferences = Self::default();
        preferences.texture_output_directory = string(&value, "texture_output_directory");
        preferences.model_output_directory = string(&value, "model_output_directory");
        preferences.settings_path =
            non_empty_or(string(&value, "settings_path"), preferences.settings_path);
        preferences.import_path = string(&value, "import_path");
        preferences.model_path = string(&value, "model_path");
        preferences.manifest_path = string(&value, "manifest_path");
        preferences.overrides_path = string(&value, "overrides_path");
        preferences.rc_path = string(&value, "rc_path");
        preferences.generate_dds = bool_field(&value, "generate_dds");
        preferences.delete_request_json = bool_field(&value, "delete_request_json");
        preferences.delete_tif_after_dds = bool_field(&value, "delete_tif_after_dds");
        preferences.export_associated_textures = bool_field(&value, "export_associated_textures");
        preferences.conversion_unit = non_empty_or(
            string(&value, "conversion_unit"),
            preferences.conversion_unit,
        );
        preferences.conversion_scale = value
            .get("conversion_scale")
            .and_then(Value::as_f64)
            .unwrap_or(preferences.conversion_scale);
        // Unknown / missing language codes fall back to "en".
        preferences.language = normalize_language(&string(&value, "language"));
        preferences
    }

    pub fn save(&self) -> Result<(), String> {
        let path = preferences_path();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("failed to create {}: {error}", parent.display()))?;
        }
        let value = json!({
            "texture_output_directory": self.texture_output_directory,
            "model_output_directory": self.model_output_directory,
            "settings_path": self.settings_path,
            "import_path": self.import_path,
            "model_path": self.model_path,
            "manifest_path": self.manifest_path,
            "overrides_path": self.overrides_path,
            "rc_path": self.rc_path,
            "generate_dds": self.generate_dds,
            "delete_request_json": self.delete_request_json,
            "delete_tif_after_dds": self.delete_tif_after_dds,
            "export_associated_textures": self.export_associated_textures,
            "conversion_unit": self.conversion_unit,
            "conversion_scale": self.conversion_scale,
            "language": self.language,
        });
        let text = serde_json::to_string_pretty(&value)
            .expect("application preference values are serializable");
        fs::write(&path, format!("{text}\n"))
            .map_err(|error| format!("failed to write {}: {error}", path.display()))
    }
}

pub fn embedded_texture_directory(model_path: &Path) -> PathBuf {
    let stem = model_path
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("model");
    local_app_data()
        .join("CryEngineTextureProcessor")
        .join("embedded")
        .join(stem)
}

fn preferences_path() -> PathBuf {
    local_app_data()
        .join("CryEngineTextureProcessor")
        .join("gui-state.json")
}

fn local_app_data() -> PathBuf {
    env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(env::temp_dir)
}

fn string(value: &Value, key: &str) -> String {
    value
        .get(key)
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned()
}

fn bool_field(value: &Value, key: &str) -> bool {
    value.get(key).and_then(Value::as_bool).unwrap_or(false)
}

fn non_empty_or(value: String, fallback: String) -> String {
    if value.trim().is_empty() {
        fallback
    } else {
        value
    }
}

/// Canonicalize a stored language code. Only "zh-cn" is recognized alongside
/// "en"; anything else (empty, unknown, legacy) resolves to "en".
fn normalize_language(code: &str) -> String {
    match code {
        "zh-cn" => "zh-cn".to_owned(),
        _ => "en".to_owned(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn language_defaults_to_en() {
        assert_eq!(AppPreferences::default().language, "en");
    }

    #[test]
    fn language_normalizes_unknown_to_en() {
        assert_eq!(normalize_language("zh-cn"), "zh-cn");
        assert_eq!(normalize_language("en"), "en");
        assert_eq!(normalize_language("fr"), "en");
        assert_eq!(normalize_language(""), "en");
    }

    #[test]
    fn language_survives_save_load_round_trip() {
        // Isolate the on-disk prefs to a temp dir via LOCALAPPDATA; this is the
        // only prefs test that touches env, so no intra-crate race.
        let temp = env::temp_dir().join(format!(
            "texproc-prefs-test-{}",
            std::process::id()
        ));
        let previous = env::var_os("LOCALAPPDATA");
        env::set_var("LOCALAPPDATA", &temp);

        let mut prefs = AppPreferences::default();
        prefs.language = "zh-cn".to_owned();
        prefs.save().expect("save prefs");
        assert_eq!(AppPreferences::load().language, "zh-cn");

        // An unknown code on disk loads back as "en".
        prefs.language = "de".to_owned();
        prefs.save().expect("save prefs");
        assert_eq!(AppPreferences::load().language, "en");

        match previous {
            Some(value) => env::set_var("LOCALAPPDATA", value),
            None => env::remove_var("LOCALAPPDATA"),
        }
        let _ = fs::remove_dir_all(&temp);
    }
}
