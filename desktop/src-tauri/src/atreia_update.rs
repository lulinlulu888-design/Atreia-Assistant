//! Atreia-only updates. Never accepts a package URL or checksum from the webview.
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    path::{Path, PathBuf},
    sync::atomic::{AtomicBool, Ordering},
    time::Duration,
};
use tauri::{Emitter, Manager};
use tokio::io::AsyncWriteExt;

const API: &str =
    "https://api.github.com/repos/lulinlulu888-design/Atreia-Assistant/releases/latest";
const PREFIX: &str = "https://github.com/lulinlulu888-design/Atreia-Assistant/releases/download/";
const MAX_PACKAGE: u64 = 512 * 1024 * 1024;
static BUSY: AtomicBool = AtomicBool::new(false);
pub fn is_busy() -> bool {
    BUSY.load(Ordering::SeqCst)
}
struct Guard;
impl Drop for Guard {
    fn drop(&mut self) {
        BUSY.store(false, Ordering::SeqCst);
    }
}

#[derive(Deserialize)]
struct Asset {
    name: String,
    browser_download_url: String,
    digest: Option<String>,
    size: u64,
    state: String,
}
#[derive(Deserialize)]
struct Release {
    tag_name: String,
    draft: bool,
    prerelease: bool,
    assets: Vec<Asset>,
}
#[derive(Serialize, Clone, Debug)]
pub struct Update {
    status: String,
    current: String,
    latest: Option<String>,
    message: String,
    #[serde(skip)]
    url: String,
    #[serde(skip)]
    hash: String,
    #[serde(skip)]
    size: u64,
}

fn version(value: &str) -> Result<[u64; 3], String> {
    let value = value.strip_prefix('v').unwrap_or(value);
    let parts: Vec<_> = value.split('.').collect();
    if parts.len() != 3 {
        return Err("更新版本号无效".into());
    }
    let mut result = [0; 3];
    for (index, part) in parts.iter().enumerate() {
        if part.is_empty()
            || !part.bytes().all(|b| b.is_ascii_digit())
            || (part.len() > 1 && part.starts_with('0'))
        {
            return Err("更新版本号无效".into());
        }
        result[index] = part.parse().map_err(|_| "更新版本号无效")?;
    }
    Ok(result)
}
fn select(raw: &str, current: &str) -> Result<Update, String> {
    let release: Release = serde_json::from_str(raw).map_err(|_| "更新元数据无效")?;
    if release.draft || release.prerelease {
        return Err("不接受草稿或预发布更新".into());
    }
    let mut result = Update {
        status: "up_to_date".into(),
        current: current.into(),
        latest: Some(release.tag_name.clone()),
        message: "已是最新正式版本".into(),
        url: String::new(),
        hash: String::new(),
        size: 0,
    };
    if version(&release.tag_name)? <= version(current)? {
        return Ok(result);
    }
    let expected_name = format!(
        "Atreia-Assistant_{}_x64.msi",
        release
            .tag_name
            .strip_prefix('v')
            .unwrap_or(&release.tag_name)
    );
    let packages: Vec<_> = release
        .assets
        .iter()
        .filter(|a| a.name == expected_name)
        .collect();
    if packages.len() != 1 {
        return Err("正式版本缺少唯一的 Atreia-Assistant_*_x64.msi 安装包".into());
    }
    let asset = packages[0];
    let expected_url = format!("{}{}/{}", PREFIX, release.tag_name, asset.name);
    if asset.state != "uploaded"
        || asset.browser_download_url != expected_url
        || !asset
            .name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"-_.".contains(&b))
    {
        return Err("更新包来源不可信".into());
    }
    let hash = asset
        .digest
        .as_deref()
        .and_then(|s| s.strip_prefix("sha256:"))
        .ok_or("更新包缺少 GitHub SHA-256，拒绝安装")?;
    if hash.len() != 64
        || !hash.bytes().all(|b| b.is_ascii_hexdigit())
        || asset.size == 0
        || asset.size > MAX_PACKAGE
    {
        return Err("更新包校验信息无效".into());
    }
    result.status = "available".into();
    result.message = format!("发现正式版本 {}，可下载更新", release.tag_name);
    result.url = expected_url;
    result.hash = hash.to_ascii_lowercase();
    result.size = asset.size;
    Ok(result)
}
fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .user_agent("Atreia-Assistant-Updater")
        .redirect(reqwest::redirect::Policy::custom(|attempt| {
            let url = attempt.url();
            if attempt.previous().len() < 5
                && url.scheme() == "https"
                && matches!(
                    url.host_str(),
                    Some(
                        "github.com"
                            | "api.github.com"
                            | "release-assets.githubusercontent.com"
                            | "objects.githubusercontent.com"
                    )
                )
            {
                attempt.follow()
            } else {
                attempt.stop()
            }
        }))
        .build()
        .map_err(|e| e.to_string())
}
async fn check(current: &str) -> Result<Update, String> {
    let mut response = client()?
        .get(API)
        .header("Accept", "application/vnd.github+json")
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .map_err(|_| "无法连接更新服务，请稍后重试")?;
    if response.status() == reqwest::StatusCode::NOT_FOUND {
        return Ok(Update {
            status: "no_release".into(),
            current: current.into(),
            latest: None,
            message: "项目尚无正式 Release，不会下载未知更新包".into(),
            url: String::new(),
            hash: String::new(),
            size: 0,
        });
    }
    if !response.status().is_success() {
        return Err(format!("更新检查失败：HTTP {}", response.status()));
    }
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(|_| "更新元数据读取失败")? {
        if bytes.len() + chunk.len() > 1024 * 1024 {
            return Err("更新元数据过大".into());
        }
        bytes.extend_from_slice(&chunk);
    }
    select(
        std::str::from_utf8(&bytes).map_err(|_| "更新元数据编码无效")?,
        current,
    )
}

async fn download(
    http: &reqwest::Client,
    update: &Update,
    directory: &Path,
    progress: impl Fn(u64),
) -> Result<PathBuf, String> {
    let response = http
        .get(&update.url)
        .timeout(Duration::from_secs(600))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err(format!("下载失败：HTTP {}", response.status()));
    }
    if response.content_length().is_some_and(|n| n != update.size) {
        return Err("更新包大小与发布记录不一致".into());
    }
    let path = directory.join("Atreia-update.msi");
    let mut file = tokio::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .await
        .map_err(|e| e.to_string())?;
    let result = async {
        let mut stream = response.bytes_stream();
        let mut size = 0u64;
        let mut hash = Sha256::new();
        while let Some(chunk) = stream.next().await {
            let chunk = chunk.map_err(|e| e.to_string())?;
            size += chunk.len() as u64;
            if size > update.size || size > MAX_PACKAGE {
                return Err("更新包超过声明大小".to_string());
            }
            hash.update(&chunk);
            file.write_all(&chunk).await.map_err(|e| e.to_string())?;
            progress(size * 100 / update.size);
        }
        file.flush().await.map_err(|e| e.to_string())?;
        let digest: String = hash.finalize().iter().map(|b| format!("{b:02x}")).collect();
        if size != update.size || digest != update.hash {
            return Err("更新包 SHA-256 或大小校验失败，未安装".into());
        }
        Ok(path.clone())
    }
    .await;
    drop(file);
    if result.is_err() {
        let _ = tokio::fs::remove_file(&path).await;
    }
    result
}

#[tauri::command]
pub async fn atreia_check_update(app: tauri::AppHandle) -> Result<Update, String> {
    check(&app.package_info().version.to_string()).await
}
async fn stage_and_handoff(
    http: &reqwest::Client,
    update: &Update,
    directory: &Path,
    progress: impl Fn(u64),
    installer: impl FnOnce(&Path) -> Result<(), String>,
) -> Result<(), String> {
    let package = download(http, update, directory, progress).await?;
    installer(&package)
}
#[tauri::command]
pub async fn atreia_install_update(app: tauri::AppHandle) -> Result<(), String> {
    if BUSY.swap(true, Ordering::SeqCst) {
        return Err("更新正在进行".into());
    }
    let _guard = Guard;
    if crate::atreia_localization::is_busy()
        || crate::atreia_localization::is_capture_starting()
        || app.get_webview_window("main").is_some()
        || app
            .state::<crate::atreia_localization::CaptureControl>()
            .0
            .lock()
            .is_running()
    {
        return Err("请结束汉化操作并退出战斗统计后更新".into());
    }
    if !cfg!(windows) {
        return Err("此平台请手动更新".into());
    }
    // Re-fetch the authoritative release; never trust a stale UI download URL.
    let update = check(&app.package_info().version.to_string()).await?;
    if update.status != "available" {
        return Err(update.message);
    }
    let prompt = format!(
        "下载并安装 {}？\n校验通过后助手会退出，安装程序将重新启动助手。\n不会自动安装或修改游戏汉化。",
        update.latest.as_deref().unwrap_or("")
    );
    let accepted = tokio::task::spawn_blocking(move || {
        crate::platform::dialog::ask_yes_no("亚特雷亚助手更新", &prompt)
    })
    .await
    .map_err(|e| e.to_string())?;
    if !accepted {
        return Err("已取消更新".into());
    }
    let directory = std::env::temp_dir().join(format!(
        "atreia-update-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_nanos()
    ));
    std::fs::create_dir(&directory).map_err(|e| e.to_string())?;
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let install_dir = exe
        .parent()
        .ok_or("无法确定安装目录")?
        .to_string_lossy()
        .trim_end_matches('\\')
        .to_string();
    stage_and_handoff(
        &client()?,
        &update,
        &directory,
        |percent| {
            let _ = app.emit("atreia-update-progress", percent);
        },
        |package| crate::platform::updater::run_installer(package, &install_dir),
    )
    .await?;
    app.exit(0);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn metadata(tag: &str) -> serde_json::Value {
        serde_json::json!({"tag_name":tag,"draft":false,"prerelease":false,"assets":[{"name":"Atreia-Assistant_2.0.49_x64.msi","browser_download_url":format!("{}{}/Atreia-Assistant_2.0.49_x64.msi",PREFIX,tag),"digest":format!("sha256:{}","ab".repeat(32)),"size":123,"state":"uploaded"}]})
    }
    #[test]
    fn versions_and_upgrade_only() {
        assert!(version("1.2.3-beta").is_err());
        assert!(version("1.02.3").is_err());
        assert!(version("1.2").is_err());
        assert_eq!(
            select(&metadata("v2.0.49").to_string(), "2.0.48")
                .unwrap()
                .status,
            "available"
        );
        for current in ["2.0.49", "2.1.0", "3.0.0"] {
            assert_eq!(
                select(&metadata("v2.0.49").to_string(), current)
                    .unwrap()
                    .status,
                "up_to_date"
            );
        }
    }
    #[test]
    fn rejects_untrusted_or_incomplete_releases() {
        for (key, value) in [
            ("digest", serde_json::Value::Null),
            ("digest", serde_json::json!("sha256:bad")),
            ("size", serde_json::json!(0)),
            ("size", serde_json::json!(MAX_PACKAGE + 1)),
            (
                "browser_download_url",
                serde_json::json!("https://evil.example/update.msi"),
            ),
            ("state", serde_json::json!("new")),
            ("name", serde_json::json!("other.msi")),
        ] {
            let mut m = metadata("v2.0.49");
            m["assets"][0][key] = value;
            assert!(select(&m.to_string(), "2.0.48").is_err(), "{key}");
        }
        for key in ["draft", "prerelease"] {
            let mut m = metadata("v2.0.49");
            m[key] = serde_json::json!(true);
            assert!(select(&m.to_string(), "2.0.48").is_err());
        }
        let mut m = metadata("v2.0.49");
        let a = m["assets"][0].clone();
        m["assets"].as_array_mut().unwrap().push(a);
        assert!(select(&m.to_string(), "2.0.48").is_err());
    }
    #[tokio::test]
    async fn downloads_verify_bytes_and_clean_failures_without_installing() {
        use std::io::{Read, Write};
        for scenario in [
            "valid",
            "bad-hash",
            "wrong-size",
            "truncated",
            "http-error",
            "existing-file",
        ] {
            let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
            let address = listener.local_addr().unwrap();
            let status = if scenario == "http-error" {
                "404 Not Found"
            } else {
                "200 OK"
            };
            let body = b"synthetic package bytes";
            let sent = if scenario == "truncated" {
                &body[..5]
            } else {
                &body[..]
            };
            let server = std::thread::spawn(move || {
                let (mut socket, _) = listener.accept().unwrap();
                let mut request = [0; 4096];
                let _ = socket.read(&mut request);
                let response = format!(
                    "HTTP/1.1 {status}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                    body.len()
                );
                let _ = socket.write_all(response.as_bytes());
                let _ = socket.write_all(sent);
            });
            let directory = std::env::temp_dir().join(format!(
                "atreia-download-test-{}-{scenario}",
                std::process::id()
            ));
            std::fs::create_dir(&directory).unwrap();
            let package = directory.join("Atreia-update.msi");
            if scenario == "existing-file" {
                std::fs::write(&package, b"do not overwrite").unwrap();
            }
            let hash = Sha256::digest(body)
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<String>();
            let update = Update {
                status: "available".into(),
                current: "2.0.48".into(),
                latest: Some("v2.0.49".into()),
                message: String::new(),
                url: format!("http://{address}/fixture"),
                hash: if scenario == "bad-hash" {
                    "00".repeat(32)
                } else {
                    hash
                },
                size: body.len() as u64 + u64::from(scenario == "wrong-size"),
            };
            let launches = std::sync::atomic::AtomicUsize::new(0);
            let result = stage_and_handoff(
                &reqwest::Client::new(),
                &update,
                &directory,
                |_| {},
                |path| {
                    assert_eq!(std::fs::read(path).unwrap(), body);
                    launches.fetch_add(1, Ordering::SeqCst);
                    Ok(())
                },
            )
            .await;
            server.join().unwrap();
            if scenario == "valid" {
                assert_eq!(std::fs::read(&package).unwrap(), body);
                assert!(result.is_ok());
            } else if scenario == "existing-file" {
                assert!(result.is_err());
                assert_eq!(std::fs::read(&package).unwrap(), b"do not overwrite");
            } else {
                assert!(result.is_err(), "{scenario}");
                assert!(!package.exists(), "{scenario}");
            }
            assert_eq!(
                launches.load(Ordering::SeqCst),
                usize::from(scenario == "valid")
            );
            std::fs::remove_dir_all(directory).unwrap();
        }
    }
    #[tokio::test]
    #[ignore = "explicit read-only live GitHub service verification"]
    async fn live_github_release_check() {
        let result = check(env!("CARGO_PKG_VERSION")).await.unwrap();
        assert!(["available", "up_to_date", "no_release"].contains(&result.status.as_str()));
        println!("{}", serde_json::to_string(&result).unwrap());
    }
}
