//! Global hotkeys. Parsing the label is OS-neutral; registering it is not, and
//! comes from the OS implementation as `HotkeyManager`.

pub use super::os::hotkeys::HotkeyManager;

/// Parse a hotkey label like "Ctrl+Alt+R" or "Ctrl+Shift+F5" into (modifiers, vk_code).
/// Returns None if the label is empty or unparseable.
///
/// The numbers are Win32's (MOD_* flags and virtual-key codes) because that is
/// what settings have always stored; another OS maps them to its own keys.
pub fn parse_hotkey_label(label: &str) -> Option<(u32, u32)> {
    let label = label.trim();
    if label.is_empty() {
        return None;
    }

    let mut mods: u32 = 0;
    let mut vk: Option<u32> = None;

    for part in label.split('+') {
        let p = part.trim();
        match p.to_lowercase().as_str() {
            "ctrl" | "control" => mods |= 0x0002,
            "alt" => mods |= 0x0001,
            "shift" => mods |= 0x0004,
            "win" | "super" => mods |= 0x0008,
            _ => {
                // Try to parse as a key name
                vk = Some(match p.to_uppercase().as_str() {
                    "BACKSPACE" => 0x08,
                    "TAB" => 0x09,
                    "ENTER" | "RETURN" => 0x0D,
                    "ESC" | "ESCAPE" => 0x1B,
                    "SPACE" => 0x20,
                    "PAGEUP" => 0x21,
                    "PAGEDOWN" => 0x22,
                    "END" => 0x23,
                    "HOME" => 0x24,
                    "LEFT" => 0x25,
                    "UP" => 0x26,
                    "RIGHT" => 0x27,
                    "DOWN" => 0x28,
                    "INSERT" => 0x2D,
                    "DELETE" => 0x2E,
                    "F1" => 0x70, "F2" => 0x71, "F3" => 0x72, "F4" => 0x73,
                    "F5" => 0x74, "F6" => 0x75, "F7" => 0x76, "F8" => 0x77,
                    "F9" => 0x78, "F10" => 0x79, "F11" => 0x7A, "F12" => 0x7B,
                    s if s.len() == 1 => {
                        let ch = s.chars().next().unwrap();
                        if ch.is_ascii_alphanumeric() {
                            ch.to_ascii_uppercase() as u32
                        } else {
                            return None;
                        }
                    }
                    _ => return None,
                });
            }
        }
    }

    match vk {
        Some(k) if mods > 0 => Some((mods, k)),
        _ => None,
    }
}
