# 开发指南

本文适用于亚特雷亚助手 2.0.64。命令默认在仓库根目录执行；旧 Python/Tk 原型见[历史开发说明](../LEGACY_DEVELOPMENT.md)。

## 目录

| 路径 | 职责 |
| --- | --- |
| desktop/ | 当前 Rust / Tauri 桌面助手及前端 |
| localization/ | Steam 日文入口、PURPLE 桥接和译文构建工具 |
| tests/ | Python 及汉化安全测试资料 |
| backend/ | 早期协议后端及保留的回归测试 |
| website/ | a2go.cc 的 Nuxt 官网、下载 API 和部署配置 |
| docs/ | GitHub Pages 备用站点、静态指南和更新清单 |
| releases/ | 逐版本说明、构建记录与来源摘要 |
| documentation/ | 当前维护入口和历史归档 |

## 环境与无组件开发

使用 Windows x64、Node.js 24、Rust 1.93、MSVC/Tauri 构建依赖。汉化工具与 Python 测试按 CI 使用 Python 3.12 及 [requirements-build.txt](../localization/requirements-build.txt)。官网要求 Node.js 24.15.0 或以上。

仅开发 UI 或桌面逻辑时，不需要游戏数据或汉化组件：

```powershell
Set-Location desktop
npm ci --ignore-scripts --no-audit --no-fund
npm run build
node --test tests/*.test.cjs tests/*.test.mjs
cargo test --locked --manifest-path src-tauri/Cargo.toml --lib
npm run tauri build -- --no-bundle --debug
Set-Location ..
```

这种构建不提供可用的完整汉化组件。根目录 `build-desktop.ps1` 是带已审核双端组件的构建入口，会要求 Steam 和 PURPLE 的 helper、摘要及协议均正确；不能作为全新克隆后的无组件快捷构建命令。

Npcap 仅在实际开启 DPS/雷达采集时需要；安装或还原游戏汉化应在游戏退出后进行。自动化测试不替代驱动和游戏现场验收。

## 汉化与回归检查

```powershell
python -m pip install -r localization/requirements-build.txt
python -X utf8 -m unittest discover -s tests -q
./test-localization-safety.ps1
cargo test --locked --manifest-path backend/Cargo.toml
```

准备双端组件见[汉化方案](../localization/README.md)。`prepare-release-localization.ps1` 使用版本固定输入、新输出目录，并要求重建 DAT 摘要与本版已验收文件一致。

本地带组件桌面构建：

```powershell
./build-desktop.ps1 -DebugBuild
```

该脚本生成前端、运行前端及 C# 安全检查并编译程序；Rust/Python 检查仍按上面的命令或 CI 执行。它不启动助手、不抓包，也不改写游戏。

真实资源只读检测和隔离事务验证使用对应版本构建记录中的命令及预期值。不要把旧版键数硬套给新资源；不要用真实游戏目录运行仅接受隔离标记的事务测试器。

## 官网与文档检查

```powershell
Set-Location website
npm ci
npm run generate
python -X utf8 check_build.py
Set-Location ..
python -X utf8 -m unittest discover -s website/tests -v
node --test desktop/tests/website-seo.test.cjs desktop/tests/download-page.test.cjs
```

官网测试使用测试数据，不向生产下载计数写入模拟点击。只修改 Markdown 时，检查相对链接、引用的文件路径及差异即可，不需要重建 MSI。

## CI 和正式打包

- [desktop.yml](../.github/workflows/desktop.yml)：无游戏资源的桌面构建、前端、Rust 及 C# 检查。
- [tests.yml](../.github/workflows/tests.yml)：Python、协议后端及历史冻结包的合成回归。
- [release.yml](../.github/workflows/release.yml)：版本固定输入、完整组件、正式 MSI、材料归档及 S3。
- [pages.yml](../.github/workflows/pages.yml)：备用站点部署。

维护过程中保留独立窗口、中文快捷方式、本地统计和译文来源校验。不要把缺少实机验收的功能描述为已全面验证。正式发布步骤见[发布与官网同步](RELEASING.md)。
