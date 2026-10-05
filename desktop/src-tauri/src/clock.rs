//! Time for the parse path.
//!
//! Two callers need "now", and they disagree about what it means. Live capture
//! wants the wall clock. Replay — and, on the server, re-derivation of an
//! uploaded encounter — wants the timestamp the packet was *captured* at, or the
//! same bytes produce different numbers on every run.
//!
//! `StreamProcessor` already had `set_override_timestamp` for its own damage
//! records, but `DataStorage` reached for `SystemTime::now()` directly, so a
//! replay's idle-reset and zone-reset decisions were still made against the
//! replaying machine's clock. That is the bug this module closes.
//!
//! Two further reasons it is a module and not a function:
//!
//! - `SystemTime::now()` **panics** on `wasm32-unknown-unknown`, which is the
//!   target the parser is compiled to so the server can re-derive an encounter
//!   with the same code the client ran.
//! - The override is **thread-local**, not global. `replay_file` runs on a
//!   `spawn_blocking` thread while live capture may still be running on its own;
//!   a global would let a replay rewrite the clock out from under a live fight.

use std::cell::Cell;

thread_local! {
    /// Capture time for this thread, when it is replaying rather than capturing.
    static OVERRIDE_MS: Cell<Option<i64>> = const { Cell::new(None) };
}

/// Pin this thread's clock to a capture timestamp, or `None` to read the wall
/// clock again. Set it per packet while replaying.
pub fn set_override(ms: Option<i64>) {
    OVERRIDE_MS.with(|c| c.set(ms));
}

/// Milliseconds since the Unix epoch — the capture timestamp while replaying,
/// otherwise the wall clock.
pub fn now_ms() -> i64 {
    if let Some(ms) = OVERRIDE_MS.with(|c| c.get()) {
        return ms;
    }
    wall_clock_ms()
}

#[cfg(not(target_arch = "wasm32"))]
fn wall_clock_ms() -> i64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// On wasm32 there is no clock to read. Re-derivation always sets an override,
/// so reaching this means a caller ran outside a replay — return the epoch
/// rather than panicking, and let the missing override show up as absurd
/// timestamps instead of a crashed request.
#[cfg(target_arch = "wasm32")]
fn wall_clock_ms() -> i64 {
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn override_pins_the_clock_and_clears() {
        set_override(Some(1_700_000_000_000));
        assert_eq!(now_ms(), 1_700_000_000_000);
        set_override(None);
        assert!(now_ms() > 1_600_000_000_000, "wall clock should resume");
    }

    #[test]
    fn override_does_not_leak_across_threads() {
        set_override(Some(42));
        let other = std::thread::spawn(|| now_ms()).join().unwrap();
        assert_ne!(other, 42, "override must be thread-local");
        set_override(None);
    }
}
