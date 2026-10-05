# 亚特雷亚助手 · A2Tools 整合分支

本目录直接基于 taengu/A2Tools-DPS-Meter 的提交
`70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98`，不是独立原创统计软件。
上游：https://github.com/taengu/A2Tools-DPS-Meter
完整上游 LICENSE、源码署名和 README 保留，修改版继续使用 GPL-3.0。

启动先显示约 480×350 的功能选择页，“战斗统计”与“游戏汉化”互相独立。
只有明确开启战斗统计才建立约 320×180 的透明置顶悬浮窗并开始采集。
汉化功能在选择页内打开，不打开统计浮窗。设置/详情也是按需打开，
不恢复上次留下的详情窗口到启动页上。

新增游戏汉化入口，调用本项目的版本固定汉化桥接组件。该组件可选，
不包含在源码中，也不自动下载。两端共用经过版本和摘要核验的语言表编解码器，
始终读取所选端的当前资源；保留键、顺序和运行时参数，不能直接套用另一端旧表。
本地官方繁体补译按原英文文本 SHA-256 绑定，仅填补尚未翻译的文本。
只有用户明确选择目标并确认后才执行安装/还原；原引擎保留备份及回滚。

独立应用标识避免覆盖原 A2Tools 设置，不迁移旧工具设置。启动采集需
本地确认，取消不抓包。保留上游先检查网卡 TCP 流量再识别战斗通道的
自动检测方式，这比 Python 分支的精确 PID 范围更宽，确认框明确告知。
关闭原项目更新入口，避免把整合版更新回上游版本；禁用账号/上传命令
及自动上传、Discord 活动，保留本地统计和历史。
Npcap 仍由用户按官方许可安装，不捆绑驱动或安装器。
支持 Npcap 标准安装目录，无需启用 WinPcap 兼容模式；仅从 Windows
系统目录加载并核实 Npcap 版本，不从当前工作目录加载同名 DLL。

统计设置提供“停止统计并返回首页”，停止当前采集后保存本地战斗记录、
关闭统计相关窗口，再显示功能选择页。每次启动使用独立停止标记，
旧线程不会被下一次启动重新激活。统计窗口不包含汉化入口、上游账号、
联系方式、收款按钮或日志上传入口；许可证及来源署名保留。

Windows CI 见 `.github/workflows/desktop.yml`，检查启动页测试、Rust 测试
及完整桌面构建；不安装驱动、不启动抓包、不发布汉化引擎或游戏资源。

开发构建：`npm ci`，`npm run build`，`npm run tauri build -- --no-bundle`。
也可在根目录运行 `./build-desktop.ps1`；可选
`-LocalizationEnginePath '完整路径/Aion2-Steam-CN-v2.4.0.exe'`
会复用已有摘要校验及桥接编译流程，只加入本地测试组件。
另外可提供 `-LocalizationDecoderPath '完整路径/oo2core_9_win64.dll'`
及 `-LocalizationAdditionsPath '完整路径/localization-additions.json.gz'`。
解压依赖只接受核准摘要；补译压缩数据嵌入本地桥接组件，不提交游戏文本到 Git。
补译生成器为 `localization/build_official_additions.py`，输入必须是键集合一致的
本地英文与繁体表；`localization/locale_codec.py` 可离线解码用户已有资源。
维护工具依赖 blake3、cryptography、lz4 与 opencc-python-reimplemented，
这些 Python 依赖不用于玩家安装流程。
脚本不会启动应用、驱动或修改游戏。依赖和组件的发布审计仍需另行完成。
这是迁移中的开发分支，不能把构建通过等同于游戏实测通过。
Python/Tk 原实现保留在根目录，当前修改未替换其发布入口。
