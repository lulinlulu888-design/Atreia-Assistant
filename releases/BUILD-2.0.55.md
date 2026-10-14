# 2.0.55 构建与验收记录

应用源码对应 v2.0.55。基础引擎、解压依赖、已发布 Steam 修订、依赖源码和许可证沿用 SHA-256 固定的 2.0.51 构建材料。本版来源附件含三个当前客户端语言快照及一份 Steam 人工审查记录。游戏数据不提交 Git；公开再分发范围沿用 THIRD_PARTY_NOTICES.md 中的授权记录。

- 基础材料：`Atreia-Assistant_2.0.51_build-materials.zip`，SHA-256 `b7dab6b9ac30c92a9bf17e3dd5b6117272e9147e8940c7763ceee28937a4d219`。
- 本版来源：`Atreia-Assistant_2.0.55_localization-sources.zip`，SHA-256 `410896f5201b4d7e8a69bcd29d8ff96c056a2b912525b206faff2502e0537e1b`。

## 来源绑定与生成

| 输入 | SHA-256 |
| --- | --- |
| 当前 Steam `steam-en-US.json` | `f7f9052a1b15e9a8815337a49db5271f71b7ee713dba13439e3debc696b8c696` |
| 当前 PURPLE `purple-en-US.json` | `86784036c93ea93090f0f3e4f3f4859d8e04855d7faa2636e6171499bf61834e` |
| 当前 PURPLE `purple-zh-TW.json` | `bd0eab7d1344c07ebb88f2ebd045b6a298a810f48743062d82dc9c947ea6f11c` |
| Steam 人工审查 `steam-reviewed.json` | `cb58fcf4751f6bf3ac17a5686f20c6651f04cc5a069d3aad53c1f56586d464db` |
| 旧 Steam `current-steam.json` | `f8c79eb669613ba68aaff45a22395b9cd12138631253d5789f96b023330254bf` |
| 已发布修订 `corrections.json.gz` | `768e67b1693156f02d63f2b817990aff4b0cca5ff5f16968ebf69331684014f1` |

使用 Python 3.12 与 opencc-python-reimplemented 0.1.7 运行 `localization/build_dual_release.py`，同时提供 `--steam-baseline` 和 `--reviewed-steam`。脚本固定校验以上输入，拒绝未知或混合来源。

合并保留原始修订的全部 entries 变体和 corrections，新增 18,920 个当前官方来源变体，保护 138,573 个 Steam 未变同源键，保留 14 个已审查同源变体。人工审查共 98 条 Steam 记录，追加 97 个来源变体并替换 1 条原样英文；已有不同中文译文不得被人工追加记录覆盖。数值、机器标签及运行时表达式保留；`<Red Halloween Candy>` 是已审查的显示名，译为 `<红色风味万圣节糖果>`。

生成 `dual-corrections.json.gz` 的 SHA-256 为 `9a682f9c5f2b1479fb9ff2e266da501b6d98cfe76dbc8ddaedc5aeea47c52289`。随后用本标签下的 C# 源码重新编译桥接程序，不直接复用旧桥接 EXE。

## 从构建材料重建

将 `application-source.zip` 解压为工作目录。材料包中的 `localization-inputs/dual-sources/` 提供本版来源，`localization-inputs/` 同时保留经摘要验证的历史输入。以下输出目录必须尚不存在：

```powershell
$materials = 'C:/path/to/unpacked-build-materials'
$i = "$materials/localization-inputs"
python localization/build_dual_release.py `
  "$i/corrections.json.gz" "$i/dual-sources/steam-en-US.json" `
  "$i/dual-sources/purple-en-US.json" "$i/dual-sources/purple-zh-TW.json" `
  ./build/rebuilt-dual-2.0.55 `
  --steam-baseline "$i/current-steam.json" `
  --reviewed-steam "$i/dual-sources/steam-reviewed.json"
./prepare-localization.ps1 `
  -Engine "$materials/component/Aion2-Steam-CN-v2.4.0.exe" `
  -DecoderPath "$materials/component/dependencies/oo2core_9_win64.dll" `
  -AdditionsPath ./build/rebuilt-dual-2.0.55/dual-corrections.json.gz `
  -Destination ./build/rebuilt-component-2.0.55
Copy-Item ./build/rebuilt-component-2.0.55/* ./desktop/src-tauri/vendor/localization/ -Recurse -Force
Copy-Item "$materials/notices/*" ./desktop/src-tauri/vendor/notices/ -Recurse -Force
cd desktop
npm ci --ignore-scripts
npm run tauri build -- --bundles msi --ci
```

发布工作流重新生成本版 `build.json`，记录本版 version、标签构建的 GITHUB_SHA、2.0.51 基础材料出处与摘要、沿用的 352 个依赖源码包、`releases/compatibility-2.0.55.json` 的双端版本，以及 `dual/review.json.inputs` 的全部来源摘要。它不继承基础材料中旧版 version/commit。component、application-source.zip 和 BUILD.md 对应本版；依赖源码及许可证沿用已验证基础材料。

## 本地资源和隔离事务验收（2026-10-14）

- Steam Build 25926599：153,042 个键；PURPLE TW 123：157,507 个键。
- 两端原生生成与编码回读、独立 Python 解码通过；全量键及顺序一致，运行时参数差异为 0。
- 独立审计使用旧 Steam 源表和旧译表加已发布修订，152,617 条原文未变记录的译文逐条一致。当前变化文本绑定当前源 SHA，不以同键旧长文译文替代。
- 两端当前实际 PAK 的隔离副本完成安装、重复安装、注入写入失败回滚和逐字节还原。测试器只接受 `isolated-test.marker` 目录。
- 隔离安装保留的实际 DAT 与单独生成验收 DAT 摘要一致；隔离目录安装状态最终为 restored。
- Steam 实际隔离安装 DAT SHA-256：`4e89f033f1075f3365ddfd8b761c77f880780707febe288b287d575368ed305d`。
- PURPLE 实际隔离安装 DAT SHA-256：`3a88bf8d3037883fafc2f9196e13fb84e761871618130160ba931ef46190686e`。

## 自动测试与独立审查

- Python：169 通过、8 跳过；Node：79 通过；Rust：156 通过、5 项显式实机测试默认忽略；C#：45 项安全检查通过。
- 本地 MSI 构建及桌面快捷方式、必装功能和卸载清理记录的只读包检查通过；此检查不执行 MSI 安装或升级。
- 独立发布前审查核对旧补译/修订保留、当前来源绑定、同名 PAK 资源歧义拒绝、进程输出限制与超时、安装事务守卫及本版构建元数据。
- 新读取器使用列表中的完整成员名称，保留真实大小写，拒绝非预期路径或多个同名成员；临时解包位于独立临时目录，不写游戏目录。
- 安装仍保留游戏关闭检查、源摘要前后核验、备份迁移、失败回滚和 Commit；还原沿用原引擎事务。

## 实际桌面交互与用户安装

用户在本地 2.0.55 窗口自行切换到 PURPLE 并批准安装，助手返回安装完成，显示 21,398 条额外补译。之后的只读独立解码确认：真实安装 DAT 包含 157,507 个键、顺序一致、参数差异为 0，SHA-256 为上列 PURPLE 摘要；状态文件为 installed 且 payload_hash 一致；pre_pak_hash 为 `f06c0ccbdc588c656df0ccb9be8c1a33436797568ee6a51fcd7b9790312a736c`，与保存的原始 PAK 备份一致。

实际桌面的目录检测、取消与返回交互未完成完整验收，相应逻辑已有 Node/Rust 自动测试覆盖。本次没有执行真实 Steam 汉化写入、真实 PURPLE 还原、真实 MSI 跨版本覆盖升级或战斗抓包；没有完成游戏内所有界面和实战验收。隔离事务、用户一次安装及自动测试的结果分别记录，不相互代替。

发布工作流只接受含已审核来源附件的草稿，测试及打包通过后转为正式版本，不覆盖旧版本附件。官网安装链接、SEO 软件版本及备用更新记录在公开 MSI 下载并核对 GitHub digest/大小之后单独同步。
