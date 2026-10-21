# Steam / PURPLE 汉化组件

2026-10-21：助手 2.0.57 基于 2.0.56 适配 Steam Build 26077854，新增 244 条源文绑定补译，并审查修订 361 条历史漏译/中英混杂记录。当前表 153,185 个键，完整合并额外补译/纠错计数 3,811。重建、输入摘要与实际隔离安装验证见 [BUILD-2.0.57](../releases/BUILD-2.0.57.md)。PURPLE 来源变体沿用 2.0.56，不扩展其当前版本的兼容承诺。

桌面入口支持两个客户端，必须选择包含 `Aion2/Content` 的游戏根目录。
安装前退出游戏；安装后将游戏文字语言设为 **English**。
检测与汉化不会启动战斗统计。安装操作需要本地确认，支持还原。

## 为什么两端可以汉化

两端都有 `Aion2/Content/L10N/Text/en-US/L10NString.dat` 对应的语言资源。
关闭英文语言 PAK 的覆盖后，游戏可使用生成的独立语言表。
duoluoyuji/Aion2-Steam-CN 的脚本也使用此共同路径：发现两个客户端，
复制同一份 DAT，并替换英文 PAK。它声明支持两端不代表一份旧表适合所有更新。
2026-10-05 本机 PURPLE 有 156,439 个键，参考译文仅有 152,629 个键，不能直接替换。
当前 PURPLE TW 123 已有 157,507 个键，必须以本端当前资源重新生成译文。

本项目先解码所选端的当前英文表，保留全部键和顺序，然后依次使用：

1. 原文 SHA-256 匹配的参考译文。
2. 原文完全一致且译文无歧义的其他键译文。
3. 本地官方繁体表转换的简体补译，以及审查过的 Steam 差异译文。

补译按“键 + 原文 SHA-256”绑定，同一个键可以保存多个客户端版本。
例如删角色提示分别保留 Steam 的 24 小时与 PURPLE 的 7 天。
运行时参数必须保持一致；编码后重新解码，核对全部键、顺序和文本。
新增/变更文本仍缺补译时，在写入前失败，不把英文回退冒充成功。
图标标识、变量及官方 `Neural Frame Fusion` 品牌名保持原样。

## 当前版本：2.0.55（2026-10-14）

本次适配 Steam Build 25926599 与 PURPLE TW 123。新版语言包的内部资源路径存在大小写差异；读取器先列出包内成员，再使用实际名称读取，并拒绝同名歧义或非预期路径。游戏目录不用于临时解包输出。

| 客户端 | 当前键数 | 已验证范围 |
| --- | ---: | --- |
| Steam / Global | 153,042 | 资源生成、编码回读、独立解码、隔离安装及还原 |
| PURPLE TW | 157,507 | 资源生成、编码回读、独立解码、隔离安装及还原；用户手动真实安装 |

合并保留原有补译变体和国服术语修订，只为当前来源追加译文。以旧 Steam 源表保护未改变的文本，152,617 条原文未变的记录保持已发布的修订译文。98 条 Steam 专属或仍未翻译的文本经过人工审查，包含活动、货币、转服与道具规则；保留本端的数值、条件和运行时参数，不按 PURPLE 同键旧文案套译。两端同源的 `Trick or Treat` 补为“不给糖就捣蛋”。

两端当前实际 PAK 的隔离副本通过安装、重复安装、注入失败回滚和逐字节还原。独立解码隔离安装保留的实际 DAT，全部键和顺序一致，运行时参数差异为 0。用户另在 2.0.55 桌面窗口自行批准 PURPLE 安装，实际 DAT 摘要与隔离验收产物一致，安装状态及原始备份摘要一致；本次没有执行真实 Steam 写入或真实 PURPLE 还原。

实际桌面的目录检测、取消与返回交互未完成完整验收，自动前端及 Rust 测试已覆盖相应逻辑。上述资源和事务验证不等同于完整游戏内画面或实战验收。完整来源摘要、重建步骤和测试范围见 [2.0.55 构建与验收记录](../releases/BUILD-2.0.55.md)。

## 本地准备与构建

源码不分发引擎、解压 DLL 或完整游戏文本。引擎限定为核准的 v2.4.0，
解压 DLL 校验已知 SHA-256，不会自动下载运行未知组件。
玩家安装时不需要 Python；以下流程仅供本地维护构建。

下面的 `prepare-dual-localization.ps1` 示例沿用历史快照审查入口，其生成器会拒绝未匹配的版本。重建当前 2.0.55 应使用本版构建记录中的 `build_dual_release.py` 流程，以及配套的已审核来源附件、旧 Steam 源表和人工审查文件。

准备 Python 环境中的 `blake3`、`cryptography`、`lz4`、
`opencc-python-reimplemented`，并提供自己已有的游戏资源与组件：

```powershell
./prepare-dual-localization.ps1 `
  -Engine 'C:/Downloads/Aion2-Steam-CN-v2.4.0.exe' `
  -PurpleRoot 'D:/AION2_TW' `
  -SteamRoot 'D:/SteamLibrary/steamapps/common/AION2' `
  -DecoderPath 'C:/Dependencies/oo2core_9_win64.dll' `
  -Python 'C:/PythonEnv/Scripts/python.exe' `
  -Destination './build/dual-localization'

./build-desktop.ps1 `
  -LocalizationEnginePath 'C:/Downloads/Aion2-Steam-CN-v2.4.0.exe' `
  -LocalizationDecoderPath 'C:/Dependencies/oo2core_9_win64.dll' `
  -LocalizationAdditionsPath './build/dual-localization/localization-additions.json.gz' `
  -DebugBuild
```

准备脚本只读游戏文件；输出目录必须为新目录。输入需包含当前原始英文 PAK，
不能使用已替换的汉化标记包。Steam 差异生成器锁定审查过的输入摘要；
其他版本需重新审查，不会自动按相同键名套用不对应的繁体文本。
补译压缩数据嵌入本地桥接 EXE，不能随源码提交。
仅提供引擎而缺少所需补译的构建，安装会在完整性检查时停止。

## 验证记录（2026-10-05 本机资源）

| 客户端 | 当前键数 | 参考译文缺键 | 实际额外补译 | 新增/变更的英文可见文本残留 |
| --- | ---: | ---: | ---: | ---: |
| PURPLE TW | 156,439 | 6,144 | 18,779 | 0 |
| Steam / Global | 152,723 | 214 | 1,819 | 0 |

“额外补译”包含新增键及已变化的原文，不是表的总译文数量。
残留检查排除图标标识和官方品牌名，不能证明每条已有译文的语义完美。
两端实际 PAK 的隔离副本完成：安装、重复安装、模拟写入失败回滚、
逐字节还原；更换为更新原始 PAK 后，验证备份分代和还原不会写回旧版本。
正式游戏目录未被这些测试修改。游戏内画面/排版仍未实测，不能把构建通过
等同于游戏运行验证通过。
另外，在打包助手的实际界面点击两端“检测”，验证了前端、Rust 后端、
桥接组件与本地真实资源的完整只读调用链。Windows 规范化路径使用兼容格式，
不把 `\\?\` 前缀传给旧版 .NET Framework；此问题已有 Windows 回归测试。
检测的 JSON `supplemented` 字段与界面消息一致。真实目录只读回归检查
同时核对当前键数、补译数量，以及检测前后英文语言包和独立语言目录的文件名、
SHA-256；本机两端均通过，原有 Steam 汉化状态未被修改。
当本机实际 AION2 进程运行时，正式桥接组件在临时合成目录上拒绝两个客户端的
安装与还原（四种请求），目录内容逐字节不变；此测试不对真实游戏目录发起写操作。
该运行中保护验证不等同于安装后的游戏内显示验证。

## 2026-10-10 游戏更新适配（助手 2.0.49）

本次以更新完成后的实际英文 PAK 为准，旧组件分别缺少 PURPLE 49 条、
Steam 103 条新增/变更可见文本补译；检测拒绝安装，不改游戏文件。
新组件使用本次官方 TW 表，并审查生成 217 条 Steam 独立来源变体。
维护构建继续锁定整对客户端源表摘要，拒绝未审查的新版本或混合快照；
Steam 的商店分类、服务器维护、处罚提示和创始者礼包不按 PURPLE 键名套译。
翅膀描述保留 Steam 更新后的飞行力 1,000/2,500 及本端战斗属性。

| 客户端 | 当前键数 | 额外补译 | 新增/变更可见文本缺译 |
| --- | ---: | ---: | ---: |
| PURPLE TW | 156,480 | 19,030 | 0 |
| Steam / Global | 152,774 | 1,927 | 0 |

两端真实目录的只读检测验证文件清单和 SHA-256 不变；桥接结果明确返回
`client` 和 `game_root`，测试核对归属，避免将不同客户端报告错配。
两端当前实际 PAK 的隔离副本通过安装、重复安装、模拟失败回滚、逐字节还原。
另用独立格式解码器读取隔离安装生成的 DAT：全部键和顺序一致，运行时参数
差异均为 0；检查 Steam 新版商店/维护文本和飞行力未回退为 TW/旧值。
这些测试没有安装或还原真实游戏目录的汉化，也没有验证游戏内显示。

```powershell
./test-localization-inspection.ps1 -Component './build/dual-localization/component' `
  -GameRoot 'D:/AION2_TW' -Client purple -ExpectedKeys 156480 -ExpectedSupplemented 19030
./test-localization-inspection.ps1 -Component './build/dual-localization/component' `
  -GameRoot 'D:/SteamLibrary/steamapps/common/AION2' -Client steam -ExpectedKeys 152774 -ExpectedSupplemented 1927
python -m unittest discover -s tests -p test_localization_variants.py -v
# TestEngine 必须是本地 DEBUG 引擎，非正式包；仅对新建临时隔离目录写入。
./test-localization-roundtrip.ps1 -TestEngine 'C:/Local/DualEngine.Debug.exe' `
  -GameRoot 'D:/AION2_TW' -Client purple `
  -AdditionsPath './build/dual-localization/localization-additions.json.gz' `
  -DecoderPath 'C:/Dependencies/oo2core_9_win64.dll'
# 上一命令返回的隔离目录内保留 installed-payload.audit.dat，可独立审计。
python localization/audit_generated_payload.py `
  './build/dual-localization/manifest/L10NString.dat' `
  'C:/Local/fixture/installed-payload.audit.dat' `
  './build/dual-localization/purple-en-US.json' purple
```

2026-10-06：另在 Steam 实际目录进行了临时写入测试，预先保存了全部 7 个
原有语言文件及状态。已写入 DAT 用独立格式解码器验证：152,723 个键和顺序
与当前原始表完全相同，服务器选择菜单条目为中文。桥接进程曾停留在不可访问的
完成提示；进程退出后核对测试后文件摘要，恢复测试前文件及旧汉化状态，逐字节
一致，测试产生的文件归档保留。这不能证明游戏已加载译文，也不能将状态文件的
`installed` 单独视为原生事务正常返回的证据。两端游戏内显示验证仍未完成。

```powershell
./test-localization-safety.ps1
cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --lib
./test-localization-inspection.ps1 -Component './build/dual-localization/component' `
  -GameRoot 'D:/AION2_TW' -Client purple -ExpectedKeys 156439 -ExpectedSupplemented 18779
```

安全测试使用自造文本，不需游戏数据；覆盖来源绑定、同键分端版本、
保留已有译文、参数丢失、冲突版本、键顺序及缺译安装拦截。
`tests/LocalizationRoundtrip.cs` 是仅接受 `isolated-test.marker` 的隔离事务测试器，
必须配合原引擎 DEBUG 测试接口使用，不能对真实游戏根目录运行。

## 国服术语定向纠错

`build_mainland_corrections.py` 校对已生成的译文，不直接读写游戏目录。
英文表与旧译表必须有完全一致的键及顺序。每条纠错同时绑定源文和旧译文摘要，
只对审核过的内容生效；标签和参数不符时拒绝生成。审核依据与未完成项见
[MAINLAND_AUDIT.md](MAINLAND_AUDIT.md)。

```powershell
python localization/build_mainland_corrections.py <english.json> <previous-translation.json> <new-output-directory> `
  --additions <existing-localization-additions.json.gz>
./test-localization-safety.ps1
python -m unittest discover -s tests -q
```

输出 `corrections.json.gz` 为格式 3 资源，可作为本地构建的 `-LocalizationAdditionsPath`；
`preview.json` 是校对预览，不是可安装 DAT。省略 `--additions` 只生成独立纠错表，
不含完整补译，不能用于完整发行包。合并保留原格式 1/2 中的客户端源文变体；
不能重复输入已生成的格式 3 资源。

运行时先补未翻译条目，再按双摘要应用纠错。因此若新引擎或补译包已经改变旧译，
对应纠错会安全跳过；应针对实际流水线重新生成预览并做隔离安装、回读测试。
全表预览一致不等同于完整安装链路或游戏内显示已验证。

格式研究参考：
[CUE4Parse Aion2 格式说明代码](https://github.com/FabianFG/CUE4Parse/tree/master/CUE4Parse/GameTypes/Aion2)。
本项目通过独立格式实现与版本固定组件互操作，不重新许可原引擎或游戏数据。
原引擎及嵌入组件的公开再分发仍需单独进行许可证和对应源码审计；
本地准备与测试不代表已批准发布包含这些资源的整合 Release。
