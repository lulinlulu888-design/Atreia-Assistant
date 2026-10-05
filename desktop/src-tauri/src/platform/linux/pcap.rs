//! libpcap, as nearly every distribution ships it.

/// Tried in order. Distributions disagree on the soname: Arch and Fedora ship
/// `libpcap.so.1`, while Debian and Ubuntu keep the old `libpcap.so.0.8` and
/// have no `.so.1` at all (only the -dev package adds a bare `libpcap.so`).
/// Loading `.so.1` alone left the meter unable to capture on every
/// Debian-family system.
pub const LIBRARIES: &[&str] = &["libpcap.so.1", "libpcap.so.0.8", "libpcap.so"];

pub const MISSING_HELP: &str = "Install libpcap (e.g. `sudo apt install libpcap0.8`), then let the meter \
capture without root: `sudo setcap cap_net_raw,cap_net_admin=eip <path to the meter>`";

pub fn library_available() -> bool {
    // SAFETY: loading libpcap runs no initialisation we depend on not running.
    LIBRARIES.iter().any(|name| unsafe { libloading::Library::new(name).is_ok() })
}

/// Skip libpcap's pseudo-devices. "any" sees every packet a second time on top
/// of the real interface it arrived on; the rest carry no IP traffic.
///
/// Container networking too: Docker and Podman give every container a `veth`
/// pair and every network a `docker0` / `br-<id>` / `podman` bridge. The game,
/// under Proton, talks through the real interface, so these only add capture
/// threads (one player had 22 of them).
pub fn skip_device(name: &str) -> bool {
    name == "any"
        || ["nflog", "nfqueue", "usbmon", "dbus", "bluetooth", "veth", "docker", "br-", "podman"]
            .iter()
            .any(|prefix| name.starts_with(prefix))
}
