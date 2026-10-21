//! Backend-owned confirmation: only the dedicated window may answer it.
//! No caller-supplied `consented` flag, stale approval or silent fallback.
use parking_lot::Mutex;
use serde::Serialize;
use std::sync::{atomic::{AtomicU64, Ordering}, OnceLock};
use tauri::Manager;
use tokio::sync::oneshot;

const LABEL: &str = "atreia-confirmation";

/// Busy operations must keep their owner alive, not prevent the user from
/// cancelling the dedicated confirmation that those operations are awaiting.
pub fn protect_close(label: &str, localizing: bool, updating: bool) -> bool {
    label != LABEL && (localizing || updating)
}

fn prompt_axis(owner_start: i32, owner_extent: u32, prompt_extent: u32, work_start: i32, work_extent: u32) -> i32 {
    let desired = i64::from(owner_start) + (i64::from(owner_extent) - i64::from(prompt_extent)) / 2;
    let minimum = i64::from(work_start);
    let maximum = minimum + (i64::from(work_extent) - i64::from(prompt_extent)).max(0);
    desired.clamp(minimum, maximum).clamp(i64::from(i32::MIN), i64::from(i32::MAX)) as i32
}

#[derive(Clone, Serialize)]
pub struct Prompt {
    pub title: String,
    pub message: String,
    pub confirm_label: String,
    pub details: Vec<(String, String)>,
}

#[derive(Clone, Serialize)]
pub struct Request {
    id: u64,
    #[serde(flatten)]
    prompt: Prompt,
}

struct Pending {
    request: Request,
    sender: oneshot::Sender<bool>,
}

#[derive(Default)]
struct Broker {
    next: AtomicU64,
    pending: Mutex<Option<Pending>>,
}

impl Broker {
    fn begin(&self, prompt: Prompt) -> Result<(u64, oneshot::Receiver<bool>), String> {
        let mut pending = self.pending.lock();
        if pending.is_some() { return Err("请先处理当前确认窗口。".into()); }
        let id = self.next.fetch_add(1, Ordering::SeqCst) + 1;
        let (sender, receiver) = oneshot::channel();
        *pending = Some(Pending { request: Request { id, prompt }, sender });
        Ok((id, receiver))
    }

    fn read(&self, caller: &str) -> Result<Request, String> {
        if caller != LABEL { return Err("此窗口无权读取操作确认。".into()); }
        self.pending.lock().as_ref().map(|pending| pending.request.clone())
            .ok_or_else(|| "操作确认已结束。".into())
    }

    fn answer(&self, caller: &str, id: u64, accepted: bool) -> Result<(), String> {
        if caller != LABEL { return Err("此窗口无权确认操作。".into()); }
        let mut pending = self.pending.lock();
        if pending.as_ref().map(|p| p.request.id) != Some(id) {
            return Err("此确认已失效，请重新操作。".into());
        }
        pending.take().unwrap().sender.send(accepted)
            .map_err(|_| "操作已取消。".into())
    }
}

fn broker() -> &'static Broker {
    static BROKER: OnceLock<Broker> = OnceLock::new();
    BROKER.get_or_init(Broker::default)
}

#[tauri::command]
pub fn confirmation_request(window: tauri::WebviewWindow) -> Result<Request, String> {
    broker().read(window.label())
}

#[tauri::command]
pub fn confirmation_respond(window: tauri::WebviewWindow, id: u64, accepted: bool) -> Result<(), String> {
    broker().answer(window.label(), id, accepted)
}

#[tauri::command]
pub fn confirmation_cancel(window: tauri::WebviewWindow) -> Result<(), String> {
    let request = broker().read(window.label())?;
    broker().answer(window.label(), request.id, false)
}

pub async fn ask(app: &tauri::AppHandle, prompt: Prompt) -> Result<bool, String> {
    ask_for_window(app, "launcher", prompt).await
}

pub async fn ask_for_window(app: &tauri::AppHandle, owner_label: &str, prompt: Prompt) -> Result<bool, String> {
    let owner = app.get_webview_window(owner_label).ok_or("操作窗口已关闭，未执行操作。")?;
    let (id, receiver) = broker().begin(prompt)?;
    let built = tauri::WebviewWindowBuilder::new(app, LABEL, tauri::WebviewUrl::App("confirmation.html".into()))
        .title("亚特雷亚助手 · 确认操作")
        .inner_size(560.0, 420.0)
        .decorations(false)
        .resizable(false)
        .always_on_top(true)
        .skip_taskbar(false)
        .background_color(tauri::window::Color(233, 238, 241, 255))
        .parent(&owner)
        .and_then(|builder| builder.build());
    let window = match built {
        Ok(window) => window,
        Err(error) => { let _ = broker().answer(LABEL, id, false); return Err(format!("无法打开确认窗口，未执行操作：{error}")); }
    };
    window.on_window_event(move |event| {
        if matches!(event, tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed) {
            let _ = broker().answer(LABEL, id, false);
        }
    });
    if let (Ok(position), Ok(owner_size), Ok(size), Ok(Some(monitor))) =
        (owner.outer_position(), owner.outer_size(), window.outer_size(), owner.current_monitor()) {
        let work = monitor.work_area();
        let _ = window.set_position(tauri::PhysicalPosition {
            x: prompt_axis(position.x, owner_size.width, size.width, work.position.x, work.size.width),
            y: prompt_axis(position.y, owner_size.height, size.height, work.position.y, work.size.height),
        });
    } else { let _ = window.center(); }
    let _ = window.set_focus();
    let accepted = receiver.await.unwrap_or(false);
    // The answer is already resolved. Destroy only our own prompt, without
    // emitting a second CloseRequested while its operation guard is held.
    let _ = window.destroy();
    let _ = owner.set_focus();
    Ok(accepted)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn prompts_stay_in_the_owner_monitor_work_area() {
        assert_eq!(prompt_axis(12, 210, 560, 0, 1920), 0);
        assert_eq!(prompt_axis(1850, 210, 560, 0, 1920), 1360);
        assert_eq!(prompt_axis(-1910, 210, 560, -1920, 1920), -1920);
        assert_eq!(prompt_axis(-100, 210, 560, -1920, 1920), -560);
        assert_eq!(prompt_axis(500, 800, 560, 0, 1920), 620);
        assert_eq!(prompt_axis(500, 210, 560, 0, 400), 0);
    }
    fn prompt() -> Prompt { Prompt { title:"确认安装".into(),message:"风险说明".into(),confirm_label:"确认安装".into(),details:vec![("客户端".into(),"PURPLE".into())] } }
    #[test]
    fn busy_owner_is_protected_but_confirmation_can_always_close() {
        for localizing in [false, true] {
            for updating in [false, true] {
                assert!(!protect_close(LABEL, localizing, updating));
                for label in ["launcher", "main", "settings", "confirmation-pretender"] {
                    assert_eq!(protect_close(label, localizing, updating), localizing || updating);
                }
            }
        }
    }
    #[tokio::test]
    async fn only_the_confirmation_window_can_approve_and_only_once() {
        let broker = Broker::default();
        let (id, receiver) = broker.begin(prompt()).unwrap();
        for caller in ["launcher", "main", "settings", "confirmation-pretender"] {
            assert!(broker.read(caller).is_err());
            assert!(broker.answer(caller, id, true).is_err());
        }
        assert_eq!(broker.read(LABEL).unwrap().id, id);
        broker.answer(LABEL, id, true).unwrap();
        assert!(receiver.await.unwrap());
        assert!(broker.answer(LABEL, id, true).is_err());
    }
    #[tokio::test]
    async fn cancellation_duplicate_and_stale_answers_never_approve_a_later_action() {
        let broker = Broker::default();
        let (old, receiver) = broker.begin(prompt()).unwrap();
        assert!(broker.begin(prompt()).is_err());
        broker.answer(LABEL, old, false).unwrap();
        assert!(!receiver.await.unwrap());
        let (new, receiver) = broker.begin(prompt()).unwrap();
        assert!(broker.answer(LABEL, old, true).is_err());
        assert_eq!(broker.read(LABEL).unwrap().id, new);
        broker.answer(LABEL, new, false).unwrap();
        assert!(!receiver.await.unwrap());
    }
    #[tokio::test]
    async fn dropped_or_closed_confirmation_does_not_mean_yes() {
        let broker = Broker::default();
        let (id, receiver) = broker.begin(prompt()).unwrap();
        drop(receiver);
        assert!(broker.answer(LABEL, id, true).is_err());
        assert!(broker.read(LABEL).is_err());
        let (id, receiver) = broker.begin(prompt()).unwrap();
        broker.answer(LABEL, id, false).unwrap();
        assert!(!receiver.await.unwrap());
    }
}
