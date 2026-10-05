use std::path::Path;

/// Updates come through the platform's own package, not from the meter.
pub fn supported() -> bool {
    false
}

pub fn package_url<'a>(_packages: &crate::platform::UpdatePackages<'a>) -> &'a str {
    ""
}

/// There is no installer format for this platform yet.
pub fn run_installer(_package: &Path, _install_dir: &str) -> Result<(), String> {
    Err("automatic updates are not supported on this platform yet".to_string())
}
