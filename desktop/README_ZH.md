# A2Tools DPS Meter

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/pulls)

一款适用于 **AION 2**（永恒之塔2）的实时 DPS 统计工具。通过捕获游戏网络数据包来显示伤害、技能和战斗统计数据。

**[下载最新版本](https://github.com/taengu/A2Tools-DPS-Meter/releases)** | **[A2Tools.app](https://a2tools.app)**

[English](README.md) | [한국어](README_KO.md) | [繁體中文](README_ZH-TW.md)

---

## 功能特性

- 实时 DPS 追踪（按玩家分类）
- 技能级伤害分析（暴击、背击、招架、连击、完美）
- DOT（持续伤害）追踪
- 召唤物伤害合并至主人
- 多种目标选择模式（Boss、最后打击、全部目标、练级怪）
- DPS 图表和时间线
- Boss 战斗历史自动保存
- 延迟监控
- 多语言支持（中文简体/繁体、英语、韩语）
- 置顶透明悬浮窗
- 主题和自定义设置

## 安装方法

### 第一步 — 安装 Npcap（必需）

从 https://npcap.com/#download 下载并安装 **Npcap**。

> ⚠️ 安装过程中，**必须**勾选 **"Install Npcap in WinPcap API-compatible Mode"**。

### 第二步 — 下载并安装

👉 从 [Releases 页面](https://github.com/taengu/A2Tools-DPS-Meter/releases) 获取最新 MSI 安装包。

### 第三步 — 启动

以**管理员身份**运行 A2Tools DPS Meter。

**Linux**（通过 Proton 游玩）：提供 Ubuntu/Debian（.deb）、Fedora/openSUSE（.rpm）、Bazzite、Arch/CachyOS/Manjaro 和 Steam Deck 软件包 — 请参阅 **[Linux 指南](docs/linux.md)**（英文）。

[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?logo=ubuntu&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Debian](https://img.shields.io/badge/Debian-A81D33?logo=debian&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Linux Mint](https://img.shields.io/badge/Linux_Mint-87CF3E?logo=linuxmint&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Pop!_OS](https://img.shields.io/badge/Pop%21__OS-48B9C7?logo=popos&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Fedora](https://img.shields.io/badge/Fedora-51A2DA?logo=fedora&logoColor=white)](docs/linux.md#fedora) [![Bazzite](https://img.shields.io/badge/Bazzite-8A3FFC?logo=fedora&logoColor=white)](docs/linux.md#bazzite-silverblue-kinoite-aurora-bluefin) [![Steam Deck](https://img.shields.io/badge/Steam_Deck-1A9FFF?logo=steamdeck&logoColor=white)](docs/linux.md#steam-deck-steamos) [![openSUSE](https://img.shields.io/badge/openSUSE-73BA25?logo=opensuse&logoColor=white)](docs/linux.md#opensuse) [![Arch](https://img.shields.io/badge/Arch-1793D1?logo=archlinux&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![CachyOS](https://img.shields.io/badge/CachyOS-08A88A?logo=cachyos&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![Manjaro](https://img.shields.io/badge/Manjaro-35BF5C?logo=manjaro&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![EndeavourOS](https://img.shields.io/badge/EndeavourOS-7F3FBF?logo=endeavouros&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros)

## 从源码构建

```bash
npm install
npm run tauri build
```

开发模式：

```bash
npm run tauri dev
```

需要 [Rust](https://rustup.rs/)、[Node.js](https://nodejs.org/) (v18+) 和 [Npcap](https://npcap.com)。

## 社区

- 💬 **Discord：** https://discord.gg/Aion2Global
- 🌐 **网站：** https://a2tools.app

## 赞助支持

如果本工具对您有帮助，欢迎支持开发者！

- <img src="wechat.png" width="150">
- ☕ [Ko-fi](https://ko-fi.com/hiddencube)
- ☕ [爱发电](https://afdian.com/a/hiddencube)
- 🅿️ [PayPal](https://www.paypal.me/taengoo)
- 🎁 [加密货币捐赠](https://nowpayments.io/donation/thehiddencube)
- **BTC**: `1GexKhgVZPYRqpfCKydXLoNUXRRRUoAUwT`
- **ETH**: `0x38F0bc371A563A24eCa6034cFf77eB6173c7e3e7`
- **USDC**: `0xA9571Fc95666350f6DFFB8Fb80ee27eE7db46b56`

## 许可证

[GPL-3.0](LICENSE)
