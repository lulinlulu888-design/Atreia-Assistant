//! What is actually inside a `saveRawPackets` capture.
//!
//! `packets_*.txt` is the whole server->client game connection, not a combat
//! feed, so the honest question for `docs/PRIVACY.md` is not "does it contain
//! combat data" but "what else is in there". This decompresses the LZ4 bundles
//! and reports the printable strings, which is the fastest way to see whether a
//! capture carries chat, mail, or bystanders' names.
//!
//! Diagnostic only — run it deliberately:
//!   A2_REPLAY_CAPTURE=... cargo test --test capture_contents -- --ignored --nocapture

use a2tools_dps_meter_lib::capture::framing::{walk, FrameKind};

fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    let b = hex.as_bytes();
    if b.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(b.len() / 2);
    for pair in b.chunks(2) {
        let hi = (pair[0] as char).to_digit(16)?;
        let lo = (pair[1] as char).to_digit(16)?;
        out.push(((hi << 4) | lo) as u8);
    }
    Some(out)
}

/// Pull every plain packet out of a buffer, decompressing bundles recursively.
fn flatten(buffer: &[u8], out: &mut Vec<Vec<u8>>, depth: usize) {
    if depth > 4 {
        return;
    }
    for frame in walk(buffer).frames {
        match frame.kind {
            FrameKind::Packet => out.push(frame.bytes(buffer).to_vec()),
            FrameKind::Bundle => {
                let payload = frame.payload(buffer);
                if payload.len() < 7 {
                    continue;
                }
                let size =
                    u32::from_le_bytes([payload[2], payload[3], payload[4], payload[5]]) as usize;
                if size == 0 || size > 1_000_000 {
                    continue;
                }
                if let Ok(inner) = lz4_flex::decompress(&payload[6..], size) {
                    flatten(&inner, out, depth + 1);
                }
            }
        }
    }
}

/// Runs of printable text long enough to be words rather than coincidence.
fn strings_in(data: &[u8], min: usize) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur: Vec<u8> = Vec::new();
    let mut flush = |cur: &mut Vec<u8>| {
        if cur.len() >= min {
            if let Ok(s) = std::str::from_utf8(cur) {
                out.push(s.to_string());
            }
        }
        cur.clear();
    };
    for &b in data {
        // ASCII printable, or a UTF-8 continuation/lead byte (CJK names).
        if (0x20..0x7F).contains(&b) || b >= 0xC0 || (0x80..0xC0).contains(&b) {
            cur.push(b);
        } else {
            flush(&mut cur);
        }
    }
    flush(&mut cur);
    out
}

#[test]
#[ignore = "diagnostic"]
fn what_is_in_a_capture() {
    let Ok(path) = std::env::var("A2_REPLAY_CAPTURE") else {
        eprintln!("A2_REPLAY_CAPTURE unset — skipping");
        return;
    };
    let text = std::fs::read_to_string(&path).expect("capture");

    let (mut lines, mut plain, mut bundled) = (0usize, 0usize, 0usize);
    let mut all_strings: Vec<String> = Vec::new();
    let mut opcode_hist: std::collections::HashMap<[u8; 2], usize> = Default::default();

    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<&str> = line.splitn(3, '|').collect();
        if parts.len() != 3 {
            continue;
        }
        let Some(bytes) = decode_hex(parts[2]) else { continue };
        lines += 1;

        let before = {
            let mut v = Vec::new();
            flatten(&bytes, &mut v, 0);
            v
        };
        for p in &before {
            // Opcode sits just past the length varint.
            let li = a2tools_dps_meter_lib::capture::stream_processor::read_varint(p, 0);
            if li.length > 0 {
                let o = li.length as usize;
                if o + 1 < p.len() {
                    *opcode_hist.entry([p[o], p[o + 1]]).or_default() += 1;
                }
            }
            all_strings.extend(strings_in(p, 6));
        }
        plain += before.len();
        bundled += 1;
    }

    println!("capture lines: {lines}, flattened packets: {plain}, buffers: {bundled}");

    let mut ops: Vec<_> = opcode_hist.into_iter().collect();
    ops.sort_by_key(|(_, n)| std::cmp::Reverse(*n));
    println!("\ntop 25 leading opcodes:");
    for (op, n) in ops.iter().take(25) {
        println!("  {:02X} {:02X}  {n:>7}", op[0], op[1]);
    }

    // Dedupe and show the longest strings — chat and mail would surface here.
    all_strings.sort();
    all_strings.dedup();
    all_strings.sort_by_key(|s| std::cmp::Reverse(s.chars().count()));
    println!("\ndistinct printable runs >= 6 bytes: {}", all_strings.len());
    println!("longest 60:");
    for s in all_strings.iter().take(60) {
        let shown: String = s.chars().take(120).collect();
        println!("  [{:>3}] {}", s.chars().count(), shown.replace('\n', " "));
    }
}
