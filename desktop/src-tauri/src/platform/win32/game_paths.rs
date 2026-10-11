use std::path::PathBuf;
use winreg::{enums::{HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_WOW64_32KEY, KEY_WOW64_64KEY}, RegKey};

pub fn steam_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    for (hive, path, name) in [(HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"), (HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")] {
        for view in [KEY_WOW64_32KEY, KEY_WOW64_64KEY] {
            if let Ok(key) = RegKey::predef(hive).open_subkey_with_flags(path, KEY_READ | view) {
                if let Ok(value) = key.get_value::<String, _>(name) { if !value.is_empty() { roots.push(PathBuf::from(value)); } }
            }
        }
    }
    for name in ["ProgramFiles(x86)", "ProgramFiles"] {
        if let Some(base) = std::env::var_os(name) { roots.push(PathBuf::from(base).join("Steam")); }
    }
    roots
}

pub fn purple_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    for name in ["ProgramFiles(x86)", "ProgramFiles"] {
        if let Some(base) = std::env::var_os(name) {
            for folder in ["NCSOFT/AION2_TW", "NCSOFT/AION2", "NC/AION2_TW", "NC/AION2"] {
                roots.push(PathBuf::from(&base).join(folder));
            }
        }
    }
    for hive in [HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE] {
        for view in [KEY_WOW64_32KEY, KEY_WOW64_64KEY] {
            let Ok(uninstall) = RegKey::predef(hive).open_subkey_with_flags(r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", KEY_READ | view) else { continue; };
            for name in uninstall.enum_keys().flatten().take(2048) {
                if name.to_ascii_lowercase().starts_with("steam app") { continue; }
                let Ok(key) = uninstall.open_subkey_with_flags(name, KEY_READ | view) else { continue; };
                if key.get_value::<String, _>("UninstallString").unwrap_or_default().to_ascii_lowercase().contains("steam://") { continue; }
                let Ok(title) = key.get_value::<String, _>("DisplayName") else { continue; };
                if !title.to_ascii_uppercase().replace(' ', "").starts_with("AION2") { continue; }
                if let Ok(location) = key.get_value::<String, _>("InstallLocation") { if !location.is_empty() { roots.push(PathBuf::from(location)); } }
            }
        }
    }
    roots
}
