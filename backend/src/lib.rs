// SPDX-License-Identifier: GPL-3.0-only
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};
use serde::Deserialize;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

const MAX_BUFFER: usize = 65536;
const MAX_FLOWS: usize = 32;

pub fn bundled_dot_skills() -> HashSet<i32> {
    serde_json::from_str::<Vec<i32>>(include_str!("../resources/dot_skill_ids.json"))
        .expect("bundled upstream DoT list must be valid JSON")
        .into_iter()
        .collect()
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Input {
    pub flow: String,
    pub timestamp_ms: i64,
    pub payload_hex: String,
    #[serde(default)]
    pub close: bool,
}

struct Flow {
    processor: StreamProcessor,
    pending: Vec<u8>,
}

pub struct Backend {
    client: String,
    storage: Arc<DataStorage>,
    skills: Arc<SkillLookup>,
    npcs: Arc<NpcLookup>,
    dot_skills: HashSet<i32>,
    flows: HashMap<String, Flow>,
    last_timestamp: Option<i64>,
    last_record_timestamp: Option<i64>,
    discarded_protocol_bytes: usize,
}

impl Backend {
    pub fn new(client: &str, dot_skills: HashSet<i32>) -> Result<Self, String> {
        if !matches!(client, "steam" | "purple") {
            return Err("client must be steam or purple".into());
        }
        Ok(Self {
            client: client.into(),
            storage: Arc::new(DataStorage::new()),
            skills: Arc::new(SkillLookup::new()),
            npcs: Arc::new(NpcLookup::new()),
            dot_skills,
            flows: HashMap::new(),
            last_timestamp: None,
            last_record_timestamp: None,
            discarded_protocol_bytes: 0,
        })
    }

    pub fn feed(&mut self, input: Input) -> Result<Value, String> {
        if input.flow.is_empty() || input.flow.len() > 128 {
            return Err("invalid flow identifier".into());
        }
        if input.timestamp_ms < 0
            || self
                .last_record_timestamp
                .is_some_and(|t| input.timestamp_ms < t)
        {
            return Err("capture timestamps must be nonnegative and ordered".into());
        }
        let payload = decode_hex(&input.payload_hex)?;
        if input.close {
            if !payload.is_empty() {
                return Err("close record must not contain payload".into());
            }
            if let Some(flow) = self.flows.remove(&input.flow) {
                self.discarded_protocol_bytes = self
                    .discarded_protocol_bytes
                    .saturating_add(flow.pending.len());
            }
            // Lifecycle housekeeping must not extend combat duration.
            self.last_record_timestamp = Some(input.timestamp_ms);
            return Ok(self.snapshot());
        }
        if !self.flows.contains_key(&input.flow) && self.flows.len() >= MAX_FLOWS {
            return Err("too many flows; start a new backend session".into());
        }
        if let Some(flow) = self.flows.get(&input.flow) {
            if flow.pending.len() + payload.len() > MAX_BUFFER {
                return Err("protocol buffer limit exceeded; capture may be incompatible".into());
            }
        }
        let flow = self.flows.entry(input.flow).or_insert_with(|| {
            let mut processor =
                StreamProcessor::new(self.storage.clone(), self.skills.clone(), self.npcs.clone());
            processor.set_dot_skill_ids(self.dot_skills.clone());
            Flow {
                processor,
                pending: Vec::new(),
            }
        });
        flow.pending.extend(payload);
        flow.processor
            .set_override_timestamp(Some(input.timestamp_ms));
        let consumed = flow.processor.consume_stream(&flow.pending);
        flow.pending.drain(..consumed);
        flow.processor.set_override_timestamp(None);
        self.last_timestamp = Some(input.timestamp_ms);
        self.last_record_timestamp = Some(input.timestamp_ms);
        Ok(self.snapshot())
    }

    pub fn snapshot(&self) -> Value {
        let names = self.storage.get_nicknames();
        let mut targets = Vec::new();
        for (target_id, target) in self.storage.get_combat_snapshot_light() {
            let duration_ms = self
                .last_timestamp
                .unwrap_or(target.last_damage_time)
                .saturating_sub(target.first_damage_time)
                .max(0);
            let mut players = Vec::new();
            for (actor_id, actor) in target.actors {
                let mut skills = Vec::new();
                for ((skill_id, dot), skill) in actor.skills {
                    skills.push(json!({"skill_id": skill_id, "dot": dot,
                        "damage": skill.total_damage, "hits": skill.hit_count,
                        "critical_hits": skill.crit_count, "multi_hit_damage": skill.multi_hit_damage}));
                }
                skills.sort_by_key(|s| {
                    (
                        s["skill_id"].as_i64().unwrap_or(0),
                        s["dot"].as_bool().unwrap_or(false),
                    )
                });
                players.push(json!({"actor_id": actor_id, "name": names.get(&actor_id),
                    "damage": actor.total_damage,
                    "dps": if duration_ms > 0 { actor.total_damage as f64 * 1000.0 / duration_ms as f64 } else { 0.0 },
                    "contribution": if target.total_damage > 0 { actor.total_damage as f64 / target.total_damage as f64 } else { 0.0 },
                    "skills": skills}));
            }
            players.sort_by_key(|p| p["actor_id"].as_i64().unwrap_or(0));
            targets.push(
                json!({"target_id": target_id, "damage": target.total_damage,
                "duration_ms": duration_ms, "players": players}),
            );
        }
        targets.sort_by_key(|t| t["target_id"].as_i64().unwrap_or(0));
        let mut healing = Vec::new();
        for (actor_id, skills) in self.storage.get_heal_snapshot() {
            for ((skill_id, hot), skill) in skills {
                healing.push(json!({"actor_id": actor_id, "skill_id": skill_id,
                    "hot": hot, "healing": skill.total_heal, "ticks": skill.tick_count}));
            }
        }
        healing.sort_by_key(|h| {
            (
                h["actor_id"].as_i64().unwrap_or(0),
                h["skill_id"].as_i64().unwrap_or(0),
                h["hot"].as_bool().unwrap_or(false),
            )
        });
        json!({"client": self.client, "compatibility": "unverified",
            "status": if targets.is_empty() && healing.is_empty() { "no_combat_detected" } else { "combat_detected" },
            "targets": targets, "healing": healing,
            "active_flows": self.flows.len(),
            "discarded_protocol_bytes": self.discarded_protocol_bytes,
            "pending_bytes": self.flows.values().map(|f| f.pending.len()).sum::<usize>()})
    }
}

fn decode_hex(text: &str) -> Result<Vec<u8>, String> {
    if text.len() > MAX_BUFFER * 2 || !text.len().is_multiple_of(2) || !text.is_ascii() {
        return Err("invalid or oversized hexadecimal payload".into());
    }
    (0..text.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&text[i..i + 2], 16)
                .map_err(|_| "invalid hexadecimal payload".into())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    // Synthetic 05 38 DoT/HoT wire record; NOT a player's captured session.
    fn tick(effect: u8, amount: u8) -> Vec<u8> {
        // Use plausible unbound entity IDs. IDs <100 need identity records
        // before the upstream healing parser accepts them.
        let mut body = vec![0x05, 0x38, 120, effect, 100, 0];
        body.extend((10000u32).to_le_bytes()); // skill code 100 after /100
        body.push(amount);
        let mut frame = vec![(body.len() + 4) as u8];
        frame.extend(body);
        frame
    }
    fn input(bytes: &[u8], timestamp_ms: i64) -> Input {
        Input {
            flow: "test".into(),
            timestamp_ms,
            payload_hex: bytes.iter().map(|b| format!("{b:02x}")).collect(),
            close: false,
        }
    }

    #[test]
    fn both_client_profiles_decode_damage_and_heal() {
        for client in ["steam", "purple"] {
            let mut backend = Backend::new(client, HashSet::from([100])).unwrap();
            let snapshot = backend.feed(input(&tick(2, 50), 1000)).unwrap();
            assert_eq!(snapshot["targets"][0]["damage"], 50);
            let snapshot = backend.feed(input(&tick(0x0B, 30), 2000)).unwrap();
            assert_eq!(snapshot["healing"][0]["healing"], 30, "{snapshot}");
            assert_eq!(snapshot["targets"][0]["players"][0]["dps"], 50.0);
            assert_eq!(snapshot["compatibility"], "unverified");
        }
    }

    #[test]
    fn protocol_frame_split_is_not_counted_early() {
        let mut backend = Backend::new("steam", HashSet::from([100])).unwrap();
        let frame = tick(2, 50);
        let snapshot = backend.feed(input(&frame[..4], 1000)).unwrap();
        assert_eq!(snapshot["status"], "no_combat_detected");
        assert_eq!(snapshot["pending_bytes"], 4);
        let snapshot = backend.feed(input(&frame[4..], 1001)).unwrap();
        assert_eq!(snapshot["targets"][0]["damage"], 50);
    }

    #[test]
    fn unknown_dot_and_status_do_not_become_damage() {
        let mut backend = Backend::new("purple", HashSet::new()).unwrap();
        assert_eq!(
            backend.feed(input(&tick(2, 50), 1000)).unwrap()["status"],
            "no_combat_detected"
        );
        assert_eq!(
            backend.feed(input(&tick(0, 50), 1001)).unwrap()["status"],
            "no_combat_detected"
        );
    }

    #[test]
    fn malformed_hex_and_time_reversal_rejected() {
        assert!(Backend::new("other", HashSet::new()).is_err());
        let mut backend = Backend::new("steam", HashSet::new()).unwrap();
        let mut bad = input(&[], 0);
        bad.payload_hex = "xx".into();
        assert!(backend.feed(bad).is_err());
        backend.feed(input(&[], 100)).unwrap();
        assert!(backend.feed(input(&[], 99)).is_err());
    }

    #[test]
    fn closed_flows_release_capacity_and_keep_combat_totals() {
        for client in ["steam", "purple"] {
            let mut backend = Backend::new(client, HashSet::from([100])).unwrap();
            backend.feed(input(&tick(2, 50), 1000)).unwrap();
            for index in 0..100 {
                let mut record = input(&tick(2, 50)[..4], 1001 + index);
                record.flow = format!("connection-{index}");
                backend.feed(record).unwrap();
                let mut close = input(&[], 1001 + index);
                close.flow = format!("connection-{index}");
                close.close = true;
                let snapshot = backend.feed(close).unwrap();
                assert_eq!(snapshot["active_flows"], 1);
                assert_eq!(snapshot["targets"][0]["damage"], 50);
            }
            assert_eq!(backend.snapshot()["discarded_protocol_bytes"], 400);
        }
    }

    #[test]
    fn active_flow_limit_and_invalid_close_remain_strict() {
        let mut backend = Backend::new("steam", HashSet::new()).unwrap();
        for index in 0..MAX_FLOWS {
            let mut record = input(&[], 1000);
            record.flow = index.to_string();
            backend.feed(record).unwrap();
        }
        assert!(backend.feed(input(&[], 1000)).is_err());
        let mut close = input(&[1], 1000);
        close.flow = "0".into();
        close.close = true;
        assert!(backend.feed(close).is_err());
        assert_eq!(backend.snapshot()["active_flows"], MAX_FLOWS);
        let mut close = input(&[], 1000);
        close.flow = "0".into();
        close.close = true;
        backend.feed(close).unwrap();
        backend.feed(input(&[], 1000)).unwrap();
    }

    #[test]
    fn close_preserves_duration_but_enforces_record_order() {
        let mut backend = Backend::new("steam", HashSet::from([100])).unwrap();
        backend.feed(input(&tick(2, 50), 1000)).unwrap();
        backend.feed(input(&tick(2, 50), 2000)).unwrap();
        let before = backend.snapshot()["targets"].clone();
        let mut close = input(&[], 5000);
        close.close = true;
        assert_eq!(backend.feed(close).unwrap()["targets"], before);
        assert!(backend.feed(input(&[], 4999)).is_err());
        backend.feed(input(&[], 5000)).unwrap();
    }
}
