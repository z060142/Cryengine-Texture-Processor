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

fn non_empty_or(value: String, fallback: String) -> String {
    if value.trim().is_empty() {
        fallback
    } else {
        value
    }
}
