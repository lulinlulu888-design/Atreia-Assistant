/// The freedesktop way, which is what a Unix-like target most likely has.
pub fn open_url(url: &str) {
    let _ = std::process::Command::new("xdg-open").arg(url).spawn();
}
