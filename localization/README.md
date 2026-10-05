# Steam / PURPLE 汉化组件

桌面入口支持两个客户端，必须选择包含 `Aion2/Content` 的游戏根目录。
安装前退出游戏；安装后将游戏文字语言设为 **English**。
检测与汉化不会启动战斗统计。安装操作需要本地确认，支持还原。

## 为什么两端可以汉化

两端都有 `Aion2/Content/L10N/Text/en-US/L10NString.dat` 对应的语言资源。
关闭英文语言 PAK 的覆盖后，游戏可使用生成的独立语言表。
duoluoyuji/Aion2-Steam-CN 的脚本也使用此共同路径：发现两个客户端，
复制同一份 DAT，并替换英文 PAK。它声明支持两端不代表一份旧表适合所有更新。
此次本机 PURPLE 有 156,439 个键，参考译文仅有 152,629 个键，不能直接替换。

本项目先解码所选端的当前英文表，保留全部键和顺序，然后依次使用：

1. 原文 SHA-256 匹配的参考译文。
2. 原文完全一致且译文无歧义的其他键译文。
3. 本地官方繁体表转换的简体补译，以及审查过的 Steam 差异译文。

补译按“键 + 原文 SHA-256”绑定，同一个键可以保存多个客户端版本。
例如删角色提示分别保留 Steam 的 24 小时与 PURPLE 的 7 天。
运行时参数必须保持一致；编码后重新解码，核对全部键、顺序和文本。
新增/变更文本仍缺补译时，在写入前失败，不把英文回退冒充成功。
图标标识、变量及官方 `Neural Frame Fusion` 品牌名保持原样。

## 本地准备与构建

源码不分发引擎、解压 DLL 或完整游戏文本。引擎限定为核准的 v2.4.0，
解压 DLL 校验已知 SHA-256，不会自动下载运行未知组件。
玩家安装时不需要 Python；以下流程仅供本地维护构建。

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

```powershell
./test-localization-safety.ps1
cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml --lib
```

安全测试使用自造文本，不需游戏数据；覆盖来源绑定、同键分端版本、
保留已有译文、参数丢失、冲突版本、键顺序及缺译安装拦截。
`tests/LocalizationRoundtrip.cs` 是仅接受 `isolated-test.marker` 的隔离事务测试器，
必须配合原引擎 DEBUG 测试接口使用，不能对真实游戏根目录运行。

格式研究参考：
[CUE4Parse Aion2 格式说明代码](https://github.com/FabianFG/CUE4Parse/tree/master/CUE4Parse/GameTypes/Aion2)。
本项目通过独立格式实现与版本固定组件互操作，不重新许可原引擎或游戏数据。
原引擎及嵌入组件的公开再分发仍需单独进行许可证和对应源码审计；
本地准备与测试不代表已批准发布包含这些资源的整合 Release。
