//! Finding the game under Proton. Its window cannot be relied on (Wayland does
//! not let one application list another's windows), so look for the process.

use std::path::Path;

fn game_running() -> bool {
    let Ok(entries) = std::fs::read_dir("/proc") else { return false };
    entries.flatten().any(|entry| {
        let pid_dir = entry.path();
        let is_pid = pid_dir
            .file_name()
            .and_then(|n| n.to_str())
            .is_some_and(|n| n.bytes().all(|b| b.is_ascii_digit()));
        is_pid && is_game(&pid_dir)
    })
}

fn is_game(pid_dir: &Path) -> bool {
    let comm = std::fs::read_to_string(pid_dir.join("comm")).unwrap_or_default();
    let cmdline = std::fs::read(pid_dir.join("cmdline")).unwrap_or_default();
    crate::platform::procfs::is_aion2_process(&comm, &cmdline)
}

/// "AION2" while the game runs. There is no window title to read the character
/// name from, so the meter learns it from the game's own self record instead.
pub fn find_aion2_window_title() -> Option<String> {
    game_running().then(|| "AION2".to_string())
}

pub fn find_aion2_window() -> bool {
    game_running()
}

/// Which window has focus is not knowable on Wayland and not wired up for X11
/// yet. Report the game as focused, so auto-hide never hides the meter rather
/// than hiding it all the time.
pub fn is_aion2_foreground() -> bool {
    true
}

/// Processes that mention "aion" in their name or first argument, for the log
/// when the game is not recognised.
pub fn describe_candidates() -> Vec<String> {
    let Ok(entries) = std::fs::read_dir("/proc") else { return Vec::new() };
    let mut out = Vec::new();
    for entry in entries.flatten() {
        let pid_dir = entry.path();
        let comm = std::fs::read_to_string(pid_dir.join("comm")).unwrap_or_default();
        let cmdline = std::fs::read(pid_dir.join("cmdline")).unwrap_or_default();
        let argv0 = String::from_utf8_lossy(cmdline.split(|&b| b == 0).next().unwrap_or(&[])).to_string();
        if comm.to_lowercase().contains("aion") || argv0.to_lowercase().contains("aion") {
            out.push(format!("comm={:?} argv0={argv0:?}", comm.trim()));
            if out.len() >= 8 {
                break;
            }
        }
    }
    out
}
