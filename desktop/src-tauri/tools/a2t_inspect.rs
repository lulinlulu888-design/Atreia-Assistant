//! `a2t-inspect` — read an Evidence Slice back and show what is in it.
//!
//! The point of this tool is that you should not have to take our word for it.
//! `docs/PRIVACY.md` claims a slice carries no character names and only packets
//! from a published list; this prints the artifact so you can check both claims
//! against the file the meter would actually upload.
//!
//! ```text
//! a2t-inspect <file.a2es>              summary, opcode histogram, blind map
//! a2t-inspect <file.a2es> --strings    every printable run in the content
//! a2t-inspect <file.a2es> --find NAME  search the decompressed content
//! ```
//!
//! It decompresses before searching. A slice keeps the game's LZ4 bundles, so
//! grepping the raw file finds nothing regardless of what is inside — which
//! would look reassuring and mean nothing.

use std::collections::HashMap;
use std::process::ExitCode;

use a2tools_dps_meter_lib::capture::evidence_slice::{self, ALLOWED_OPCODES};
use a2tools_dps_meter_lib::capture::framing::{self, FrameKind};
use a2tools_dps_meter_lib::capture::stream_processor::read_varint;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        eprintln!("{}", USAGE);
        return ExitCode::from(2);
    }

    let path = &args[0];
    let want_strings = args.iter().any(|a| a == "--strings");
    let find = args
        .iter()
        .position(|a| a == "--find")
        .and_then(|i| args.get(i + 1))
        .cloned();

    let raw = match std::fs::read(path) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("cannot read {path}: {e}");
            return ExitCode::FAILURE;
        }
    };
    // An upload sends the slice gzipped, so that is the file people will most
    // often have to hand. Read either without making them think about it.
    let was_gzipped = raw.starts_with(&[0x1f, 0x8b]);
    let data = if was_gzipped {
        use std::io::Read;
        let mut out = Vec::new();
        match flate2::read::GzDecoder::new(&raw[..]).read_to_end(&mut out) {
            Ok(_) => out,
            Err(e) => {
                eprintln!("{path} is gzipped but will not decompress: {e}");
                return ExitCode::FAILURE;
            }
        }
    } else {
        raw.clone()
    };

    let Some((records, blind_map)) = evidence_slice::decode(&data) else {
        eprintln!("{path} is not an Evidence Slice.");
        eprintln!();
        eprintln!("If this is a packets_*.txt capture, that is a different thing and a");
        eprintln!("far more sensitive one — it is the whole game connection, including");
        eprintln!("chat. See docs/PRIVACY.md before sharing one with anybody.");
        return ExitCode::FAILURE;
    };

    // Everything below reads the decompressed content, never the raw file.
    let expanded: Vec<Vec<u8>> = records
        .iter()
        .map(|(_, r)| evidence_slice::expand(r))
        .collect();
    let content_bytes: usize = expanded.iter().map(|e| e.len()).sum();

    println!("Evidence Slice: {path}");
    if was_gzipped {
        println!(
            "  file size        {} bytes gzipped ({} uncompressed, {:.1}x)",
            raw.len(),
            data.len(),
            data.len() as f64 / raw.len().max(1) as f64
        );
    } else {
        println!("  file size        {} bytes", data.len());
    }
    println!("  records          {}", records.len());
    println!("  packet content   {content_bytes} bytes (decompressed)");
    if let (Some(first), Some(last)) = (records.first(), records.last()) {
        let span = last.0 - first.0;
        println!(
            "  time span        {}.{:03}s  (offsets {} to {} ms from fight start)",
            span / 1000,
            (span % 1000).abs(),
            first.0,
            last.0
        );
    }
    println!();

    println!("Allowlist declared in this file: {} opcodes", ALLOWED_OPCODES.len());
    for (op, what) in ALLOWED_OPCODES {
        println!("  {:02X} {:02X}  {what}", op[0], op[1]);
    }
    println!();

    // What is actually in there, versus what the allowlist permits. A mismatch
    // means the file was not produced by this build.
    let mut hist: HashMap<[u8; 2], usize> = HashMap::new();
    let mut packets = 0usize;
    for buf in &expanded {
        for frame in framing::walk(buf).frames {
            if frame.kind != FrameKind::Packet {
                continue;
            }
            packets += 1;
            let p = frame.bytes(buf);
            let li = read_varint(p, 0);
            if li.length <= 0 {
                continue;
            }
            let o = li.length as usize;
            if o + 1 < p.len() {
                *hist.entry([p[o], p[o + 1]]).or_default() += 1;
            }
        }
    }
    let mut rows: Vec<_> = hist.into_iter().collect();
    rows.sort_by_key(|(_, n)| std::cmp::Reverse(*n));
    println!("Opcodes present: {packets} packets");
    let mut unexpected = 0usize;
    for (op, n) in &rows {
        let known = ALLOWED_OPCODES.iter().find(|(a, _)| **a == *op);
        match known {
            Some((_, what)) => println!("  {:02X} {:02X}  {n:>7}  {what}", op[0], op[1]),
            None => {
                unexpected += n;
                println!("  {:02X} {:02X}  {n:>7}  *** NOT ON THE ALLOWLIST ***", op[0], op[1]);
            }
        }
    }
    if unexpected > 0 {
        println!();
        println!("  {unexpected} packets are not on the allowlist. This file was not");
        println!("  produced by this build of the meter — do not trust it.");
    }
    println!();

    println!("Blinded names: {}", blind_map.len());
    println!("  Each name in the capture was replaced by a token of the same byte");
    println!("  length. The tokens are what a reader sees; the names are not here.");
    let mut tokens: Vec<_> = blind_map.iter().collect();
    tokens.sort();
    for (token, dbid) in tokens {
        println!("  {token}  <- roster id {dbid:#018x}");
    }
    println!();

    if let Some(needle) = find {
        let hits: usize = expanded
            .iter()
            .map(|b| count_occurrences(b, needle.as_bytes()))
            .sum();
        println!("Search for {needle:?}: {hits} occurrence(s) in the decompressed content");
        println!();
        if hits > 0 {
            return ExitCode::FAILURE;
        }
    }

    if want_strings {
        let mut all: Vec<String> = Vec::new();
        for buf in &expanded {
            all.extend(printable_runs(buf, 4));
        }
        all.sort();
        all.dedup();
        all.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
        println!("Printable runs of 4+ bytes: {}", all.len());
        for s in &all {
            println!("  [{:>3}] {}", s.chars().count(), s.replace('\n', " "));
        }
    } else {
        println!("Re-run with --strings to print every readable run in the content,");
        println!("or --find <name> to search it for a specific character name.");
    }

    ExitCode::SUCCESS
}

const USAGE: &str = "\
a2t-inspect — show what is inside an A2Tools Evidence Slice

  a2t-inspect <file.a2es>              summary, opcode histogram, blind map
  a2t-inspect <file.a2es> --strings    every printable run in the content
  a2t-inspect <file.a2es> --find NAME  search the content; exits 1 if found

A slice is what the meter uploads when you share a fight. It is not a packet
capture: see docs/PRIVACY.md for the difference, which matters.";

fn count_occurrences(haystack: &[u8], needle: &[u8]) -> usize {
    if needle.is_empty() || needle.len() > haystack.len() {
        return 0;
    }
    haystack.windows(needle.len()).filter(|w| *w == needle).count()
}

/// Runs of printable text, long enough to be words rather than coincidence.
fn printable_runs(data: &[u8], min: usize) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur: Vec<u8> = Vec::new();
    for &b in data {
        // ASCII printable, or any byte that could be part of a UTF-8 sequence
        // (CJK names are three bytes a character).
        if (0x20..0x7F).contains(&b) || b >= 0x80 {
            cur.push(b);
        } else {
            flush(&mut cur, min, &mut out);
        }
    }
    flush(&mut cur, min, &mut out);
    out
}

fn flush(cur: &mut Vec<u8>, min: usize, out: &mut Vec<String>) {
    if cur.len() >= min {
        if let Ok(s) = std::str::from_utf8(cur) {
            out.push(s.to_string());
        }
    }
    cur.clear();
}
