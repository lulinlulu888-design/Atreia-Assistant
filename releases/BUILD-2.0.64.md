# 2.0.64 构建与核验

应用以 2026-10-28 前 `4b4a95d` 为基线，保留官网 main `19b435e` 的 Nuxt、MongoDB 下载点击计数及 S3 自动发布。Steam 使用独立 Python 冻结组件，PURPLE 保留原 v2.4.0 引擎及自有补译桥接器；组件按客户端分别固定 SHA-256。

来源归档 `Atreia-Assistant_2.0.64_localization-sources.zip` 的 SHA-256 为 `2bbda1e41458a776e6f19d9f301f8085309580069361d93d75081ae9179bc2d0`。内容是本机官方资源、自有 2.0.63 中文映射、逐条源摘要绑定的复核以及 PURPLE 原方案的审核补译。没有参考项目的翻译 DAT。每份输入摘要见归档内 sources.json。

将归档解压到 INPUTS，将 2.0.51 构建材料中的 component 放到 BASE-COMPONENT。在 Windows 安装 localization/requirements-build.txt 中的依赖后执行：

```powershell
./prepare-release-localization.ps1 -Inputs INPUTS -BaseComponent BASE-COMPONENT -Python (Get-Command python).Source -Destination NEW-STAGE
Copy-Item NEW-STAGE/component/* desktop/src-tauri/vendor/localization/ -Recurse -Force
```

脚本从完整源表重建 Steam bundle，拒绝缺译、键序/标记/参数不匹配，并要求生成 DAT 与实机通过的 `2a11c23…df265` 一致。153,297 条中文 UI 原值之外另存 153,297 条官方日文参考，不以参考条目充当翻译。PURPLE additions 与 2.0.63 已审核文件逐字节相同，SHA-256 为 `2a4905a82ce4304f9feb58139f7a672920ccacef67c123cc8f19158af8c90704`。

发布工作流执行 Python、前端、C# 安全及 Rust 测试，构建中文 MSI，检查中文桌面快捷方式，再发布安装包、构建材料和 SHA256SUMS。S3 上传后重新下载比对。Python 运行时及依赖许可随 MSI 和构建材料一起提供。

实机验收：用户确认 Steam 全量中文正常显示，切到 English 再回日本語仍正常。所有游戏内操作由用户完成。PURPLE 保留原英文方案，本次真实资源检查为 160,286 键、24,606 条补译；不宣称本次重新完成 PURPLE 所有游戏界面或雷达现场验收。
