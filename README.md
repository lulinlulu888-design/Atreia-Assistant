# 亚特雷亚助手 · Atreia Assistant

面向《永恒之塔2》（AION2 / AION 2）Steam / Global 玩家的社区助手，规划整合简体中文汉化、DPS 战斗统计、技能伤害分析与战斗复盘。非官方项目，与 NCSOFT、Steam 无隶属或背书关系。

## 当前状态：开发中

目前提供战斗事件统计核心和自动测试，**尚不能直接读取游戏、实时显示 DPS，也没有可供普通玩家下载的安装包**。汉化功能尚未迁入；现有用户继续使用原项目，不改变旧版自动更新入口。

- [现有永恒之塔2 Steam 汉化工具及正式下载](https://github.com/lulinlulu888-design/Aion2-Steam-CN)
- [新项目源码与开发进度](https://github.com/lulinlulu888-design/Atreia-Assistant)

## 战斗统计开发路线

1. 统一事件与统计口径：伤害、治疗、暴击命中率、玩家贡献及技能分解。
2. 核查被动抓包方案、协议兼容性、许可证和隐私边界，完成 TCP 重组与事件解析。
3. 使用用户明确同意采集的本地战斗样本验证当前 Steam 客户端；模拟测试不能代替游戏实测。
4. 开发中文统计窗口、战斗历史与导出，确认可靠后再发布安装包。

默认不上传战斗或玩家信息，不注入游戏、不修改内存、不发送游戏封包、不实现自动战斗。第三方工具不保证零账号风险；启用实时采集前应核对运营方规则。Npcap 不随安装包分发，需用户从官网自行安装。

## 开发与测试

基础统计与传输模块使用 Python 标准库（Python 3.10+）。已实现玩家/技能伤害与治疗汇总、暴击率、贡献比例，以及离线 classic PCAP 记录读取和单向 TCP 数据重组。游戏协议后端使用 Rust，依赖固定提交的 GPL 解析核心；离线封包到后端的应用级连接及实时界面尚待开发。

```sh
python -m unittest discover -s tests -v
```

`transport.py` 仅支持 classic PCAP（Ethernet/raw-IP），不支持 PCAPNG。记录截断会报错；TCP 重组按序号处理乱序、重传与回绕，遇到缺口等待，冲突或超过缓存上限报错。不进行实时抓包，不上传数据，也不把未知字节猜成伤害。

已接通离线 PCAP → Ethernet/VLAN/IPv4 → TCP 载荷 → 单向按序重组，并用合成封包验证重传不会重复输出。IPv6 和 IP 分片尚不支持，会明确报错；没有把这一测试称作 AION2 实战兼容性验证。TCP 流的连接生命周期管理仍待开发。

### Rust 协议后端

```sh
cargo test --manifest-path backend/Cargo.toml
cargo run --manifest-path backend/Cargo.toml -- --client steam
# PURPLE 入口：将 steam 改为 purple
```

标准输入为逐行 JSON：`{"flow":"local-flow-1","timestamp_ms":1000,"payload_hex":"…"}`。载荷必须是已完成 TCP 重组的有序游戏字节流，不是整个网卡封包。输出为本地 JSON 快照，包含目标、玩家、技能伤害与治疗；不联网上传，不注入游戏。无可识别事件时输出 `no_combat_detected`，不能当作真实零伤害或兼容性已确认。`compatibility` 当前始终为 `unverified`。

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
