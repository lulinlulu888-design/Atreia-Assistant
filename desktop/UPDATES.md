# 助手自动更新

当前说明适用于 2.0.64。玩家从[官网](https://a2go.cc/)下载安装包，或使用主界面的“检查更新”。

## 检查与下载来源

首页启动后自动检查本仓库最新正式 Release，手动检查使用相同逻辑。GitHub API 连接失败或限流时，备用地址为：

```text
https://lulinlulu888-design.github.io/Atreia-Assistant/updates/latest.json
```

这是 GitHub Pages 备用入口，并非 a2go.cc 的 S3 下载接口。两站虽然同时保存更新清单，当前桌面代码的备用地址仍是上述 Pages URL。清单记录同仓库正式 MSI 的版本、大小和 SHA-256，不绕过正常的包校验。

只接受本仓库正式、非预发布、严格高于当前三段版本号的 Windows x64 MSI，资源名为 `Atreia-Assistant_<version>_x64.msi`。缺少、重复或未完成上传的资产会被拒绝，不采用上游 A2Tools、源码包或未知域名的下载。

## 用户操作与保护

- 检查只读取版本信息，不开始采集、下载安装包或修改游戏。
- 发现新版后显示“下载并更新”，确认后开始下载，显示进度并阻止重复操作。
- 更新前应停止 DPS/雷达采集并结束汉化事务；下载期间不关闭助手。
- 文件下载到独立临时目录，大小和完整 SHA-256 均匹配后才交给 Windows MSI 安装器。
- HTTP 错误、截断、大小或摘要不符时不启动安装；成功交接后助手退出，安装器负责升级。
- 软件升级不自动更新游戏资源，也不自动重新安装汉化。升级后请退出游戏，再检测并安装所选客户端的汉化。
- 自动安装针对 Windows。GitHub HTTPS 提供的摘要校验不等于独立代码签名。

实现见 [atreia_update.rs](src-tauri/src/atreia_update.rs)，发布端同步步骤见[发布流程](../documentation/RELEASING.md)。

## 桌面快捷方式

MSI 使用中文名称 **亚特雷亚助手**，创建桌面和开始菜单入口。桌面快捷方式复用 Tauri 的 `ApplicationShortcutDesktop`，纳入必装功能；目标引用安装器中的程序文件，不绑定构建机器路径。卸载由 Windows 安装器清理。

生成 MSI 后，从仓库根目录执行只读包检查：

```powershell
./test-installer-shortcut.ps1 -MsiPath '<generated-msi-path>'
```

包结构检查不等于已在真实桌面完成所有升级、卸载和重启场景。

## 维护验证

从 `desktop/` 执行：

```powershell
node --test tests/atreia-update.test.cjs
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib atreia_update
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib live_github_release_check -- --ignored --nocapture
```

合成包及本地 HTTP 测试覆盖下载、校验和安装器交接替身，不执行真实 MSI。最后一条显式联网读取 GitHub 最新正式版，不需要登录。

2.0.64 的正式 MSI、S3 回下载及备用更新清单已于 2026-11-02 核验，详见[本版记录](../releases/BUILD-2.0.64.md)。较早的自动更新与快捷方式验收数据移至[历史记录](../documentation/archive/updater-through-2.0.55.md)，不作为当前版本的测试结论。
