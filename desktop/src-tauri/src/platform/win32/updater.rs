//! Installing a downloaded update.

use std::path::Path;

/// Updates install themselves here (the MSI).
pub fn supported() -> bool {
    true
}

/// The manifest's package for this platform.
pub fn package_url<'a>(packages: &crate::platform::UpdatePackages<'a>) -> &'a str {
    packages.msi
}

/// Start the MSI installer over the current install and return; the caller
/// exits so the installer can replace the running files.
///
/// msiexec.exe uses its own non-standard command line parser, so
/// PROPERTY="value" pairs with spaces require literal embedded quotes, which
/// std::process::Command's normal arg quoting does not produce. raw_arg
/// controls the exact command line.
pub fn run_installer(package: &Path, install_dir: &str) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    let mut cmd = std::process::Command::new("msiexec");
    cmd.raw_arg("/i")
        .raw_arg(format!("\"{}\"", package.display()))
        .raw_arg("/passive")
        .raw_arg(format!("INSTALLDIR=\"{}\"", install_dir))
        .raw_arg("AUTOLAUNCHAPP=1");
    tracing::info!(
        "msiexec args: /i \"{}\" /passive INSTALLDIR=\"{}\" AUTOLAUNCHAPP=1",
        package.display(),
        install_dir
    );
    cmd.spawn().map(|_| ()).map_err(|e| e.to_string())
}
