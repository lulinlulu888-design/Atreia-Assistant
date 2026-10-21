# 2.0.58 构建与核验

基于 2.0.57。先按 BUILD-2.0.57.md 重建 Steam 与既有 PURPLE 双端基线，再运行 `localization/build_purple_20261022.py` 追加当前 PURPLE 变体。

原始引擎、解压组件、依赖源代码及许可证沿用固定摘要的 2.0.51 构建材料。版本 2.0.58 的 localization-sources.zip 包含 2.0.57 的六个来源文件，以及 `purple-20261022-en-US.json`、`purple-20261022-zh-TW.json`；完整游戏文本只随已获授权的构建材料提供，不提交 Git。

来源附件 SHA-256：`d8c81e9c408bcb9725b2bc5c731cf753afef25677a93143ec275bdfc9a6883e6`。

```powershell
$i = 'release-stage/materials/localization-inputs'
# First reproduce BUILD-2.0.57.md into $i/steam-26077854.json.gz.
python localization/build_purple_20261022.py `
  "$i/dual-sources/purple-20261022-en-US.json" `
  "$i/dual-sources/purple-20261022-zh-TW.json" `
  "$i/dual-sources/purple-en-US.json" "$i/steam-26077854.json.gz" "$i/purple-20261022"
./prepare-localization.ps1 -Engine release-stage/materials/component/Aion2-Steam-CN-v2.4.0.exe `
  -DecoderPath release-stage/materials/component/dependencies/oo2core_9_win64.dll `
  -AdditionsPath "$i/purple-20261022/additions.json.gz" -Destination release-stage/component
```

当前 PURPLE 验证详情及原始 PAK、独立解码产物摘要见 `releases/PURPLE-20261022.md`。Steam 产物仍为 `6a7a8cd4a68a3ef83a6451c8963a07bbedb11b31dcae38bc13b3746e7dc1f0a7`。新桥接组件补译内容与本机隔离测试相同，C# 编译器生成的二进制摘要可能不同。

上游选择性移植清单见 `desktop/ATREIA-FORK.md`，雷达技术与未验收范围见 `desktop/RADAR.md`。真实游戏定位、全部剧情显示以及覆盖升级体验未完成验证。发布包含实验功能，不将自动化测试等同于游戏内验证。
