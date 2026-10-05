use std::sync::atomic::{AtomicI64, Ordering};

use super::special_damage::SpecialDamage;

static ID_GEN: AtomicI64 = AtomicI64::new(0);

/// See `crate::clock`. A packet parsed from a replay is stamped with the time it
/// was captured, not the time it was re-read.
fn now_ms() -> i64 {
    crate::clock::now_ms()
}

#[derive(Debug, Clone)]
pub struct ParsedDamagePacket {
    id: i64,
    actor_id: i32,
    target_id: i32,
    damage: i32,
    skill_code: i32,
    damage_type: i32,
    timestamp: i64,
    specials: Vec<SpecialDamage>,
    dot: bool,
    multi_hit_count: i32,
    multi_hit_damage: i32,
    heal_amount: i32,
    hex_payload: String,
    spec_flags: [bool; 5],
}

impl ParsedDamagePacket {
    pub fn new() -> Self {
        Self {
            id: ID_GEN.fetch_add(1, Ordering::Relaxed) + 1,
            actor_id: 0,
            target_id: 0,
            damage: 0,
            skill_code: 0,
            damage_type: 0,
            timestamp: now_ms(),
            specials: Vec::new(),
            dot: false,
            multi_hit_count: 0,
            multi_hit_damage: 0,
            heal_amount: 0,
            hex_payload: String::new(),
            spec_flags: [false; 5],
        }
    }

    // Setters
    pub fn set_actor_id(&mut self, id: i32) { self.actor_id = id; }
    pub fn set_target_id(&mut self, id: i32) { self.target_id = id; }
    pub fn set_damage(&mut self, dmg: i32) { self.damage = dmg; }
    pub fn set_skill_code(&mut self, code: i32) { self.skill_code = code; }
    pub fn set_type(&mut self, t: i32) { self.damage_type = t; }
    pub fn set_specials(&mut self, s: Vec<SpecialDamage>) { self.specials = s; }
    pub fn set_dot(&mut self, d: bool) { self.dot = d; }
    pub fn set_multi_hit_count(&mut self, c: i32) { self.multi_hit_count = c; }
    pub fn set_multi_hit_damage(&mut self, d: i32) { self.multi_hit_damage = d; }
    pub fn set_heal_amount(&mut self, h: i32) { self.heal_amount = h; }
    pub fn set_hex_payload(&mut self, h: String) { self.hex_payload = h; }
    pub fn set_spec_flags(&mut self, f: [bool; 5]) { self.spec_flags = f; }
    pub fn set_timestamp(&mut self, ts: i64) { self.timestamp = ts; }

    // Getters
    pub fn id(&self) -> i64 { self.id }
    pub fn actor_id(&self) -> i32 { self.actor_id }
    pub fn target_id(&self) -> i32 { self.target_id }
    pub fn damage(&self) -> i32 { self.damage }
    pub fn skill_code(&self) -> i32 { self.skill_code }
    pub fn damage_type(&self) -> i32 { self.damage_type }
    pub fn timestamp(&self) -> i64 { self.timestamp }
    pub fn specials(&self) -> &[SpecialDamage] { &self.specials }
    pub fn is_dot(&self) -> bool { self.dot }
    pub fn multi_hit_count(&self) -> i32 { self.multi_hit_count }
    pub fn multi_hit_damage(&self) -> i32 { self.multi_hit_damage }
    pub fn heal_amount(&self) -> i32 { self.heal_amount }
    pub fn hex_payload(&self) -> &str { &self.hex_payload }
    pub fn spec_flags(&self) -> &[bool; 5] { &self.spec_flags }

    pub fn is_crit(&self) -> bool {
        self.specials.contains(&SpecialDamage::Critical)
    }

    pub fn total_damage(&self) -> i32 {
        self.damage + self.multi_hit_damage
    }
}
