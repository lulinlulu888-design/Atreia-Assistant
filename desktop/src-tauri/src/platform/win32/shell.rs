//! Handing things to the OS shell.

/// Open a URL in the default browser.
pub fn open_url(url: &str) {
    let _ = std::process::Command::new("cmd").args(["/C", "start", "", url]).spawn();
}
