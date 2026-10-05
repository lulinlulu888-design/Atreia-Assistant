use serde::{Deserialize, Serialize};

use super::details_context::{DetailsActorSummary, TargetDetailsResponse};

pub const APP_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FightRecord {
    pub id: String,
    /// Display name (for backward compat). New files also have mob_code for i18n resolution.
    pub boss_name: String,
    pub target_id: i32,
    pub start_time_ms: i64,
    pub duration_ms: i64,
    pub total_damage: i32,
    /// Job class prefix IDs (e.g. [11, 14, 17]) for language-independent storage.
    pub jobs: Vec<String>,
    /// Job class prefix IDs for i18n resolution (new field).
    #[serde(default)]
    pub job_ids: Vec<i32>,
    pub details: TargetDetailsResponse,
    pub actors: Vec<DetailsActorSummary>,
    #[serde(default)]
    pub is_train: bool,
    #[serde(default)]
    pub app_version: String,
    /// NPC mob type code for i18n boss name resolution (new field).
    #[serde(default)]
    pub mob_code: i32,
    /// The instance this was fought in, identifying both the dungeon and its
    /// difficulty tier (Ferocious Horn Den is 600091/600092/600093 for
    /// Exploration / Conquest [Normal] / Conquest [Hard]). 0 in the open world.
    ///
    /// Already parsed from the party roster packet and kept in `DataStorage`;
    /// recorded here so a shared fight can say which tier it was, and so
    /// leaderboards do not rank a Normal clear against a Hard one.
    #[serde(default)]
    pub dungeon_id: i32,
    /// The recording player's home server (`1304` = Europe, Kaisinel), else
    /// their party's; 0 when the capture never said. Its digits name the
    /// region, which a2tools.app groups uploaded logs by.
    #[serde(default)]
    pub server_id: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FightSummary {
    pub id: String,
    pub boss_name: String,
    pub target_id: i32,
    pub start_time_ms: i64,
    pub duration_ms: i64,
    pub total_damage: i32,
    pub jobs: Vec<String>,
    #[serde(default)]
    pub job_ids: Vec<i32>,
    #[serde(default)]
    pub is_train: bool,
    #[serde(default)]
    pub is_live: bool,
    #[serde(default)]
    pub app_version: String,
    #[serde(default)]
    pub mob_code: i32,
    /// The instance it was fought in (0 in the open world), so History can
    /// group fights by dungeon.
    #[serde(default)]
    pub dungeon_id: i32,
    /// One class per party member who fought, so History shows two icons
    /// for two Clerics where `jobs` has one.
    #[serde(default)]
    pub member_jobs: Vec<String>,
}

impl FightRecord {
    /// Each player's class, one entry per player. With a party roster, only
    /// its members: a summon or aura that was never tied to its owner stays
    /// in `actors` with its owner's class and no roster identity. Without
    /// one, every classed actor not named by a bare id.
    pub fn member_jobs(&self) -> Vec<String> {
        let classed = self.actors.iter().filter(|a| !a.job.is_empty());
        let mut jobs: Vec<String> = if self.actors.iter().any(|a| a.dbid != 0) {
            classed.filter(|a| a.dbid != 0).map(|a| a.job.clone()).collect()
        } else {
            classed
                .filter(|a| {
                    let id_only = a.nickname.chars().all(|c| c.is_ascii_digit() || c == '*' || c == '#');
                    a.nickname.is_empty() || !id_only
                })
                .map(|a| a.job.clone())
                .collect()
        };
        jobs.sort();
        jobs
    }
}

/// Obscure a nickname for privacy: keep first char and last char, mask the middle.
/// For CJK names (2-3 chars), keep first char, mask rest.
/// The local player's name is NOT obscured.
pub fn obscure_nickname(name: &str) -> String {
    let chars: Vec<char> = name.chars().collect();
    if chars.len() <= 1 {
        return name.to_string();
    }
    if chars.len() == 2 {
        return format!("{}*", chars[0]);
    }
    if chars.len() == 3 {
        return format!("{}*{}", chars[0], chars[2]);
    }
    // For longer names: first 2 chars + asterisks + last char
    let mask_len = (chars.len() - 3).min(4);
    let mask: String = std::iter::repeat_n('*', mask_len).collect();
    format!("{}{}{}{}", chars[0], chars[1], mask, chars[chars.len() - 1])
}
