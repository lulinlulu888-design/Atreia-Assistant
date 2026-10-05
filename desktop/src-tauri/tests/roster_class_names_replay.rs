//! Party members named from the roster when their spawns came before the meter.
//!
//! `packets_20261003_005123.txt` (A2_ROSTER_CAPTURE), 2026-10-03: the capture
//! starts with the party already in a dungeon. The roster arrives in the first
//! seconds; the player spawns that tie Stellargoth, Nono, Wowsoanime and Nyxie
//! to their entity ids only come four minutes in, after two bosses, which the
//! meter and History showed as bare ids. The roster states each member's
//! class, and each of those classes has one unnamed player fighting.

use std::sync::Arc;

use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::combat::dps_calculator::DpsCalculator;
use a2tools_dps_meter_lib::combat::ping_tracker::PingTracker;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};
use a2tools_dps_meter_lib::share::read_capture;

#[test]
fn party_members_are_named_from_the_roster_before_their_spawns() {
    let Ok(path) = std::env::var("A2_ROSTER_CAPTURE") else {
        eprintln!("A2_ROSTER_CAPTURE unset; skipping");
        return;
    };
    let storage = Arc::new(DataStorage::new());
    let mut processor =
        StreamProcessor::new(storage.clone(), Arc::new(SkillLookup::new()), Arc::new(NpcLookup::new()));
    let npcs = Arc::new(NpcLookup::new());
    npcs.load_from_json(&std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/../src/data/i18n/npcs/en.json")).unwrap());
    let mut calc = DpsCalculator::new(storage.clone(), Arc::new(SkillLookup::new()), npcs, Arc::new(PingTracker::new()));
    let mut acc = PacketAccumulator::new();

    // Replayed at the captured times, saving fights as the app does when one
    // ends, so the History records carry the names known at that moment.
    let mut saved = Vec::new();
    for (i, p) in read_capture(std::path::Path::new(&path)).unwrap().into_iter().enumerate() {
        a2tools_dps_meter_lib::clock::set_override(Some(p.captured_at_ms));
        processor.set_override_timestamp(Some(p.captured_at_ms));
        acc.append(&p.bytes);
        let used = processor.consume_stream(acc.snapshot());
        if used > 0 {
            acc.discard_bytes(used);
        }
        if i % 50 == 0 {
            calc.get_dps();
            saved.extend(calc.snapshot_boss_fights());
        }
    }
    a2tools_dps_meter_lib::clock::set_override(None);

    for (id, name) in [(199, "Stellargoth"), (1803, "Nono"), (9250, "Wowsoanime"), (1352, "Nyxie"), (9873, "Sincarion")] {
        assert_eq!(storage.get_nickname(id).as_deref(), Some(name), "entity {id}");
    }

    // Nyxie's self record names her server, Europe's 2304, which is the
    // region every saved fight is uploaded under.
    assert!(saved.iter().all(|r| r.server_id == 2304), "{:?}", saved.iter().map(|r| r.server_id).collect::<Vec<_>>());

    // History shows names masked ("Wo****e"); a row with no name showed its
    // entity id masked instead ("92*0"), all digits and asterisks.
    let first_boss_start = saved.iter().map(|r| r.start_time_ms).min().expect("a boss fight was saved");
    for record in saved.iter().filter(|r| r.start_time_ms == first_boss_start) {
        let ids: Vec<_> = record
            .actors
            .iter()
            .filter(|a| a.nickname.chars().all(|c| c.is_ascii_digit() || c == '*'))
            .map(|a| (a.actor_id, a.nickname.clone()))
            .collect();
        assert!(ids.is_empty(), "{}: rows without a name {ids:?}", record.boss_name);
    }
}
