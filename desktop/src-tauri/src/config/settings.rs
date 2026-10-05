use std::collections::HashMap;
use std::path::PathBuf;

use parking_lot::RwLock;
use tracing::info;

/// Application settings stored as key-value pairs.
/// Persists to settings.json in the app data directory.
/// Also attempts to migrate from the Kotlin app's settings.properties on first run.
pub struct Settings {
    values: RwLock<HashMap<String, String>>,
    file_path: PathBuf,
}

impl Settings {
    pub fn new(app_data_dir: PathBuf) -> Self {
        let file_path = app_data_dir.join("settings.json");
        let mut values: HashMap<String, String> = if file_path.exists() {
            match std::fs::read_to_string(&file_path) {
                Ok(text) => serde_json::from_str(&text).unwrap_or_default(),
                Err(_) => HashMap::new(),
            }
        } else {
            HashMap::new()
        };

        // Migrate from Kotlin app's settings.properties if our settings are empty
        if false && values.is_empty() {
            if let Some(migrated) = Self::try_migrate_from_kotlin() {
                values = migrated;
                info!("Migrated {} settings from Kotlin app", values.len());
            }
        }

        // Atreia is a separate local-only fork; do not inherit upstream sharing.
        values.insert("dpsMeter.autoUpload".into(), "false".into());
        values.insert("dpsMeter.discordActivity".into(), "false".into());
        values.entry("dpsMeter.language".into()).or_insert("zh-Hans".into());
        let s = Self {
            values: RwLock::new(values),
            file_path,
        };
        if !s.file_path.exists() {
            s.save();
        }
        s
    }

    pub fn get(&self, key: &str) -> Option<String> {
        self.values.read().get(key).cloned()
    }

    /// Store a value. Returns true when it actually changed, which is what gates
    /// the cross-window `setting-changed` broadcast — re-emitting on a no-op
    /// write would bounce the event back and forth between the windows.
    pub fn set(&self, key: &str, value: &str) -> bool {
        {
            let mut values = self.values.write();
            if values.get(key).is_some_and(|existing| existing == value) {
                return false;
            }
            values.insert(key.to_string(), value.to_string());
        }
        self.save();
        true
    }

    pub fn remove(&self, key: &str) {
        self.values.write().remove(key);
        self.save();
    }

    pub fn clear(&self) {
        self.values.write().clear();
        self.save();
    }

    pub fn get_all(&self) -> HashMap<String, String> {
        self.values.read().clone()
    }

    fn save(&self) {
        if let Some(parent) = self.file_path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let data = self.values.read();
        if let Ok(json) = serde_json::to_string_pretty(&*data) {
            let _ = std::fs::write(&self.file_path, json);
        }
    }

    /// Try to migrate settings from the Kotlin app's settings.properties file.
    fn try_migrate_from_kotlin() -> Option<HashMap<String, String>> {
        let appdata = std::env::var("APPDATA").ok()?;
        let kotlin_file = PathBuf::from(&appdata).join("AionDPS").join("settings.properties");
        if !kotlin_file.exists() {
            return None;
        }
        let text = std::fs::read_to_string(&kotlin_file).ok()?;
        let mut map = HashMap::new();
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') || line.starts_with('!') {
                continue;
            }
            if let Some((key, value)) = line.split_once('=') {
                map.insert(key.trim().to_string(), value.trim().to_string());
            }
        }
        if map.is_empty() { None } else { Some(map) }
    }
}
