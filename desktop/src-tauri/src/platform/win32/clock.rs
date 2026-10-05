//! The performance counter, which the newer game client stamps its pings with
//! (see `combat::ping_tracker`).

use crate::combat::ping_tracker::PerfClock;

/// The machine's performance counter for the ping tracker.
pub fn perf_clock() -> Option<PerfClock> {
    Some(read)
}

/// The performance counter in ms since boot, and the wall clock in Unix ms,
/// read together.
fn read() -> (i64, i64) {
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn QueryPerformanceCounter(count: *mut i64) -> i32;
        fn QueryPerformanceFrequency(frequency: *mut i64) -> i32;
    }
    let (mut count, mut frequency) = (0i64, 0i64);
    // SAFETY: both write one i64 through a valid pointer, and cannot fail on
    // Windows XP or later.
    unsafe {
        QueryPerformanceFrequency(&mut frequency);
        QueryPerformanceCounter(&mut count);
    }
    let wall_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64;
    let counter_ms = (count as i128 * 1000 / frequency.max(1) as i128) as i64;
    (counter_ms, wall_ms)
}
