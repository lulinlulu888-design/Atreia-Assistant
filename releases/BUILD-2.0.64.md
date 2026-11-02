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

## 正式发布核验（2026-11-02）

- 正式标签 `v2.0.64` 对应提交 `efe49a6a95d0b28ee2f24dbe946a786698dced06`；[发布工作流](https://github.com/lulinlulu888-design/Atreia-Assistant/actions/runs/41395969724) 的 Windows 构建和 S3 同步均成功。
- [GitHub 正式版](https://github.com/lulinlulu888-design/Atreia-Assistant/releases/tag/v2.0.64) 已公开 MSI、构建材料、来源归档和校验文件，不是草稿或预发布。
- 正式 MSI：`Atreia-Assistant_2.0.64_x64.msi`，51,807,018 字节（49.4 MB），SHA-256 `4bff618eee328898d543db82cb476a9b57cb8db0a607ee5b75976612e1deb44e`。GitHub 与 S3 公开地址重新下载，摘要及大小一致。
- 官网同步提交 `e1d15b9`；a2go.cc 已部署目录 `20261102061130`。首页、指南、下载清单及 GitHub Pages 备用更新清单均核对为 2.0.64；原下载计数和服务保留。
- 本地前端 107 项、Rust 177 项通过（5 项忽略），Python 280 项执行（272 项通过、8 项跳过）；另完成 C# 安全检查、MSI 结构和包内双端组件的真实目录只读检测。网站相关 25 项检查通过。

只读检测与包结构校验不等于真实 MSI 跨版本覆盖、卸载或全部游戏画面的验收。后续通用发布操作见[发布流程](../documentation/RELEASING.md)，本文件保持本版历史结果。
