//! Replays the meter's own packet logs across character changes and checks who
//! it thinks the local player is at each step.
//!
//! The captures (2026-10-01, the app's `packets_*.txt` logs) cover:
//!
//! - `packets_20261001_040431.txt`: a new character on Ariel (EU) playing the
//!   tutorial under the game's `$Kc03nyeQHr4` placeholder (entity 3877), then
//!   named Spirtmasta (entity 4294) at 04:07:45.
//! - `packets_20261001_041517.txt`: back to character select and into
//!   Spirtmasta again (new entity 10044), then onto Nezekan (Asia) as Amber1
//!   (entity 4098).
//!
//! The meter started those sessions believing it was "Aveline", a name left
//! over from an earlier session, and showed it on the new character's row.
//! Paths come from A2_IDENTITY_CAPTURE_TUTORIAL and A2_IDENTITY_CAPTURE_SWITCH;
//! each part skips when its variable is unset.

use std::sync::Arc;

use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};

const STALE_NAME: &str = "Aveline";

struct Replay {
    storage: Arc<DataStorage>,
    processor: StreamProcessor,
    acc: PacketAccumulator,
    lines: Vec<(String, Vec<u8>)>,
    next: usize,
}

impl Replay {
    fn new(path: &str) -> Self {
        let storage = Arc::new(DataStorage::new());
        // What the UI does at startup with the name it remembered.
        storage.set_local_character_name(Some(STALE_NAME.to_string()));
        let processor = StreamProcessor::new(
            storage.clone(),
            Arc::new(SkillLookup::new()),
            Arc::new(NpcLookup::new()),
        );
        let text = std::fs::read_to_string(path).expect("capture readable");
        let lines = text
            .lines()
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .filter_map(|l| {
                let mut parts = l.splitn(3, '|');
                let ts = parts.next()?;
                let _stream = parts.next()?;
                Some((ts.to_string(), decode_hex(parts.next()?)?))
            })
            .collect();
        Self { storage, processor, acc: PacketAccumulator::new(), lines, next: 0 }
    }

    /// Feed packets up to (not including) `until`, an ISO-8601 prefix.
    fn until(&mut self, until: &str) -> &DataStorage {
        while let Some((ts, bytes)) = self.lines.get(self.next) {
            if !until.is_empty() && ts.as_str() >= until {
                break;
            }
            self.acc.append(bytes);
            let consumed = self.processor.consume_stream(self.acc.snapshot());
            if consumed > 0 {
                self.acc.discard_bytes(consumed);
            }
            self.next += 1;
        }
        &self.storage
    }
}

fn who(storage: &DataStorage) -> (Option<i64>, Option<String>, bool) {
    (
        storage.local_player_id(),
        storage.local_character_name(),
        storage.local_identity_from_game(),
    )
}

fn row_name(storage: &DataStorage, id: i64) -> Option<String> {
    storage.get_nicknames().get(&(id as i32)).cloned()
}

#[test]
fn tutorial_character_then_its_chosen_name() {
    let Ok(path) = std::env::var("A2_IDENTITY_CAPTURE_TUTORIAL") else {
        eprintln!("A2_IDENTITY_CAPTURE_TUTORIAL unset; skipping");
        return;
    };
    let mut r = Replay::new(&path);

    // Mid-tutorial: the game has said this is you, and has not named you.
    let s = r.until("2026-10-01T04:06:30");
    assert_eq!(who(s), (Some(3877), None, true), "tutorial character, stale name dropped");
    assert_eq!(row_name(s, 3877), None, "no placeholder, and no leftover name, on the row");

    // Named and in the world.
    let s = r.until("");
    assert_eq!(who(s), (Some(4294), Some("Spirtmasta".into()), true));
    assert_eq!(row_name(s, 4294).as_deref(), Some("Spirtmasta"));
    assert!(
        !s.get_nicknames().values().any(|n| n == STALE_NAME),
        "the remembered name must not end up on anyone"
    );
}

#[test]
fn character_select_and_a_server_switch() {
    let Ok(path) = std::env::var("A2_IDENTITY_CAPTURE_SWITCH") else {
        eprintln!("A2_IDENTITY_CAPTURE_SWITCH unset; skipping");
        return;
    };
    let mut r = Replay::new(&path);

    // Back from character select into Spirtmasta, on a new entity id.
    let s = r.until("2026-10-01T04:16:30");
    assert_eq!(who(s), (Some(10044), Some("Spirtmasta".into()), true));

    // Then Amber1 on Nezekan.
    let s = r.until("");
    assert_eq!(who(s), (Some(4098), Some("Amber1".into()), true));
    assert_eq!(row_name(s, 4098).as_deref(), Some("Amber1"));
}

/// `packets_20261001_212712.txt` (A2_IDENTITY_CAPTURE_MIDSESSION): a player's
/// meter started while they were already in the world as ApexZ, a Sorcerer on
/// Ventus (EU), so the login self record never went past it. Their name only
/// arrives in the `04 8d` loot records sent as each mob they kill dies, which
/// tag the owner, entity 1454, with server id 1305 and the name.
#[test]
fn meter_started_mid_session() {
    let Ok(path) = std::env::var("A2_IDENTITY_CAPTURE_MIDSESSION") else {
        eprintln!("A2_IDENTITY_CAPTURE_MIDSESSION unset; skipping");
        return;
    };

    // The first kill says who you are, whatever name the meter started with.
    for start_name in [None, Some(STALE_NAME), Some("ApexZ")] {
        let mut r = Replay::new(&path);
        r.storage.set_local_character_name(start_name.map(str::to_string));
        let s = r.until("2026-10-01T21:27:22");
        assert_eq!(s.local_player_id(), None, "{start_name:?}: before the first kill");
        let s = r.until("2026-10-01T21:27:23");
        assert_eq!(who(s), (Some(1454), Some("ApexZ".into()), true), "{start_name:?}");
        let s = r.until("");
        assert_eq!(who(s), (Some(1454), Some("ApexZ".into()), true), "{start_name:?}");
        assert_eq!(row_name(s, 1454).as_deref(), Some("ApexZ"));
    }
}

fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    let hex = hex.trim();
    if !hex.len().is_multiple_of(2) {
        return None;
    }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).ok())
        .collect()
}
