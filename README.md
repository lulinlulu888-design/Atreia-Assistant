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

当前核心仅使用 Python 标准库（Python 3.10+）。已实现玩家/技能伤害与治疗汇总、暴击率、贡献比例，以及离线 classic PCAP 记录读取和单向 TCP 数据重组；封包读取与统计模块尚未通过游戏协议解析器连接。

```sh
python -m unittest discover -s tests -v
```

`transport.py` 仅支持 classic PCAP（Ethernet/raw-IP），不支持 PCAPNG。记录截断会报错；TCP 重组按序号处理乱序、重传与回绕，遇到缺口等待，冲突或超过缓存上限报错。不进行实时抓包，不上传数据，也不把未知字节猜成伤害。

统计核心接受标准化事件，不接受原始游戏封包。时间单位为毫秒，战斗时长由显式开始/结束边界决定，DPS/HPS 使用整场时长；零时长时返回 0，不制造瞬时 DPS。暴击率以伤害命中次数计，不能当作施法次数。

## 同类项目研究

- [A2Tools DPS Meter](https://github.com/taengu/A2Tools-DPS-Meter)：Rust/Tauri、Npcap、实时 DPS 与技能分析；GPL-3.0。
- [RATmeter](https://github.com/Kuroukihime/AIon2-Dps-Meter)：C# 战斗统计与历史；GPL-3.0。
- [Npcap 分发许可说明](https://npcap.com/oem/redist)：免费版通常不允许随产品分发。

这些是调研参考，不是本项目依赖或合作方。目前没有复制其源码。复用之前必须核对许可并保留相应署名与义务。协议变化、漏包和玩家身份映射都可能影响统计准确性，不宣传“100%准确”或“绝不封号”。
