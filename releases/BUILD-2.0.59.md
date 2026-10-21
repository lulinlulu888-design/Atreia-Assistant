# 2.0.59 构建与核验

汉化来源与构建步骤沿用 `BUILD-2.0.58.md`，固定引擎及组件摘要不变。来源附件沿用同一归档字节，重命名为 `Atreia-Assistant_2.0.59_localization-sources.zip`，SHA-256 为 `d8c81e9c408bcb9725b2bc5c731cf753afef25677a93143ec275bdfc9a6883e6`。

本版在桥接器中加入 `LegacyCompletionDialog.cs`，仅在安装线程确认成功通知全文、安装状态和实际 DAT 摘要一致后关闭引擎完成通知。原始引擎未改动。

除自动化安全测试外，使用正式组件（非 DEBUG testMode）在两个当前客户端原始 PAK 的临时副本上运行：

```powershell
./test-localization-completion.ps1 -Component build/completion-fix/final-component -SourcePak <original-steam-pak> -Client steam -ExpectedSupplemented 3811
./test-localization-completion.ps1 -Component build/completion-fix/final-component -SourcePak <original-purple-pak> -Client purple -ExpectedSupplemented 21816
```

两端均通过安装、重复安装及还原；原始来源文件摘要不变。独立解码产物：

- Steam：153185 键，SHA-256 `6a7a8cd4a68a3ef83a6451c8963a07bbedb11b31dcae38bc13b3746e7dc1f0a7`。
- PURPLE：157521 键，SHA-256 `b04eaacd02c6e0cd0160722840f4d034f71b9f15caeafc0e79f14b42f46ec5c2`。

两端键顺序和格式参数均核对通过。PURPLE 原始 PAK 及变体明细见 `PURPLE-20261022.md`。本轮不对正在使用的真实游戏目录进行安装或还原，不声称已完成全部游戏内界面、剧情、雷达定位或 MSI 覆盖升级的验收。
