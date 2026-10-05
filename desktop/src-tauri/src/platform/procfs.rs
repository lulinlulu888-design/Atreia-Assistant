//! Reading Linux `/proc` text. Only `platform/linux/` reads the files; the
//! parsing is plain strings and bytes, so it lives here, compiles everywhere,
//! and is tested on every build.

/// Whether a process is the game, from its `/proc/<pid>/comm` and `cmdline`.
///
/// Under Proton the game runs as a Wine process whose name (`comm`, truncated
/// to 15 bytes by the kernel) is `AION2.exe`, and whose first argument is the
/// Windows-style path to it (`Z:\...\Binaries\Win64\AION2.exe` or similar).
/// Only the process's own name and argv[0] count: Proton's wrapper scripts carry
/// the game's path further along their command lines without being the game.
pub fn is_aion2_process(comm: &str, cmdline: &[u8]) -> bool {
    let is_game = |name: &str| name.trim().eq_ignore_ascii_case("AION2.exe");
    if is_game(comm) {
        return true;
    }
    let argv0 = cmdline.split(|&b| b == 0).next().unwrap_or(&[]);
    let argv0 = String::from_utf8_lossy(argv0);
    argv0.rsplit(['/', '\\']).next().is_some_and(is_game)
}

/// Whether `/proc/self/status` shows the effective capabilities packet capture
/// needs (CAP_NET_RAW, bit 13). Root has every bit set, so this covers root too.
pub fn can_capture(status: &str) -> bool {
    const CAP_NET_RAW: u32 = 13;
    status
        .lines()
        .find_map(|line| line.strip_prefix("CapEff:"))
        .and_then(|hex| u64::from_str_radix(hex.trim(), 16).ok())
        .is_some_and(|caps| caps & (1 << CAP_NET_RAW) != 0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_the_game_under_proton() {
        assert!(is_aion2_process("AION2.exe", b""));
        assert!(is_aion2_process(
            "wine64-preload",
            b"Z:\\home\\p\\.steam\\steamapps\\common\\AION2\\Aion2\\Binaries\\Win64\\AION2.exe\0-arg\0"
        ));
        assert!(is_aion2_process("x", b"/opt/games/aion2.exe\0"));
    }

    #[test]
    fn ignores_wrappers_that_only_mention_it() {
        // Proton's own process carries the game path as a later argument.
        assert!(!is_aion2_process(
            "python3",
            b"python3\0/proton\0waitforexitandrun\0Z:\\games\\AION2.exe\0"
        ));
        assert!(!is_aion2_process("AION2Launcher", b"AION2Launcher.exe\0"));
    }

    #[test]
    fn reads_the_capture_capability() {
        let with = "Name:\tmeter\nCapInh:\t0000000000000000\nCapEff:\t0000000000003000\n";
        let without = "Name:\tmeter\nCapEff:\t0000000000000000\n";
        let root = "CapEff:\t000001ffffffffff\n";
        assert!(can_capture(with));
        assert!(!can_capture(without));
        assert!(can_capture(root));
        assert!(!can_capture("garbage"));
    }
}
