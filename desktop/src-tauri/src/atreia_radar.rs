use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use parking_lot::Mutex;
use tauri::Manager;
use crate::radar::Radar;

#[derive(Default)]
pub struct RadarControl {
    pub active: AtomicBool,
    pub combat_active: AtomicBool,
    pub generation: std::sync::atomic::AtomicU64,
    pub data: Mutex<Radar>,
}
impl RadarControl {
    pub fn needs_capture(&self) -> bool {
        self.active.load(Ordering::SeqCst) || self.combat_active.load(Ordering::SeqCst)
    }
    pub fn stop(&self) {
        self.active.store(false,Ordering::SeqCst);
        self.generation.fetch_add(1,Ordering::SeqCst);
        self.data.lock().reset();
    }
}

#[tauri::command]
pub async fn open_radar(app:tauri::AppHandle)->Result<(),String> {
    if let Some(window)=app.get_webview_window("radar") {
        window.set_min_size(Option::<tauri::Size>::None).map_err(|e|e.to_string())?;
        window.set_size(tauri::LogicalSize::new(210.,240.)).map_err(|e|e.to_string())?;
        window.set_resizable(false).map_err(|e|e.to_string())?;
        window.show().map_err(|e|e.to_string())?;
        return window.set_focus().map_err(|e|e.to_string());
    }
    tauri::WebviewWindowBuilder::new(&app,"radar",tauri::WebviewUrl::App("radar.html".into()))
        .title("亚特雷亚助手 · 隐藏宝箱雷达").inner_size(210.,240.).resizable(false)
        .decorations(false).transparent(true).shadow(false)
        .always_on_top(true).build().map_err(|e|e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn fit_radar_window(window:tauri::WebviewWindow, scale:f64)->Result<(),String> {
    if window.label()!="radar" || !scale.is_finite() || !(0.5..=4.).contains(&scale) {
        return Err("雷达窗口尺寸请求无效。".into());
    }
    // Follow the DPS overlay's physical-pixel sizing, including WebView text
    // scaling. CSS-only changes cannot shrink an already-created OS window.
    window.set_min_size(Option::<tauri::Size>::None).map_err(|e|e.to_string())?;
    window.set_size(tauri::PhysicalSize::new((210.*scale).ceil() as u32,(240.*scale).ceil() as u32)).map_err(|e|e.to_string())?;
    window.set_resizable(false).map_err(|e|e.to_string())
}

#[tauri::command]
pub async fn open_radar_settings(app:tauri::AppHandle)->Result<(),String> {
    if let Some(window)=app.get_webview_window("radar-settings") {
        window.show().map_err(|e|e.to_string())?;
        return window.set_focus().map_err(|e|e.to_string());
    }
    tauri::WebviewWindowBuilder::new(&app,"radar-settings",tauri::WebviewUrl::App("radar.html".into()))
        .title("亚特雷亚助手 · 雷达设置").inner_size(330.,470.).min_inner_size(300.,400.)
        .background_color(tauri::window::Color(233,238,241,255))
        .build().map_err(|e|e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn radar_snapshot(app:tauri::AppHandle)->serde_json::Value {
    let control=app.state::<Arc<RadarControl>>();
    let now=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis() as i64;
    serde_json::json!({"active":control.active.load(Ordering::SeqCst),"data":control.data.lock().snapshot(now)})
}

#[tauri::command]
pub fn stop_radar(app:tauri::AppHandle) {
    app.state::<Arc<RadarControl>>().stop();
    if !app.state::<Arc<RadarControl>>().needs_capture() {
        app.state::<crate::atreia_localization::CaptureControl>().0.lock().stop();
    }
}

#[tauri::command]
pub async fn start_radar(app:tauri::AppHandle)->Result<(),String> {
    crate::atreia_localization::start_radar_capture(app).await
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn capture_is_shared_but_feature_switches_are_independent() {
        let control=RadarControl::default();
        for radar in [false,true] { for combat in [false,true] {
            control.active.store(radar,Ordering::SeqCst);control.combat_active.store(combat,Ordering::SeqCst);
            assert_eq!(control.needs_capture(),radar||combat);
            let generation=control.generation.load(Ordering::SeqCst);control.stop();
            assert!(!control.active.load(Ordering::SeqCst));assert_eq!(control.needs_capture(),combat);
            assert_eq!(control.generation.load(Ordering::SeqCst),generation+1);
        } }
    }
}
