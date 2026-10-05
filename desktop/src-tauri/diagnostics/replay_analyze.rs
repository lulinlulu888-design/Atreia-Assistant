// Replays a raw packet dump (from packet_dump.exe) through the PRODUCTION
// parsing pipeline (StreamAssembler + StreamProcessor) to determine, per flow,
// how many damage events the CURRENT parser can still extract.
//
//   cargo run --bin replay_analyze -- <dumpfile> [data_dir]
//
// If the top combat flows yield 0 damage events, the wire protocol changed
// structurally (not just the port-lock signature).

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use a2tools_dps_meter_lib::capture::stream_assembler::StreamAssembler;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};

fn decode_hex(hex: &str) -> Vec<u8> {
    let h = hex.trim();
    let mut out = Vec::with_capacity(h.len() / 2);
    let b = h.as_bytes();
    let mut i = 0;
    while i + 1 < b.len() {
        let hi = hexval(b[i]);
        let lo = hexval(b[i + 1]);
        if let (Some(hi), Some(lo)) = (hi, lo) {
            out.push((hi << 4) | lo);
        }
        i += 2;
    }
    out
}
fn hexval(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}

struct Flow {
    packets: Vec<Vec<u8>>,
    bytes: usize,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dump_path = args.get(1).cloned().unwrap_or_else(|| {
        std::fs::read_to_string("dumpfile.txt")
            .map(|s| s.trim().to_string())
            .unwrap_or_default()
    });
    if dump_path.is_empty() {
        eprintln!("usage: replay_analyze <dumpfile> [data_dir]");
        return;
    }
    let data_dir = args.get(2).cloned().unwrap_or_else(|| "src/data".to_string());

    // Load i18n lookups + dot ids (best effort).
    let skill_lookup = Arc::new(SkillLookup::new());
    let npc_lookup = Arc::new(NpcLookup::new());
    if let Ok(t) = std::fs::read_to_string(format!("{}/i18n/skills/en.json", data_dir)) {
        skill_lookup.load_from_json(&t);
        println!("[i] loaded skills/en.json");
    } else {
        println!("[!] skills json not found under {} (continuing empty)", data_dir);
    }
    if let Ok(t) = std::fs::read_to_string(format!("{}/i18n/npcs/en.json", data_dir)) {
        npc_lookup.load_from_json(&t);
    }
    let dot_ids: HashSet<i32> = std::fs::read_to_string(format!("{}/dot_skill_ids.json", data_dir))
        .ok()
        .and_then(|t| serde_json::from_str::<Vec<i32>>(&t).ok())
        .map(|v| v.into_iter().collect())
        .unwrap_or_default();
    println!("[i] dot ids loaded: {}", dot_ids.len());

    // Read dump, group by flow.
    let content = match std::fs::read_to_string(&dump_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("cannot read {}: {}", dump_path, e);
            return;
        }
    };
    let mut flows: HashMap<String, Flow> = HashMap::new();
    for line in content.lines() {
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.splitn(6, '|').collect();
        if parts.len() < 6 {
            continue;
        }
        let flow_key = parts[1].to_string();
        let data = decode_hex(parts[5]);
        if data.is_empty() {
            continue;
        }
        let f = flows.entry(flow_key).or_insert_with(|| Flow { packets: Vec::new(), bytes: 0 });
        f.bytes += data.len();
        f.packets.push(data);
    }

    println!("\nAnalyzing {} flows from {}\n", flows.len(), dump_path);

    let mut results: Vec<(String, usize, usize, i64, i64)> = Vec::new(); // flow, pkts, bytes, dmg_events, total_dmg

    for (flow, f) in &flows {
        let ds = Arc::new(DataStorage::new());
        let mut proc = StreamProcessor::new(ds.clone(), skill_lookup.clone(), npc_lookup.clone());
        proc.set_dot_skill_ids(dot_ids.clone());
        let mut asm = StreamAssembler::new();

        for pkt in &f.packets {
            asm.process_chunk(pkt, &mut proc);
        }

        let dmg_events = ds.damage_generation();
        let snap = ds.get_combat_snapshot();
        let total_dmg: i64 = snap.values().map(|t| t.total_damage).sum();
        results.push((flow.clone(), f.packets.len(), f.bytes, dmg_events, total_dmg));
    }

    // Sort by damage events, then bytes.
    results.sort_by(|a, b| b.3.cmp(&a.3).then(b.2.cmp(&a.2)));

    println!(
        "{:<46} {:>7} {:>10} {:>11} {:>14}",
        "flow (src->dst)", "pkts", "bytes", "dmg_events", "total_damage"
    );
    println!("{}", "-".repeat(92));
    for (flow, pkts, bytes, ev, dmg) in results.iter().take(30) {
        let f = if flow.len() > 46 { flow[flow.len() - 46..].to_string() } else { flow.clone() };
        println!("{:<46} {:>7} {:>10} {:>11} {:>14}", f, pkts, bytes, ev, dmg);
    }

    let total_events: i64 = results.iter().map(|r| r.3).sum();
    println!("\nTOTAL damage events parsed across ALL flows: {}", total_events);
    if total_events == 0 {
        println!(">>> The current parser extracts ZERO damage. The wire protocol/framing changed structurally.");
    } else {
        println!(">>> Parser still works on at least one flow — the failure is likely port detection / signature only.");
    }
}
