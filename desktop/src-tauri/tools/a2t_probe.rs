//! `a2t-probe` — a workbench for reversing packet structure.
//!
//! The parser was built one opcode at a time by staring at hex. This is the tool
//! that work wanted: it decodes a capture into plain packets (streams
//! reassembled, LZ4 bundles expanded) and then lets you ask questions of it.
//!
//! ```text
//! a2t-probe opcodes  <capture>                     what is in this capture
//! a2t-probe find     <capture> --u32 110730120     where does this value appear
//! a2t-probe find     <capture> --string Misti      ...or this text
//! a2t-probe find     <capture> --hex 0F            ...or these bytes
//! a2t-probe tables   <capture> --items items.json  item-id tables, slot-decoded
//! a2t-probe dump     <capture> --opcode 45,36      annotated hexdump
//! a2t-probe diff     <before> <after>              what changed between captures
//! ```
//!
//! **`diff` is the one that finds structure.** Take a capture, change one thing
//! in game — equip a different chestpiece, pick a specialisation node — take a
//! second capture, and diff them. The values that appear in one and not the
//! other are the field you are looking for, without having to guess an opcode.
//! Everything else here is for confirming what diff turns up.
//!
//! Every view prints byte offsets into the *decoded* packet, which is what
//! `--at` takes, so you can go from "this value is somewhere" to "here is the
//! record around it" in two commands.

use std::collections::{HashMap, HashSet};
use std::process::ExitCode;

use a2tools_dps_meter_lib::capture::framing::{self, FrameKind};
use a2tools_dps_meter_lib::capture::packet_accumulator::PacketAccumulator;
use a2tools_dps_meter_lib::capture::stream_processor::read_varint;
use a2tools_dps_meter_lib::share;

/// A packet as the parser would see it, with where it came from.
struct Packet {
    index: usize,
    at_ms: i64,
    bytes: Vec<u8>,
}

impl Packet {
    /// The two bytes just past the length varint — what the parser dispatches on.
    fn opcode(&self) -> Option<[u8; 2]> {
        let li = read_varint(&self.bytes, 0);
        if li.length <= 0 {
            return None;
        }
        let o = li.length as usize;
        (o + 1 < self.bytes.len()).then(|| [self.bytes[o], self.bytes[o + 1]])
    }
}

fn load(path: &str) -> Vec<Packet> {
    fn expand(buf: &[u8], out: &mut Vec<Vec<u8>>, depth: usize, top: bool) {
        if depth > 4 {
            return;
        }
        let frames = if top {
            framing::walk(buf).frames
        } else {
            framing::walk_inner(buf).frames
        };
        for f in frames {
            match f.kind {
                FrameKind::Packet => out.push(f.bytes(buf).to_vec()),
                FrameKind::Bundle => {
                    if let Some(d) = framing::decompress_bundle(f.payload(buf)) {
                        expand(&d, out, depth + 1, false);
                    }
                }
            }
        }
    }

    let mut out = Vec::new();
    let mut streams: HashMap<String, PacketAccumulator> = HashMap::new();
    let caps = match share::read_capture(std::path::Path::new(path)) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("{e}");
            return out;
        }
    };
    for cap in caps {
        let acc = streams
            .entry(cap.stream.clone())
            .or_insert_with(PacketAccumulator::new);
        acc.append(&cap.bytes);
        let buf = acc.snapshot().to_vec();
        let walk = framing::walk(&buf);
        let mut plain = Vec::new();
        for f in &walk.frames {
            match f.kind {
                FrameKind::Packet => plain.push(f.bytes(&buf).to_vec()),
                FrameKind::Bundle => {
                    if let Some(d) = framing::decompress_bundle(f.payload(&buf)) {
                        expand(&d, &mut plain, 1, false);
                    }
                }
            }
        }
        acc.discard_bytes(walk.consumed);
        for bytes in plain {
            out.push(Packet {
                index: out.len(),
                at_ms: cap.captured_at_ms,
                bytes,
            });
        }
    }
    out
}

fn hex(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|b| format!("{b:02X}"))
        .collect::<Vec<_>>()
        .join(" ")
}

/// The reversing view: every plausible reading of the same bytes, side by side.
///
/// A field is only obvious once you can see that offset 12 is a varint of 5 and
/// offset 13 starts a UTF-8 string of that length. Printing one interpretation
/// at a time is what makes this slow by hand.
fn annotate(bytes: &[u8], from: usize, len: usize) {
    let end = (from + len).min(bytes.len());
    let mut o = from;
    while o < end {
        let b = bytes[o];
        let mut readings: Vec<String> = Vec::new();

        let v = read_varint(bytes, o);
        if v.length > 0 && v.value > 0 {
            readings.push(format!("varint({}) w={}", v.value, v.length));
        }
        if o + 4 <= bytes.len() {
            let u = u32::from_le_bytes([bytes[o], bytes[o + 1], bytes[o + 2], bytes[o + 3]]);
            if u > 1000 {
                readings.push(format!("u32({u})"));
            }
        }
        // `<u8 len><utf8>` is how every name in this protocol is written.
        let slen = b as usize;
        if (2..=40).contains(&slen) && o + 1 + slen <= bytes.len() {
            if let Ok(s) = std::str::from_utf8(&bytes[o + 1..o + 1 + slen]) {
                if !s.chars().any(|c| c.is_control()) && s.chars().any(|c| c.is_alphanumeric()) {
                    readings.push(format!("str({slen})={s:?}"));
                }
            }
        }

        println!(
            "  {o:>6}  {b:02X}  {:<24} {}",
            hex(&bytes[o..(o + 4).min(bytes.len())]),
            readings.join("  |  ")
        );
        o += 1;
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() < 2 || args.iter().any(|a| a == "-h" || a == "--help") {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    }
    let cmd = args[0].as_str();
    let value_of = |name: &str| -> Option<String> {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .cloned()
    };
    let num = |name: &str| value_of(name).and_then(|v| v.parse::<usize>().ok());
    let limit = num("--limit").unwrap_or(10);
    let near = num("--near").unwrap_or(48);

    match cmd {
        "opcodes" => {
            let packets = load(&args[1]);
            println!("{} packets", packets.len());
            let mut hist: HashMap<[u8; 2], (usize, usize)> = HashMap::new();
            for p in &packets {
                if let Some(op) = p.opcode() {
                    let e = hist.entry(op).or_insert((0, 0));
                    e.0 += 1;
                    e.1 += p.bytes.len();
                }
            }
            let mut rows: Vec<_> = hist.into_iter().collect();
            rows.sort_by_key(|(_, (n, _))| std::cmp::Reverse(*n));
            println!("\n  opcode   packets      bytes   mean");
            for (op, (n, bytes)) in rows.iter().take(40) {
                println!(
                    "  {:02X} {:02X}  {n:>8}  {bytes:>9}  {:>5}",
                    op[0],
                    op[1],
                    bytes / n.max(&1)
                );
            }
        }

        "find" => {
            let packets = load(&args[1]);
            let needle: Vec<u8> = if let Some(v) = value_of("--u32") {
                match v.parse::<u32>() {
                    Ok(n) => n.to_le_bytes().to_vec(),
                    Err(_) => {
                        eprintln!("--u32 needs a number");
                        return ExitCode::FAILURE;
                    }
                }
            } else if let Some(s) = value_of("--string") {
                s.into_bytes()
            } else if let Some(h) = value_of("--hex") {
                let cleaned: String = h.chars().filter(|c| c.is_ascii_hexdigit()).collect();
                match (0..cleaned.len())
                    .step_by(2)
                    .map(|i| u8::from_str_radix(&cleaned[i..i + 2], 16))
                    .collect::<Result<Vec<u8>, _>>()
                {
                    Ok(b) if !b.is_empty() => b,
                    _ => {
                        eprintln!("--hex needs hex bytes, e.g. 0F or '45 36'");
                        return ExitCode::FAILURE;
                    }
                }
            } else {
                eprintln!("find needs --u32, --string or --hex");
                return ExitCode::FAILURE;
            };

            println!("searching {} packets for {}", packets.len(), hex(&needle));
            let mut shown = 0;
            for p in &packets {
                if p.bytes.len() < needle.len() {
                    continue;
                }
                for (offset, w) in p.bytes.windows(needle.len()).enumerate() {
                    if w != needle.as_slice() {
                        continue;
                    }
                    let op = p.opcode().unwrap_or([0, 0]);
                    println!(
                        "\npacket #{} ({} bytes, opcode {:02X} {:02X}, t={}ms) @ {offset}",
                        p.index,
                        p.bytes.len(),
                        op[0],
                        op[1],
                        p.at_ms
                    );
                    let from = offset.saturating_sub(near / 2);
                    println!("  {}", hex(&p.bytes[from..(offset + near).min(p.bytes.len())]));
                    shown += 1;
                    if shown >= limit {
                        println!("\n({limit} shown; --limit for more)");
                        return ExitCode::SUCCESS;
                    }
                    break; // one hit per packet keeps the output readable
                }
            }
            if shown == 0 {
                println!("not found");
                return ExitCode::FAILURE;
            }
        }

        "dump" => {
            let packets = load(&args[1]);
            let want: Option<[u8; 2]> = value_of("--opcode").and_then(|s| {
                let parts: Vec<u8> = s
                    .split(|c: char| !c.is_ascii_hexdigit())
                    .filter(|p| !p.is_empty())
                    .filter_map(|p| u8::from_str_radix(p, 16).ok())
                    .collect();
                (parts.len() == 2).then(|| [parts[0], parts[1]])
            });
            let at = num("--at");
            let mut shown = 0;
            for p in &packets {
                if let Some(op) = want {
                    if p.opcode() != Some(op) {
                        continue;
                    }
                }
                if let Some(index) = num("--packet") {
                    if p.index != index {
                        continue;
                    }
                }
                let op = p.opcode().unwrap_or([0, 0]);
                println!(
                    "\n=== packet #{} — {} bytes, opcode {:02X} {:02X}, t={}ms ===",
                    p.index,
                    p.bytes.len(),
                    op[0],
                    op[1],
                    p.at_ms
                );
                let from = at.unwrap_or(0);
                annotate(&p.bytes, from, near);
                shown += 1;
                if shown >= limit {
                    break;
                }
            }
            if shown == 0 {
                println!("no packet matched");
                return ExitCode::FAILURE;
            }
        }

        "tables" => {
            let Some(db) = value_of("--items") else {
                eprintln!("tables needs --items <_raw_items.json>");
                return ExitCode::FAILURE;
            };
            let ids = match load_item_ids(&db) {
                Some(i) => i,
                None => {
                    eprintln!("could not read {db}");
                    return ExitCode::FAILURE;
                }
            };
            println!("{} known item ids", ids.len());
            let packets = load(&args[1]);
            let mut shown = 0;
            for p in &packets {
                let mut hits: Vec<(usize, u32)> = Vec::new();
                for (i, w) in p.bytes.windows(4).enumerate() {
                    let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
                    if ids.contains(&v) {
                        hits.push((i, v));
                    }
                }
                if hits.len() < 4 {
                    continue;
                }
                let strides: Vec<usize> = hits.windows(2).map(|w| w[1].0 - w[0].0).collect();
                let tight = strides.iter().filter(|&&s| s < 64).count();
                if tight < 3 {
                    continue;
                }
                let op = p.opcode().unwrap_or([0, 0]);
                println!(
                    "\n=== packet #{}, {} bytes, opcode {:02X} {:02X}, {} ids, first @ {} ===",
                    p.index,
                    p.bytes.len(),
                    op[0],
                    op[1],
                    hits.len(),
                    hits[0].0
                );
                for (offset, id) in hits.iter().take(16) {
                    // The byte before an id has been a constant tag; the two
                    // after it have looked like a slot index and a length.
                    let tag = (*offset > 0).then(|| p.bytes[offset - 1]);
                    let after = &p.bytes[(offset + 4).min(p.bytes.len())
                        ..(offset + 8).min(p.bytes.len())];
                    println!(
                        "  @{offset:<6} id={id:<11} tag={:<4} after={}",
                        tag.map(|t| format!("{t:02X}")).unwrap_or_default(),
                        hex(after)
                    );
                }
                shown += 1;
                if shown >= limit {
                    break;
                }
            }
            if shown == 0 {
                println!("no item tables found");
            }
        }

        "diff" => {
            if args.len() < 3 {
                eprintln!("diff needs two captures");
                return ExitCode::FAILURE;
            }
            let a = load(&args[1]);
            let b = load(&args[2]);
            println!("before: {} packets, after: {} packets", a.len(), b.len());

            // Every u32 that appears in one capture and not the other. Change one
            // thing in game between captures and the field falls out of this.
            let u32s = |ps: &[Packet]| -> HashSet<u32> {
                let mut set = HashSet::new();
                for p in ps {
                    for w in p.bytes.windows(4) {
                        let v = u32::from_le_bytes([w[0], w[1], w[2], w[3]]);
                        // Below this is mostly lengths, counters and noise.
                        if v > 1_000_000 {
                            set.insert(v);
                        }
                    }
                }
                set
            };
            let (sa, sb) = (u32s(&a), u32s(&b));
            let only_b: Vec<u32> = {
                let mut v: Vec<u32> = sb.difference(&sa).copied().collect();
                v.sort_unstable();
                v
            };
            let only_a: Vec<u32> = {
                let mut v: Vec<u32> = sa.difference(&sb).copied().collect();
                v.sort_unstable();
                v
            };
            println!("\nonly in AFTER  ({}):", only_b.len());
            for v in only_b.iter().take(60) {
                println!("  {v:<12} 0x{v:08X}");
            }
            println!("\nonly in BEFORE ({}):", only_a.len());
            for v in only_a.iter().take(60) {
                println!("  {v:<12} 0x{v:08X}");
            }

            let ops = |ps: &[Packet]| -> HashSet<[u8; 2]> {
                ps.iter().filter_map(|p| p.opcode()).collect()
            };
            let (oa, ob) = (ops(&a), ops(&b));
            let new_ops: Vec<_> = ob.difference(&oa).collect();
            if !new_ops.is_empty() {
                println!("\nopcodes only in AFTER:");
                for op in new_ops {
                    println!("  {:02X} {:02X}", op[0], op[1]);
                }
            }
            println!(
                "\nNarrow it: a2t-probe find <after> --u32 <value>  then  dump --packet N --at OFF"
            );
        }

        other => {
            eprintln!("unknown command {other:?}\n\n{USAGE}");
            return ExitCode::from(2);
        }
    }
    ExitCode::SUCCESS
}

fn load_item_ids(path: &str) -> Option<HashSet<u32>> {
    let text = std::fs::read_to_string(path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&text).ok()?;
    Some(
        value
            .get("items")?
            .as_array()?
            .iter()
            .filter_map(|i| i.get("id").and_then(|v| v.as_u64()))
            .map(|v| v as u32)
            .collect(),
    )
}

const USAGE: &str = "\
a2t-probe — explore the structure of an AION 2 packet capture

  a2t-probe opcodes <capture>
      What is in this capture: every leading opcode, packet count, mean size.

  a2t-probe find <capture> (--u32 N | --string S | --hex BYTES) [--limit N] [--near N]
      Where a value appears, with the bytes around each hit.

  a2t-probe dump <capture> [--opcode 45,36] [--packet N] [--at OFFSET] [--near N]
      Annotated hexdump: each offset read as a varint, a u32 and a length-prefixed
      string at once, which is what makes a field obvious.

  a2t-probe tables <capture> --items <_raw_items.json> [--limit N]
      Item-id tables, with the tag byte before each id and the bytes after it.

  a2t-probe diff <before> <after>
      Values present in one capture and not the other. Change ONE thing in game
      between the two and the field you are hunting falls out of this list.

Captures are packets_*.txt from the meter (Settings -> Diagnostics -> Enable
packet logging). Offsets are into the decoded packet, so they feed straight back
into `dump --at`.";
