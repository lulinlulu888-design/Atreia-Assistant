//! Updating the installed package: the package manager that installed the
//! meter installs the new one (the Arch package through pacman, the .deb
//! through apt, the .rpm through dnf or zypper), and pkexec asks for the
//! password through the desktop's own prompt (KDE, GNOME…). Each package's
//! install script grants packet capture to the new binary again.

use std::path::Path;
use std::process::{Command, Stdio};

use crate::platform::UpdatePackages;

const INSTALLED_BINARY: &str = "/usr/bin/a2tools-dps-meter";

/// The package manager that owns the installed meter, and how it installs a
/// downloaded package file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Manager {
    Pacman,
    Apt,
    Dpkg,
    Dnf,
    Zypper,
    Rpm,
}

impl Manager {
    /// The command, run as root, that installs the package file given as `$1`.
    fn install_command(self) -> &'static str {
        match self {
            Manager::Pacman => "/usr/bin/pacman -U --noconfirm",
            // apt resolves any new dependency; dpkg alone would leave it broken.
            Manager::Apt => "/usr/bin/apt-get install -y --allow-downgrades",
            Manager::Dpkg => "/usr/bin/dpkg -i",
            Manager::Dnf => "/usr/bin/dnf install -y",
            // Our packages are not signed with a key zypper knows.
            Manager::Zypper => "/usr/bin/zypper --non-interactive install --allow-unsigned-rpm",
            Manager::Rpm => "/usr/bin/rpm -U --replacepkgs",
        }
    }

    fn package<'a>(self, packages: &UpdatePackages<'a>) -> &'a str {
        match self {
            Manager::Pacman => packages.arch,
            Manager::Apt | Manager::Dpkg => packages.deb,
            Manager::Dnf | Manager::Zypper | Manager::Rpm => packages.rpm,
        }
    }
}

fn succeeds(program: &str, args: &[&str]) -> bool {
    Path::new(program).exists()
        && Command::new(program)
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success())
}

/// Which package manager installed the running meter, asked of each one's
/// database. A build run from a checkout, or a copy put in place by hand, is
/// owned by none of them and is left alone.
fn manager() -> Option<Manager> {
    let installed = std::env::current_exe().is_ok_and(|exe| exe == Path::new(INSTALLED_BINARY));
    if !installed || !Path::new("/usr/bin/pkexec").exists() {
        return None;
    }
    // Bazzite, Silverblue, Kinoite and the other image-based Fedoras: /usr is
    // read-only, a package is layered with rpm-ostree and only takes effect
    // after a reboot. The meter comes from our RPM repository there and is
    // updated with the system (`rpm-ostree upgrade`, or the distribution's
    // automatic updates), so offering a dnf install would only fail and ask
    // again at every start.
    if Path::new("/run/ostree-booted").exists() {
        return None;
    }
    if succeeds("/usr/bin/pacman", &["-Qqo", INSTALLED_BINARY]) {
        return Some(Manager::Pacman);
    }
    if succeeds("/usr/bin/dpkg", &["-S", INSTALLED_BINARY]) {
        return Some(if Path::new("/usr/bin/apt-get").exists() { Manager::Apt } else { Manager::Dpkg });
    }
    if succeeds("/usr/bin/rpm", &["-qf", INSTALLED_BINARY]) {
        return Some(if Path::new("/usr/bin/dnf").exists() {
            Manager::Dnf
        } else if Path::new("/usr/bin/zypper").exists() {
            Manager::Zypper
        } else {
            Manager::Rpm
        });
    }
    None
}

/// Only a meter a package manager installed updates itself.
pub fn supported() -> bool {
    manager().is_some()
}

/// The manifest's package for the package manager that installed this meter.
pub fn package_url<'a>(packages: &UpdatePackages<'a>) -> &'a str {
    manager().map_or("", |m| m.package(packages))
}

/// Hand the package to its package manager once the meter has exited, then
/// start the meter again: the new one, or the old one if the password prompt
/// was cancelled, so a refused update never leaves the player without a meter.
pub fn run_installer(package: &Path, _install_dir: &str) -> Result<(), String> {
    use std::os::unix::process::CommandExt;
    let manager = manager().ok_or("this install cannot update itself")?;
    let script = format!(
        r#"
        while kill -0 "$2" 2>/dev/null; do sleep 0.2; done
        pkexec {install} "$1"
        rm -f "$1"
        exec {INSTALLED_BINARY}
    "#,
        install = manager.install_command(),
    );
    tracing::info!("Updating through {:?}: {}", manager, package.display());
    Command::new("/bin/sh")
        .arg("-c")
        .arg(script)
        .arg("a2tools-update")
        .arg(package)
        .arg(std::process::id().to_string())
        .stdin(Stdio::null())
        // Its own process group, so closing a terminal the meter was started
        // from does not take the update down with it.
        .process_group(0)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("could not start the update: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn each_manager_takes_its_own_package() {
        let p = UpdatePackages { msi: "m", arch: "a", deb: "d", rpm: "r" };
        assert_eq!(Manager::Pacman.package(&p), "a");
        assert_eq!(Manager::Apt.package(&p), "d");
        assert_eq!(Manager::Dpkg.package(&p), "d");
        assert_eq!(Manager::Dnf.package(&p), "r");
        assert_eq!(Manager::Zypper.package(&p), "r");
        assert_eq!(Manager::Rpm.package(&p), "r");
    }

    #[test]
    fn a_test_run_is_not_an_installed_meter() {
        // The test binary is not /usr/bin/a2tools-dps-meter.
        assert_eq!(manager(), None);
        assert!(!supported());
    }
}
