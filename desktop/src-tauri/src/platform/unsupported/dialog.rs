/// No native dialogs: the question is logged and answered "no".
pub fn ask_yes_no(title: &str, message: &str) -> bool {
    tracing::info!("{title}: {message} (no dialog on this platform; answering no)");
    false
}

pub fn show_error(title: &str, message: &str) {
    tracing::error!("{title}: {message}");
}
