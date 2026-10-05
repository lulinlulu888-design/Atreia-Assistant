/// On Linux the question the meter is really asking is "can we capture?",
/// which needs CAP_NET_RAW (granted with `setcap`, or by running as root).
pub fn is_admin() -> bool {
    std::fs::read_to_string("/proc/self/status")
        .is_ok_and(|status| crate::platform::procfs::can_capture(&status))
}
