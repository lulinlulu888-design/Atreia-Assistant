//! Hunting for the packets that carry equipped gear.
//!
//! The official armory is rate-limited, regional, and — by its own module's
//! account in `A2-Tools/src/armory.py` — cannot report which specialisation node
//! a player picked. A packet-sourced cache would not have those limits, but only
//! if we can find where the game states a character's equipment.
//!
//! Rather than guess at opcodes, this uses the item database A2-Tools already
//! has (`data/gamedata/_raw_items.json`, ~3.2 MB of real item ids) as an oracle:
//! decode every packet in a capture, look for little-endian u32s that are known
//! item ids, and report which opcodes carry clusters of them. A packet holding
//! six known item ids at once is an equipment record; one holding a single hit
//! is a coincidence.
//!
//!   A2_REPLAY_CAPTURE=... A2_ITEM_DB=.../\_raw_items.json \
//!     cargo test --test find_gear_packets -- --ignored --nocapture

use std::collections::{HashMap, HashSet};

use a2tools_dps_meter_lib::capture::framing::{self, FrameKind};
use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::read_varint;
use a2tools_dps_meter_lib::share;

/// Item ids from the A2-Tools game data dump.
fn load_item_ids(path: &str) -> HashSet<u32> {
    let text = std::fs::read_to_string(path).expect("item db");
    let value: serde_json::Value = serde_json::from_str(&text).expect("item db is json");
    let items = value
        .get("items")
        .and_then(|v| v.as_array())
        .expect("an `items` array");
    items
        .iter()
        .filter_map(|i| i.get("id").and_then(|v| v.as_u64()))
        .map(|v| v as u32)
        .collect()
}

/// Every plain packet in the capture, bundles decompressed, streams reassembled.
fn all_packets(path: &str) -> Vec<Vec<u8>> {
    fn inner(buf: &[u8], out: &mut Vec<Vec<u8>>, depth: usize) {
        if depth > 4 {
            return;
        }
        for f in framing::walk_inner(buf).frames {
            match f.kind {
                FrameKind::Packet => out.push(f.bytes(buf).to_vec()),
                FrameKind::Bundle => {
                    if let Some(d) = framing::decompress_bundle(f.payload(buf)) {
                        inner(&d, out, depth + 1);
                    }
                }
            }
        }
    }

    let mut out = Vec::new();
    let mut streams: HashMap<String, PacketAccumulator> = HashMap::new();
    for cap in share::read_capture(std::path::Path::new(path)).expect("capture") {
        let acc = streams
            .entry(cap.stream.clone())
            .or_insert_with(PacketAccumulator::new);
        acc.append(&cap.bytes);
        let buf = acc.snapshot().to_vec();
        let walk = framing::walk(&buf);
        for f in &walk.frames {
            match f.kind {
                FrameKind::Packet => out.push(f.bytes(&buf).to_vec()),
                FrameKind::Bundle => {
                    if let Some(d) = framing::decompress_bundle(f.payload(&buf)) {
                        inner(&d, &mut out, 1);
                    }
                }
            }
        }
        acc.discard_bytes(walk.consumed);
    }
    out
}

fn leading_opcode(packet: &[u8]) -> Option<[u8; 2]> {
    let li = read_varint(packet, 0);
    if li.length <= 0 {
        return None;
    }
    let o = li.length as usize;
    (o + 1 < packet.len()).then(|| [packet[o], packet[o + 1]])
}

#[test]
#[ignore = "diagnostic"]
fn which_packets_carry_item_ids() {
    let (Ok(capture), Ok(db)) = (
        std::env::var("A2_REPLAY_CAPTURE"),
        std::env::var("A2_ITEM_DB"),
    ) else {
        eprintln!("A2_REPLAY_CAPTURE and A2_ITEM_DB must both be set — skipping");
        return;
    };

    let items = load_item_ids(&db);
    println!("item database: {} ids", items.len());
    let sample: Vec<u32> = items.iter().take(3).copied().collect();
    println!("  e.g. {sample:?}");

    let packets = all_packets(&capture);
    println!("capture: {} packets", packets.len());

    // How many distinct known item ids each packet mentions.
    let mut per_opcode: HashMap<[u8; 2], (usize, usize)> = HashMap::new();
    let mut best: Vec<(usize, [u8; 2], Vec<u32>, Vec<u8>)> = Vec::new();

    for packet in &packets {
        if packet.len() < 8 {
            continue;
        }
        let mut hits: Vec<u32> = Vec::new();
        for w in packet.windows(4) {
            let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
            if items.contains(&v) && !hits.contains(&v) {
                hits.push(v);
            }
        }
        if hits.is_empty() {
            continue;
        }
        let op = leading_opcode(packet).unwrap_or([0, 0]);
        let e = per_opcode.entry(op).or_insert((0, 0));
        e.0 += 1;
        e.1 += hits.len();
        if hits.len() >= 2 {
            best.push((hits.len(), op, hits, packet.clone()));
        }
    }

    let mut rows: Vec<_> = per_opcode.into_iter().collect();
    rows.sort_by_key(|(_, (_, total))| std::cmp::Reverse(*total));
    println!("\nopcodes mentioning known item ids (packets, total id hits):");
    for (op, (count, total)) in rows.iter().take(25) {
        println!("  {:02X} {:02X}  packets={count:<6} ids={total}", op[0], op[1]);
    }

    best.sort_by_key(|(n, _, _, _)| std::cmp::Reverse(*n));
    println!("\nrichest packets (most distinct item ids in one packet):");
    for (n, op, hits, packet) in best.iter().take(8) {
        println!(
            "\n  opcode {:02X} {:02X}, {n} item ids, {} bytes",
            op[0],
            op[1],
            packet.len()
        );
        println!("    ids: {:?}", &hits[..hits.len().min(12)]);
        let hex: String = packet
            .iter()
            .take(160)
            .map(|b| format!("{b:02X}"))
            .collect::<Vec<_>>()
            .join(" ");
        println!("    {hex}");
    }

    if best.is_empty() {
        println!(
            "\nNo packet carried two or more known item ids. Equipment is probably \
             not broadcast during a dungeon run — try a capture that includes \
             logging in, zoning, or opening a character panel."
        );
    }
}

/// Where do the item-id clusters sit relative to the records we already parse?
///
/// If equipment hangs off the player-spawn record (`45 36`) then we already keep
/// those packets in the Evidence Slice, we already know whose entity id they
/// belong to, and the work is parsing rather than discovery.
#[test]
#[ignore = "diagnostic"]
fn where_do_item_clusters_sit() {
    let (Ok(capture), Ok(db)) = (
        std::env::var("A2_REPLAY_CAPTURE"),
        std::env::var("A2_ITEM_DB"),
    ) else {
        eprintln!("A2_REPLAY_CAPTURE and A2_ITEM_DB must both be set — skipping");
        return;
    };
    let items = load_item_ids(&db);
    let packets = all_packets(&capture);

    // Opcodes the parser already understands, so we can say whether equipment
    // rides along with something we keep.
    const KNOWN: &[([u8; 2], &str)] = &[
        ([0x33, 0x36], "self identity"),
        ([0x44, 0x36], "player spawn"),
        ([0x45, 0x36], "player spawn"),
        ([0x40, 0x36], "summon spawn"),
        ([0x02, 0x97], "party roster"),
        ([0x04, 0x38], "damage"),
    ];

    let mut preceded_by: HashMap<&str, usize> = HashMap::new();
    let mut clusters = 0usize;
    let mut unanchored = 0usize;
    let mut example: Option<(usize, Vec<u8>)> = None;

    for packet in &packets {
        // Positions of every known item id in this packet.
        let mut hits: Vec<usize> = Vec::new();
        for (i, w) in packet.windows(4).enumerate() {
            let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
            if items.contains(&v) {
                hits.push(i);
            }
        }
        if hits.len() < 4 {
            continue;
        }
        clusters += 1;
        let first = hits[0];

        // Walk backwards for the nearest opcode we recognise.
        let mut found = None;
        let window = first.saturating_sub(400);
        for j in (window..first).rev() {
            if j + 1 >= packet.len() {
                continue;
            }
            let pair = [packet[j], packet[j + 1]];
            if let Some((_, what)) = KNOWN.iter().find(|(k, _)| *k == pair) {
                found = Some((*what, first - j));
                break;
            }
        }
        match found {
            Some((what, distance)) => {
                *preceded_by.entry(what).or_default() += 1;
                if what.contains("spawn") && example.is_none() && hits.len() >= 8 {
                    example = Some((distance, packet.clone()));
                }
            }
            None => unanchored += 1,
        }
    }

    println!("item-id clusters (4+ ids in one packet): {clusters}");
    let mut rows: Vec<_> = preceded_by.into_iter().collect();
    rows.sort_by_key(|(_, n)| std::cmp::Reverse(*n));
    println!("nearest preceding record we already parse:");
    for (what, n) in rows {
        println!("  {what:<16} {n}");
    }
    println!("  {unanchored:<16} (nothing recognised within 400 bytes)");

    if let Some((distance, packet)) = example {
        println!("\nexample: cluster begins {distance} bytes after a spawn record");
        let hex: String = packet
            .iter()
            .take(260)
            .map(|b| format!("{b:02X}"))
            .collect::<Vec<_>>()
            .join(" ");
        println!("  {hex}");
    }
}

/// What does an equipment record actually look like?
///
/// The ids arrive in slot order (weapon 110x, armour 210x1..210x7, accessories
/// 310x), which is not something random bytes do — so the structure is there.
/// This prints the bytes *around* a cluster and the stride between consecutive
/// ids, which is what tells you the per-slot record size and where the enchant
/// level and grade would sit.
#[test]
#[ignore = "diagnostic"]
fn dump_an_equipment_record() {
    let (Ok(capture), Ok(db)) = (
        std::env::var("A2_REPLAY_CAPTURE"),
        std::env::var("A2_ITEM_DB"),
    ) else {
        eprintln!("A2_REPLAY_CAPTURE and A2_ITEM_DB must both be set — skipping");
        return;
    };
    let items = load_item_ids(&db);
    let packets = all_packets(&capture);

    let mut shown = 0;
    for packet in &packets {
        let mut hits: Vec<(usize, u32)> = Vec::new();
        for (i, w) in packet.windows(4).enumerate() {
            let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
            if items.contains(&v) {
                hits.push((i, v));
            }
        }
        // A full set is a weapon plus seven armour slots; 8 is a real loadout.
        if hits.len() < 8 {
            continue;
        }
        // Consecutive ids at a regular stride are a table, not coincidence.
        let strides: Vec<usize> = hits.windows(2).map(|w| w[1].0 - w[0].0).collect();
        let regular = strides.iter().filter(|&&s| s < 64).count();
        if regular < 5 {
            continue;
        }

        println!("\n=== packet, {} bytes, {} item ids ===", packet.len(), hits.len());
        println!("strides between ids: {:?}", &strides[..strides.len().min(14)]);

        let start = hits[0].0.saturating_sub(24);
        let end = (hits[hits.len() - 1].0 + 24).min(packet.len());
        for (offset, id) in hits.iter().take(14) {
            let from = offset.saturating_sub(8);
            let to = (offset + 16).min(packet.len());
            let hex: String = packet[from..to]
                .iter()
                .map(|b| format!("{b:02X}"))
                .collect::<Vec<_>>()
                .join(" ");
            println!("  @{offset:<6} id={id:<11} ctx: {hex}");
        }
        println!("  region {start}..{end}");

        shown += 1;
        if shown >= 3 {
            break;
        }
    }
    if shown == 0 {
        println!("No regular item table found — the ids may be spread rather than tabulated.");
    }
}

/// Whose gear is it?
///
/// A cached build is worthless without a character attached, and the item table
/// itself carries no name. The five party members' entity ids are known from the
/// replay tests, so: search backwards from each equipment table for a varint
/// equal to one of them, and see whether the binding is consistent.
#[test]
#[ignore = "diagnostic"]
fn what_identifies_the_owner_of_a_gear_table() {
    let (Ok(capture), Ok(db)) = (
        std::env::var("A2_REPLAY_CAPTURE"),
        std::env::var("A2_ITEM_DB"),
    ) else {
        eprintln!("A2_REPLAY_CAPTURE and A2_ITEM_DB must both be set — skipping");
        return;
    };
    let items = load_item_ids(&db);
    let packets = all_packets(&capture);

    // From tests/capture_replay.rs: the five players in this run.
    const KNOWN_ENTITIES: &[(i32, &str)] = &[
        (4099, "Misti"),
        (48, "Grandine"),
        (12490, "M7"),
        (7525, "JiuZhou"),
        (3691, "Mamepoko"),
    ];

    for packet in &packets {
        let mut hits: Vec<(usize, u32)> = Vec::new();
        for (i, w) in packet.windows(4).enumerate() {
            let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
            if items.contains(&v) {
                hits.push((i, v));
            }
        }
        if hits.len() < 8 {
            continue;
        }
        let strides: Vec<usize> = hits.windows(2).map(|w| w[1].0 - w[0].0).collect();
        if strides.iter().filter(|&&s| s < 64).count() < 5 {
            continue;
        }

        let first = hits[0].0;
        println!("\n=== gear table at {first}, {} items ===", hits.len());

        // The two bytes before the weapon id looked like a marker (60 0F).
        if first >= 2 {
            println!(
                "  2 bytes before first id: {:02X} {:02X}",
                packet[first - 2],
                packet[first - 1]
            );
        }

        // Any known entity id encoded as a varint in the preceding 300 bytes?
        let from = first.saturating_sub(300);
        let mut found = Vec::new();
        for j in from..first {
            let v = read_varint(packet, j);
            if v.length <= 0 {
                continue;
            }
            if let Some((id, who)) = KNOWN_ENTITIES.iter().find(|(id, _)| *id == v.value) {
                found.push((first - j, *id, *who, v.length));
            }
        }
        found.sort_by_key(|(d, _, _, _)| *d);
        if found.is_empty() {
            println!("  no known entity id within 300 bytes before the table");
        } else {
            for (distance, id, who, len) in found.iter().take(6) {
                println!("  -{distance:<4} entity {id} ({who}) as a {len}-byte varint");
            }
        }
    }
}
