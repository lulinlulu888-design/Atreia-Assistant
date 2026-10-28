# 2.0.63 构建与核验

在 2.0.62 的可复现基线及 Hidden Cube 源文绑定纠错后，执行 `localization/build_clients_20261028.py`，再针对当前两端执行 `unify_hidden_cube.py`。前者锁定完整输入摘要与基线解压摘要，拒绝未知版本、冲突、参数差异和未审查文本；后者新增统一一条“隐藏宝箱”变体。真实游戏目录只读。

来源归档 `Atreia-Assistant_2.0.63_localization-sources.zip` SHA-256：`6956c0f51c7da1657352adf091c1c96d1b8eb91bff6faaf4c616b87c6c395a10`。包含前版八个来源文件、新版两个英文表、PURPLE 官方繁体表以及前版 Steam 独立解码表，不包含密钥、数据库连接信息或用户数据。

当前输入 SHA-256：

- Steam：`37fb7ea8bc04abf35a671101a431a196192706c9aa6f331049f71acf086f73c5`。
- PURPLE 英文：`017e180fb47b3d51c3de7510781887fe5205c0f0dbc23c228aaf1ce492455a02`。
- PURPLE 繁体：`0829937316c9636617059c28b73ada2df536fa24a2a7a8f537101b95b3b08ccd`。

本地验收：

- Steam Build 26262663：153,297 键、额外补译 4,170 条；PURPLE TW 127：160,286 键、额外补译 24,606 条。生产桥接器只读检测与编码回读、缺译检查通过。
- 两端真实 PAK 的隔离副本通过生产桥接器安装、重复安装、逐字节还原，原始游戏 PAK 不变。
- 独立 Python 解码隔离产物，全部键顺序一致，参数差异 0。Steam 152,916 条原文未变记录与本机之前安装的已发布译文一致。
- Steam 产物 SHA-256：`8a98b714abd22115bdabbc84325cbafcbbc599ce06eedfbdf035abeab2fa1891`。
- PURPLE 产物 SHA-256：`93024e1fb9761df9167db30f4ff74f28e0885819c3a62639eef69498f19ebce5`。
- Python 199 项（8 跳过），前端 106 项，C# 安全检查 58 项通过。Rust 174 项通过、5 项忽略。
- 本地 MSI 构建及中文桌面快捷方式、必选安装功能、卸载清理检查通过。MSI SHA-256：`bfd11cb5a448f6eabe0a819b9ab008d62b4c1e4cd8c714dd4d7b037efa976bfa`；公开 CI 安装包需按其自身摘要单独核对。

正式 CI 重建及公开下载以对应 Actions 运行和 Release 附件为准，本记录中的本地 MSI 不冒充 CI 产物。隔离验收不等同于完整游戏内剧情、界面或宝箱雷达实战验收。
