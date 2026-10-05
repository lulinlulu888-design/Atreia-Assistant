// The desktop app never needs a console, including local preview builds.
// Command-line tools have separate entry points and retain their consoles.
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

fn main() {
    a2tools_dps_meter_lib::run()
}
