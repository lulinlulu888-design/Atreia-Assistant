use super::damage_packet::ParsedDamagePacket;

/// Maximum idle gap before a fight is considered ended and a new one begins.
const IDLE_RESET_MS: i64 = 30_000;

#[derive(Debug, Clone)]
pub struct TargetInfo {
    pub target_id: i32,
    pub damaged_amount: i64,
    pub target_damage_started: i64,
    pub target_damage_ended: i64,
    last_processed_id: i64,
    /// Set when an idle gap was detected — signals that old packets should be pruned
    pub idle_reset_at: Option<i64>,
}

impl TargetInfo {
    pub fn new(target_id: i32, first_timestamp: i64) -> Self {
        Self {
            target_id,
            damaged_amount: 0,
            target_damage_started: first_timestamp,
            target_damage_ended: first_timestamp,
            last_processed_id: -1,
            idle_reset_at: None,
        }
    }

    pub fn process_pdp(&mut self, pdp: &ParsedDamagePacket) {
        if pdp.id() <= self.last_processed_id {
            return;
        }
        let ts = pdp.timestamp();

        // If the gap since last damage exceeds the idle threshold,
        // reset the fight window — this is a new encounter on the same target.
        if self.target_damage_ended > 0
            && ts - self.target_damage_ended > IDLE_RESET_MS
        {
            self.idle_reset_at = Some(ts);
            self.target_damage_started = ts;
            self.target_damage_ended = ts;
            self.damaged_amount = 0;
        }

        self.damaged_amount += pdp.total_damage() as i64;
        if ts < self.target_damage_started {
            self.target_damage_started = ts;
        }
        if ts > self.target_damage_ended {
            self.target_damage_ended = ts;
        }
        self.last_processed_id = pdp.id();
    }

    pub fn battle_time(&self) -> i64 {
        if self.target_damage_started == i64::MAX {
            return 0;
        }
        self.target_damage_ended - self.target_damage_started
    }

    pub fn last_damage_time(&self) -> i64 {
        self.target_damage_ended
    }

    /// Take and clear the idle reset timestamp, if any.
    pub fn take_idle_reset(&mut self) -> Option<i64> {
        self.idle_reset_at.take()
    }
}
