use std::path::PathBuf;
pub fn steam_roots() -> Vec<PathBuf> {
    let Some(home) = std::env::var_os("HOME") else { return Vec::new(); };
    [".steam/steam", ".local/share/Steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
        .iter().map(|folder| PathBuf::from(&home).join(folder)).collect()
}
pub fn purple_roots() -> Vec<PathBuf> { Vec::new() }
