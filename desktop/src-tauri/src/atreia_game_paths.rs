//! Read-only discovery from client configuration; never scans whole drives.
use keyvalues_parser::{Obj, Value};
use std::{io::Read, path::{Path, PathBuf}};

const MAX_CONFIG: u64 = 2 * 1024 * 1024;

fn config_text(path: &Path) -> Option<String> {
    let file = std::fs::File::open(path).ok()?;
    let mut text = String::new();
    file.take(MAX_CONFIG + 1).read_to_string(&mut text).ok()?;
    (text.len() as u64 <= MAX_CONFIG).then_some(text)
}

fn field<'a>(object: &'a Obj<'_>, name: &str) -> Option<&'a str> {
    object.iter().find(|(key, _)| key.eq_ignore_ascii_case(name))?
        .1.iter().find_map(Value::get_str)
}

pub fn normalize(root: &Path) -> Option<PathBuf> {
    let mut path = if root.is_file() { root.parent()?.to_path_buf() } else { root.to_path_buf() };
    for _ in 0..7 {
        for candidate in [path.clone(), path.join("AION2"), path.join("AION2_TW")] {
            if candidate.join("Aion2/Content/Paks/L10N/Text").is_dir() {
                return dunce::canonicalize(candidate).ok();
            }
        }
        path = path.parent()?.to_path_buf();
    }
    None
}

fn add(roots: &mut Vec<PathBuf>, candidate: &Path) {
    // Discovery stays inside the configured client location. Parent walking
    // is reserved for a folder the user explicitly selects in the picker.
    if !candidate.join("Aion2/Content/Paks/L10N/Text").is_dir() { return; }
    if let Ok(root) = dunce::canonicalize(candidate) {
        if !roots.contains(&root) { roots.push(root); }
    }
}

fn library_paths(text: &str) -> Vec<PathBuf> {
    let Ok(document) = keyvalues_parser::parse(text.trim_start_matches('\u{feff}')) else { return vec![]; };
    let Some(object) = document.value.get_obj() else { return vec![]; };
    object.iter().filter(|(key, _)| key.bytes().all(|c| c.is_ascii_digit()))
        .flat_map(|(_, values)| values.iter()).filter_map(|value| {
            value.get_obj().and_then(|o| field(o, "path")).or_else(|| value.get_str())
        }).filter(|path| !path.is_empty() && !path.contains('\0'))
        .map(PathBuf::from).collect()
}

pub fn discover(client: &str, seeds: &[PathBuf]) -> Result<Vec<PathBuf>, String> {
    let mut roots = Vec::new();
    match client {
        "purple" => { for seed in seeds { for candidate in [seed.clone(), seed.join("AION2"), seed.join("AION2_TW")] { add(&mut roots, &candidate); } } }
        "steam" => {
            let mut libraries = seeds.to_vec();
            for seed in seeds {
                if let Some(text) = config_text(&seed.join("steamapps/libraryfolders.vdf")) {
                    libraries.extend(library_paths(&text));
                }
            }
            for library in libraries {
                let apps = library.join("steamapps");
                add(&mut roots, &apps.join("common/AION2"));
                let Ok(entries) = std::fs::read_dir(&apps) else { continue; };
                for entry in entries.flatten().take(512) {
                    let path = entry.path();
                    let name = entry.file_name();
                    let name = name.to_string_lossy();
                    if !name.starts_with("appmanifest_") || path.extension().and_then(|s| s.to_str()) != Some("acf") { continue; }
                    let Some(text) = config_text(&path) else { continue; };
                    let Ok(document) = keyvalues_parser::parse(&text) else { continue; };
                    let Some(object) = document.value.get_obj() else { continue; };
                    let Some(name) = field(object, "name") else { continue; };
                    if !name.to_ascii_uppercase().replace(' ', "").starts_with("AION2") { continue; }
                    let Some(folder) = field(object, "installdir") else { continue; };
                    // Steam install folders are single directory names, not arbitrary paths.
                    if folder.is_empty() || folder == "." || folder == ".." || folder.contains(['/', '\\', '\0', ':']) { continue; }
                    add(&mut roots, &apps.join("common").join(folder));
                }
            }
        }
        _ => return Err("未知客户端。".into()),
    }
    roots.sort();
    Ok(roots)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!("atreia-paths-{}-{name}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap(); root
    }
    fn game(root: &Path) { std::fs::create_dir_all(root.join("Aion2/Content/Paks/L10N/Text/en-US")).unwrap(); }
    #[test]
    fn parses_new_and_legacy_libraries_without_reading_comment_paths() {
        let text = r#""libraryfolders" { "0" { "path" "D:\\SteamLibrary" "apps" {} } "1" "E:\\旧库" // "path" "Z:\\not-a-library"
        }"#;
        assert_eq!(library_paths(text), vec![PathBuf::from(r"D:\SteamLibrary"), PathBuf::from(r"E:\旧库")]);
        assert!(library_paths("bad { malformed").is_empty());
    }
    #[test]
    fn discovers_secondary_library_and_manifest_folder_and_deduplicates() {
        let stage = fixture("steam"); let steam = stage.join("Steam"); let library = stage.join("SteamLibrary");
        std::fs::create_dir_all(steam.join("steamapps")).unwrap();
        game(&library.join("steamapps/common/CustomAion"));
        let escaped = library.to_string_lossy().replace('\\', "\\\\");
        std::fs::write(steam.join("steamapps/libraryfolders.vdf"), format!("\"libraryfolders\" {{ \"1\" {{ \"path\" \"{escaped}\" }} }}")).unwrap();
        std::fs::write(library.join("steamapps/appmanifest_123.acf"), "\"AppState\" { \"name\" \"AION 2\" \"installdir\" \"CustomAion\" }").unwrap();
        let roots = discover("steam", &[steam, library.clone()]).unwrap();
        assert_eq!(roots, vec![dunce::canonicalize(library.join("steamapps/common/CustomAion")).unwrap()]);
        assert!(discover("purple", &[]).unwrap().is_empty());
        std::fs::remove_dir_all(stage).unwrap();
    }
    #[test]
    fn normalizes_selected_game_parent_without_accepting_arbitrary_layouts() {
        let stage = fixture("purple"); game(&stage.join("AION2_TW"));
        assert_eq!(discover("purple", &[stage.clone(), stage.join("AION2_TW")]).unwrap().len(), 1);
        assert!(normalize(&fixture("empty")).is_none());
        assert!(discover("other", &[]).is_err());
        std::fs::remove_dir_all(stage).unwrap(); std::fs::remove_dir_all(fixture("empty")).unwrap();
    }
    #[test]
    fn discovery_does_not_walk_into_another_clients_sibling_installation() {
        let stage = fixture("client-scope"); game(&stage.join("AION2_TW"));
        assert!(discover("steam", &[stage.join("Steam")]).unwrap().is_empty());
        assert!(discover("purple", &[stage.join("missing/NC")]).unwrap().is_empty());
        std::fs::remove_dir_all(stage).unwrap();
    }
    #[test]
    #[ignore = "explicit read-only verification against this machine's installed games"]
    fn live_installed_game_discovery() {
        let steam = discover("steam", &crate::platform::game_paths::steam_roots()).unwrap();
        let purple = discover("purple", &crate::platform::game_paths::purple_roots()).unwrap();
        assert!(!steam.is_empty(), "No installed Steam game found on this test machine");
        println!("Steam installations: {}; PURPLE installations: {}", steam.len(), purple.len());
    }
}
