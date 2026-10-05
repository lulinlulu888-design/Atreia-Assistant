// Standalone packet-capture diagnostic for A2Tools DPS Meter.
//
// Purpose: after an AION 2 game update, the meter stops detecting packets.
// The built-in packet logger only runs AFTER the combat port locks (which
// itself requires the MAGIC signature 06 00 36), so it cannot diagnose a
// signature/opcode change. This tool taps the RAW pcap stream before any
// filtering and dumps everything, plus a live per-flow summary that shows
// which connection is the game and whether the known signatures still appear.
//
// Run from an ADMIN terminal (Npcap requires it), with the game running:
//     cargo run --bin packet_dump
// or run the built exe directly (as admin):
//     target\debug\packet_dump.exe
//
// Go fight something for ~30s, then press Ctrl+C. Send me the printed
// summary and the dump file path.
//
// Also the server-collection tool: every game server the client is sent to
// (enter each server, an empty character select is enough) is printed and
// kept in game_servers.json beside the dump; flows_<stamp>.txt logs each new
// connection with a timestamp, plus HTTPS hostnames. Picking a region at the
// region selector shows its login server there (port 13700).

use std::collections::HashMap;
use std::io::Write;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use a2tools_dps_meter_lib::capture::captured_payload::CapturedPayload;
use a2tools_dps_meter_lib::capture::pcap_capturer::PcapCapturer;
use tokio::sync::mpsc;

// Known protocol signatures (pre-update) we want to detect presence of.
const MAGIC: [u8; 3] = [0x06, 0x00, 0x36]; // combat port-lock signature
const SIG_DAMAGE: [u8; 2] = [0x04, 0x38]; // damage packet opcode
const SIG_DOT: [u8; 2] = [0x05, 0x38]; // damage-over-time
const SIG_DEATH: [u8; 2] = [0x41, 0x36]; // death event
const SIG_HP: [u8; 2] = [0x1B, 0x92]; // hp/mp update
const SIG_SPAWN: [u8; 2] = [0x40, 0x36]; // mob/summon spawn
const SIG_BUNDLE: [u8; 2] = [0xFF, 0xFF]; // lz4 compressed bundle

const TLS_CONTENT_TYPES: [u8; 4] = [0x14, 0x15, 0x16, 0x17];
const TLS_VERSIONS: [u8; 5] = [0x00, 0x01, 0x02, 0x03, 0x04];

const MAX_DUMP_BYTES: u64 = 80 * 1024 * 1024; // safety cap on dump file

#[derive(Default, Clone)]
struct FlowStats {
    device: String,
    packets: u64,
    bytes: u64,
    tls_packets: u64,
    has_magic: u64,
    has_damage: u64,
    has_dot: u64,
    has_death: u64,
    has_hp: u64,
    has_spawn: u64,
    has_bundle: u64,
    first_seen: i64,
    last_seen: i64,
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

fn looks_like_tls(data: &[u8]) -> bool {
    if data.len() < 3 {
        return false;
    }
    TLS_CONTENT_TYPES.contains(&data[0]) && data[1] == 0x03 && TLS_VERSIONS.contains(&data[2])
}

fn contains(data: &[u8], needle: &[u8]) -> bool {
    if needle.len() > data.len() {
        return false;
    }
    data.windows(needle.len()).any(|w| w == needle)
}

/// The body of the game's `0F 39 00 00` server-connect record, which the
/// server sends the moment the client enters a server (even to an empty
/// character select; not for a full server, which refuses first):
///
/// ```text
/// 0F 39 00 00 <server id u16 LE> <n u8> <IPv4 as ASCII, n bytes> <port u16 LE>
/// ```
///
/// The id keys the game's string table (`ServerName_<id>_desc`). Requiring a
/// whole dotted IPv4 and a non-zero port keeps chance matches out.
fn parse_server_connect(body: &[u8]) -> Option<(u16, std::net::Ipv4Addr, u16)> {
    let id = u16::from_le_bytes([*body.first()?, *body.get(1)?]);
    let n = *body.get(2)? as usize;
    if !(7..=15).contains(&n) {
        return None;
    }
    let address: std::net::Ipv4Addr = std::str::from_utf8(body.get(3..3 + n)?).ok()?.parse().ok()?;
    let port = u16::from_le_bytes([*body.get(3 + n)?, *body.get(4 + n)?]);
    (id != 0 && port != 0).then_some((id, address, port))
}

/// Keep every server seen in `game_servers.json` beside the dump, keyed by id.
fn record_game_server(flow_path: &std::path::Path, id: u16, address: &std::net::Ipv4Addr, port: u16) {
    let path = flow_path.with_file_name("game_servers.json");
    let mut all: serde_json::Map<String, serde_json::Value> = std::fs::read_to_string(&path)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default();
    let now = chrono::Local::now().to_rfc3339();
    let entry = all.entry(id.to_string()).or_insert_with(|| serde_json::json!({ "firstSeen": now }));
    entry["address"] = serde_json::json!(address.to_string());
    entry["port"] = serde_json::json!(port);
    entry["lastSeen"] = serde_json::json!(now);
    if let Ok(text) = serde_json::to_string_pretty(&all) {
        let _ = std::fs::write(&path, text);
    }
}

/// The server name from a TLS ClientHello, if this payload is one.
fn tls_sni(d: &[u8]) -> Option<String> {
    // record: 16 03 xx len(2) | handshake: 01 len(3) ver(2) random(32)
    if d.len() < 44 || d[0] != 0x16 || d[1] != 0x03 || d[5] != 0x01 {
        return None;
    }
    let mut p = 5 + 4 + 2 + 32;
    let sid = *d.get(p)? as usize;
    p += 1 + sid;
    let cs = u16::from_be_bytes([*d.get(p)?, *d.get(p + 1)?]) as usize;
    p += 2 + cs;
    let cm = *d.get(p)? as usize;
    p += 1 + cm;
    let ext_end = p + 2 + u16::from_be_bytes([*d.get(p)?, *d.get(p + 1)?]) as usize;
    p += 2;
    while p + 4 <= ext_end.min(d.len()) {
        let ty = u16::from_be_bytes([d[p], d[p + 1]]);
        let len = u16::from_be_bytes([d[p + 2], d[p + 3]]) as usize;
        if ty == 0 {
            // server_name list: len(2) type(1)=0 name_len(2) name
            let n = u16::from_be_bytes([*d.get(p + 7)?, *d.get(p + 8)?]) as usize;
            return std::str::from_utf8(d.get(p + 9..p + 9 + n)?).ok().map(str::to_string);
        }
        p += 4 + len;
    }
    None
}

fn to_hex(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        s.push_str(&format!("{:02X}", b));
    }
    s
}

#[tokio::main]
async fn main() {
    // Console logging so PcapCapturer's device-list / "Capture active" lines show.
    tracing_subscriber::fmt()
        .with_target(false)
        .with_max_level(tracing::Level::INFO)
        .init();

    let stamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
    let dump_path = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join(format!("rawpackets_{}.txt", stamp));

    let file = match std::fs::File::create(&dump_path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("FATAL: could not create dump file {}: {}", dump_path.display(), e);
            return;
        }
    };
    let mut dump = std::io::BufWriter::new(file);
    let flow_path = dump_path.with_file_name(format!("flows_{}.txt", stamp));
    let mut flow_log = std::fs::File::create(&flow_path).expect("flow log");
    println!(" Flow log:  {}", flow_path.display());
    let _ = writeln!(
        dump,
        "# A2Tools raw packet dump {}\n# Format: TIMESTAMP_MS|SRCIP:SRCPORT->DSTIP:DSTPORT|DEV|TLS/PLAIN|LEN|HEX\n",
        chrono::Local::now().format("%+")
    );

    println!("\n========================================================");
    println!(" A2Tools DPS Meter — RAW packet capture (diagnostic)");
    println!("========================================================");
    println!(" Dump file: {}", dump_path.display());
    println!(" 1. Make sure AION 2 is running.");
    println!(" 2. Go fight something and deal damage for ~30s.");
    println!(" 3. Press Ctrl+C to stop, then send me the summary + dump file.");
    println!("--------------------------------------------------------\n");

    let (tx, mut rx) = mpsc::channel::<CapturedPayload>(8192);
    let capturer = PcapCapturer::new(tx);
    capturer.start();

    // Flush + final summary on Ctrl+C (handler flips a global flag).
    install_ctrlc_handler();
    let stop = &STOP_FLAG;

    let mut flows: HashMap<(String, u16, String, u16), FlowStats> = HashMap::new();
    let mut dumped_bytes: u64 = 0;
    let mut dump_capped = false;
    let mut last_summary = Instant::now();
    let mut total_packets: u64 = 0;

    loop {
        if stop.load(Ordering::SeqCst) {
            break;
        }

        let cap = match tokio::time::timeout(Duration::from_millis(500), rx.recv()).await {
            Ok(Some(c)) => c,
            Ok(None) => break, // channel closed
            Err(_) => {
                // timeout: periodic summary even when idle
                if last_summary.elapsed() >= Duration::from_secs(3) {
                    print_summary(&flows, total_packets, dumped_bytes, dump_capped);
                    last_summary = Instant::now();
                }
                continue;
            }
        };

        total_packets += 1;
        let src_ip = cap.src_ip.clone().unwrap_or_default();
        let dst_ip = cap.dst_ip.clone().unwrap_or_default();
        let dev = cap.device_name.clone().unwrap_or_default();
        let is_tls = looks_like_tls(&cap.data);

        let key = (src_ip.clone(), cap.src_port, dst_ip.clone(), cap.dst_port);
        // One timestamped line per new connection (and per TLS hostname), so
        // connections can be matched to what the player was doing at the time.
        if !flows.contains_key(&key) {
            let _ = writeln!(
                flow_log,
                "{} NEWFLOW {}:{} -> {}:{} dev={} tls={} len={} head={}",
                chrono::Local::now().format("%H:%M:%S%.3f"),
                src_ip, cap.src_port, dst_ip, cap.dst_port, dev, is_tls, cap.data.len(),
                to_hex(&cap.data[..cap.data.len().min(24)])
            );
            let _ = flow_log.flush();
        }
        if let Some(host) = tls_sni(&cap.data) {
            let _ = writeln!(
                flow_log,
                "{} SNI {} ({}:{} -> {}:{})",
                chrono::Local::now().format("%H:%M:%S%.3f"),
                host, src_ip, cap.src_port, dst_ip, cap.dst_port
            );
            let _ = flow_log.flush();
        }
        let st = flows.entry(key).or_insert_with(|| {
            let mut s = FlowStats::default();
            s.device = dev.clone();
            s.first_seen = now_ms();
            s
        });
        st.packets += 1;
        st.bytes += cap.data.len() as u64;
        st.last_seen = now_ms();
        if is_tls {
            st.tls_packets += 1;
        } else {
            if contains(&cap.data, &MAGIC) { st.has_magic += 1; }
            if contains(&cap.data, &SIG_DAMAGE) { st.has_damage += 1; }
            if contains(&cap.data, &SIG_DOT) { st.has_dot += 1; }
            if contains(&cap.data, &SIG_DEATH) { st.has_death += 1; }
            if contains(&cap.data, &SIG_HP) { st.has_hp += 1; }
            if contains(&cap.data, &SIG_SPAWN) { st.has_spawn += 1; }
            if contains(&cap.data, &SIG_BUNDLE) { st.has_bundle += 1; }
        }

        // The game's server-connect record, wherever it turns up.
        if let Some(at) = cap.data.windows(4).position(|w| w == [0x0F, 0x39, 0x00, 0x00]) {
            let _ = writeln!(
                flow_log,
                "{} SERVERCONNECT {}:{} -> {}:{} {}",
                chrono::Local::now().format("%H:%M:%S%.3f"),
                src_ip, cap.src_port, dst_ip, cap.dst_port,
                to_hex(&cap.data[at..cap.data.len().min(at + 32)])
            );
            let _ = flow_log.flush();
            if let Some((id, address, port)) = parse_server_connect(&cap.data[at + 4..]) {
                println!("game server: id {} at {}:{}", id, address, port);
                record_game_server(&flow_path, id, &address, port);
            }
        }

        // Dump non-TLS payloads (TLS is encrypted = useless hex, only count it).
        // Web ports are skipped outright: TLS continuation segments don't start
        // with a record header, and browser traffic filled the cap in minutes.
        let web = [80u16, 443].iter().any(|p| cap.src_port == *p || cap.dst_port == *p);
        if !is_tls && !web && !dump_capped {
            let line = format!(
                "{}|{}:{}->{}:{}|{}|PLAIN|{}|{}\n",
                cap.captured_at_ms,
                src_ip, cap.src_port, dst_ip, cap.dst_port,
                dev, cap.data.len(), to_hex(&cap.data)
            );
            if dump.write_all(line.as_bytes()).is_ok() {
                let _ = dump.flush();
                dumped_bytes += line.len() as u64;
                if dumped_bytes >= MAX_DUMP_BYTES {
                    dump_capped = true;
                    println!("\n[!] Dump file hit {} MB cap — stopping further writes (stats still live).\n", MAX_DUMP_BYTES / (1024 * 1024));
                }
            }
        }

        if last_summary.elapsed() >= Duration::from_secs(3) {
            print_summary(&flows, total_packets, dumped_bytes, dump_capped);
            last_summary = Instant::now();
        }
    }

    capturer.stop();
    let _ = dump.flush();

    println!("\n\n================= FINAL SUMMARY =================");
    print_summary(&flows, total_packets, dumped_bytes, dump_capped);
    println!("\nDump file written to:\n  {}", dump_path.display());
    println!("Send me that file + the table above.\n");
}

fn print_summary(
    flows: &HashMap<(String, u16, String, u16), FlowStats>,
    total_packets: u64,
    dumped_bytes: u64,
    capped: bool,
) {
    let mut rows: Vec<(&(String, u16, String, u16), &FlowStats)> = flows.iter().collect();
    rows.sort_by(|a, b| b.1.bytes.cmp(&a.1.bytes));

    println!(
        "\n--- flows: {} | total pkts: {} | dumped: {} KB{} ---",
        flows.len(),
        total_packets,
        dumped_bytes / 1024,
        if capped { " (CAPPED)" } else { "" }
    );
    println!(
        "{:<42} {:>6} {:>9} {:>5} {:>5} {:>4} {:>4} {:>4} {:>4} {:>4} {:>4}",
        "flow (src->dst)", "pkts", "bytes", "TLS", "MAG", "DMG", "DOT", "DTH", "HP", "SPN", "BND"
    );
    for (k, s) in rows.iter().take(18) {
        let flow = format!("{}:{}->{}:{}", k.0, k.1, k.2, k.3);
        let flow = if flow.len() > 42 { flow[flow.len() - 42..].to_string() } else { flow };
        println!(
            "{:<42} {:>6} {:>9} {:>5} {:>5} {:>4} {:>4} {:>4} {:>4} {:>4} {:>4}",
            flow, s.packets, s.bytes, s.tls_packets,
            s.has_magic, s.has_damage, s.has_dot, s.has_death, s.has_hp, s.has_spawn, s.has_bundle
        );
    }
    println!("(MAG=06 00 36 lock sig, DMG=04 38, DOT=05 38, DTH=41 36, HP=1B 92, SPN=40 36, BND=FF FF)");
}

// Global stop flag; the Ctrl+C handler sets it, the main loop polls it.
static STOP_FLAG: AtomicBool = AtomicBool::new(false);

#[cfg(windows)]
fn install_ctrlc_handler() {
    unsafe extern "system" fn handler(_ctrl_type: u32) -> i32 {
        STOP_FLAG.store(true, Ordering::SeqCst);
        1 // TRUE: handled (don't terminate immediately; let main flush & exit)
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn SetConsoleCtrlHandler(
            handler: Option<unsafe extern "system" fn(u32) -> i32>,
            add: i32,
        ) -> i32;
    }
    unsafe {
        SetConsoleCtrlHandler(Some(handler), 1);
    }
}

#[cfg(not(windows))]
fn install_ctrlc_handler() {}

#[cfg(test)]
mod tests {
    use super::parse_server_connect;

    fn hex(s: &str) -> Vec<u8> {
        s.split_whitespace().map(|b| u8::from_str_radix(b, 16).unwrap()).collect()
    }

    #[test]
    fn reads_the_server_connect_records_seen_on_2026_10_01() {
        let ariel = hex("1A 05 0E 31 39 33 2E 32 30 32 2E 31 31 32 2E 39 39 10 34 17 03");
        assert_eq!(parse_server_connect(&ariel), Some((1306, "193.202.112.99".parse().unwrap(), 13328)));
        let nezekan = hex("DE 05 0F 31 39 33 2E 32 30 32 2E 31 31 32 2E 32 30 30 10 34 9A 02");
        assert_eq!(parse_server_connect(&nezekan), Some((1502, "193.202.112.200".parse().unwrap(), 13328)));
        assert_eq!(parse_server_connect(&hex("1A 05 0E 31 39 33 2E 32 30 32 2E 31 31 32 2E 39 39 00 00")), None);
        assert_eq!(parse_server_connect(&hex("1A 05 0E 41 42 43")), None);
    }
}
