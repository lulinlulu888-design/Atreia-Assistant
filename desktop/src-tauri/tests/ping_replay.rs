//! Replays two-way raw captures (the `packet_dump` diagnostic's format) through
//! the ping tracker, once per ping-timestamp format the game uses:
//!
//! - KR/TW: the echoed client time is wall-clock .NET milliseconds, so ping is
//!   arrival minus that, no request needed.
//! - Since the 2026-10 client elsewhere: the echoed time counts from an
//!   arbitrary epoch, so ping has to be timed against the request.
//!
//! Captures come from A2_PING_CAPTURES as `path@server_port` entries separated by
//! `;`. The test skips when it is unset so it never fails on a machine that does
//! not have the files.

use a2tools_dps_meter_lib::capture::captured_payload::CapturedPayload;
use a2tools_dps_meter_lib::combat::ping_tracker::PingTracker;

const DOTNET_EPOCH_OFFSET_MS: i64 = 62135596800000;
/// The whole response frame header: length 0x18 (21 bytes) then `03 36 00 00`.
/// Matching the length too keeps the reference from picking up `03 36 00 00`
/// that happens to sit inside some other packet.
const PING_RS: [u8; 5] = [0x18, 0x03, 0x36, 0x00, 0x00];

struct Packet {
    at_ms: i64,
    src_port: u16,
    dst_port: u16,
    data: Vec<u8>,
}

fn load(path: &str, server_port: u16) -> Vec<Packet> {
    let text = std::fs::read_to_string(path).expect("capture readable");
    let mut out = Vec::new();
    for line in text.lines() {
        // TIMESTAMP_MS|SRCIP:SRCPORT->DSTIP:DSTPORT|DEV|TLS/PLAIN|LEN|HEX
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 6 || !parts[0].starts_with(|c: char| c.is_ascii_digit()) {
            continue;
        }
        let Some((src, dst)) = parts[1].split_once("->") else { continue };
        let port = |s: &str| s.rsplit(':').next().and_then(|p| p.parse::<u16>().ok());
        let (Some(src_port), Some(dst_port)) = (port(src), port(dst)) else { continue };
        if src_port != server_port && dst_port != server_port {
            continue;
        }
        let Ok(at_ms) = parts[0].parse::<f64>() else { continue };
        let Some(data) = decode_hex(parts[5]) else { continue };
        out.push(Packet { at_ms: at_ms as i64, src_port, dst_port, data });
    }
    out
}

fn cap(p: &Packet) -> CapturedPayload {
    CapturedPayload {
        src_port: p.src_port,
        dst_port: p.dst_port,
        data: p.data.clone(),
        device_name: None,
        captured_at_ms: p.at_ms,
        src_ip: None,
        dst_ip: None,
        tcp_seq: 0,
        tcp_ack: 0,
    }
}

fn echoed_client_time(data: &[u8]) -> Option<i64> {
    let i = data.windows(PING_RS.len()).position(|w| w == PING_RS)?;
    let at = i + PING_RS.len();
    let bytes: [u8; 8] = data.get(at..at + 8)?.try_into().ok()?;
    Some(i64::from_le_bytes(bytes))
}

struct Outcome {
    responses: usize,
    wall_clock_format: usize,
    reported: usize,
    worst_error_ms: i64,
}

/// Feed the capture to a fresh tracker. With `requests` off, only the server's
/// side is fed, which is what a wall-clock timestamp should be enough for.
fn run(packets: &[Packet], server_port: u16, requests: bool) -> Outcome {
    // Replayed timestamps are on the performance counter as it ran then.
    let tracker = PingTracker::new();
    let mut last_request: Option<i64> = None;
    let mut o = Outcome { responses: 0, wall_clock_format: 0, reported: 0, worst_error_ms: 0 };

    for p in packets {
        let outbound = p.dst_port == server_port;
        if outbound {
            if !requests {
                continue;
            }
            // Independent reference: the client's ping request is its only
            // 12- or 13-byte frame (length prefix 0x0F / 0x10).
            if p.data.len() == 12 && p.data[0] == 0x0F || p.data.len() == 13 && p.data[0] == 0x10 {
                last_request = Some(p.at_ms);
            }
            tracker.on_packet(&cap(p), server_port);
            continue;
        }

        let recorded = || tracker.get_ping_history(i64::MIN, i64::MAX).len();
        let before = recorded();
        tracker.on_packet(&cap(p), server_port);
        let Some(client_time) = echoed_client_time(&p.data) else { continue };
        o.responses += 1;

        // Same priority as the tracker: the request when it was seen, since
        // that needs no clock; the wall-clock reading otherwise.
        let wall_clock_rtt = p.at_ms - (client_time - DOTNET_EPOCH_OFFSET_MS);
        let wall_clock = (1..=9999).contains(&wall_clock_rtt);
        if wall_clock {
            o.wall_clock_format += 1;
        }
        let expected = last_request
            .map(|t| p.at_ms - t)
            .filter(|rtt| (0..=9999).contains(rtt))
            .or(wall_clock.then_some(wall_clock_rtt));
        if recorded() > before {
            o.reported += 1;
            if let (Some(n), Some(e)) = (tracker.current_ping_ms(), expected) {
                o.worst_error_ms = o.worst_error_ms.max((n as i64 - e).abs());
            }
        }
    }
    o
}

#[test]
fn both_ping_timestamp_formats_replay() {
    let Ok(spec) = std::env::var("A2_PING_CAPTURES") else {
        eprintln!("A2_PING_CAPTURES not set; skipping");
        return;
    };
    for entry in spec.split(';').filter(|s| !s.trim().is_empty()) {
        let (path, port) = entry.rsplit_once('@').expect("path@server_port");
        let port: u16 = port.trim().parse().expect("server port");
        let packets = load(path.trim(), port);

        let both = run(&packets, port, true);
        let server_only = run(&packets, port, false);
        let wall_clock = both.wall_clock_format == both.responses;
        eprintln!(
            "{path}: {} responses, format {}, reported {} (worst error {} ms); server side only: reported {}",
            both.responses,
            if wall_clock { "wall-clock .NET ms" } else { "arbitrary epoch" },
            both.reported,
            both.worst_error_ms,
            server_only.reported,
        );

        assert!(both.responses >= 3, "{path}: too few ping responses to judge");
        assert!(
            both.wall_clock_format == 0 || wall_clock,
            "{path}: formats mixed within one capture"
        );
        assert!(both.worst_error_ms <= 2, "{path}: ping off by {} ms", both.worst_error_ms);
        if wall_clock {
            // Every response resolves on its own, requests or not.
            assert_eq!(both.reported, both.responses, "{path}");
            assert_eq!(server_only.reported, server_only.responses, "{path}");
        } else {
            // A response can only resolve once its request has been seen; the
            // capture may start between the two.
            assert!(both.reported + 1 >= both.responses, "{path}");
            assert_eq!(server_only.reported, 0, "{path}: nothing to time it against");
        }
    }
}

fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    let hex = hex.trim();
    if hex.len() % 2 != 0 {
        return None;
    }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).ok())
        .collect()
}
