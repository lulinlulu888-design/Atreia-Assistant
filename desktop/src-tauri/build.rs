fn main() {
    // `tauri_build` generates the Windows resource bundle and the capability
    // schema. It cannot run for the wasm32 build of the parser — that build
    // exists so the log service can re-derive an uploaded fight with the same
    // code the client ran, and it has no Tauri in it at all.
    #[cfg(feature = "desktop")]
    tauri_build::build();
}
