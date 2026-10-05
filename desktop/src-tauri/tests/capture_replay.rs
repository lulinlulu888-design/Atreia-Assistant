//! Replays a real packet capture through the parser and asserts the identity /
//! summon-attribution results.
//!
//! The capture is a 5-player party clearing a dungeon. Before the mask-driven
//! identity records and the spawn `parent_key` link went in, this session showed
//! two of the five players as bare `#id` rows and scattered their pets across a
//! dozen more — one player (entity 48) was missing entirely, because the damage
//! parser's `>= 100` resync gate discarded every record they appeared in.
//!
//! The capture path is supplied by A2_REPLAY_CAPTURE; the test skips when unset
//! so it never fails on a machine that does not have the file.

use std::collections::HashMap;
use std::sync::Arc;

use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::combat::dps_calculator::DpsCalculator;
use a2tools_dps_meter_lib::combat::ping_tracker::PingTracker;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};

/// Replay the capture, stopping at `until` (an ISO-8601 prefix, compared
/// lexicographically). Entity ids are session-scoped and get reissued on every
/// zone change, so "who is entity N" is only a question with an answer within
/// one zone — replaying past the end of the run would assert against the ids the
/// game handed out on the way back to town.
fn replay(path: &str, until: &str) -> Arc<DataStorage> {
    let storage = Arc::new(DataStorage::new());
    let mut processor = StreamProcessor::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
    );

    let text = std::fs::read_to_string(path).expect("capture readable");
    let mut streams: HashMap<String, PacketAccumulator> = HashMap::new();

    for line in text.lines() {
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut parts = line.splitn(3, '|');
        let (ts, key, hex) = match (parts.next(), parts.next(), parts.next()) {
            (Some(a), Some(b), Some(c)) => (a, b, c),
            _ => continue,
        };
        if !until.is_empty() && ts >= until {
            break;
        }
        let Some(bytes) = decode_hex(hex) else { continue };

        let acc = streams
            .entry(key.to_string())
            .or_insert_with(PacketAccumulator::new);
        acc.append(&bytes);
        let consumed = processor.consume_stream(acc.snapshot());
        if consumed > 0 {
            acc.discard_bytes(consumed);
        }
    }
    storage
}

fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    if !hex.len().is_multiple_of(2) {
        return None;
    }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).ok())
        .collect()
}

#[test]
fn resolves_party_identities_and_summon_owners() {
    let Ok(path) = std::env::var("A2_REPLAY_CAPTURE") else {
        eprintln!("A2_REPLAY_CAPTURE unset — skipping");
        return;
    };
    // Cut off just after the run's last damage (18:47:25.95) and before the
    // party leaves the instance at 18:47:42, which reissues everyone's ids.
    let storage = replay(&path, "2026-08-15T18:47:30");

    let nicknames = storage.get_nicknames();
    let by_name: HashMap<&str, i32> = nicknames.iter().map(|(&id, n)| (n.as_str(), id)).collect();

    // Every one of the five party members must resolve to an entity id. Grandine
    // (48) and Misti (4099) are the two that used to stay unnamed: Grandine sits
    // under the old id floor, and Misti is the local player, whose record uses
    // the `33 36` opcode with mask2 = 0x37 rather than the 0x0B/0x37 byte pair
    // the previous self-detail matcher looked for.
    for name in ["Misti", "Grandine", "M7", "九州依然在", "丨Mamepoko丨"] {
        assert!(
            by_name.contains_key(name),
            "party member {name} was not identified; resolved names: {:?}",
            nicknames.values().collect::<Vec<_>>()
        );
    }
    assert_eq!(by_name.get("Misti"), Some(&4099), "Misti entity id");
    assert_eq!(by_name.get("Grandine"), Some(&48), "Grandine entity id");

    // The local player is bound from the `33 36` self record without the user
    // having configured a character name.
    assert_eq!(storage.local_player_id(), Some(4099), "local player");

    // Summons resolve to their owner through the spawn's parent_key, which works
    // even for owners who had not been named when the summon spawned.
    let summons = storage.get_summon_data();
    let mut owned: HashMap<i32, usize> = HashMap::new();
    for &owner in summons.values() {
        *owned.entry(owner).or_default() += 1;
    }
    // The Spiritmaster (Grandine) and the Sorcerer (Misti) are the two classes
    // whose spells spawn damage-dealing entities in this capture.
    assert!(
        owned.get(&48).copied().unwrap_or(0) >= 40,
        "expected Grandine's pets to link to entity 48, got {owned:?}"
    );
    assert!(
        owned.get(&4099).copied().unwrap_or(0) >= 15,
        "expected Misti's spell entities to link to entity 4099, got {owned:?}"
    );

    // Party roster: names, and the combat power shown next to them.
    let party = storage.get_party_members();
    assert_eq!(party.len(), 5, "party roster members: {party:?}");
    let misti = party.get("Misti").expect("Misti in roster");
    assert_eq!(misti.level, 50);
    assert_eq!(misti.gear_score, 6008);
    assert_eq!(misti.combat_power, 833_876);
    assert_eq!(misti.server_id, 2014);
    for (name, member) in &party {
        assert!(
            (100_000..10_000_000).contains(&member.combat_power),
            "{name} combat power out of range: {}",
            member.combat_power
        );
    }
}

/// The roster id every party member carries, which log sharing uses instead of a
/// character name.
///
/// Two properties matter and neither is obvious from the parse: `dbid` must be
/// populated for everyone (it was read and thrown away before), and `server_id`
/// must really be its top sixteen bits. The second is a self-check on the
/// plumbing — the roster parse *anchors* on `server_id` to find combat power, so
/// if these two ever disagreed the anchor would be searching for the wrong value
/// and the numbers past it would be silently wrong.
#[test]
fn party_roster_carries_a_stable_id_per_member() {
    let Ok(path) = std::env::var("A2_REPLAY_CAPTURE") else {
        eprintln!("A2_REPLAY_CAPTURE unset — skipping");
        return;
    };
    let storage = replay(&path, "2026-08-15T18:47:30");
    let party = storage.get_party_members();
    assert_eq!(party.len(), 5, "party roster members: {party:?}");

    let mut seen = std::collections::HashSet::new();
    for (name, m) in &party {
        assert_ne!(m.dbid, 0, "{name} has no dbid");
        assert_eq!(
            (m.dbid >> 48) as u16,
            m.server_id,
            "{name}: server_id {} is not the top 16 bits of dbid {:#x}",
            m.server_id,
            m.dbid
        );
        assert!(seen.insert(m.dbid), "{name} shares a dbid with another member");
    }

    // All five are on one world, so the ids differ only below the server half —
    // i.e. the low 48 bits are what actually identifies a person.
    let low_bits: std::collections::HashSet<u64> =
        party.values().map(|m| m.dbid & 0x0000_FFFF_FFFF_FFFF).collect();
    assert_eq!(low_bits.len(), 5, "low 48 bits should be distinct per member");
}

/// What the meter actually puts on screen: five named rows, no leftover `#id`
/// rows for the pets, and a combat power on every one of them.
#[test]
fn meter_rows_are_all_named_with_combat_power() {
    let Ok(path) = std::env::var("A2_REPLAY_CAPTURE") else {
        eprintln!("A2_REPLAY_CAPTURE unset — skipping");
        return;
    };
    let storage = replay(&path, "2026-08-15T18:47:30");

    let mut calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    calc.set_target_selection_mode("allTargets");
    let dps = calc.get_dps();

    let mut rows: Vec<_> = dps.map.iter().map(|(&id, d)| (id, d)).collect();
    rows.sort_by(|a, b| b.1.amount.total_cmp(&a.1.amount));

    println!("battle_time={}ms  rows={}", dps.battle_time, rows.len());
    for (id, d) in &rows {
        println!(
            "  #{id:<7} {:<16} {:<14} dmg={:>12.0}  {:>5.1}%  cp={}",
            d.nickname, d.job, d.amount, d.damage_contribution, d.combat_power
        );
    }

    // Anything the parser could not name shows up as a bare id — that is exactly
    // the failure this capture was reported for, so no row may be in that state.
    let unnamed: Vec<_> = rows
        .iter()
        .filter(|(id, d)| d.nickname == id.to_string() || d.nickname.is_empty())
        .collect();
    assert!(unnamed.is_empty(), "unnamed rows on the meter: {unnamed:?}");

    let named: Vec<&str> = rows.iter().map(|(_, d)| d.nickname.as_str()).collect();
    for name in ["Misti", "Grandine", "M7", "九州依然在", "丨Mamepoko丨"] {
        assert!(named.contains(&name), "{name} missing from meter rows: {named:?}");
    }
    assert_eq!(rows.len(), 5, "expected exactly the five party members: {named:?}");

    for (id, d) in &rows {
        assert!(
            d.combat_power > 0,
            "row #{id} ({}) has no combat power",
            d.nickname
        );
    }
}

/// A Cleric's Divine Aura entities are created without any spawn packet, so the
/// `parent_key` link cannot fire. They must still collapse onto the Cleric — who
/// in this capture is himself unnamed, hence a pure id-to-id attribution.
#[test]
fn divine_auras_collapse_onto_an_unnamed_cleric() {
    let Ok(path) = std::env::var("A2_REPLAY_AURA_CAPTURE") else {
        eprintln!("A2_REPLAY_AURA_CAPTURE unset — skipping");
        return;
    };
    let storage = replay(&path, "");
    let mut calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    calc.set_target_selection_mode("allTargets");
    let dps = calc.get_dps();

    let mut rows: Vec<_> = dps.map.iter().map(|(&id, d)| (id, d)).collect();
    rows.sort_by(|a, b| b.1.amount.total_cmp(&a.1.amount));
    for (id, d) in &rows {
        println!("  #{id:<7} {:<12} dmg={:>10.0}", d.job, d.amount);
    }
    let ids: Vec<i32> = rows.iter().map(|(id, _)| *id).collect();
    for aura in [31168, 21357, 31307, 37274] {
        assert!(!ids.contains(&aura), "aura #{aura} still has its own row: {ids:?}");
    }
    assert!(ids.contains(&5492), "the Cleric (5492) should be a row: {ids:?}");
}

#[test]
#[ignore = "diagnostic"]
fn dump_party_roster() {
    let Ok(path) = std::env::var("A2_REPLAY_PARTY_CAPTURE") else { return };
    let storage = replay(&path, "");
    let party = storage.get_party_members();
    println!("roster members: {}", party.len());
    let mut v: Vec<_> = party.iter().collect();
    v.sort_by_key(|(_, m)| m.slot);
    for (name, m) in v {
        println!(
            "  slot={} {:<18} lvl={} gear={} cp={} srv={} dbid={:#018x} low48={:#014x} ({})",
            m.slot, name, m.level, m.gear_score, m.combat_power, m.server_id,
            m.dbid, m.dbid & 0x0000_FFFF_FFFF_FFFF, m.dbid & 0x0000_FFFF_FFFF_FFFF
        );
    }
    println!("local player id: {:?}  name: {:?}", storage.local_player_id(), storage.local_character_name());

    let mut calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    calc.set_target_selection_mode("allTargets");
    let dps = calc.get_dps();
    println!("meter rows: {}", dps.map.len());
    let mut rows: Vec<_> = dps.map.iter().collect();
    rows.sort_by(|a, b| b.1.amount.total_cmp(&a.1.amount));
    for (id, d) in rows {
        println!("  #{id:<7} {:<18} job={:<8} dmg={:>10.0} cp={}", d.nickname, d.job, d.amount, d.combat_power);
    }
}

/// A supporter's name renders gold on everyone's meter — including the meters of
/// people who are not supporters, which is the whole requirement.
///
/// Uses the real capture so the join it exercises is the real one: meter row ->
/// character name -> party roster -> `dbid` -> hashed roster entry. A unit test
/// with a synthetic row would not touch any of that.
#[test]
fn a_supporter_in_the_party_is_flagged_on_the_local_players_meter() {
    let Ok(path) = std::env::var("A2_REPLAY_CAPTURE") else {
        eprintln!("A2_REPLAY_CAPTURE unset — skipping");
        return;
    };
    let storage = replay(&path, "2026-08-15T18:47:30");

    // Grandine is a supporter; the local player (Misti) is not. Gold has to
    // appear for someone else, on this machine.
    use a2tools_dps_meter_lib::supporters::{self, KeyKind};
    let roster = supporters::Roster::parse(&supporters::build(
        KeyKind::Name,
        b"test-salt",
        &["Grandine".to_string()],
    ))
    .expect("roster parses");
    storage.set_supporters(roster);

    let mut calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    calc.set_target_selection_mode("allTargets");
    let dps = calc.get_dps();

    let flagged: Vec<&str> = dps
        .map
        .values()
        .filter(|d| d.is_supporter)
        .map(|d| d.nickname.as_str())
        .collect();
    assert_eq!(
        flagged,
        vec!["Grandine"],
        "exactly the supporter should be flagged; got {flagged:?}"
    );

    // And it is cosmetic. Compared against a *separate* calculator over the same
    // storage with no roster, rather than by resetting this one — resetting
    // clears the damage, which would make this pass by comparing zero to zero.
    let before: Vec<(i32, f64)> = dps.map.iter().map(|(&id, d)| (id, d.amount)).collect();
    assert!(!before.is_empty(), "no rows to compare");

    storage.set_supporters(supporters::Roster::default());
    let mut plain_calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    plain_calc.set_target_selection_mode("allTargets");
    let plain = plain_calc.get_dps();

    assert!(
        plain.map.values().all(|d| !d.is_supporter),
        "clearing the roster must clear the flag"
    );
    for (id, amount) in before {
        let row = plain.map.get(&id).expect("the same rows without a roster");
        assert_eq!(row.amount, amount, "damage changed when the roster did");
    }
}

/// Check a capture for who the local supporter roster would gild.
///
/// A one-off for testing the gold name against your own play: point it at a
/// capture and a name, and it reports whether that row comes back flagged. Saves
/// having to get in game, zone, and squint at the overlay.
///
///   A2_REPLAY_CAPTURE=<capture> A2_SUPPORTER=<name> \
///     cargo test --test capture_replay who_would_be_gold -- --ignored --nocapture
#[test]
#[ignore = "diagnostic"]
fn who_would_be_gold() {
    let (Ok(path), Ok(name)) = (
        std::env::var("A2_REPLAY_CAPTURE"),
        std::env::var("A2_SUPPORTER"),
    ) else {
        eprintln!("A2_REPLAY_CAPTURE and A2_SUPPORTER must both be set — skipping");
        return;
    };
    let storage = replay(&path, "");

    use a2tools_dps_meter_lib::supporters::{self, KeyKind};
    let roster = supporters::Roster::parse(&supporters::build(
        KeyKind::Name,
        b"a2tools-supporters-v1",
        &[name.clone()],
    ))
    .expect("roster");
    println!("roster: {} entry for {name:?}", roster.len());
    storage.set_supporters(roster);

    let mut calc = DpsCalculator::new(
        storage.clone(),
        Arc::new(SkillLookup::new()),
        Arc::new(NpcLookup::new()),
        Arc::new(PingTracker::new()),
    );
    calc.set_target_selection_mode("allTargets");
    let dps = calc.get_dps();

    println!("meter rows:");
    let mut rows: Vec<_> = dps.map.iter().collect();
    rows.sort_by(|a, b| b.1.amount.total_cmp(&a.1.amount));
    for (id, d) in rows {
        println!(
            "  #{id:<7} {:<20} {}",
            d.nickname,
            if d.is_supporter { "GOLD" } else { "-" }
        );
    }
}
