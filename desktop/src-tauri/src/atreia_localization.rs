//! Atreia additions. Upstream capture stays inert until the launcher action.
use parking_lot::Mutex;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    process::Command,
    sync::atomic::{AtomicBool, Ordering},
};
use tauri::{Emitter, Manager};

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
pub async fn open_localization(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("localization") {
        window.emit("atreia-localization-opened", ()).map_err(|e| e.to_string())?;
        window.show().map_err(|e| e.to_string())?;
        return window.set_focus().map_err(|e| e.to_string());
    }
    tauri::WebviewWindowBuilder::new(&app, "localization", tauri::WebviewUrl::App("localization.html".into()))
        .title("亚特雷亚助手 · 游戏汉化")
        .inner_size(600.0, 470.0).min_inner_size(460.0, 380.0)
        .background_color(tauri::window::Color(233, 238, 241, 255))
        .build().map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn hide_localization(window: tauri::WebviewWindow, app: tauri::AppHandle) -> Result<(), String> {
    if window.label() != "localization" { return Err("此窗口无权关闭汉化界面。".into()); }
    if is_busy() || crate::atreia_update::is_busy() { return Err("请等待当前操作完成。".into()); }
    window.hide().map_err(|e| e.to_string())?;
    if let Some(launcher) = app.get_webview_window("launcher") { let _ = launcher.set_focus(); }
    Ok(())
}

pub async fn start_radar_capture(app: tauri::AppHandle) -> Result<(), String> {
    if crate::atreia_update::is_busy() || is_busy() { return Err("请等待当前更新或汉化操作完成。".into()); }
    if CAPTURE_STARTING.swap(true, Ordering::SeqCst) { return Err("采集正在启动，请稍候。".into()); }
    struct Guard;
    impl Drop for Guard { fn drop(&mut self) { CAPTURE_STARTING.store(false,Ordering::SeqCst); } }
    let _guard=Guard;
    if crate::atreia_update::is_busy() || is_busy() { return Err("请等待当前更新或汉化操作完成。".into()); }
    if !crate::platform::pcap::library_available() { return Err("未能加载 Npcap。请从 Npcap 官网安装驱动，安装完成后重试。".into()); }
    let accepted=crate::atreia_confirmation::ask(&app,crate::atreia_confirmation::Prompt {
        title:"开启隐藏宝箱雷达".into(),confirm_label:"确认开启".into(),details:vec![],
        message:"使用 Npcap 只读检测本机网卡 TCP 流量，在本机识别游戏连接与隐藏宝箱。\n初始采集可能看到其他程序的流量，不上传、不发送封包、不读取游戏内存。\n第三方工具有游戏规则风险。取消不会开启雷达。".into(),
    }).await?;
    if !accepted { return Err("已取消，未开启雷达。".into()); }
    if app.get_webview_window("radar").is_none() { return Err("雷达窗口已关闭。".into()); }
    let radar=app.state::<std::sync::Arc<crate::atreia_radar::RadarControl>>();
    radar.stop();
    radar.active.store(true,Ordering::SeqCst);
    let task_app=app.clone();
    let started=tauri::async_runtime::spawn_blocking(move || {
        let control=task_app.state::<CaptureControl>(); let mut capturer=control.0.lock();
        if !capturer.is_running() { capturer.start(); }
        capturer.is_running()
    }).await.map_err(|e|e.to_string())?;
    if !started || app.get_webview_window("radar").is_none() {
        crate::atreia_radar::stop_radar(app.clone());
        return Err("雷达未能启动，请检查 Npcap、网卡权限或重新打开窗口。".into());
    }
    Ok(())
}

#[tauri::command]
pub async fn open_combat(app: tauri::AppHandle) -> Result<(), String> {
    if crate::atreia_update::is_busy() { return Err("请等待助手更新完成。".into()); }
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
    if crate::atreia_update::is_busy() { return Err("请等待助手更新完成。".into()); }
    // Recheck after claiming our flag: localization may have started between
    // the initial check and swap. Both sides use SeqCst and recheck each other.
    if LOCALIZATION_BUSY.load(Ordering::SeqCst) {
        return Err("请等待汉化操作完成。".into());
    }
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
    let consent = crate::atreia_confirmation::ask(&app, crate::atreia_confirmation::Prompt {
        title: "开启战斗统计".into(), confirm_label: "确认开启".into(), details: vec![],
        message: "使用 Npcap 只读检测本机网卡上的 TCP 流量并识别游戏战斗连接。\n初始检测可能看到其他程序的流量，仅在本机处理，不上传，不发送封包。\n第三方工具仍有游戏规则风险。取消不会开始采集。".into(),
    }).await?;
    if !consent {
        return Err("已取消，未启动采集。".into());
    }
    tauri::WebviewWindowBuilder::new(&app, "main", tauri::WebviewUrl::App("index.html".into()))
        .title("亚特雷亚助手 · 战斗统计")
        .inner_size(400.0, 220.0)
        .decorations(false)
        .transparent(true)
        .always_on_top(true)
        .shadow(false)
        .build()
        .map_err(|e| e.to_string())?;
    app.state::<std::sync::Arc<crate::atreia_radar::RadarControl>>().combat_active.store(true,Ordering::SeqCst);
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
    if app.get_webview_window("main").is_none() {
        if !app.state::<std::sync::Arc<crate::atreia_radar::RadarControl>>().active.load(Ordering::SeqCst) {
            app.state::<CaptureControl>().0.lock().stop();
        }
        return Err("统计窗口已关闭，采集已停止。".into());
    }
    Ok(())
}

fn validate_target_root(root: &str) -> Result<PathBuf, String> {
    // .NET Framework rejects std::canonicalize's Windows verbatim prefix.
    // Preserve canonical target validation while using legacy-compatible paths.
    let path = dunce::canonicalize(Path::new(root))
        .map_err(|_| "游戏目录不存在")?;
    if !path.join("Aion2/Content").is_dir() {
        return Err("请选择包含 Aion2/Content 的游戏根目录。".into());
    }
    Ok(path)
}

fn validate_target(root: &str, client: &str, operation: &str) -> Result<PathBuf, String> {
    if !["inspect", "install", "restore"].contains(&operation) {
        return Err("未知汉化操作".into());
    }
    if !["steam", "purple"].contains(&client) {
        return Err("未知客户端。".into());
    }
    validate_target_root(root)
}

/// Read-only compatibility check used by the launcher before offering an action.
/// A directory check does not replace the source-table checks performed by installation.
#[tauri::command]
pub fn inspect_localization_target(root: String, client: String) -> Result<Value, String> {
    let root = validate_target_root(&root)?;
    let text_packages = root.join("Aion2/Content/Paks/L10N/Text");
    if !text_packages.is_dir() {
        return Err("未找到本地化文本包目录 Aion2/Content/Paks/L10N/Text。".into());
    }

    match client.as_str() {
        "steam" => Ok(serde_json::json!({
            "ok": true,
            "supported": true,
            "root": root,
            "message": "已检测到 Steam / Global 游戏目录和本地化文本包；可继续使用 Steam 汉化组件检测、安装或还原。"
        })),
        "purple" => Ok(serde_json::json!({
            "ok": true,
            "supported": true,
            "root": root,
            "message": "已检测到 PURPLE 游戏目录和本地化文本包；安装时将读取当前英文语言表并核对键值，使用独立的本地备份支持还原。"
        })),
        _ => Err("未知客户端。".into()),
    }
}

struct BusyGuard;
impl Drop for BusyGuard {
    fn drop(&mut self) {
        LOCALIZATION_BUSY.store(false, Ordering::SeqCst);
    }
}

#[tauri::command]
pub async fn discover_localization_roots(client: String) -> Result<Vec<PathBuf>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let seeds = match client.as_str() {
            "steam" => crate::platform::game_paths::steam_roots(),
            "purple" => crate::platform::game_paths::purple_roots(),
            _ => return Err("未知客户端。".into()),
        };
        crate::atreia_game_paths::discover(&client, &seeds)
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn browse_localization_root(window: tauri::WebviewWindow, start: Option<String>) -> Result<Option<PathBuf>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(selected) = crate::platform::screenshot::pick_folder(&window, start.as_deref()) else { return Ok(None); };
        crate::atreia_game_paths::normalize(Path::new(&selected))
            .map(Some).ok_or_else(|| "请选择包含 Aion2 文件夹的游戏目录。".into())
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn localization_execute(
    app: tauri::AppHandle,
    root: String,
    client: String,
    operation: String,
) -> Result<Value, String> {
    if crate::atreia_update::is_busy() { return Err("请等待助手更新完成。".into()); }
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
    if crate::atreia_update::is_busy() { return Err("请等待助手更新完成。".into()); }
    if operation != "inspect"
        && (CAPTURE_STARTING.load(Ordering::SeqCst)
            || app.state::<CaptureControl>().0.lock().is_running())
    {
        return Err("请退出战斗统计并关闭游戏，再安装或还原汉化。".into());
    }
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
        if operation != "inspect" {
            let restoring = operation == "restore";
            let accepted = tauri::async_runtime::block_on(crate::atreia_confirmation::ask(&app, crate::atreia_confirmation::Prompt {
                title: if restoring { "还原游戏语言" } else { "安装 / 更新汉化" }.into(),
                confirm_label: if restoring { "确认还原" } else { "确认安装" }.into(),
                details: vec![("客户端".into(), if client == "purple" { "PURPLE" } else { "Steam / Global" }.into()), ("游戏目录".into(), root.display().to_string())],
                message: if restoring { "请先完全退出游戏。\n将根据校验过的备份还原语言文件；若游戏版本或备份不匹配，会停止操作。\n取消会返回汉化面板，不修改游戏文件。" } else { "请先完全退出游戏。\n将重新核对当前语言资源并写入汉化文件。原引擎保留备份、兼容检查和失败回滚。\n取消会返回汉化面板，不修改游戏文件。" }.into(),
            }))?;
            if !accepted {
                return Ok(serde_json::json!({"ok":false,"cancelled":true,"operation":operation,"message":"已取消，未修改游戏。"}));
            }
            let _ = app.emit_to("launcher", "atreia-localization-stage", serde_json::json!({"operation":operation,"client":client,"stage":"running"}));
            let _ = app.emit_to("localization", "atreia-localization-stage", serde_json::json!({"operation":operation,"client":client,"stage":"running"}));
        }
        let mut command = Command::new(helper);
        command.current_dir(dunce::simplified(&directory)).arg(dunce::simplified(&engine)).arg(&operation).arg(dunce::simplified(&root)).arg(&client);
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
    #[cfg(windows)]
    #[test]
    fn game_root_does_not_pass_verbatim_prefix_to_framework() {
        let root = std::env::temp_dir().join(format!("atreia-framework-path-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Aion2/Content")).unwrap();
        let validated = validate_target_root(&root.to_string_lossy()).unwrap();
        assert!(!validated.to_string_lossy().starts_with(r"\\?\"));
        assert_eq!(validated.canonicalize().unwrap(), root.canonicalize().unwrap());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn rejects_unknown_operation_and_invalid_roots_before_any_process() {
        assert!(validate_target(".", "steam", "execute").is_err());
        assert!(validate_target(".", "purple", "install").is_err());
        assert!(validate_target(".", "steam", "install").is_err());
    }

    #[test]
    fn a_valid_purple_layout_is_inspectable_and_installable() {
        let root = std::env::temp_dir().join(format!("atreia-purple-{}", std::process::id()));
        std::fs::create_dir_all(root.join("Aion2/Content/Paks/L10N/Text")).unwrap();
        let path = root.to_string_lossy().into_owned();
        let result = inspect_localization_target(path.clone(), "purple".into()).unwrap();
        assert_eq!(result["supported"], true);
        assert!(validate_target(&path, "purple", "install").is_ok());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn busy_guard_releases_after_worker_finishes() {
        LOCALIZATION_BUSY.store(true, Ordering::SeqCst);
        drop(BusyGuard);
        assert!(!LOCALIZATION_BUSY.load(Ordering::SeqCst));
    }

    #[test]
    #[ignore = "explicit read-only inspection using the packaged bridge and an automatically found Steam game"]
    fn live_auto_discovered_steam_inspection() {
        let roots = crate::atreia_game_paths::discover("steam", &crate::platform::game_paths::steam_roots()).unwrap();
        assert_eq!(roots.len(), 1, "Select a specific fixture when several installations exist");
        let directory = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("vendor/localization");
        let pak = roots[0].join("Aion2/Content/Paks/L10N/Text/en-US/pakchunk502000-Windows_0_P.pak");
        let before = std::fs::read(&pak).unwrap();
        let output = Command::new(directory.join("Atreia-Localization-Bridge.exe"))
            .current_dir(&directory).arg(directory.join("Aion2-Steam-CN-v2.4.0.exe"))
            .arg("inspect").arg(&roots[0]).arg("steam").output().unwrap();
        let response: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert!(output.status.success(), "{}", response["message"]);
        assert_eq!(response["ok"], true); assert_eq!(response["operation"], "inspect");
        assert_eq!(std::fs::read(pak).unwrap(), before);
        println!("{}", response["message"]);
    }
}
