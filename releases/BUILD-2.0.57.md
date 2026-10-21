# 2.0.57 构建与核验

应用源码基于 2.0.56。原始引擎、依赖源代码及许可证沿用固定摘要的 2.0.51 构建材料；先按 BUILD-2.0.55.md 重建双端补译，再追加本版 Steam 修订。

本版 localization-sources.zip 包含上一版的四个来源文件，以及 `steam-26077854.json`、`steam-26077854-report.json`。客户端游戏数据留在发行构建材料中，不提交 Git。脚本锁定输入摘要，拒绝未知或混合快照。

来源附件 SHA-256：`9b3d5ca48e69fa674e756e8bc82cc3720c79669a9090ef8b2e63c50904246f99`。

```powershell
$i = 'release-stage/materials/localization-inputs'
python localization/build_dual_release.py "$i/corrections.json.gz" `
  "$i/dual-sources/steam-en-US.json" "$i/dual-sources/purple-en-US.json" `
  "$i/dual-sources/purple-zh-TW.json" "$i/dual" `
  --steam-baseline "$i/current-steam.json" `
  --reviewed-steam "$i/dual-sources/steam-reviewed.json"
python localization/build_steam_26077854.py `
  "$i/dual-sources/steam-26077854.json" "$i/dual/dual-corrections.json.gz" `
  "$i/dual-sources/steam-26077854-report.json" "$i/steam-26077854.json.gz"
./prepare-localization.ps1 -Engine release-stage/materials/component/Aion2-Steam-CN-v2.4.0.exe `
  -DecoderPath release-stage/materials/component/dependencies/oo2core_9_win64.dll `
  -AdditionsPath "$i/steam-26077854.json.gz" -Destination release-stage/component
```

双端基线按解压后的精确 JSON 摘要验证，避免 Python/zlib 版本不同导致 gzip 文件摘要变化而误判。基线内容 SHA-256：`94569d872871395d3e74fe0a43a4099ab8250dece33cd4d11a275e5df5797339`。

Steam 当前原始 PAK SHA-256：`4565d9d817f6ca8a7a11bbd0d25d0d91c6306c234be5f279ecfb33d5fba47080`。来源键数 153,185。新增补译 244 条，另有全表历史修订 361 条；完整合并的额外补译/纠错计数为 3,811，不能将它解释成新增行数。

两份 reviewed JSON 以完整原文摘要绑定；历史纠错同时绑定旧译摘要。对于已有纠错后的再次修订，构建阶段将其组合为原始旧译绑定，原生单次纠错阶段即可生效。未经审查的源文本与参数变动会拒绝生成。

本地使用当前 Steam 原始 PAK 的副本验证，实际游戏文件不写入。原生校验、独立 Python 解码核对全部键、顺序和运行时参数；隔离事务覆盖安装、重复安装、注入失败回滚和逐字节还原。源表中的机器标识、测试条目、品牌名及未逐一审查的残留英文不计作全游戏翻译验收。

隔离安装实际 DAT SHA-256：`6a7a8cd4a68a3ef83a6451c8963a07bbedb11b31dcae38bc13b3746e7dc1f0a7`。独立审计核对 361 条修订全部生效：笔记 34、任务 68、物品/界面 212、成就 16、引导 1、称号 30。目标类别的整段英文段落检测为 0；该检测不等同于逐字语义或所有混合短语验收。

本地测试：Python 182 项（174 通过、8 跳过），Rust 156 通过、5 项显式实机测试默认忽略，C# 45 项安全检查通过。Node 版本徽标检查发现遗漏后已修正，正式发布工作流重新执行全部前端测试及构建。

PURPLE 变体保留上一版来源，不用本机旧客户端的检测失败替代 TW 123 的已发布结果，也不据此声明支持未来版本。战斗协议与游戏内显示不在本次实测范围。MSI 包只读检查不等同于真实覆盖升级测试。
