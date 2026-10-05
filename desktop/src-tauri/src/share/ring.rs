//! The last stretch of captured traffic, held in memory, so a boss fight can be
//! turned into an Evidence Slice without packet logging having been on.
//!
//! Packet logging writes everything to disk and is off by default, for good
//! reason: a capture holds chat and bystanders. But a slice can only be cut
//! from the packets, so without this nobody could upload a fight unless they
//! had thought to turn logging on first.
//!
//! What is here never touches disk. It is the same segments the parser is
//! already being fed, kept for about an hour and then dropped; the only thing
//! ever written is the slice the builder cuts from it, which is allowlisted,
//! name-blinded and verified, and only for a fight the meter saved.

use std::collections::VecDeque;

use parking_lot::Mutex;

use crate::capture::evidence_slice::{CapturedPacket, LEAD_IN_MS, PRELUDE_MS, TAIL_MS};

/// Long enough for the slice's prelude plus a long fight. Older than this and
/// a segment can no longer be part of any slice worth cutting.
const KEEP_MS: i64 = PRELUDE_MS + LEAD_IN_MS + TAIL_MS + 35 * 60_000;
/// A ceiling that an hour of real play does not approach (a half-hour capture
/// is about 3 MB). It exists so nothing unexpected can grow this without bound.
const MAX_BYTES: usize = 96 * 1024 * 1024;

struct Ring {
    packets: VecDeque<CapturedPacket>,
    bytes: usize,
}

static RING: Mutex<Ring> = Mutex::new(Ring { packets: VecDeque::new(), bytes: 0 });

/// Remember one captured segment. Called for exactly the segments the packet
/// logger would have been given, with the clock the parser stamps hits with.
pub fn record(src_port: u16, data: &[u8]) {
    let now = crate::clock::now_ms();
    let mut ring = RING.lock();
    ring.bytes += data.len();
    ring.packets.push_back(CapturedPacket {
        captured_at_ms: now,
        stream: format!("Client:{src_port}"),
        bytes: data.to_vec(),
    });
    while let Some(front) = ring.packets.front() {
        if front.captured_at_ms >= now - KEEP_MS && ring.bytes <= MAX_BYTES {
            break;
        }
        let gone = ring.packets.pop_front().map(|p| p.bytes.len()).unwrap_or(0);
        ring.bytes -= gone;
    }
}

/// Everything currently held, oldest first.
pub fn snapshot() -> Vec<CapturedPacket> {
    RING.lock().packets.iter().cloned().collect()
}

#[cfg(test)]
pub fn clear() {
    let mut ring = RING.lock();
    ring.packets.clear();
    ring.bytes = 0;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_recent_segments_and_forgets_old_ones() {
        clear();
        crate::clock::set_override(Some(1_000_000));
        record(7777, &[1, 2, 3]);
        crate::clock::set_override(Some(1_000_000 + KEEP_MS + 1));
        record(7777, &[4, 5]);
        let held = snapshot();
        crate::clock::set_override(None);
        assert_eq!(held.len(), 1);
        assert_eq!(held[0].bytes, vec![4, 5]);
        assert_eq!(held[0].stream, "Client:7777");
        clear();
    }
}
