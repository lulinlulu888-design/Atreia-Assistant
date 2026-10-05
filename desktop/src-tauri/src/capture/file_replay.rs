use std::io::BufRead;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use tokio::sync::mpsc;
use tracing::{error, info};

use super::captured_payload::CapturedPayload;

/// Replays captured packets from a text file.
/// Format: TIMESTAMP|STREAMKEY|HEX_DATA (lines starting with # are comments)
pub struct FileReplay {
    running: Arc<AtomicBool>,
}

impl FileReplay {
    pub fn new() -> Self {
        Self {
            running: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Replay a packet capture file, sending payloads to the channel.
    /// Set `accelerate` to true to skip inter-packet delays.
    pub async fn start(
        &self,
        file_path: &str,
        sender: mpsc::Sender<CapturedPayload>,
        accelerate: bool,
    ) {
        if self.running.swap(true, Ordering::SeqCst) {
            return;
        }

        let path = Path::new(file_path);
        if !path.exists() {
            error!("Replay file not found: {}", file_path);
            self.running.store(false, Ordering::SeqCst);
            return;
        }

        info!("Starting offline replay from {}", file_path);

        let file = match std::fs::File::open(path) {
            Ok(f) => f,
            Err(e) => {
                error!("Failed to open replay file: {}", e);
                self.running.store(false, Ordering::SeqCst);
                return;
            }
        };

        let reader = std::io::BufReader::new(file);
        let mut line_count = 0;
        let mut packet_count = 0;

        for line in reader.lines() {
            if !self.running.load(Ordering::SeqCst) {
                break;
            }

            let line = match line {
                Ok(l) => l,
                Err(_) => continue,
            };

            line_count += 1;

            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            let parts: Vec<&str> = line.splitn(3, '|').collect();
            if parts.len() != 3 {
                continue;
            }

            let _timestamp = parts[0];
            let stream_key = parts[1];
            let hex_data = parts[2];

            // Extract port from "Client:PORT"
            let src_port: u16 = stream_key
                .rsplit(':')
                .next()
                .and_then(|s| s.parse().ok())
                .unwrap_or(55555);
            let dst_port: u16 = 50349;

            let data = match decode_hex(hex_data) {
                Some(d) => d,
                None => continue,
            };

            let payload = CapturedPayload {
                src_port,
                dst_port,
                data,
                device_name: Some("FileReplay".to_string()),
                captured_at_ms: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as i64,
                src_ip: None,
                dst_ip: None,
                tcp_seq: 0,
                tcp_ack: 0,
            };

            let _ = sender.send(payload).await;
            packet_count += 1;

            if !accelerate {
                // Small yield to prevent blocking the runtime
                tokio::task::yield_now().await;
            }
        }

        info!(
            "Finished replaying file: {} lines, {} packets",
            line_count, packet_count
        );
        self.running.store(false, Ordering::SeqCst);
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);
    }
}

fn decode_hex(hex: &str) -> Option<Vec<u8>> {
    let clean: String = hex.chars().filter(|c| !c.is_whitespace()).collect();
    if clean.len() % 2 != 0 {
        return None;
    }
    let mut bytes = Vec::with_capacity(clean.len() / 2);
    for chunk in clean.as_bytes().chunks(2) {
        let high = hex_digit(chunk[0])?;
        let low = hex_digit(chunk[1])?;
        bytes.push((high << 4) | low);
    }
    Some(bytes)
}

fn hex_digit(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'a'..=b'f' => Some(b - b'a' + 10),
        b'A'..=b'F' => Some(b - b'A' + 10),
        _ => None,
    }
}
