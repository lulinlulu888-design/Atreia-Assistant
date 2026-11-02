# 正式发布与官网同步

适用版本：2.0.64，流程核对日期：2026-11-02。历史版本的材料与结果见[版本索引](../releases/README.md)。

## 发布链路

审核当前游戏资源与翻译 → 版本固定输入归档 → GitHub 草稿 → 正式标签触发构建 → MSI / 构建材料 / 校验文件 → 正式 Release → S3 上传回读 → 更新两站清单 → 官网部署与公开验收。

游戏更新适配和发布是两个步骤。不能仅修改版本号，就把旧源表或旧验证结果用于新客户端。

## 1. 准备候选版本

- Steam 与 PURPLE 分别审查入口、原文变化、译文、备份及迁移；保留已有国服术语，参数和数值以各端当前源文为准。
- 更新应用版本：`desktop/package.json`、`desktop/package-lock.json`、`desktop/src-tauri/Cargo.toml`、`desktop/src-tauri/Cargo.lock`、`desktop/src-tauri/tauri.conf.json` 及主界面显示。
- 准备 `releases/<version>.md`、`BUILD-<version>.md`、`compatibility-<version>.json`、`localization-<version>.json`。
- 来源压缩包使用 `Atreia-Assistant_<version>_localization-sources.zip`，在本版清单中固定 SHA-256。只包含经过审核的发布输入，不加入账号凭据、用户截图或运行日志。
- 完整测试及组件准备见[开发指南](DEVELOPMENT.md)和[2.0.64 构建记录](../releases/BUILD-2.0.64.md)。

当前 `prepare-release-localization.ps1` 还固定了 2.0.64 的键数和验收约束。将来游戏资源变化时，需要审查并更新这些约束，不能仅更换归档名称。

## 2. 建立草稿并触发构建

[release.yml](../.github/workflows/release.yml) 目前根据精确标题查找唯一草稿：

```text
亚特雷亚助手 <version> · Steam 日文入口修复，PURPLE 沿用原方案
```

草稿先只附带一个已审核来源归档。发布标签使用 `v2.NUMBER.NUMBER`，指向版本及输入摘要已提交的代码，并明确选中该标签。以后若修改标题，须同步工作流的匹配逻辑。

推送正式标签后，Windows 工作流：

1. 校验标签与应用版本、基础材料、草稿和来源归档摘要。
2. 从输入重建 Steam bundle，核对已验收 DAT；构建独立的 PURPLE 原方案组件。
3. 收集许可，运行 Python、前端、C# 与 Rust 检查，构建 MSI。
4. 检查中文快捷方式，归档应用源码、组件来源、依赖材料及校验文件。
5. 上传 MSI、构建材料和 `SHA256SUMS.txt`，再将草稿转为正式最新版本。

工作流会拒绝草稿中出现意外附件或构建期间被修改的发布状态。失败时先检查日志与草稿，再重试；不要覆盖已公开的同版本安装包或移动正式标签。

## 3. 核验 S3 下载

正式 Release 成功后，依赖作业使用 GitHub OIDC 临时角色上传安装包和校验文件到 S3，并重新下载逐字节比较。权限和桶路径见[官网运维](../website/README.md)。

需要独立重试同步时，现有 [sync-downloads.yml](../.github/workflows/sync-downloads.yml) 支持 `v2.NUMBER.NUMBER-sync-downloads` 标签；它同步已存在的正式版，不重新编译 MSI。

官网下载切换前，应确认：

- GitHub Release 不是草稿或预发布，只有一个匹配版本的 Windows x64 MSI。
- 从公开 GitHub 地址和 S3 地址取回的 MSI 大小、SHA-256 与校验文件一致。
- 不能用本机另一次构建的 MSI 摘要替代云端正式资产摘要。

## 4. 更新官网和软件备用更新入口

| 文件 | 内容 |
| --- | --- |
| website/release.json | a2go.cc 的 S3 下载地址、版本、大小、摘要及更新文案 |
| website/public/updates/latest.json | a2go.cc 托管的 GitHub 安装包更新清单 |
| docs/updates/latest.json | 桌面程序实际使用的 GitHub Pages 备用更新清单 |
| docs/index.html | 备用站点版本、下载按钮、静态大小、日期及结构化数据 |
| 两站 guides/localization.html | 客户端语言和安装方法变化时同步更新 |
| README、文档导航及版本索引 | 当前版本与验证范围 |

两份 `latest.json` 都填写同一 GitHub 正式资产的地址、大小和 digest，不能把 S3 地址直接塞入有域名白名单的软件更新器。

提交后，GitHub Pages 由 [pages.yml](../.github/workflows/pages.yml) 自动部署；a2go.cc 需另外执行：

```powershell
Set-Location website
npm ci
npm run generate
python -X utf8 check_build.py
Set-Location ..
node --test desktop/tests/website-seo.test.cjs desktop/tests/download-page.test.cjs
./website/deploy/publish.ps1
```

部署通过新目录与原子符号链接切换保留回滚点，不修改 hczs 站点或清空 MongoDB 点击记录。

## 5. 发布后验收

读取公开首页、`download-release.json`、两站 `updates/latest.json` 和安装指南，确认版本与摘要一致。浏览器查看下载按钮、发布说明和真实截图版本；读取 `/api/downloads` 确认统计服务正常，不为测试向生产计数写入合成点击。

发布结果记录在版本构建文档中。明确区分用户实机反馈和自动化测试，未完成的游戏场景不要写成“全量实测”。

2.0.64 已于 2026-11-02 完成正式发布、S3 公开回下载和两站同步。具体包摘要见[发布核验记录](../releases/BUILD-2.0.64.md)。
