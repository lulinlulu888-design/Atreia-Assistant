//! a2t-derive: prove the log service's derivation against real captures.
//!
//!   a2t-derive <app-data-dir> [fight-id ...]   saved fights a capture covers
//!   a2t-derive --capture <packets_*.txt>        every boss fight in a capture
//!
//! For each fight: replay the WHOLE capture the way the live meter reads it,
//! cut the Evidence Slice an upload would send, run `rederive::derive_fight`
//! over the slice alone (the function the service runs, with the same data
//! tables), and compare the two record for record: per actor, per skill, hit
//! counts. A saved fight's record is shown too, but only as context: it was
//! made by whichever build was running that day, so it can differ from both
//! for reasons that have nothing to do with the slice.
//!
//! "identical" here is the claim the upload design rests on: a log's numbers
//! can be reproduced from the slice alone.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use a2tools_dps_meter_lib::capture::evidence_slice::{self, CapturedPacket, NameMap};
use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::StreamProcessor;
use a2tools_dps_meter_lib::combat::data_storage::DataStorage;
use a2tools_dps_meter_lib::combat::dps_calculator::DpsCalculator;
use a2tools_dps_meter_lib::combat::ping_tracker::PingTracker;
use a2tools_dps_meter_lib::entity::fight_record::FightRecord;
use a2tools_dps_meter_lib::i18n::lookup::{NpcLookup, SkillLookup};
use a2tools_dps_meter_lib::rederive::derive_fight;
use a2tools_dps_meter_lib::share::{find_captures, read_capture};

struct Tables {
    npcs: String,
    skills: String,
    dots: String,
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("usage: a2t-derive <app-data-dir> [fight-id ...] | --capture <file>");
        std::process::exit(2);
    }
    let data = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../src/data");
    let t = Tables {
        npcs: std::fs::read_to_string(data.join("i18n/npcs/en.json")).expect("npcs/en.json"),
        skills: std::fs::read_to_string(data.join("i18n/skills/en.json")).expect("skills/en.json"),
        dots: std::fs::read_to_string(data.join("dot_skill_ids.json")).expect("dot_skill_ids.json"),
    };

    let (tried, same) = if args[0] == "--capture" {
        from_capture(Path::new(args.get(1).expect("capture path")), &t)
    } else {
        from_history(Path::new(&args[0]), &args[1..], &t)
    };
    println!("\n{same} of {tried} fights: slice re-derived identically to the whole capture");
    std::process::exit(if same == tried && tried > 0 { 0 } else { 1 });
}

/// Saved fights that some capture in the data dir covers.
fn from_history(dir: &Path, wanted: &[String], t: &Tables) -> (usize, usize) {
    let captures = find_captures(dir);
    let mut fights: Vec<FightRecord> = std::fs::read_dir(dir.join("history"))
        .expect("history dir")
        .filter_map(|e| e.ok())
        .filter_map(|e| std::fs::read_to_string(e.path()).ok())
        .filter_map(|txt| serde_json::from_str::<FightRecord>(&txt).ok())
        .filter(|r| wanted.is_empty() || wanted.contains(&r.id))
        .collect();
    fights.sort_by_key(|r| r.start_time_ms);

    let (mut tried, mut same) = (0, 0);
    for saved in &fights {
        let packets = covering(&captures, saved.start_time_ms);
        if packets.is_empty() {
            continue;
        }
        let (storage, whole) = replay(&packets, t);
        let Some(w) = whole
            .into_iter()
            .filter(|r| r.mob_code == saved.mob_code)
            .min_by_key(|r| (r.start_time_ms - saved.start_time_ms).abs())
        else {
            continue; // the capture does not actually contain this fight
        };
        tried += 1;
        println!("\n== {} {} (saved record: total {}, whole capture: total {})",
                 saved.id, saved.boss_name, saved.details.total_target_damage,
                 w.details.total_target_damage);
        if check(&packets, &storage, &w, t) {
            same += 1;
        }
        ring_check(&packets, &storage, &w, t);
    }
    (tried, same)
}

/// The automatic path: the same segments through the in-memory ring, the
/// slice cut by `save_slice` as the auto-save would, read back and derived.
fn ring_check(packets: &[CapturedPacket], storage: &DataStorage, w: &FightRecord, t: &Tables) {
    use std::io::Read;
    use std::sync::Mutex;
    // The ring is process-wide, like the live one. Feed each capture once, or
    // a second fight from the same capture sees every packet twice.
    static FED: Mutex<Vec<i64>> = Mutex::new(Vec::new());
    let mark = packets.first().map(|p| p.captured_at_ms).unwrap_or(0);
    let fresh = { let mut fed = FED.lock().unwrap(); if fed.contains(&mark) { false } else { fed.push(mark); true } };
    for p in packets.iter().filter(|_| fresh) {
        a2tools_dps_meter_lib::clock::set_override(Some(p.captured_at_ms));
        let port: u16 = p.stream.trim_start_matches("Client:").parse().unwrap_or(0);
        a2tools_dps_meter_lib::share::ring::record(port, &p.bytes);
    }
    a2tools_dps_meter_lib::clock::set_override(None);
    let dir = std::env::temp_dir().join(format!("a2t-ring-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let result = a2tools_dps_meter_lib::share::save_slice(&dir, w, storage).and_then(|bytes| {
        let gz = std::fs::read(a2tools_dps_meter_lib::share::slices_dir(&dir).join(format!("{}.a2es.gz", w.id)))
            .map_err(|e| e.to_string())?;
        let mut slice = Vec::new();
        flate2::read::GzDecoder::new(&gz[..]).read_to_end(&mut slice).map_err(|e| e.to_string())?;
        let d = derive_fight(&slice, &t.npcs, &t.skills, &t.dots).map_err(|e| format!("{e:?}"))?;
        Ok((bytes, d))
    });
    match result {
        Ok((bytes, d)) => {
            let same = d.record.details.total_target_damage == w.details.total_target_damage
                && d.record.details.skills.len() == w.details.skills.len()
                && d.record.mob_code == w.mob_code;
            println!("   from memory (no packet logging): {} bytes gzipped, total {} -> {}",
                     bytes, d.record.details.total_target_damage,
                     if same { "identical" } else { "DIFFERENT" });
        }
        Err(e) => println!("   from memory: failed: {e}"),
    }
    let _ = std::fs::remove_dir_all(&dir);
}

/// Every boss fight in one capture file.
fn from_capture(path: &Path, t: &Tables) -> (usize, usize) {
    let packets = read_capture(path).expect("capture");
    let (storage, mut whole) = replay(&packets, t);
    whole.sort_by_key(|r| r.start_time_ms);
    let (mut tried, mut same) = (0, 0);
    for w in &whole {
        tried += 1;
        println!("\n== {} {} ({} ms, {} actors, total {})", w.id, w.boss_name, w.duration_ms,
                 w.actors.len(), w.details.total_target_damage);
        if check(&packets, &storage, w, t) {
            same += 1;
        }
    }
    (tried, same)
}

fn covering(captures: &[PathBuf], at_ms: i64) -> Vec<CapturedPacket> {
    let mut all = Vec::new();
    for c in captures {
        let Ok(p) = read_capture(c) else { continue };
        let (Some(f), Some(l)) = (p.first(), p.last()) else { continue };
        if f.captured_at_ms <= at_ms && l.captured_at_ms >= at_ms {
            all.extend(p);
        }
    }
    all.sort_by_key(|p| p.captured_at_ms);
    all
}

fn lookups(t: &Tables) -> (Arc<NpcLookup>, Arc<SkillLookup>) {
    let npc = Arc::new(NpcLookup::new());
    npc.load_from_json(&t.npcs);
    let sk = Arc::new(SkillLookup::new());
    sk.load_from_json(&t.skills);
    (npc, sk)
}

/// The whole capture, reassembled and replayed the way the live meter reads it.
fn replay(packets: &[CapturedPacket], t: &Tables) -> (Arc<DataStorage>, Vec<FightRecord>) {
    let (npc, sk) = lookups(t);
    let storage = Arc::new(DataStorage::new());
    let mut proc = StreamProcessor::new(storage.clone(), sk.clone(), npc.clone());
    if let Ok(ids) = serde_json::from_str::<Vec<i32>>(&t.dots) {
        proc.set_dot_skill_ids(ids.into_iter().collect());
    }
    let mut streams: HashMap<String, PacketAccumulator> = HashMap::new();
    // Saved as the live meter saves them: every 30 seconds, a fight's record
    // rewritten while it runs and frozen once it has gone quiet. A snapshot
    // taken only at the end of the capture is not what anyone saw: by then a
    // player who changed entity id has had their damage moved off the old id,
    // and a dummy hit again has been reset, which made correct slices look wrong.
    let mut calc = DpsCalculator::new(storage.clone(), sk, npc, Arc::new(PingTracker::new()));
    let mut saved: HashMap<String, FightRecord> = HashMap::new();
    let mut next_save = packets.first().map(|p| p.captured_at_ms + 30_000).unwrap_or(0);
    for p in packets {
        proc.set_override_timestamp(Some(p.captured_at_ms));
        let acc = streams.entry(p.stream.clone()).or_insert_with(PacketAccumulator::new);
        acc.append(&p.bytes);
        let used = proc.consume_stream(acc.snapshot());
        if used > 0 {
            acc.discard_bytes(used);
        }
        if p.captured_at_ms >= next_save {
            for r in calc.snapshot_boss_fights() {
                saved.insert(r.id.clone(), r);
            }
            next_save = p.captured_at_ms + 30_000;
        }
    }
    // Fights still running when the capture stops: the meter saves those on
    // its next tick, which a capture that ends never reaches. (Fights already
    // frozen are not in this snapshot.)
    for r in calc.snapshot_boss_fights_force() {
        saved.insert(r.id.clone(), r);
    }
    proc.set_override_timestamp(None);
    (storage, saved.into_values().collect())
}

/// Cut the slice for `w`, derive it, and compare. True when identical.
fn check(packets: &[CapturedPacket], storage: &DataStorage, w: &FightRecord, t: &Tables) -> bool {
    // The names the meter resolved, which is what the upload blinds.
    let mut names: NameMap = NameMap::new();
    for (name, member) in storage.get_party_members() {
        names.insert(name.clone(), member.dbid);
    }
    for name in storage.get_nicknames().values() {
        names.entry(name.clone()).or_insert(0);
    }
    let slice = match evidence_slice::build(packets, w.start_time_ms, w.start_time_ms + w.duration_ms, &names) {
        Ok(s) => evidence_slice::encode(&s),
        Err(e) => {
            println!("   slice failed: {e:?}");
            return false;
        }
    };
    let d = match derive_fight(&slice, &t.npcs, &t.skills, &t.dots) {
        Ok(d) => d,
        Err(e) => {
            println!("   derive failed: {e:?} ({} bytes of slice)", slice.len());
            // What the slice does hold, against the fight it should have held.
            if let Ok(enc) = a2tools_dps_meter_lib::rederive::derive(&slice) {
                let fought = enc.targets.iter().find(|t| t.target_id == w.target_id);
                println!("     the fight's target {} (mob {}): {}", w.target_id, w.mob_code,
                         match fought {
                             Some(t) => format!("in the slice as mob {}, {} damage over {} ms",
                                                t.mob_code, t.total_damage, t.duration_ms),
                             None => "not in the slice".to_string(),
                         });
                for t in enc.targets.iter().take(4) {
                    println!("     target {} mob {} damage {} over {} ms", t.target_id, t.mob_code,
                             t.total_damage, t.duration_ms);
                }
            }
            return false;
        }
    };
    let got = &d.record;
    if let Ok(dir) = std::env::var("A2_WRITE_SLICE") {
        // What an upload sends, and what the service must answer, for testing
        // the deployed Worker against this build.
        let dir = Path::new(&dir);
        let _ = std::fs::create_dir_all(dir);
        let _ = std::fs::write(dir.join(format!("{}.a2es.gz", w.id)),
                               a2tools_dps_meter_lib::share::gzip(&slice).unwrap_or_default());
        let _ = std::fs::write(dir.join(format!("{}.derived.json", w.id)),
                               serde_json::to_vec(&d).unwrap_or_default());
    }

    let rows = |r: &FightRecord| -> HashMap<(i32, i32, bool), (i64, i32)> {
        r.details.skills.iter().map(|s| ((s.actor_id, s.code, s.is_dot), (s.dmg as i64, s.time))).collect()
    };
    let (a, b) = (rows(w), rows(got));
    let keys: HashSet<_> = a.keys().chain(b.keys()).copied().collect();
    let mut diffs: Vec<_> = keys.into_iter().filter(|k| a.get(k) != b.get(k)).collect();
    diffs.sort();

    let same_boss = w.mob_code == got.mob_code;
    let same_dungeon = w.dungeon_id == got.dungeon_id;
    let identical = same_boss && diffs.is_empty()
        && w.details.total_target_damage == got.details.total_target_damage;
    // The region a log is filed under comes from this; a slice that loses
    // the record naming the server files the log as "unknown".
    let same_server = w.server_id == got.server_id;
    println!("   slice {} bytes ({} gzipped): boss {} target {}/{} {}  dungeon {}/{} {}  server {}/{} {}  total {} / {} over {} / {} ms  skill rows {} / {}  -> {}",
             slice.len(), gz_len(&slice), got.mob_code,
             w.target_id, got.target_id, if w.target_id == got.target_id { "ok" } else { "MISMATCH" },
             w.dungeon_id, got.dungeon_id,
             if same_dungeon { "ok" } else { "MISMATCH" },
             w.server_id, got.server_id, if same_server { "ok" } else { "MISMATCH" },
             w.details.total_target_damage, got.details.total_target_damage, w.duration_ms, got.duration_ms,
             a.len(), b.len(), if identical { "identical" } else { "DIFFERENT" });
    for k in diffs.iter().take(if std::env::var("A2_ALL_ROWS").is_ok() { usize::MAX } else { 12 }) {
        println!("     row {:?}: whole {:?} slice {:?}", k, a.get(k), b.get(k));
    }
    identical
}

fn gz_len(data: &[u8]) -> usize {
    a2tools_dps_meter_lib::share::gzip(data).map(|g| g.len()).unwrap_or(0)
}
