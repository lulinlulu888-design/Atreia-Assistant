# 第三方许可与来源

亚特雷亚助手按根目录 LICENSE 中的 GPL v3 发布。当前仅作开发测试，未发布安装包。

## A2Tools DPS Meter 解析核心

- 上游：https://github.com/taengu/A2Tools-DPS-Meter
- 固定源码提交：`70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98`
- 上游许可：GNU GPL v3，保留上游版权与署名；解析器源码注释记载由 Kotlin StreamProcessor 移植。
- 用途：Rust 后端依赖其协议拆帧、压缩包解析、伤害/治疗解析与身份映射。没有把上游完整软件换名当作原创。
- `backend/resources/dot_skill_ids.json` 来自上述固定提交的 `src/data/dot_skill_ids.json`，未修改，遵循相同许可。它是上游筛选的持续伤害技能列表，不代表当前 Steam/PURPLE 技能数据已全部验证。
- 不启用上游 `desktop` 功能；本项目后端不引入其账号登录、战斗上传、更新或 Discord 功能。
- 构建通过 Cargo 拉取固定提交，发布二进制之前必须同时提供本项目及对应依赖的可构建源码与许可；仅放安装包不满足发布要求。

Python 传输和统计模块为本项目新增代码。上游核心的测试结果不代表新项目或 Steam/PURPLE 实战已经验证。

Npcap 不打包分发；用户需按其官网许可自行安装。Rust 传递依赖的许可应在二进制发布前完整盘点并包含所需通知。当前没有进行二进制发布。

## 本地开发版打包工具

### WinDivert 采集组件

新版 Windows 开发包包含官方 [WinDivert 2.2.2-A](https://github.com/basil00/WinDivert/releases/tag/v2.2.2) 的原始 x64 DLL 和已签名驱动，选择 LGPL v3 许可，保留随包完整 LICENSE、README、VERSION。官方源码见 [v2.2.2 源码](https://github.com/basil00/WinDivert/tree/v2.2.2)。未修改库或驱动，也未将其声称为本项目原创；本项目只读适配器为新增代码。打包归档摘要来自本地对官方资产的核查，不能称为上游发布的摘要。公开二进制发布前仍需提供对应组件源码、构建资料及完整运行时通知，当前未完成发布审计。

组件仅在用户确认采集后调用 WinDivertOpen；这可能加载系统驱动，需管理员权限。只使用 SNIFF 和 RECV_ONLY，不阻断、修改或注入游戏封包；不代表第三方游戏规则允许使用，也不保证驱动与所有安全软件兼容。

`build-windows.ps1` 使用 `requirements-build.txt` 中固定版本的 PyInstaller 及构建依赖；只生成本地测试包，不发布二进制。PyInstaller 的许可与打包例外见 [官方许可说明](https://pyinstaller.org/en/stable/license.html)。该例外不替代本项目、Rust 依赖及随包 Python/Tcl/Tk 等运行时各自的许可要求。对外提供下载前仍需完成对应源码、运行时许可与通知文件审计；当前不声称已完成这一发布审计。

## Rust 依赖清单与许可文本收集

构建并缓存 Windows 后端依赖后，可运行 `python audit_dependencies.py --output dist/license-inventory`（输出目录必须尚不存在）。脚本使用锁定依赖和 Windows 目标元数据，记录组件名称、版本、许可表达式和来源类别，收集可找到的许可/通知文本；不会公开本机缓存目录或账号路径。上游解析核心的仓库级 GPL 依据仅适用于上述固定来源和提交，不会仅凭同名包套用许可。

当前锁定配置在本地生成了 47 个组件的清单。报告始终标记 `release_audit_complete: false`：它不是完整合规审计，也没有包含可重建的全部对应源码、Python/Tcl/Tk 运行时审计或实际客户端验证。CI 可保存清单和许可文本用于检查，不发布二进制。
