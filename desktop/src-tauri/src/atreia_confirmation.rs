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
    let owner = app.get_webview_window("launcher").ok_or("主页已关闭，未执行操作。")?;
    let (id, receiver) = broker().begin(prompt)?;
    let built = tauri::WebviewWindowBuilder::new(app, LABEL, tauri::WebviewUrl::App("confirmation.html".into()))
        .title("亚特雷亚助手 · 确认操作")
        .inner_size(560.0, 420.0)
        .decorations(false)
        .resizable(false)
        .skip_taskbar(true)
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
    if let (Ok(position), Ok(owner_size), Ok(size)) = (owner.outer_position(), owner.outer_size(), window.outer_size()) {
        let _ = window.set_position(tauri::PhysicalPosition {
            x: position.x + (owner_size.width as i32 - size.width as i32) / 2,
            y: position.y + (owner_size.height as i32 - size.height as i32) / 2,
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
