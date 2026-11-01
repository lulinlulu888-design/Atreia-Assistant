fn main() {
    let pin = std::path::Path::new("vendor/localization/helper.sha256");
    println!("cargo:rerun-if-changed={}", pin.display());
    let hash = std::fs::read_to_string(pin).unwrap_or_default();
    let hash = hash.trim();
    assert!(hash.is_empty() || (hash.len() == 64 && hash.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())),
        "Invalid prepared localization helper digest");
    println!("cargo:rustc-env=ATREIA_LOCALIZATION_HELPER_SHA256={hash}");
    // `tauri_build` generates the Windows resource bundle and the capability
    // schema. It cannot run for the wasm32 build of the parser — that build
    // exists so the log service can re-derive an uploaded fight with the same
    // code the client ran, and it has no Tauri in it at all.
    #[cfg(feature = "desktop")]
    tauri_build::build();
}
