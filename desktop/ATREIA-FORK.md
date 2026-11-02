# 亚特雷亚助手桌面整合说明

当前桌面发布入口为本目录的 Rust / Tauri 程序，适用版本 2.0.64。玩家下载与设置见[项目首页](../README.md)，构建命令见[开发指南](../documentation/DEVELOPMENT.md)。

## 上游来源

本目录基于 [taengu/A2Tools-DPS-Meter](https://github.com/taengu/A2Tools-DPS-Meter) 的固定提交 `70aade3fef1ef8b15fe5ce3d27cfdbfc5f854b98`，保留上游 LICENSE、源码署名和原 README，修改版继续使用 GPL-3.0。它不是独立原创的统计软件。

2026-10-22 对照上游 v2.0.74（899375ba）定向移植以下修复，不代表完整合并该版本：

| 提交 | 原作者 | 内容 |
| --- | --- | --- |
| 722dd6b8 | Seralth | 附加伤害记录尾部解析 |
| 8f2d81a3 | taengu | 小额暴击使用伤害值而非攻击者系数 |
| 7a0ad04c | taengu | 护盾吸收不计为额外伤害，正确处理受护盾影响的 DoT |
| 6f806dc6 / 3631610 | Nullceptions | 根据原生鼠标位置清理过期悬停提示 |

回归测试重放相关记录。原生指针轮询仅在显示提示时运行，不上传指针数据。自动化检查不等同于所有游戏场景的实测。

## 独立窗口与采集

- 启动显示 680 × 500 逻辑像素主界面，打开功能后继续保留。
- 汉化、DPS 和雷达分别打开独立窗口；关闭主界面留在托盘，已开启工具继续工作。
- DPS 开启前显示采集确认；雷达打开窗口时不采集，点击浮窗开启按钮直接启动。
- DPS 与雷达共享 Rust / Npcap 采集管线，开关独立；关闭一项不会停止另一项仍需的采集。
- 仅显示主页或汉化窗口不启动采集。窗口可同时存在，不代表可以在游戏运行或采集事务冲突时改写语言资源。
- 统计保留本地记录与历史，不启用账号、战斗上传、Discord 活动或上游软件更新入口。

采集先只读检查网卡 TCP 流量再识别游戏连接，不是历史 Python 原型的精确 PID 限定采集。Npcap 由用户自行安装，本项目不捆绑驱动；支持其标准安装目录，不要求 WinPcap 兼容模式。

窗口尺寸、材质及界面验证入口见[UI.md](UI.md)，雷达限制见[RADAR.md](RADAR.md)。

## 分客户端汉化

Steam 使用独立的日文入口冻结组件；PURPLE 使用原英文引擎及专用桥接器。两端分别固定组件摘要、校验协议并拒绝跨端操作。

Git 源码不附带原引擎、解压库或完整游戏语言文本。获授权的发布材料、来源记录、对应源码及许可放在正式 Release 中；不能仅因调用接口就将这些资源视为 GPL。详见[第三方来源](../THIRD_PARTY_NOTICES.md)。

源码入口：

- [atreia_localization.rs](src-tauri/src/atreia_localization.rs)：客户端路由、独立窗口、事务与组件检查。
- [atreia_radar.rs](src-tauri/src/atreia_radar.rs)：雷达窗口、设置和共享采集生命周期。
- [atreia_update.rs](src-tauri/src/atreia_update.rs)：本项目更新清单、下载和包校验。
- [汉化维护说明](../localization/README.md)：译文来源、组件布局与重建流程。

## 开发和发布

[desktop.yml](../.github/workflows/desktop.yml) 不含游戏资源，可检查前端、Rust、C# 和桌面构建；[release.yml](../.github/workflows/release.yml) 另行准备完整双端组件并生成正式 MSI。两种构建的前提不同，详见[开发指南](../documentation/DEVELOPMENT.md)。

应用基线、当前游戏版本和实机结果以[2.0.64 构建记录](../releases/BUILD-2.0.64.md)为准。根目录的 Python/Tk 代码保留作历史研究，不再是当前 Windows 正式安装包入口。
