//! The clock the game stamps pings with, as Wine provides it.
//!
//! Wine implements QueryPerformanceCounter on CLOCK_MONOTONIC_RAW (in 100 ns
//! units, 10 MHz), so reading that clock gives the same counter the game sees.
//! Not yet verified against a capture from a Proton player: if it is wrong,
//! the ping tracker notices it disagreeing with request timing and stops
//! using it.

use crate::combat::ping_tracker::PerfClock;

pub fn perf_clock() -> Option<PerfClock> {
    Some(read)
}

#[repr(C)]
struct Timespec {
    tv_sec: i64,
    tv_nsec: i64,
}

unsafe extern "C" {
    fn clock_gettime(clock_id: i32, tp: *mut Timespec) -> i32;
}

const CLOCK_MONOTONIC_RAW: i32 = 4;

fn read() -> (i64, i64) {
    let mut ts = Timespec { tv_sec: 0, tv_nsec: 0 };
    // SAFETY: writes one timespec through a valid pointer.
    unsafe { clock_gettime(CLOCK_MONOTONIC_RAW, &mut ts) };
    let wall_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64;
    (ts.tv_sec * 1000 + ts.tv_nsec / 1_000_000, wall_ms)
}
