# 2.0.60 构建与核验

汉化内容和生产桥接器沿用 `BUILD-2.0.59.md`，全部来源、参数及 DAT 摘要不变。来源附件采用相同归档字节并重命名为 `Atreia-Assistant_2.0.60_localization-sources.zip`，SHA-256 为 `d8c81e9c408bcb9725b2bc5c731cf753afef25677a93143ec275bdfc9a6883e6`。

本版仅变更原生确认窗口的置顶与任务栏可见性，不改变同意、取消、调用窗口权限或采集启动逻辑。Node 测试覆盖窗口配置和交互，Rust 确认测试覆盖调用权限、取消、重复及过期回答。

以 GitHub Actions 固定 Windows 工具链重建并测试 MSI；真实游戏定位与升级安装体验仍未完成验收。
