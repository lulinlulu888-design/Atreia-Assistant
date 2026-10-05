//! Atreia additions. Upstream capture stays inert until the launcher action.
use parking_lot::Mutex;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicBool, Ordering},
};
use tauri::Manager;

pub struct CaptureControl(pub Mutex<crate::capture::pcap_capturer::PcapCapturer>);
static LOCALIZATION_BUSY: AtomicBool = AtomicBool::new(false);
static CAPTURE_STARTING: AtomicBool = AtomicBool::new(false);
const ENGINE_HASH: &str = "1d01a3ab4c9604296da6b2265fd0a5a1247d628d31fd4ab02eb8bac539340e58";

pub fn is_busy() -> bool {
    LOCALIZATION_BUSY.load(Ordering::SeqCst)
}

pub fn is_capture_starting() -> bool {
    CAPTURE_STARTING.load(Ordering::SeqCst)
}

#[tauri::command]
pub async fn open_combat(app: tauri::AppHandle) -> Result<(), String> {
    if LOCALIZATION_BUSY.load(Ordering::SeqCst) {
        return Err("请等待汉化操作完成。".into());
    }
    if CAPTURE_STARTING.swap(true, Ordering::SeqCst) {
        return Err("战斗统计正在启动。".into());
    }
    struct StartGuard;
    impl Drop for StartGuard {
        fn drop(&mut self) {
            CAPTURE_STARTING.store(false, Ordering::SeqCst);
        }
    }
    let _guard = StartGuard;
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        return Ok(());
    }
    if !crate::platform::pcap::library_available() {
        return Err(
            "未能加载 Npcap。请从 Npcap 官网安装驱动，安装完成后重试。".into(),
        );
    }
    // This upstream autodetector initially examines adapter TCP traffic. State
    // that scope honestly; it is not the older exact-PID Python collector.
    let consent = tauri::async_runtime::spawn_blocking(|| crate::platform::dialog::ask_yes_no(
        "开启战斗统计", "开始使用 Npcap 只读检测本机网卡上的 TCP 流量并识别游戏战斗连接吗？\n初始检测可能看到其他程序的流量，仅在本机处理，不上传，不发送封包。\n第三方工具仍有游戏规则风险。选择“否”不会开始采集。"
    )).await.map_err(|e| e.to_string())?;
    if !consent {
        return Err("已取消，未启动采集。".into());
    }
    tauri::WebviewWindowBuilder::new(&app, "main", tauri::WebviewUrl::App("index.html".into()))
        .title("亚特雷亚助手 · 战斗统计")
        .inner_size(320.0, 180.0)
        .decorations(false)
        .transparent(true)
        .always_on_top(true)
        .shadow(false)
        .build()
        .map_err(|e| e.to_string())?;
    let task_app = app.clone();
    let started = tauri::async_runtime::spawn_blocking(move || {
        let control = task_app.state::<CaptureControl>();
        let mut capturer = control.0.lock();
        capturer.start();
        capturer.is_running()
    })
    .await
    .map_err(|e| e.to_string())?;
    if !started {
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.close();
        }
        return Err("Npcap 未能启动，请检查驱动、网卡及安装时设置的权限。".into());
    }
    if let Some(window) = app.get_webview_window("launcher") {
        let _ = window.hide();
    }
    Ok(())
}

fn validate_target(root: &str, client: &str, operation: &str) -> Result<PathBuf, String> {
    if !["inspect", "install", "restore"].contains(&operation) {
        return Err("未知汉化操作".into());
    }
    if client != "steam" {
        return Err("PURPLE 汉化安装尚未验证，不能套用 Steam 引擎。".into());
    }
    let path = Path::new(root)
        .canonicalize()
        .map_err(|_| "游戏目录不存在")?;
    if !path.join("Aion2/Content").is_dir() {
        return Err("请选择包含 Aion2/Content 的游戏根目录。".into());
    }
    Ok(path)
}

struct BusyGuard;
impl Drop for BusyGuard {
    fn drop(&mut self) {
        LOCALIZATION_BUSY.store(false, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn localization_execute(
    app: tauri::AppHandle,
    root: String,
    client: String,
    operation: String,
) -> Result<Value, String> {
    if operation != "inspect"
        && (CAPTURE_STARTING.load(Ordering::SeqCst)
            || app.state::<CaptureControl>().0.lock().is_running())
    {
        return Err("请退出战斗统计并关闭游戏，再安装或还原汉化。".into());
    }
    if LOCALIZATION_BUSY.swap(true, Ordering::SeqCst) {
        return Err("汉化操作正在进行，请等待完成。".into());
    }
    let guard = BusyGuard;
    // Own the guard in the blocking worker: closing the UI never kills an
    // engine transaction or releases its lock before it has finished.
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = guard;
        let root = validate_target(&root, &client, &operation)?;
        let mut directory = app.path().resource_dir().map_err(|e| e.to_string())?.join("vendor/localization");
        #[cfg(debug_assertions)]
        if !directory.join("Atreia-Localization-Bridge.exe").is_file() {
            directory = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("vendor/localization");
        }
        let engine = directory.join("Aion2-Steam-CN-v2.4.0.exe");
        let helper = directory.join("Atreia-Localization-Bridge.exe");
        let bytes = std::fs::read(&engine).map_err(|_| "未提供汉化组件；不会自动下载未知程序。")?;
        let digest = Sha256::digest(bytes).iter().map(|byte| format!("{byte:02x}")).collect::<String>();
        if digest != ENGINE_HASH || !helper.is_file() {
            return Err("汉化组件缺失或校验不匹配。".into());
        }
        if operation != "inspect" && !crate::platform::dialog::ask_yes_no("确认游戏汉化操作",
            &format!("操作：{}\n目标：{}\n客户端：Steam / Global\n\n请先退出游戏。该操作会修改语言文件，原引擎保留备份、兼容检查和回滚。确定继续吗？", operation, root.display())) {
            return Ok(serde_json::json!({"ok":false,"cancelled":true,"operation":operation,"message":"已取消，未修改游戏。"}));
        }
        let mut command = Command::new(helper);
        command.current_dir(&directory).arg(engine).arg(&operation).arg(root).arg("steam");
        #[cfg(windows)] {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW; native engine dialogs remain visible
        }
        // Never timeout/kill install or restore: allow it to finish or roll back.
        let output = command.output().map_err(|e| e.to_string())?;
        if output.stdout.len() > 1024 * 1024 { return Err("引擎输出过大，请检查安装状态。".into()); }
        let response: Value = serde_json::from_slice(&output.stdout).map_err(|_| "引擎返回无效状态")?;
        if response["operation"].as_str() != Some(&operation) || response["ok"].as_bool().is_none() || !response["message"].is_string() {
            return Err("引擎返回无效状态，不能确认操作成功。".into());
        }
        if !output.status.success() && response["cancelled"] != true { return Err(response["message"].as_str().unwrap_or("操作失败").into()); }
        Ok(response)
    }).await.map_err(|e| e.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_unknown_operation_and_purple_before_any_process() {
        assert!(validate_target(".", "steam", "execute").is_err());
        assert!(validate_target(".", "purple", "install").is_err());
        assert!(validate_target(".", "steam", "install").is_err());
    }
    #[test]
    fn busy_guard_releases_after_worker_finishes() {
        LOCALIZATION_BUSY.store(true, Ordering::SeqCst);
        drop(BusyGuard);
        assert!(!LOCALIZATION_BUSY.load(Ordering::SeqCst));
    }
}
