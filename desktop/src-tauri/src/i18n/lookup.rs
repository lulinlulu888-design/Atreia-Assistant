use std::collections::HashMap;

use parking_lot::RwLock;

/// Skill code to skill name lookup. Thread-safe and reloadable.
pub struct SkillLookup {
    skills: RwLock<HashMap<i32, String>>,
}

impl SkillLookup {
    pub fn new() -> Self {
        Self { skills: RwLock::new(HashMap::new()) }
    }

    pub fn load_from_json(&self, json_text: &str) {
        if let Ok(map) = serde_json::from_str::<HashMap<String, String>>(json_text) {
            let mut skills = self.skills.write();
            skills.clear();
            for (key, value) in map {
                if let Ok(code) = key.parse::<i32>() {
                    skills.insert(code, value);
                }
            }
        }
    }

    pub fn get_skill_name(&self, code: i32) -> String {
        self.skills.read().get(&code).cloned().unwrap_or_default()
    }

    pub fn lookup_skill_name(&self, code: i32) -> String {
        let skills = self.skills.read();
        if let Some(name) = skills.get(&code) {
            return name.clone();
        }
        if (3_000_000..=3_099_999).contains(&code) {
            if let Some(name) = skills.get(&(code * 10 + 1)) {
                return name.clone();
            }
        }
        String::new()
    }

    pub fn contains(&self, code: i32) -> bool {
        self.skills.read().contains_key(&code)
    }
}

/// NPC/boss code to name lookup. Thread-safe and reloadable.
pub struct NpcLookup {
    npcs: RwLock<HashMap<i32, NpcInfo>>,
}

struct NpcInfo {
    name: String,
    is_boss: bool,
    /// A training dummy: a scarecrow, a punching bag, a test target.
    is_dummy: bool,
}

/// English names of training dummies, for a table that does not flag them all
/// (`isDummy`). The rule a2tools.app uses too.
const DUMMY_NAMES: &[&str] = &["Training Scarecrow", "Punching Bag"];

impl NpcLookup {
    pub fn new() -> Self {
        Self { npcs: RwLock::new(HashMap::new()) }
    }

    pub fn load_from_json(&self, json_text: &str) {
        if let Ok(map) = serde_json::from_str::<HashMap<String, serde_json::Value>>(json_text) {
            let mut npcs = self.npcs.write();
            npcs.clear();
            for (key, value) in &map {
                let code = match key.parse::<i32>() {
                    Ok(c) => c,
                    Err(_) => continue,
                };
                if let Some(obj) = value.as_object() {
                    let name = obj.get("name")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    let is_boss = obj.get("isBoss")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                    let is_dummy = obj.get("isDummy").and_then(|v| v.as_bool()).unwrap_or(false)
                        || DUMMY_NAMES.iter().any(|d| name.contains(d));
                    npcs.insert(code, NpcInfo { name, is_boss, is_dummy });
                } else if let Some(name) = value.as_str() {
                    let is_dummy = DUMMY_NAMES.iter().any(|d| name.contains(d));
                    npcs.insert(code, NpcInfo { name: name.to_string(), is_boss: false, is_dummy });
                }
            }
        }
    }

    pub fn get_npc_name(&self, code: i32) -> String {
        self.npcs.read().get(&code).map(|n| n.name.clone()).unwrap_or_default()
    }

    pub fn is_boss(&self, code: i32) -> bool {
        self.npcs.read().get(&code).is_some_and(|n| n.is_boss)
    }

    /// Whether `code` is a training dummy. Fights against one are training,
    /// not boss fights: History marks them so and they are never uploaded.
    ///
    /// Taken from the NPC table, every language of which flags them
    /// (`isDummy`), plus the English names a2tools.app also goes by. A list
    /// kept by hand fell behind: it missed three scarecrows the table marks
    /// as bosses, so fights on them were saved, and uploaded, as boss fights.
    /// `TRAINING_DUMMY_CODES` still answers before a table has loaded.
    pub fn is_training_dummy(&self, code: i32) -> bool {
        TRAINING_DUMMY_CODES.contains(&code)
            || self.npcs.read().get(&code).is_some_and(|n| n.is_dummy)
    }
}

/// Training scarecrows known before the NPC table flagged dummies, kept so a
/// lookup with no table loaded still recognises them.
const TRAINING_DUMMY_CODES: &[i32] = &[
    2300229, 2300919, 2310229, 2310919, 2320229, 2320919,
    2400032, 2400035, 2400392, 2500075, 2500076, 2701376,
    2090773, 2702605,
];

/// Load skill and NPC data for a specific language from a data directory.
pub fn load_language(
    skill_lookup: &SkillLookup,
    npc_lookup: &NpcLookup,
    data_dir: &std::path::Path,
    language: &str,
) {
    // Every locale shipped under src/data/i18n. Anything else falls back to
    // English rather than loading nothing, so an unknown setting degrades to
    // readable names instead of bare ids.
    let lang = match language {
        "de" | "en" | "es" | "fr" | "ja" | "ko" | "pt" | "ru" | "zh-Hans" | "zh-Hant" => language,
        _ => "en",
    };

    let skills_path = data_dir.join("i18n").join("skills").join(format!("{}.json", lang));
    if let Ok(text) = std::fs::read_to_string(&skills_path) {
        skill_lookup.load_from_json(&text);
        tracing::info!("Loaded skills ({}) from {}", lang, skills_path.display());
    } else {
        // Fallback to English
        let en_path = data_dir.join("i18n").join("skills").join("en.json");
        if let Ok(text) = std::fs::read_to_string(&en_path) {
            skill_lookup.load_from_json(&text);
        }
    }

    let npcs_path = data_dir.join("i18n").join("npcs").join(format!("{}.json", lang));
    if let Ok(text) = std::fs::read_to_string(&npcs_path) {
        npc_lookup.load_from_json(&text);
        tracing::info!("Loaded NPCs ({}) from {}", lang, npcs_path.display());
    } else {
        let en_path = data_dir.join("i18n").join("npcs").join("en.json");
        if let Ok(text) = std::fs::read_to_string(&en_path) {
            npc_lookup.load_from_json(&text);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The three scarecrows the old hand-kept list missed (two of them flagged
    /// as bosses), recognised whatever language the table is in.
    #[test]
    fn every_language_table_knows_the_scarecrows() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../src/data/i18n/npcs");
        for lang in ["en", "ko", "zh-Hans", "zh-Hant", "ja", "de", "fr", "es", "pt", "ru"] {
            let lookup = NpcLookup::new();
            lookup.load_from_json(&std::fs::read_to_string(dir.join(format!("{lang}.json"))).unwrap());
            for code in [2090773, 2400035, 2702605, 2300229, 2090458] {
                assert!(lookup.is_training_dummy(code), "{lang}: {code}");
            }
            // A real boss (Terminator Bargott) is not one.
            assert!(lookup.is_boss(2301208) && !lookup.is_training_dummy(2301208), "{lang}");
        }
    }

    #[test]
    fn dummies_by_flag_by_name_and_before_any_table() {
        let lookup = NpcLookup::new();
        assert!(lookup.is_training_dummy(2400035), "known before a table loads");
        assert!(!lookup.is_training_dummy(1));
        lookup.load_from_json(
            r#"{"1": {"name": "Punching Bag", "isBoss": false},
                "2": {"name": "Odd Target", "isBoss": true, "isDummy": true},
                "3": {"name": "Ancient Dragon", "isBoss": true}}"#,
        );
        assert!(lookup.is_training_dummy(1), "by name");
        assert!(lookup.is_training_dummy(2), "by flag");
        assert!(!lookup.is_training_dummy(3));
    }
}
