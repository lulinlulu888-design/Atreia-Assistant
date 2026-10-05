/// No global hotkeys on this platform.
pub struct HotkeyManager;

impl HotkeyManager {
    pub fn new() -> Self {
        Self
    }
    #[allow(clippy::too_many_arguments)]
    pub fn start(
        &self,
        _: u32,
        _: u32,
        _: u32,
        _: u32,
        _: u32,
        _: u32,
        _: impl Fn() + Send + 'static,
        _: impl Fn() + Send + 'static,
        _: impl Fn() + Send + 'static,
    ) {
    }
    pub fn stop(&self) {}
}
