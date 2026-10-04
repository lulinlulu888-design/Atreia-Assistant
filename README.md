# 亚特雷亚助手 · Atreia Assistant

面向《永恒之塔2》（AION2 / AION 2）Steam / Global 和 PURPLE 玩家的开源社区助手，规划整合简体中文汉化、DPS 战斗统计、技能伤害分析与战斗复盘。非官方项目，与 NCSOFT、Steam 无隶属或背书关系。

## 当前状态：开发中

目前提供中文开发版窗口、离线封包解析、手动开启的 Npcap 实时采集入口和自动测试。**两端当前游戏版本尚未实测，没有可供普通玩家下载的安装包**；采集入口通过的是模拟接口测试，不代表真实驱动或游戏兼容性已验证。汉化功能尚未迁入；现有用户继续使用原项目，不改变旧版自动更新入口。

- [现有永恒之塔2 Steam 汉化工具及正式下载](https://github.com/lulinlulu888-design/Aion2-Steam-CN)
- [新项目源码与开发进度](https://github.com/lulinlulu888-design/Atreia-Assistant)

## 战斗统计开发路线

1. 统一事件与统计口径：伤害、治疗、暴击命中率、玩家贡献及技能分解。
2. 核查被动抓包方案、协议兼容性、许可证和隐私边界，完成 TCP 重组与事件解析。
3. 使用用户明确同意采集的本地战斗样本分别验证当前 Steam 和 PURPLE 客户端；模拟测试不能代替游戏实测。
4. 完善中文统计窗口、战斗历史与导出，确认可靠后再发布安装包。

默认不上传战斗或玩家信息，不注入游戏、不修改内存、不发送游戏封包、不实现自动战斗。第三方工具不保证零账号风险；启用实时采集前应核对运营方规则。Npcap 不随安装包分发，需用户从官网自行安装。

## 开发与测试

基础统计、传输模块与 Tkinter 窗口使用 Python 标准库（Python 3.10+，窗口需要 Tk）。已实现玩家/技能伤害与治疗汇总、暴击率、贡献比例，以及离线 classic PCAP 记录读取和单向 TCP 数据重组。游戏协议后端使用 Rust，依赖固定提交的 GPL 解析核心；窗口通过本地子进程连接后端，不联网上传。

```sh
python -m unittest discover -s tests -v
```

`transport.py` 仅支持 classic PCAP（Ethernet/raw-IP），不支持 PCAPNG。记录截断会报错；TCP 重组按序号处理乱序、重传与回绕，遇到缺口等待，冲突或超过缓存上限报错。传输模块自身不进行实时抓包，不上传数据，也不把未知字节猜成伤害。

已接通离线 PCAP → Ethernet/VLAN/IPv4 → TCP 载荷 → 单向按序重组 → Rust 后端 → 中文窗口，并用合成封包验证两种客户端入口与重传去重。IPv6 和 IP 分片尚不支持，会明确报错；没有把这一测试称作 AION2 实战兼容性验证。重连、FIN/RST 会释放解析流，同时保留战斗总量；最多保留 32 条活跃流。保留最近 128 条已关闭连接标记防止延迟重传重复计数，同一连接地址再次使用需观察到新 SYN；漏掉连接建立或关闭仍可能影响统计，不是生产级完整 TCP 实现。

### 启动中文开发版窗口（Windows 64 位）

```sh
cargo build --release --locked --manifest-path backend/Cargo.toml
python app.py
# 指定其他位置的本地后端：python app.py --backend "路径/atreia-combat-backend.exe"
```

选择 Steam / Global 或 PURPLE，填写实际游戏 TCP 端口，可打开已授权采集的 `.pcap` 文件查看候选伤害、技能分解与治疗记录。未知名称暂显示数字 ID，治疗总量不能直接视为有效治疗量。

选中玩家后，技能分解会在快照刷新时保持选择并更新数值；玩家昵称变化不会切换到其他目标或角色。界面会明确提示中途采集、TCP 缺口、协议待解析与关闭时丢弃的残帧，避免把不完整数据当作完整战斗成绩。

实时入口需要用户从 [Npcap 官网](https://npcap.com/#download) 自行安装驱动，再手动刷新并选择网卡、填写游戏服务器 IPv4 和端口、确认采集范围后点击开始。程序不自动安装或提权，不默认启动采集，不发送封包；过滤器仅选定 IP/端口，关闭混杂模式。当前不支持 loopback、IPv6 或其他链路类型，VPN/加速器环境需另行验证。

Windows 下可点击“检测游戏连接”：只读取 `AION2.exe` 的进程路径和已建立 TCP 连接，不读取进程内存、启动参数、账号或封包内容，也不会启动采集。候选需手动选择后才填入服务器 IP/端口；可能包含非战斗服务连接，不能以检测成功证明协议兼容。Steam 安装路径仅作为提示，其他路径不会自动判定为 PURPLE。游戏未运行、路径读取受限、IPv6 或加速器代理环境可能没有候选，仍可手动填写；程序不会为检测自动提权。

停止按钮终止本地分析。报告仅在用户选择导出时保存，可能包含玩家昵称；中途开始、缺包、提前停止或错误后的报告可能不完整。未识别到事件不代表没有战斗。尚未完成真实 Npcap 驱动测试、Steam/PURPLE 游戏实测或窗口视觉验收。

实时分析时可点击“开始新一场”，确认后清空本场伤害与治疗，保留角色身份和 TCP 连接。上一场候选统计保留在内存历史中（最近 20 场），随“导出本地报告”一起保存；退出后内存历史消失，超过 20 场的最早记录会移出历史，需提前导出。分场是手动边界，不是已验证的 Boss 开战/结束识别；跨边界的缺包、乱序及残帧可能影响场次归属。清零时丢弃待解析残帧并显示诊断，旧快照不能恢复上一场数值。

### 本地开发版打包

Windows 64 位上安装 Python（含 Tk）和 Rust 后，在 PowerShell 运行：

```powershell
./build-windows.ps1
# 已有后端时可跳过重复编译：
./build-windows.ps1 -SkipBackendBuild -BackendPath '完整路径/atreia-combat-backend.exe'
```

脚本在项目专用 `.venv-build` 安装固定版本的打包依赖，构建独立文件夹版 `Atreia-Assistant-dev.exe`，输出到全新的 `dist/dev-时间-随机标识`，不会清理已有文件。必须保留整个应用文件夹及 `_internal`，不能只复制 EXE。构建后的应用在目标机无需另装 Python/Rust；Npcap 仍需用户自行安装，不随包分发。

每次打包执行隐藏的合成封包自检，检查 Tk 窗口创建、随包后端定位、Steam/PURPLE 候选解析、重传去重和手动分场，并输出 `synthetic-self-test.json`。报告始终注明没有测试真实游戏、没有启动采集。CI 只保存自检报告，不上传二进制。打包成功不等于实战或窗口视觉验收通过；在兼容性验证及对应源码/依赖许可审计完成前，不发布或分发该开发测试包。

打包资源定位依据 [PyInstaller 官方运行时说明](https://pyinstaller.org/en/stable/runtime-information.html)，依赖版本记录在 `requirements-build.txt`；本地构建和自检已在 Python 3.14 的 Windows 环境执行。

### Rust 协议后端

```sh
cargo test --manifest-path backend/Cargo.toml
cargo run --manifest-path backend/Cargo.toml -- --client steam
# PURPLE 入口：将 steam 改为 purple
```

标准输入为逐行 JSON：`{"flow":"local-flow-1","timestamp_ms":1000,"payload_hex":"…"}`。载荷必须是已完成 TCP 重组的有序游戏字节流，不是整个网卡封包。输出为本地 JSON 快照，包含目标、玩家、技能伤害与治疗；不联网上传，不注入游戏。无可识别事件时输出 `no_combat_detected`，不能当作真实零伤害或兼容性已确认。`compatibility` 当前始终为 `unverified`。

连接关闭时发送同格式的空载荷并增加 `"close":true`，释放对应解析流而不清空战斗数据，也不延长战斗时长。快照的 `active_flows`、`pending_bytes` 和 `discarded_protocol_bytes` 分别表示活跃流数、待解析字节与关闭时丢弃的残帧字节；这些诊断不能代替完整性验证。

手动分场命令为 `{"flow":"session-control","timestamp_ms":0,"payload_hex":"","reset":true}`；不能同时含载荷或 `close`。回复包含新场快照及 `previous_encounter` 上一场快照，`encounter_id` 和 `revision` 用于防止异步刷新回退。清零不会放宽后续数据的时间顺序校验。

### 客户端验证矩阵

| 目标客户端 | 开发入口 | 当前版本实战验证 |
| --- | --- | --- |
| Steam / Global | `--client steam` | 未验证，需要真实战斗样本 |
| PURPLE | `--client purple` | 未验证，需要地区和版本信息及真实战斗样本 |

两个入口目前使用同一候选解析核心，不代表已经证明两个客户端协议相同。后续按客户端、地区、版本分别记录测试证据；不支持的加密或协议不会绕过，也不读取账号密码。

统计核心接受标准化事件，不接受原始游戏封包。时间单位为毫秒，战斗时长由显式开始/结束边界决定，DPS/HPS 使用整场时长；零时长时返回 0，不制造瞬时 DPS。暴击率以伤害命中次数计，不能当作施法次数。

## 同类项目研究

- [A2Tools DPS Meter](https://github.com/taengu/A2Tools-DPS-Meter)：Rust/Tauri、Npcap、实时 DPS 与技能分析；GPL-3.0。
- [RATmeter](https://github.com/Kuroukihime/AIon2-Dps-Meter)：C# 战斗统计与历史；GPL-3.0。
- [Npcap 分发许可说明](https://npcap.com/oem/redist)：免费版通常不允许随产品分发。

本项目按 GPL v3 开源。A2Tools 的解析核心已作为固定提交的依赖，持续伤害技能列表保留来源；RATmeter 仅为调研参考，没有使用其源码。双方均不是本项目合作方。详见 [第三方许可与来源](THIRD_PARTY_NOTICES.md) 和 [完整许可](LICENSE)。协议变化、漏包和玩家身份映射都可能影响统计准确性，不宣传“100%准确”或“绝不封号”。
