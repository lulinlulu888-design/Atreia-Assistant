use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use tokio::sync::mpsc;
use tracing::info;

use crate::capture::captured_payload::CapturedPayload;
use crate::capture::combat_port_detector::CombatPortDetector;
use crate::capture::stream_assembler::StreamAssembler;
use crate::capture::stream_processor::StreamProcessor;
use crate::combat::data_storage::DataStorage;
use crate::combat::ping_tracker::PingTracker;
use crate::i18n::lookup::{NpcLookup, SkillLookup};
use crate::platform::window_detector;

/// Pre-lock combat signatures: a cheap gate deciding which packets are worth
/// running through the parser before a port is locked. The port only actually
/// locks when the parser extracts *real damage* (see `run`), so this gate just
/// limits parse attempts — it does not by itself decide the lock.
///
/// The game's per-record terminator `?? 00 36` had leading byte `0x06`
/// pre-2026-06; the June 2026 update changed it to `0x0E` (`06 00 36` ->
/// `0E 00 36`), which silently broke the old single-magic port detection while
/// leaving the parser itself unaffected. We accept both leading bytes so the
/// gate survives that transition.
const COMBAT_SIGNATURES: [&[u8]; 2] = [
    &[0x0E, 0x00, 0x36], // current (post June 2026) record terminator
    &[0x06, 0x00, 0x36], // legacy terminator (pre June 2026)
];
/// How many signature-bearing server->client packets a single flow must produce
/// *within SIGNATURE_WINDOW_MS* before it may lock the port. The live game stream
/// emits the record terminator ~19x/sec even while idle (movement/heartbeat), so it
/// clears this in well under a second. A coincidental loopback service (e.g. a local
/// helper on port 16005 during a game cold-start) produces the 3-byte pattern only a
/// handful of times over minutes and never reaches the threshold inside the window —
/// so it can no longer hijack the lock. The window (vs. a plain running total) means
/// only a *high-rate* flow qualifies, not one that slowly drips coincidental matches.
const SIGNATURE_LOCK_THRESHOLD: u32 = 12;
/// Sliding window for the signature-rate lock; the THRESHOLD packets must land within
/// this span. Reset the per-flow count whenever the gap since the last hit exceeds it.
const SIGNATURE_WINDOW_MS: i64 = 3_000;
const TLS_CONTENT_TYPES: [u8; 4] = [0x14, 0x15, 0x16, 0x17];
const TLS_VERSIONS: [u8; 5] = [0x00, 0x01, 0x02, 0x03, 0x04];
const WINDOW_CHECK_STOPPED_MS: i64 = 10_000;
const WINDOW_CHECK_RUNNING_MS: i64 = 60_000;
const STALE_CONNECTION_MS: i64 = 120_000;
/// While no port is locked, how often to log what the capture is seeing. Before
/// the lock every gate is silent, so without this a meter that never locks
/// leaves a log that cannot say why.
const UNLOCKED_REPORT_MS: i64 = 30_000;

/// Per-device packet counts while unlocked, for the periodic report. It is
/// written when a packet arrives, so a capture that sees nothing at all stays
/// silent; the device list at startup covers that case.
#[derive(Default)]
struct UnlockedStats {
    /// device -> (packets, packets carrying a combat signature)
    by_device: HashMap<String, (u64, u64)>,
    /// Packets dropped because no AION2 window was found.
    no_window: u64,
}

impl UnlockedStats {
    fn note(&mut self, cap: &CapturedPayload) {
        let device = cap.device_name.clone().unwrap_or_else(|| "?".into());
        let entry = self.by_device.entry(device).or_default();
        entry.0 += 1;
        if contains_any(&cap.data, &COMBAT_SIGNATURES) {
            entry.1 += 1;
        }
    }

    fn report(&self, window_found: bool) -> String {
        let mut devices: Vec<_> = self.by_device.iter().collect();
        devices.sort_by(|a, b| b.1 .0.cmp(&a.1 .0));
        let mut out = format!(
            "Not locked yet (last {} s): AION2 window {}",
            UNLOCKED_REPORT_MS / 1000,
            if window_found { "found" } else { "NOT found" }
        );
        if self.no_window > 0 {
            out += &format!(", {} packets ignored for that", self.no_window);
        }
        if !window_found {
            // What might have been the game, so the next log says why it was
            // not recognised (a localised title, a launcher, ...).
            let candidates = window_detector::describe_candidates();
            if candidates.is_empty() {
                out += " (no window or program mentions \"aion\")";
            } else {
                out += &format!(" (look-alikes: {})", candidates.join(" | "));
            }
        }
        for (device, (packets, marked)) in devices.iter().take(8) {
            out += &format!("; {}: {} packets, {} with game markers", device, packets, marked);
        }
        out
    }
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

/// Routes captured packets through port detection, filtering, and the parsing pipeline.
pub struct CaptureDispatcher {
    data_storage: Arc<DataStorage>,
    skill_lookup: Arc<SkillLookup>,
    npc_lookup: Arc<NpcLookup>,
    port_detector: Arc<CombatPortDetector>,
    ping_tracker: Arc<PingTracker>,
    dot_skill_ids: std::collections::HashSet<i32>,
    suspended: Arc<AtomicBool>,
}

impl CaptureDispatcher {
    pub fn new(
        data_storage: Arc<DataStorage>,
        skill_lookup: Arc<SkillLookup>,
        npc_lookup: Arc<NpcLookup>,
        port_detector: Arc<CombatPortDetector>,
        ping_tracker: Arc<PingTracker>,
    ) -> Self {
        Self {
            data_storage,
            skill_lookup,
            npc_lookup,
            port_detector,
            ping_tracker,
            dot_skill_ids: std::collections::HashSet::new(),
            suspended: Arc::new(AtomicBool::new(false)),
        }
    }

    pub fn set_dot_skill_ids(&mut self, ids: std::collections::HashSet<i32>) {
        self.dot_skill_ids = ids;
    }

    /// Share the "suspended" switch with whoever flips it (the header's
    /// suspend button, through `suspend_capture`). While it is on, captured
    /// packets are dropped, so nothing is counted and the fight timer stops.
    pub fn use_suspend_flag(&mut self, flag: Arc<AtomicBool>) {
        self.suspended = flag;
    }

    /// Run the dispatch loop, consuming packets from the channel.
    pub async fn run(&self, mut receiver: mpsc::Receiver<CapturedPayload>) {
        let mut assemblers: HashMap<(u16, u16), (StreamAssembler, StreamProcessor)> = HashMap::new();
        // Per-flow count of signature-bearing packets seen while still unlocked, used
        // for the no-combat-needed signature lock (see SIGNATURE_LOCK_THRESHOLD).
        // Per-flow signature-rate tracker: (count_in_window, last_hit_ms).
        let mut sig_hits: HashMap<(u16, u16), (u32, i64)> = HashMap::new();
        let mut last_window_check_ms: i64 = 0;
        let mut is_aion_running = false;
        let mut window_logged: Option<bool> = None;
        let mut unlocked_stats = UnlockedStats::default();
        let mut last_unlocked_report_ms = now_ms();

        while let Some(cap) = receiver.recv().await {
            if self.suspended.load(Ordering::SeqCst) {
                continue;
            }

            // Check AION window
            let now = now_ms();
            let interval = if is_aion_running { WINDOW_CHECK_RUNNING_MS } else { WINDOW_CHECK_STOPPED_MS };
            if now - last_window_check_ms >= interval {
                last_window_check_ms = now;
                let title = window_detector::find_aion2_window_title();
                let running = title.is_some();
                if window_logged != Some(running) {
                    match &title {
                        Some(t) => info!("AION2 window found: {:?}", t),
                        None => info!(
                            "No AION2 window found (looking for a title starting with \"AION2\", or a window owned by AION2.exe); packets are ignored until there is one"
                        ),
                    }
                    window_logged = Some(running);
                }
                if !running && is_aion_running {
                    self.port_detector.reset();
                    self.ping_tracker.reset();
                    assemblers.clear();
                    sig_hits.clear();
                }
                is_aion_running = running;
            }

            // While unlocked, count what arrives on each device and report it
            // now and then, so a log from a meter that never locks says why.
            if self.port_detector.current_port().is_none() {
                unlocked_stats.note(&cap);
                if !is_aion_running {
                    unlocked_stats.no_window += 1;
                }
                if now - last_unlocked_report_ms >= UNLOCKED_REPORT_MS {
                    info!("{}", unlocked_stats.report(is_aion_running));
                    unlocked_stats = UnlockedStats::default();
                    last_unlocked_report_ms = now;
                }
            } else {
                last_unlocked_report_ms = now;
            }

            if !is_aion_running {
                continue;
            }

            // Stale connection check
            if is_aion_running && self.port_detector.current_port().is_some() {
                let last_parsed = self.port_detector.last_parsed_at_ms();
                if last_parsed > 0 && now - last_parsed > STALE_CONNECTION_MS {
                    info!("No packets parsed for {}ms, resetting lock", now - last_parsed);
                    self.port_detector.reset();
                    self.ping_tracker.reset();
                    assemblers.clear();
                    sig_hits.clear();
                }
            }

            let current_port = self.port_detector.current_port();
            let locked_device = self.port_detector.current_device();

            // Device filter
            if let Some(ref dev) = locked_device {
                if !device_matches(dev, cap.device_name.as_deref()) {
                    continue;
                }
            }

            // Preferred device filter
            if current_port.is_none() {
                if let Some(ref pref) = self.port_detector.preferred_device() {
                    if !device_matches(pref, cap.device_name.as_deref()) {
                        continue;
                    }
                }
            }

            // Port filter
            if let Some(port) = current_port {
                if cap.src_port != port && cap.dst_port != port {
                    continue;
                }
            }

            // Feed to ping tracker — also marks connection alive to prevent stale reset
            if let Some(port) = current_port {
                let had_ping_before = self.ping_tracker.current_ping_ms();
                self.ping_tracker.on_packet(&cap, port);
                let has_ping_now = self.ping_tracker.current_ping_ms();
                // If a new ping was received, mark the connection as active
                if has_ping_now != had_ping_before {
                    self.port_detector.mark_packet_parsed();
                }
            }

            // Only parse server->client (src == locked port)
            if let Some(port) = current_port {
                if cap.src_port != port {
                    continue;
                }
            }

            // Pre-lock filters. Once a port is locked these checks are skipped
            // entirely (the port/direction filters above already gate traffic),
            // keeping the hot path cheap during heavy combat.
            let unlocked = current_port.is_none();
            if unlocked {
                if looks_like_tls(&cap.data) {
                    continue;
                }
                if !contains_any(&cap.data, &COMBAT_SIGNATURES) {
                    continue;
                }
            }

            // Log raw packet if packet logging is enabled
            crate::logging::logger::log_packet(&cap);
            // And keep it in memory for a while, so a boss fight can be shared
            // without packet logging having been on. See `share::ring`.
            crate::share::ring::record(cap.src_port, &cap.data);

            // Get or create assembler
            let a = cap.src_port.min(cap.dst_port);
            let b = cap.src_port.max(cap.dst_port);
            let key = (a, b);

            let (assembler, processor) = assemblers.entry(key).or_insert_with(|| {
                let mut proc = StreamProcessor::new(self.data_storage.clone(), self.skill_lookup.clone(), self.npc_lookup.clone());
                proc.set_dot_skill_ids(self.dot_skill_ids.clone());
                (StreamAssembler::new(), proc)
            });

            if unlocked {
                self.port_detector.register_candidate(cap.src_port, key, cap.device_name.as_deref());
                // Count this signature-bearing packet against its source port (the
                // signature only ever travels server->client). The lock decision is
                // made below, after process_chunk, so we don't touch `assemblers`
                // while the assembler for this flow is still borrowed.
                // Windowed signature rate: reset the count if too long since the last
                // hit, so only a sustained high-rate flow (the live game) accumulates.
                let now = now_ms();
                let slot = sig_hits.entry(key).or_insert((0, now));
                if now - slot.1 > SIGNATURE_WINDOW_MS {
                    slot.0 = 0;
                }
                slot.0 += 1;
                slot.1 = now;
            }

            // A flow locks the port only by sustaining the game's signature RATE
            // (SIGNATURE_LOCK_THRESHOLD hits within SIGNATURE_WINDOW_MS). We deliberately
            // do NOT lock on a single parsed-damage event any more: a coincidental
            // loopback service can momentarily misparse as "damage" and steal the lock
            // during a cold start (observed locking onto port 16005 instead of the game).
            // Real combat produces a flood of signatures too, so the rate gate covers
            // both idle and combat while staying robust. Spawns/names are still parsed
            // into the store pre-lock, so mobs seen before the first fight stay identified.
            let parsed = assembler.process_chunk(&cap.data, processor);

            let signature_locked =
                unlocked && sig_hits.get(&key).map(|(c, _)| *c).unwrap_or(0) >= SIGNATURE_LOCK_THRESHOLD;
            if signature_locked && self.port_detector.current_port().is_none() {
                self.port_detector.confirm_candidate(cap.src_port, cap.dst_port, cap.device_name.as_deref());
                // On lock, GC the orphaned candidate assemblers (the relay's
                // duplicate external flows) so only the locked flow is processed.
                if self.port_detector.current_port().is_some() {
                    assemblers.retain(|k, _| *k == key);
                    sig_hits.clear();
                }
            }

            if parsed {
                self.port_detector.mark_packet_parsed();
            }
        }
    }
}

fn looks_like_tls(data: &[u8]) -> bool {
    if data.len() < 3 {
        return false;
    }
    let content_type = data[0];
    let major = data[1];
    let minor = data[2];
    TLS_CONTENT_TYPES.contains(&content_type) && major == 0x03 && TLS_VERSIONS.contains(&minor)
}

fn contains_bytes(data: &[u8], needle: &[u8]) -> bool {
    needle.len() <= data.len() && data.windows(needle.len()).any(|w| w == needle)
}

fn contains_any(data: &[u8], needles: &[&[u8]]) -> bool {
    needles.iter().any(|n| contains_bytes(data, n))
}

fn device_matches(locked: &str, packet_device: Option<&str>) -> bool {
    match packet_device {
        Some(d) if !d.trim().is_empty() => d.trim().eq_ignore_ascii_case(locked),
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cap(device: &str, data: &[u8]) -> CapturedPayload {
        CapturedPayload {
            src_port: 1,
            dst_port: 2,
            data: data.to_vec(),
            device_name: Some(device.into()),
            captured_at_ms: 0,
            src_ip: None,
            dst_ip: None,
            tcp_seq: 0,
            tcp_ack: 0,
        }
    }

    #[test]
    fn unlocked_report_names_each_device_and_the_window() {
        let mut stats = UnlockedStats::default();
        stats.note(&cap("NordLynx Tunnel", &[0x0E, 0x00, 0x36, 0x01]));
        stats.note(&cap("NordLynx Tunnel", &[0x01, 0x02]));
        stats.note(&cap("Realtek", &[0x01]));
        stats.no_window = 3;
        let line = stats.report(false);
        assert!(line.contains("AION2 window NOT found, 3 packets ignored for that"), "{line}");
        assert!(line.contains("NordLynx Tunnel: 2 packets, 1 with game markers"), "{line}");
        assert!(line.contains("Realtek: 1 packets, 0 with game markers"), "{line}");
        assert!(line.find("NordLynx").unwrap() < line.find("Realtek").unwrap(), "busiest first");
    }
}
