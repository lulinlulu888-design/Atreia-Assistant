use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicI64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use parking_lot::Mutex;
use tracing::info;

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}

/// How long to hold off locking a physical/external port after the first combat
/// candidate, giving a loopback relay tunnel (ping-reducer) time to surface and
/// take precedence. A loopback flow locks immediately and ignores this window;
/// direct-connection users simply wait this long once before the first lock.
const LOOPBACK_GRACE_MS: i64 = 2500;

/// Global combat port detector — identifies which network device and port
/// carry AION 2 game traffic by looking for the combat signature bytes.
pub struct CombatPortDetector {
    inner: Mutex<Inner>,
    last_parsed_at_ms: AtomicI64,
}

struct Inner {
    locked_port: Option<u16>,
    locked_device: Option<String>,
    candidates: HashMap<u16, Option<String>>,
    device_flows: HashMap<String, HashSet<(u16, u16)>>,
    preferred_device: Option<String>,
    /// Wall-clock of the first combat candidate seen since the last reset; used
    /// to time the loopback-preference grace window.
    first_candidate_ms: i64,
}

impl CombatPortDetector {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(Inner {
                locked_port: None,
                locked_device: None,
                candidates: HashMap::new(),
                device_flows: HashMap::new(),
                preferred_device: None,
                first_candidate_ms: 0,
            }),
            last_parsed_at_ms: AtomicI64::new(0),
        }
    }

    pub fn current_port(&self) -> Option<u16> {
        self.inner.lock().locked_port
    }

    pub fn current_device(&self) -> Option<String> {
        self.inner.lock().locked_device.clone()
    }

    pub fn last_parsed_at_ms(&self) -> i64 {
        self.last_parsed_at_ms.load(Ordering::Relaxed)
    }

    pub fn preferred_device(&self) -> Option<String> {
        self.inner.lock().preferred_device.clone()
    }

    pub fn set_preferred_device(&self, device: Option<String>) {
        self.inner.lock().preferred_device = device.map(|d| d.trim().to_string()).filter(|d| !d.is_empty());
    }

    pub fn register_candidate(&self, port: u16, flow_key: (u16, u16), device_name: Option<&str>) {
        let mut inner = self.inner.lock();
        let trimmed = device_name.map(|d| d.trim().to_string()).filter(|d| !d.is_empty());

        if inner.locked_port.is_some() {
            // Promote to loopback if applicable
            if let Some(ref dev) = trimmed {
                if inner.locked_port == Some(port) && is_loopback(dev) && !is_loopback_opt(&inner.locked_device) {
                    info!("Switching combat device to loopback: {:?} -> {}", inner.locked_device, dev);
                    inner.locked_device = Some(dev.clone());
                }
            }
            return;
        }

        if inner.first_candidate_ms == 0 {
            inner.first_candidate_ms = now_ms();
        }

        if let Some(ref dev) = trimmed {
            inner.device_flows.entry(dev.clone()).or_default().insert(flow_key);
        }

        // Note: loopback flows are no longer locked here on sight. Locking is
        // gated on the flow actually producing combat (see confirm_candidate),
        // so a coincidental loopback service can't hijack the lock.
        inner.candidates.entry(port).or_insert(trimmed);
    }

    pub fn confirm_candidate(&self, port_a: u16, port_b: u16, device_name: Option<&str>) {
        let mut inner = self.inner.lock();
        if inner.locked_port.is_some() {
            return;
        }

        let port = if inner.candidates.contains_key(&port_a) {
            Some(port_a)
        } else if inner.candidates.contains_key(&port_b) {
            Some(port_b)
        } else {
            None
        };

        let port = match port {
            Some(p) => p,
            None => return,
        };

        let trimmed = device_name.map(|d| d.trim().to_string()).filter(|d| !d.is_empty());
        let candidate_device = inner.candidates.get(&port).cloned().flatten();
        let device_for_lock = trimmed.or(candidate_device);

        // A loopback flow is the relay/ping-reducer's local tunnel — the exact
        // stream the game client consumes — so lock it the instant it produces
        // combat, ahead of any external session.
        if is_loopback_opt(&device_for_lock) {
            Self::lock_inner(&mut inner, port, device_for_lock);
            return;
        }

        // Physical/external flow: hold off briefly. With a ping-reducer the same
        // combat arrives on several external sessions and is relayed to a
        // loopback tunnel a moment later; this grace lets that loopback flow
        // appear and win. If none shows up, commit to the physical port (direct
        // connection / no relay).
        let waited = now_ms() - inner.first_candidate_ms;
        if inner.first_candidate_ms != 0 && waited < LOOPBACK_GRACE_MS {
            return;
        }

        Self::lock_inner(&mut inner, port, device_for_lock);
    }

    fn lock_inner(inner: &mut Inner, port: u16, device: Option<String>) {
        if inner.locked_port.is_none() {
            inner.locked_port = Some(port);
            inner.locked_device = device.clone();
            info!("Combat port locked: {}", port);
            inner.candidates.clear();
            inner.device_flows.clear();
        }
    }

    pub fn mark_packet_parsed(&self) {
        self.last_parsed_at_ms.store(now_ms(), Ordering::Relaxed);
    }

    pub fn reset(&self) {
        let mut inner = self.inner.lock();
        let was_locked = inner.locked_port.is_some();
        inner.locked_port = None;
        inner.locked_device = None;
        inner.candidates.clear();
        inner.device_flows.clear();
        inner.first_candidate_ms = 0;
        self.last_parsed_at_ms.store(0, Ordering::Relaxed);
        if was_locked {
            info!("Combat port lock cleared");
        }
    }
}

fn is_loopback(name: &str) -> bool {
    name.to_lowercase().contains("loopback")
}

fn is_loopback_opt(name: &Option<String>) -> bool {
    name.as_ref().is_some_and(|n| is_loopback(n))
}
