# 助手自动更新

首页启动 1 秒后自动检查本项目 GitHub 最新正式 Release；也可点击“检查更新”。
检查不会启动统计，不会下载、安装软件或修改游戏文件。发现新版后显示“下载并更新”，
点击后还有本地确认；取消或网络错误可重试。更新下载期间显示百分比，阻止重复更新
和关闭助手，并与汉化事务、战斗统计互斥。安装程序启动成功后助手退出，MSI 重新启动助手。

只接受本仓库正式发布、严格高于当前三段版本号的 Windows x64 MSI。
发布资源名称必须是 `Atreia-Assistant_<version>_x64.msi`，例如
`Atreia-Assistant_2.0.50_x64.msi`。上传到正式 GitHub Release，等待资源状态为
`uploaded` 并带 GitHub `digest: sha256:...`；缺失或重复的安装资源会拒绝更新。
不会改用上游 A2Tools 包、源码压缩包、其他仓库或未知域名。

下载使用独立临时目录、不覆盖已有文件；校验声明大小和完整 SHA-256 后才交给
现有 Windows MSI 安装器。网络截断、HTTP 错误、大小或摘要不符时不启动安装器。
更新前请结束统计和汉化事务；它不自动更新游戏，也不自动重新安装汉化。
Linux 暂不自动安装。SHA-256 来自 GitHub 的 HTTPS 发布 API，非独立代码签名。

测试：

```powershell
node --test tests/atreia-update.test.cjs
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib atreia_update
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib live_github_release_check -- --ignored --nocapture
npm run tauri build -- --no-bundle --debug
```

测试用合成包和本地 HTTP 服务覆盖完整下载、校验、安装器交接（替身），
不会实际运行 MSI 或覆盖用户已安装的助手。真实 GitHub 检查不需要登录。
2026-10-06 检查时，本仓库 latest Release 接口返回 404；这是历史记录，当前状态以
GitHub 为准。2.0.50 已从源码重建并通过 MSI 包检查，但未在真实桌面完成跨版本
MSI 覆盖/重启测试；不能把替身测试描述为已完成真实升级。

## 桌面快捷方式

MSI 复用 Tauri 内置 `ApplicationShortcutDesktop`，并通过 WiX `componentRefs`
将它纳入必装的 `External` 功能，避免另建重复快捷方式。目标使用安装器文件引用
`[!Path]`，工作目录为 `INSTALLDIR`，不绑定构建机器的路径；卸载由 MSI 清理。
此配置遵循 [Tauri WiX 组件引用配置](https://v2.tauri.app/reference/config/#wixconfig)。

每次生成 MSI 后，从仓库根目录执行只读包检查：

```powershell
./test-installer-shortcut.ps1 -MsiPath '<generated-msi-path>'
```

2026-10-12：2.0.50 已完整源码重建，MSI 的桌面目标、必装功能及卸载清理记录检查通过；
解包核对版本与三个汉化组件的 SHA-256 一致。未在真实桌面执行安装、升级或卸载测试。
