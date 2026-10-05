// Simulates the EXACT CaptureDispatcher + CombatPortDetector logic (post-fix)
// over a raw packet dump, to validate that detection locks the correct flow
// (the loopback relay tunnel) and recovers full damage.
//
//   cargo run --bin sim_dispatch -- <dumpfile> [data_dir]

use std::collections::HashMap;
use std::sync::Arc;

use a2tools_dps_meter_lib::capture::stream_assembler::StreamAssembler;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};

// Pre-lock signature gate (mirrors capture_dispatcher::COMBAT_SIGNATURES).
const SIGS: &[&[u8]] = &[&[0x0E, 0x00, 0x36], &[0x06, 0x00, 0x36]];
const LOOPBACK_GRACE_MS: i64 = 2500;

const TLS_CONTENT_TYPES: [u8; 4] = [0x14, 0x15, 0x16, 0x17];
const TLS_VERSIONS: [u8; 5] = [0x00, 0x01, 0x02, 0x03, 0x04];

fn looks_like_tls(d: &[u8]) -> bool {
    d.len() >= 3 && TLS_CONTENT_TYPES.contains(&d[0]) && d[1] == 0x03 && TLS_VERSIONS.contains(&d[2])
}
fn contains(d: &[u8], n: &[u8]) -> bool {
    n.len() <= d.len() && d.windows(n.len()).any(|w| w == n)
}
fn contains_any(d: &[u8], sigs: &[&[u8]]) -> bool {
    sigs.iter().any(|s| contains(d, s))
}
fn is_loopback(dev: &str) -> bool {
    dev.to_lowercase().contains("loopback")
}
fn hexval(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}
fn decode_hex(h: &str) -> Vec<u8> {
    let b = h.trim().as_bytes();
    let mut out = Vec::with_capacity(b.len() / 2);
    let mut i = 0;
    while i + 1 < b.len() {
        if let (Some(hi), Some(lo)) = (hexval(b[i]), hexval(b[i + 1])) {
            out.push((hi << 4) | lo);
        }
        i += 2;
    }
    out
}

struct Pkt {
    ts: i64,
    src_port: u16,
    dst_port: u16,
    device: String,
    tls: bool,
    data: Vec<u8>,
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dump_path = args.get(1).cloned().unwrap_or_else(|| {
        std::fs::read_to_string("dumpfile.txt").map(|s| s.trim().to_string()).unwrap_or_default()
    });
    let data_dir = args.get(2).cloned().unwrap_or_else(|| "src/data".to_string());

    let skill_lookup = Arc::new(SkillLookup::new());
    let npc_lookup = Arc::new(NpcLookup::new());
    if let Ok(t) = std::fs::read_to_string(format!("{}/i18n/skills/en.json", data_dir)) {
        skill_lookup.load_from_json(&t);
    }
    if let Ok(t) = std::fs::read_to_string(format!("{}/i18n/npcs/en.json", data_dir)) {
        npc_lookup.load_from_json(&t);
    }
    let dot_ids: std::collections::HashSet<i32> =
        std::fs::read_to_string(format!("{}/dot_skill_ids.json", data_dir))
            .ok()
            .and_then(|t| serde_json::from_str::<Vec<i32>>(&t).ok())
            .map(|v| v.into_iter().collect())
            .unwrap_or_default();

    let content = std::fs::read_to_string(&dump_path).expect("read dump");
    let mut pkts: Vec<Pkt> = Vec::new();
    for line in content.lines() {
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let p: Vec<&str> = line.splitn(6, '|').collect();
        if p.len() < 6 {
            continue;
        }
        let ts: i64 = p[0].parse().unwrap_or(0);
        let (src, dst) = match p[1].split_once("->") {
            Some(x) => x,
            None => continue,
        };
        let src_port: u16 = src.rsplit(':').next().and_then(|s| s.parse().ok()).unwrap_or(0);
        let dst_port: u16 = dst.rsplit(':').next().and_then(|s| s.parse().ok()).unwrap_or(0);
        let device = p[2].to_string();
        let data = decode_hex(p[5]);
        if data.is_empty() {
            continue;
        }
        pkts.push(Pkt { ts, src_port, dst_port, device, tls: looks_like_tls(&data), data });
    }
    println!("Loaded {} packets from {}\n", pkts.len(), dump_path);

    // ---- Replicate dispatcher + detector ----
    let real_store = Arc::new(DataStorage::new());
    let mut assemblers: HashMap<(u16, u16), (StreamAssembler, StreamProcessor)> = HashMap::new();
    let mut locked_port: Option<u16> = None;
    let mut locked_device = String::new();
    let mut first_candidate_ms: i64 = 0;
    let mut candidates: HashMap<u16, String> = HashMap::new();

    for p in &pkts {
        let unlocked = locked_port.is_none();
        if let Some(port) = locked_port {
            if p.src_port != port {
                continue; // post-lock: server->client only
            }
        } else {
            if p.tls {
                continue;
            }
            if !contains_any(&p.data, SIGS) {
                continue;
            }
        }

        let key = (p.src_port.min(p.dst_port), p.src_port.max(p.dst_port));
        let (asm, proc) = assemblers.entry(key).or_insert_with(|| {
            let mut pr = StreamProcessor::new(real_store.clone(), skill_lookup.clone(), npc_lookup.clone());
            pr.set_dot_skill_ids(dot_ids.clone());
            (StreamAssembler::new(), pr)
        });

        if unlocked {
            if first_candidate_ms == 0 {
                first_candidate_ms = p.ts;
            }
            candidates.entry(p.src_port).or_insert(p.device.clone());
        }

        let before = real_store.damage_generation();
        asm.process_chunk(&p.data, proc);

        if unlocked && real_store.damage_generation() != before {
            // confirm_candidate
            let dev = candidates.get(&p.src_port).cloned().unwrap_or_else(|| p.device.clone());
            let do_lock = if is_loopback(&dev) {
                true
            } else {
                let waited = p.ts - first_candidate_ms;
                !(first_candidate_ms != 0 && waited < LOOPBACK_GRACE_MS)
            };
            if do_lock {
                locked_port = Some(p.src_port);
                locked_device = dev.clone();
                assemblers.retain(|k, _| *k == key);
                println!(
                    "LOCKED port {} on device '{}' (loopback={}) at ts {}",
                    p.src_port, dev, is_loopback(&dev), p.ts
                );
            }
        }
    }

    match locked_port {
        None => println!("NEVER LOCKED."),
        Some(port) => {
            let ev = real_store.damage_generation();
            let snap = real_store.get_combat_snapshot();
            let total: i64 = snap.values().map(|t| t.total_damage).sum();
            println!(
                "\nLocked port {} (device '{}').\nStore: {} damage events, {} total damage, {} targets",
                port, locked_device, ev, total, snap.len()
            );

            // ---- Mob detection diagnostics ----
            let mobs = real_store.get_mob_data(); // actor_id -> mob_type_id
            println!("\nMob spawns registered (actor_id -> mob_type -> name):");
            if mobs.is_empty() {
                println!("  (none) — spawn packet parsing produced NO mob types.");
            }
            for (actor, mtype) in &mobs {
                let name = npc_lookup.get_npc_name(*mtype);
                let boss = npc_lookup.is_boss(*mtype);
                println!(
                    "  {} -> {} -> '{}'{}",
                    actor, mtype,
                    if name.is_empty() { "<unknown>" } else { &name },
                    if boss { " [BOSS]" } else { "" }
                );
            }
            println!("\nDamage targets (target_id -> has mob_type? -> name):");
            for tid in snap.keys() {
                let mtype = mobs.get(tid).copied();
                let name = mtype.map(|m| npc_lookup.get_npc_name(m)).unwrap_or_default();
                println!(
                    "  {} -> {} -> '{}'",
                    tid,
                    mtype.map(|m| m.to_string()).unwrap_or_else(|| "NONE".to_string()),
                    if name.is_empty() { "<unknown>" } else { &name }
                );
            }
        }
    }
}
