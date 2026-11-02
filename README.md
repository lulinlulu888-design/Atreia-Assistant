# 亚特雷亚助手｜AION2 汉化、DPS 战斗统计与宝箱雷达

亚特雷亚助手（Atreia Assistant）是面向《永恒之塔2》（AION2）玩家的免费开源 Windows 社区工具。简体中文汉化沿用国服《永恒之塔》的名称与术语；战斗统计和实验性隐藏宝箱雷达使用独立浮窗。

**[官网下载](https://a2go.cc/)** · **[最新正式版 2.0.64](https://github.com/lulinlulu888-design/Atreia-Assistant/releases/tag/v2.0.64)** · **[文档导航](documentation/README.md)** · **[问题反馈](https://github.com/lulinlulu888-design/Atreia-Assistant/issues)**

## 安装与开始使用

1. 从官网下载 Windows x64 整合安装包 `Atreia-Assistant_<version>_x64.msi`，无需下载 Source code。
2. 安装后通过中文桌面快捷方式 **亚特雷亚助手** 启动。
3. 在主界面打开“游戏汉化”“战斗统计”或“隐藏宝箱雷达”。三个窗口可以分别或同时打开；关闭主窗口后保留在系统托盘。

升级助手本身不会修改游戏资源。更新汉化时，请完全退出游戏，在“游戏汉化”窗口选择客户端，点击“检测”，通过后点击“安装 / 更新汉化”。备份与还原由对应客户端组件处理。

## 游戏汉化：两端语言设置不同

| 客户端 | 安装汉化后的文字语言 | 2.0.64 验证基线 |
| --- | --- | --- |
| Steam / Global | **日本語** | Steam Build 26262663，153,297 条中文 UI 文本 |
| PURPLE 台服 | **English** | PURPLE TW 127，160,286 条语言记录 |

Steam 在 2.0.64 改用日文入口，修复界面显示问号的问题；PURPLE 沿用原英文入口，无需日文资源。语音语言可以保持自己的设置。

Steam 中文显示、切到 English 再切回日本語已由用户实机确认。PURPLE 本次完成原方案的真实资源只读检查和编码回读检查；游戏内所有界面尚未逐一验收。后续游戏更新需重新检测，不能将上述版本的验证结果直接用于新资源。

- [安装与还原指南](docs/guides/localization.html)
- [汉化方案与构建入口](localization/README.md)
- [2.0.64 更新说明](releases/2.0.64.md) · [验证记录](localization/JAPANESE_ENTRY_STATUS.md)

## 战斗统计与隐藏宝箱雷达

**战斗统计**显示 DPS、伤害、治疗、玩家贡献和技能明细，支持回看本机战斗历史。首次使用采集功能需安装 [Npcap](https://npcap.com/#download)；本项目支持标准安装目录，无需 SDK 或 WinPcap 兼容模式。开启统计时确认采集提示，主界面和汉化窗口继续保留。

**隐藏宝箱雷达**默认是 210 × 240 逻辑像素的紧凑浮窗。打开窗口不会开始采集，点击浮窗开启按钮直接启动；可与 DPS 同时运行。雷达为实验功能：角色定位已在本地观察成功，可见宝箱标记与真实距离尚未完成全面现场验收。

- [DPS 使用指南](docs/guides/combat.html)
- [雷达行为及验证边界](desktop/RADAR.md)
- [桌面窗口与界面说明](desktop/UI.md)

## 软件更新

首页自动检查本项目正式版本，也可手动“检查更新”。下载前需要确认，安装包通过大小与 SHA-256 校验后交给 Windows 安装器。更新前请停止采集并结束汉化事务；软件升级后需要另外重新检测并安装游戏汉化。

官网通过 S3 提供安装包，保留 GitHub 备用下载。官网显示的是**下载按钮点击次数**，不代表下载完成次数或独立用户数。详见 [自动更新机制](desktop/UPDATES.md) 和 [官网部署说明](website/README.md)。

## 开发、发布与项目来源

- [开发环境、目录与常用检查](documentation/DEVELOPMENT.md)
- [正式版本发布和官网同步](documentation/RELEASING.md)
- [版本记录与构建材料索引](releases/README.md)
- [桌面整合及上游来源](desktop/ATREIA-FORK.md)
- [第三方来源与许可](THIRD_PARTY_NOTICES.md) · [GPL-3.0 许可证](LICENSE)

桌面程序位于 `desktop/`，基于 [A2Tools DPS Meter](https://github.com/taengu/A2Tools-DPS-Meter) 修改，保留原作者署名与许可。统计在本机处理，不自动上传战斗数据，不注入游戏或修改游戏内存。汉化修改本地语言资源，并提供备份与还原。

本工具与 NCSOFT、Steam 无隶属或背书关系。早期 Python/Tk 原型及旧流程保留在[历史文档](documentation/README.md#历史资料)，不作为当前玩家操作说明。
