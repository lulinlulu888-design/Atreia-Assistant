use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetailsActorSummary {
    pub actor_id: i32,
    pub nickname: String,
    #[serde(default)]
    pub job: String,
    /// Job class prefix ID (e.g. 11=Gladiator) for language-independent storage
    #[serde(default)]
    pub job_id: i32,
    #[serde(default)]
    pub party_heal: i64,
    #[serde(default)]
    pub regen: i64,
    #[serde(default)]
    pub damage_received: i64,
    #[serde(default)]
    pub hits_received: i32,
    /// Roster id for this actor, or 0 when the party roster never named them
    /// (solo play, or a player who joined before the roster packet arrived).
    ///
    /// Local-only. It is deliberately *not* what goes on the wire when a fight
    /// is shared: uploads carry `sha256(dbid)` so the server can tell two rows
    /// apart without learning who they are. See `docs/PRIVACY.md`.
    #[serde(default)]
    pub dbid: u64,
    /// World/server id, the top 16 bits of `dbid`. 0 when unknown.
    #[serde(default)]
    pub server_id: u16,
    /// Renders this name gold in the Details party bars. See
    /// `crate::supporters`; cosmetic only.
    #[serde(default)]
    pub is_supporter: bool,
    /// Character level, gear score and combat power from the party roster, as
    /// the game reported them for this fight. 0 when the roster never named
    /// the actor: only your own party's members are on it.
    ///
    /// Saved with the fight because they change: a gear score from today says
    /// nothing about a fight from last month, and the class statistics compare
    /// players at like strength.
    #[serde(default)]
    pub level: i32,
    #[serde(default)]
    pub gear_score: i32,
    #[serde(default)]
    pub combat_power: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetailsTargetSummary {
    pub target_id: i32,
    #[serde(default)]
    pub target_name: String,
    #[serde(default)]
    pub max_hp: i32,
    pub battle_time: i64,
    pub last_damage_time: i64,
    pub total_damage: i32,
    pub actor_damage: std::collections::HashMap<i32, i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetailsContext {
    pub current_target_id: i32,
    pub targets: Vec<DetailsTargetSummary>,
    pub actors: Vec<DetailsActorSummary>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetailSkillEntry {
    pub actor_id: i32,
    pub code: i32,
    pub name: String,
    pub time: i32,
    pub dmg: i32,
    pub multi_hit_count: i32,
    pub multi_hit_damage: i32,
    #[serde(default)]
    pub multi_hit_hits: i32,
    #[serde(default)]
    pub min_dmg: i32,
    #[serde(default)]
    pub max_dmg: i32,
    pub crit: i32,
    pub parry: i32,
    pub back: i32,
    #[serde(default)]
    pub frontal: i32,
    pub perfect: i32,
    pub double: i32,
    pub smite: i32,
    pub powershard: i32,
    pub regen: i32,
    #[serde(default)]
    pub job: String,
    #[serde(default)]
    pub is_dot: bool,
    #[serde(default)]
    pub hit_timestamps: Vec<i64>,
    #[serde(default)]
    pub specs: Vec<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PingPoint {
    pub ts_ms: i64,
    pub ping_ms: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TargetDetailsResponse {
    pub target_id: i32,
    #[serde(default)]
    pub max_hp: i32,
    pub total_target_damage: i32,
    pub battle_time: i64,
    #[serde(default)]
    pub start_time: i64,
    pub skills: Vec<DetailSkillEntry>,
    #[serde(default)]
    pub ping_history: Vec<PingPoint>,
    /// Per-actor / per-skill HEALING done in this fight. Reuses DetailSkillEntry:
    /// `dmg` = heal amount, `time` = tick count, `is_dot` = HoT. Empty for old files.
    #[serde(default)]
    pub heal_skills: Vec<DetailSkillEntry>,
}
