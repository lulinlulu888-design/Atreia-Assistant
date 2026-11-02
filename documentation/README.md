# 项目文档导航

适用版本：**2.0.64**；整理日期：**2026-11-02**。

## 玩家使用

| 文档 | 内容 |
| --- | --- |
| [项目首页](../README.md) | 下载、三个功能入口、客户端语言设置 |
| [汉化安装与还原](../docs/guides/localization.html) | Steam 选择日本語，PURPLE 选择 English |
| [战斗统计指南](../docs/guides/combat.html) | Npcap、统计浮窗与战斗记录 |
| [隐藏宝箱雷达](../desktop/RADAR.md) | 开关、定位、显示方式与实验功能限制 |
| [软件自动更新](../desktop/UPDATES.md) | 版本检查、包校验与快捷方式 |
| [2.0.64 更新说明](../releases/2.0.64.md) | 本次改动和升级步骤 |

## 开发与维护

| 文档 | 内容 |
| --- | --- |
| [开发指南](DEVELOPMENT.md) | 目录、构建前提、检查命令 |
| [发布与官网同步](RELEASING.md) | 来源准备、正式包、S3、版本清单和部署 |
| [汉化方案](../localization/README.md) | 两端独立组件、翻译规则和构建入口 |
| [汉化验证状态](../localization/JAPANESE_ENTRY_STATUS.md) | 实机结果、资源检查与未验证边界 |
| [桌面整合说明](../desktop/ATREIA-FORK.md) | 上游来源、独立窗口与采集生命周期 |
| [桌面界面说明](../desktop/UI.md) | 窗口尺寸、材质和预览方法 |
| [官网运维](../website/README.md) | Nuxt、共用服务器、MongoDB 点击统计和 S3 |
| [第三方来源与许可](../THIRD_PARTY_NOTICES.md) | 署名、单独授权组件与发行材料 |
| [版本与构建索引](../releases/README.md) | 各版更新说明和可追溯构建记录 |

## 历史资料

历史资料保留当时的术语、路径、数字和验收结论，不能当作当前安装指引。

- [Python/Tk 原型开发记录](../LEGACY_DEVELOPMENT.md)
- [旧英文入口汉化记录](archive/localization-english-entry.md)
- [2.0.52 界面与验证记录](archive/ui-2.0.52.md)
- [2.0.55 及以前自动更新验证记录](archive/updater-through-2.0.55.md)
- [2026-10-12 国服术语审计](../localization/MAINLAND_AUDIT.md)：保留证据和纠错依据，其中数量属于历史快照。
- `desktop/README*.md` 为保留署名的 A2Tools 上游文档，顶部标明归属；本项目安装和构建以这里的当前文档为准。

## 文档维护规则

1. 玩家说明放在根 README 和安装指南；实现细节放在对应组件说明。
2. 发布版本、游戏构建号、记录数、日期必须注明适用范围；不使用无日期的“当前全部通过”代替证据。
3. 区分自动化检查、真实资源只读检查、隔离安装还原和游戏内显示验收。
4. Steam 与 PURPLE 的语言入口、组件和备份分别说明；不恢复“两端统一 English”的旧指引。
5. 先核验正式下载，再更新官网清单；详见[发布流程](RELEASING.md)。
6. 版本记录保持历史事实；过时的长篇操作说明归档并保留入口，不直接混进当前 README。
