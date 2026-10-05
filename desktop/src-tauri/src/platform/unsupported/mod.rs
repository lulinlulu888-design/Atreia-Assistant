//! Every target the meter does not support yet. Same modules and signatures as
//! `../win32/`; each does the safe nothing, so the crate compiles and the parts
//! that are OS-neutral can be built and tested here. A real port (`../linux/`)
//! replaces this for its target.

pub mod admin;
pub mod clock;
pub mod dialog;
pub mod hotkeys;
pub mod pcap;
pub mod process;
pub mod screen;
pub mod secret;
pub mod shell;
pub mod updater;
pub mod window;
pub mod window_detector;
