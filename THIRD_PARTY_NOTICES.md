# 第三方许可与来源

## 可选的原汉化引擎

2026-10-12：项目维护者明确确认已取得原汉化引擎、游戏语言数据及 oo2core 解压库的
公开分发授权，并要求发布整合安装包。后续发行以该授权确认为前提；这些组件不因此
改为 GPL 许可。以下“仅本机测试、不上传”的描述记录此前状态，不再是维护者当前的
发布决定；此确认也不替代其他开源依赖的许可通知及对应源码要求。

整合发行调用原项目 `Aion2-Steam-CN` 的 v2.4.0 程序集，资产 SHA-256 为 `1d01a3ab4c9604296da6b2265fd0a5a1247d628d31fd4ab02eb8bac539340e58`。Git 仓库不提交该引擎二进制、解压库或完整游戏语言数据；获授权的组件随整合安装包分发。原项目、语言数据和嵌入组件不因接口调用而自动受本项目 GPL 许可覆盖。

亚特雷亚助手按根目录 LICENSE 中的 GPL v3 发布。整合发行对应源码见同名 Git 标签及 Release 的构建材料压缩包；后者提供原引擎源码、补译资源、构建说明和锁定 Rust 依赖的源代码包。汉化数据和解压组件沿用其单独授权。

官网使用的 Lucide 0.469.0 图标脚本与 ISC / Feather MIT 许可一并保存于 `docs/assets/`。
新羽翼“2”标志及原创场景图的生成说明见 `docs/assets/brand/README.md`。

## A2Tools DPS Meter 解析核心

新增 `desktop/` 目录直接保存以下固定提交的完整上游源码，并作启动页、汉化入口和本地化分支修改；上游 LICENSE 和原有作者署名保留。该整合分支不是本项目原创统计软件，继续按 GPL v3 提供对应源码。账号、上传、上游更新和 Discord 活动不作为整合版功能启用。

- 上游：https://github.com/taengu/A2Tools-DPS-Meter
- 固定源码提交：`70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98`
- 2026-10-22 定向移植上游 v2.0.74 相关修复：`722dd6b8`、`8f2d81a3`、`7a0ad04c`、`6f806dc6 / 3631610`，涵盖附加伤害、暴击、护盾与悬停提示；原作者 Seralth、taengu、Nullceptions 的 GPL-3.0 代码按原许可保留。详见 `desktop/ATREIA-FORK.md`，不代表完整合并上游全部功能。
- 上游许可：GNU GPL v3，保留上游版权与署名；解析器源码注释记载由 Kotlin StreamProcessor 移植。
- 用途：Rust 后端依赖其协议拆帧、压缩包解析、伤害/治疗解析与身份映射。没有把上游完整软件换名当作原创。
- `backend/resources/dot_skill_ids.json` 来自上述固定提交的 `src/data/dot_skill_ids.json`，未修改，遵循相同许可。它是上游筛选的持续伤害技能列表，不代表当前 Steam/PURPLE 技能数据已全部验证。
- 不启用上游 `desktop` 功能；本项目后端不引入其账号登录、战斗上传、更新或 Discord 功能。
- 构建通过 Cargo 拉取固定提交，发布二进制之前必须同时提供本项目及对应依赖的可构建源码与许可；仅放安装包不满足发布要求。

Python 传输和统计模块为本项目新增代码。上游核心的测试结果不代表新项目或 Steam/PURPLE 实战已经验证。

Npcap 不打包分发；用户需按其官网许可自行安装。桌面 MSI 的 `vendor/notices` 包含锁定 Rust 依赖及前端运行时的许可文本、来源与清单。

## 本地开发版打包工具

### WinDivert 采集组件

历史开发包曾包含官方 [WinDivert 2.2.2-A](https://github.com/basil00/WinDivert/releases/tag/v2.2.2) 的原始 x64 DLL 和已签名驱动，选择 LGPL v3 许可。当前已切回 Npcap，构建脚本不再加入 WinDivert 组件。历史包中的 LICENSE、README、VERSION 和许可要求仍有效；官方源码见 [v2.2.2 源码](https://github.com/basil00/WinDivert/tree/v2.2.2)。研究适配器源码保留，不自动加载。

组件仅在用户确认采集后调用 WinDivertOpen；这可能加载系统驱动，需管理员权限。只使用 SNIFF 和 RECV_ONLY，不阻断、修改或注入游戏封包；不代表第三方游戏规则允许使用，也不保证驱动与所有安全软件兼容。

`build-windows.ps1` 使用 `requirements-build.txt` 中固定版本的 PyInstaller 及构建依赖；只生成本地测试包，不发布二进制。PyInstaller 的许可与打包例外见 [官方许可说明](https://pyinstaller.org/en/stable/license.html)。该例外不替代本项目、Rust 依赖及随包 Python/Tcl/Tk 等运行时各自的许可要求。对外提供下载前仍需完成对应源码、运行时许可与通知文件审计；当前不声称已完成这一发布审计。

## Rust 依赖清单与许可文本收集

构建并缓存 Windows 后端依赖后，可运行 `python audit_dependencies.py --output dist/license-inventory`（输出目录必须尚不存在）。脚本使用锁定依赖和 Windows 目标元数据，记录组件名称、版本、许可表达式和来源类别，收集可找到的许可/通知文本；不会公开本机缓存目录或账号路径。上游解析核心的仓库级 GPL 依据仅适用于上述固定来源和提交，不会仅凭同名包套用许可。

当前锁定配置在本地生成了 47 个组件的清单。报告始终标记 `release_audit_complete: false`：它不是完整合规审计，也没有包含可重建的全部对应源码、Python/Tcl/Tk 运行时审计或实际客户端验证。CI 可保存清单和许可文本用于检查，不发布二进制。

Windows 打包时自动执行该收集步骤，将清单和许可文本包含在应用的 `_internal/licenses/rust` 中。缺少许可依据或未收集到文本时停止构建；这项检查不代替完整对应源码、运行时资料或发布许可审查。
