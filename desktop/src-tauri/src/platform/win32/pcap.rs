//! Which packet-capture library to load. The API is libpcap's on every OS;
//! on Windows it comes from Npcap.

/// The library `capture::pcap_capturer` loads at runtime (the first of these
/// that loads).
pub const LIBRARIES: &[&str] = &["wpcap.dll"];

/// What to tell the player when it will not load.
pub const MISSING_HELP: &str = "Is Npcap installed? Download from https://npcap.com";

/// Whether the capture library can be loaded at all.
pub fn library_available() -> bool {
    load_library().is_ok()
}

/// Prefer the normal Npcap installation; compatibility mode is not required.
/// Never search the working directory for a packet capture DLL.
pub fn load_library() -> Result<libloading::Library, String> {
    use std::{ffi::CStr, path::PathBuf};
    use windows::Win32::System::SystemInformation::GetSystemDirectoryW;
    let mut buffer = vec![0u16; 32768];
    let length = unsafe { GetSystemDirectoryW(Some(&mut buffer)) } as usize;
    if length == 0 || length >= buffer.len() {
        return Err("Cannot locate Windows system directory".into());
    }
    let system = PathBuf::from(String::from_utf16_lossy(&buffer[..length]));
    let mut errors = Vec::new();
    for path in [system.join("Npcap/wpcap.dll"), system.join("wpcap.dll")] {
        let result = unsafe {
            // LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32:
            // Packet.dll resolves beside wpcap.dll, not in an untrusted cwd.
            libloading::os::windows::Library::load_with_flags(&path, 0x100 | 0x800)
        };
        match result {
            Ok(library) => {
                let library: libloading::Library = library.into();
                let valid = unsafe {
                    library.get::<unsafe extern "C" fn() -> *const std::ffi::c_char>(b"pcap_lib_version\0")
                        .map(|version| {
                            let value = version();
                            !value.is_null() && CStr::from_ptr(value).to_bytes().starts_with(b"Npcap version")
                        }).unwrap_or(false)
                };
                if valid { return Ok(library); }
                errors.push(format!("{}: not Npcap", path.display()));
            }
            Err(error) => errors.push(format!("{}: {error}", path.display())),
        }
    }
    Err(format!("{MISSING_HELP}\n{}", errors.join("; ")))
}

#[cfg(test)]
mod tests {
    #[test]
    #[ignore = "requires an installed Npcap runtime; does not start capture"]
    fn installed_npcap_loads() {
        super::load_library().expect("installed Npcap must load through its system path");
    }
}

/// Devices not worth opening on this OS. None here.
pub fn skip_device(_name: &str) -> bool {
    false
}
