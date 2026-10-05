use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use super::analyzed_skill::AnalyzedSkill;
use super::damage_packet::ParsedDamagePacket;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PersonalData {
    pub job: String,
    pub dps: f64,
    pub amount: f64,
    pub damage_contribution: f64,
    #[serde(skip)]
    pub analyzed_data: HashMap<i32, AnalyzedSkill>,
    pub nickname: String,
    /// Combat power from the party roster packet, or 0 when this player isn't in
    /// your party (the roster is the only source, so non-party players have none).
    pub combat_power: i64,
    /// Renders this player's name gold. Resolved locally against a roster the
    /// meter downloads — see `crate::supporters`; nothing about your party is
    /// ever sent anywhere to work this out.
    ///
    /// Cosmetic and nothing else. It must never affect ordering, bar colour, or
    /// any number, because a meter that flatters the people who paid is not a
    /// meter anybody should trust.
    #[serde(default)]
    pub is_supporter: bool,
}

impl PersonalData {
    pub fn new(nickname: String) -> Self {
        Self {
            job: String::new(),
            dps: 0.0,
            amount: 0.0,
            damage_contribution: 0.0,
            analyzed_data: HashMap::new(),
            nickname,
            combat_power: 0,
            is_supporter: false,
        }
    }

    pub fn with_job(nickname: String, job: String) -> Self {
        Self {
            job,
            dps: 0.0,
            amount: 0.0,
            damage_contribution: 0.0,
            analyzed_data: HashMap::new(),
            nickname,
            combat_power: 0,
            is_supporter: false,
        }
    }

    pub fn process_pdp(&mut self, pdp: &ParsedDamagePacket, skill_name: &str) {
        self.amount += pdp.total_damage() as f64;
        let skill_code = pdp.skill_code();
        let skill = self.analyzed_data.entry(skill_code).or_insert_with(|| {
            AnalyzedSkill::new(skill_code, skill_name.to_string())
        });
        skill.process_pdp(pdp);
    }

    pub fn merge_from(&mut self, other: &PersonalData) {
        self.amount += other.amount;
        for (skill_code, other_skill) in &other.analyzed_data {
            let existing = self.analyzed_data.entry(*skill_code).or_insert_with(|| {
                AnalyzedSkill::new(*skill_code, other_skill.skill_name.clone())
            });
            existing.merge_from(other_skill);
        }
    }
}
