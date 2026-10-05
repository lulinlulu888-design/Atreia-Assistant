/// The conventional libpcap soname, so a port has a starting point; capture is
/// not supported here yet.
pub const LIBRARIES: &[&str] = &["libpcap.so.1"];

pub const MISSING_HELP: &str = "Packet capture is not supported on this platform yet.";

pub fn library_available() -> bool {
    false
}

/// Devices not worth opening on this OS. None here.
pub fn skip_device(_name: &str) -> bool {
    false
}
