# 汉化方案与维护

当前正式版：**2.0.64**。玩家安装步骤见[汉化安装与还原指南](../docs/guides/localization.html)；本页面向维护者，所有相对命令路径均以仓库根目录为基准。

## 客户端入口

| 项目 | Steam / Global | PURPLE 台服 |
| --- | --- | --- |
| 游戏文字语言 | 日本語（ja-JP） | English（en-US） |
| 验证资源版本 | Build 26262663 | TW 127 |
| 实现 | 自有日文入口组件，冻结为独立 EXE | 原 v2.4.0 引擎及 PURPLE 专用桥接器 |
| 组件位置 | desktop/src-tauri/vendor/localization/ | 同目录下的 purple/ |
| 语言记录 | 153,297 条中文 UI + 153,297 条独立官方日文参考 | 160,286 条，额外补译/纠错计数 24,606 |
| 本轮验证 | 中文显示及语言切换实机通过，资源与事务检查通过 | 真实资源只读检查、缺译及编码回读检查通过 |

参考条目不是额外的中文翻译；PURPLE 的补译计数也不是本次新增条数。资源完整性检查不等于所有游戏界面均已人工验收。详细证据、摘要和限制见[验证状态](JAPANESE_ENTRY_STATUS.md)及[2.0.64 构建记录](../releases/BUILD-2.0.64.md)。

两端组件各自固定 SHA-256，并验证协议和客户端归属。缺少本端组件时停止，不套用另一端。PURPLE 不要求本地存在日文资源。

## 翻译来源和国服风格

- 使用自有中文映射、当前客户端官方资源及源文摘要绑定的审查记录，没有直接套用参考项目的翻译 DAT。
- 保留键顺序、运行时参数、标签及本端数值；同键但原文变化的内容需要重新审查。
- 专名以人物身份和上下文为依据，沿用国服已核对写法，例如“伊斯拉佩尔”；统一使用“隐藏宝箱”。
- 不按服务器列表的位置配对人物，不用另一端旧表覆盖当前客户端，不把英文回退算成补译成功。
- 既有术语依据与当时待核对项见[国服风格审计](MAINLAND_AUDIT.md)。该文中的数量属于注明日期的历史快照。

Steam 生成流程保存独立官方日文参考；PURPLE 继续使用本地官方繁体表转换及审核补译。来源、产物和旧译均须满足对应摘要检查。

## 备份、迁移与还原

Steam 使用 `.bak` 扩展名隔离备份，避免切换语言时重新加载备份。旧英文入口迁移先核对并恢复原资源，再安装日文入口；未知资源或冲突备份会中止操作。PURPLE 保留原英文方案的备份和还原流程。

检测读取所选客户端的真实资源。安装和还原要求游戏退出，并使用各自的校验、回滚和事务保护；不要手动删除备份或强行绕过版本不匹配。

## 重建 2.0.64

依赖、来源归档及固定摘要以[本版构建记录](../releases/BUILD-2.0.64.md)、[来源清单](../releases/localization-2.0.64.json)和[正式工作流](../.github/workflows/release.yml)为准。Git 不保存完整游戏文本、原引擎或解压库，相关获授权材料放在对应 Release 附件。

在 Windows 上将本版来源归档解压至 `INPUTS`，将已核验的基础材料 `component` 放至 `BASE-COMPONENT`，使用尚不存在的输出目录：

```powershell
python -m pip install -r localization/requirements-build.txt
./prepare-release-localization.ps1 -Inputs INPUTS -BaseComponent BASE-COMPONENT -Python (Get-Command python).Source -Destination NEW-STAGE
Copy-Item NEW-STAGE/component/* desktop/src-tauri/vendor/localization/ -Recurse -Force
python -X utf8 prepare-python-notices.py desktop/src-tauri/vendor/notices/japanese-helper
./build-desktop.ps1 -DebugBuild
```

这些命令重建已审核的 2.0.64 输入，不是任意游戏更新的通用适配命令。准备脚本只读取来源文件，不安装或还原游戏汉化。完整正式 MSI 还需工作流中的基础许可、对应源码、测试与打包步骤，见[发布流程](../documentation/RELEASING.md)。

## 源码入口

| 文件 | 用途 |
| --- | --- |
| [build_japanese_bundle.py](build_japanese_bundle.py) | 根据完整官方表、自有中文及审查记录生成 Steam bundle |
| [entry_host.py](entry_host.py) | Steam 检测、安装、旧入口迁移、备份及还原 |
| [freeze_entry_host.py](freeze_entry_host.py) | 冻结 Steam 专用组件 |
| [EngineBridge.cs](EngineBridge.cs) | PURPLE 原英文方案桥接，正式构建使用 PURPLE_ONLY |
| [mainland_names.py](mainland_names.py) | 国服人物身份及译名规则 |
| [../prepare-release-localization.ps1](../prepare-release-localization.ps1) | 从版本固定输入重建双端组件 |

旧 `prepare-dual-localization.ps1`、`build_dual_release.py` 等工具保留用于历史版本研究，不能代替当前 Steam 日文入口流程。整理前的英文入口说明、2.0.49—2.0.58 验证片段保存在[历史归档](../documentation/archive/localization-english-entry.md)。

检查命令统一见[开发文档](../documentation/DEVELOPMENT.md)。对应版本发布记录只记录当时结果，不随新版本改写为当前兼容承诺。
