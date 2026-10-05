# A2Tools DPS Meter

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/pulls)

適用於 **AION 2**（永恆之塔2）的即時 DPS 統計工具。透過擷取遊戲網路封包來顯示傷害、技能和戰鬥統計數據。

**[下載最新版本](https://github.com/taengu/A2Tools-DPS-Meter/releases)** | **[A2Tools.app](https://a2tools.app)**

[English](README.md) | [한국어](README_KO.md) | [简体中文](README_ZH.md)

---

## 功能特色

- 即時 DPS 追蹤（依玩家分類）
- 技能級傷害分析（暴擊、背擊、招架、連擊、完美）
- DOT（持續傷害）追蹤
- 召喚物傷害合併至主人
- 多種目標選擇模式（Boss、最後打擊、全部目標、練級怪）
- DPS 圖表和時間軸
- Boss 戰鬥歷史自動儲存
- 延遲監控
- 多語言支援（繁體中文/簡體中文、英語、韓語）
- 置頂透明懸浮視窗
- 主題和自訂設定

## 安裝方法

### 第一步 — 安裝 Npcap（必要）

從 https://npcap.com/#download 下載並安裝 **Npcap**。

> ⚠️ 安裝過程中，**必須**勾選 **"Install Npcap in WinPcap API-compatible Mode"**。

### 第二步 — 下載並安裝

👉 從 [Releases 頁面](https://github.com/taengu/A2Tools-DPS-Meter/releases) 取得最新 MSI 安裝程式。

### 第三步 — 啟動

以**系統管理員身分**執行 A2Tools DPS Meter。

**Linux**（透過 Proton 遊玩）：提供 Ubuntu/Debian（.deb）、Fedora/openSUSE（.rpm）、Bazzite、Arch/CachyOS/Manjaro 和 Steam Deck 套件 — 請參閱 **[Linux 指南](docs/linux.md)**（英文）。

[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?logo=ubuntu&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Debian](https://img.shields.io/badge/Debian-A81D33?logo=debian&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Linux Mint](https://img.shields.io/badge/Linux_Mint-87CF3E?logo=linuxmint&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Pop!_OS](https://img.shields.io/badge/Pop%21__OS-48B9C7?logo=popos&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Fedora](https://img.shields.io/badge/Fedora-51A2DA?logo=fedora&logoColor=white)](docs/linux.md#fedora) [![Bazzite](https://img.shields.io/badge/Bazzite-8A3FFC?logo=fedora&logoColor=white)](docs/linux.md#bazzite-silverblue-kinoite-aurora-bluefin) [![Steam Deck](https://img.shields.io/badge/Steam_Deck-1A9FFF?logo=steamdeck&logoColor=white)](docs/linux.md#steam-deck-steamos) [![openSUSE](https://img.shields.io/badge/openSUSE-73BA25?logo=opensuse&logoColor=white)](docs/linux.md#opensuse) [![Arch](https://img.shields.io/badge/Arch-1793D1?logo=archlinux&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![CachyOS](https://img.shields.io/badge/CachyOS-08A88A?logo=cachyos&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![Manjaro](https://img.shields.io/badge/Manjaro-35BF5C?logo=manjaro&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![EndeavourOS](https://img.shields.io/badge/EndeavourOS-7F3FBF?logo=endeavouros&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros)

## 從原始碼建構

```bash
npm install
npm run tauri build
```

開發模式：

```bash
npm run tauri dev
```

需要 [Rust](https://rustup.rs/)、[Node.js](https://nodejs.org/) (v18+) 和 [Npcap](https://npcap.com)。

## 社群

- 💬 **Discord：** https://discord.gg/Aion2Global
- 🌐 **網站：** https://a2tools.app

## 贊助支持

如果本工具對您有幫助，歡迎支持開發者！

- <img src="wechat.png" width="150">
- ☕ [Ko-fi](https://ko-fi.com/hiddencube)
- ☕ [愛發電](https://afdian.com/a/hiddencube)
- 🅿️ [PayPal](https://www.paypal.me/taengoo)
- 🎁 [加密貨幣捐贈](https://nowpayments.io/donation/thehiddencube)
- **BTC**: `1GexKhgVZPYRqpfCKydXLoNUXRRRUoAUwT`
- **ETH**: `0x38F0bc371A563A24eCa6034cFf77eB6173c7e3e7`
- **USDC**: `0xA9571Fc95666350f6DFFB8Fb80ee27eE7db46b56`

## 授權條款

[GPL-3.0](LICENSE)
