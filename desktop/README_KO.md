# A2Tools DPS Meter

[![License](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/taengu/A2Tools-DPS-Meter)](https://github.com/taengu/A2Tools-DPS-Meter/pulls)

AION 2 실시간 DPS 미터 오버레이. 게임 네트워크 패킷을 캡처하여 데미지, 스킬, 전투 통계를 표시합니다.

**[최신 버전 다운로드](https://github.com/taengu/A2Tools-DPS-Meter/releases)** | **[A2Tools.app](https://a2tools.app)**

[English](README.md) | [简体中文](README_ZH.md) | [繁體中文](README_ZH-TW.md)

## 주요 기능

- 실시간 DPS 추적 (플레이어별 분석)
- 스킬별 데미지 분석 (치명타, 백어택, 패리, 더블, 퍼펙트)
- DOT (지속 피해) 추적
- 소환수 데미지 주인에게 합산
- 다양한 타겟 선택 모드 (보스, 마지막 타격, 전체, 트레인)
- DPS 차트 및 타임라인
- 보스전 자동 저장
- 핑 모니터링
- 다국어 지원 (한국어, 영어, 중국어 번체/간체)
- 항상 위 투명 오버레이
- 테마 및 커스터마이징

## 요구 사항

- **Windows 10/11** (x86_64)
- **[Npcap](https://npcap.com)** — 패킷 캡처에 필요
  - 설치 시 **"Install Npcap in WinPcap API-compatible Mode"** 체크
- **관리자 권한** — 패킷 캡처에 필요

## 설치

1. [Npcap](https://npcap.com) 설치 (WinPcap API 호환 모드 활성화)
2. [Releases](https://github.com/taengu/A2Tools-DPS-Meter/releases)에서 최신 MSI 설치 프로그램 다운로드
3. 설치 프로그램 실행
4. A2Tools DPS Meter 실행 (관리자 권한으로)

**Linux** (Proton으로 플레이): Ubuntu/Debian(.deb), Fedora/openSUSE(.rpm), Bazzite, Arch/CachyOS/Manjaro, Steam Deck용 패키지 — **[Linux 가이드](docs/linux.md)** (영어)를 참고하세요.

[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?logo=ubuntu&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Debian](https://img.shields.io/badge/Debian-A81D33?logo=debian&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Linux Mint](https://img.shields.io/badge/Linux_Mint-87CF3E?logo=linuxmint&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Pop!_OS](https://img.shields.io/badge/Pop%21__OS-48B9C7?logo=popos&logoColor=white)](docs/linux.md#ubuntu-debian-linux-mint-pop_os) [![Fedora](https://img.shields.io/badge/Fedora-51A2DA?logo=fedora&logoColor=white)](docs/linux.md#fedora) [![Bazzite](https://img.shields.io/badge/Bazzite-8A3FFC?logo=fedora&logoColor=white)](docs/linux.md#bazzite-silverblue-kinoite-aurora-bluefin) [![Steam Deck](https://img.shields.io/badge/Steam_Deck-1A9FFF?logo=steamdeck&logoColor=white)](docs/linux.md#steam-deck-steamos) [![openSUSE](https://img.shields.io/badge/openSUSE-73BA25?logo=opensuse&logoColor=white)](docs/linux.md#opensuse) [![Arch](https://img.shields.io/badge/Arch-1793D1?logo=archlinux&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![CachyOS](https://img.shields.io/badge/CachyOS-08A88A?logo=cachyos&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![Manjaro](https://img.shields.io/badge/Manjaro-35BF5C?logo=manjaro&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros) [![EndeavourOS](https://img.shields.io/badge/EndeavourOS-7F3FBF?logo=endeavouros&logoColor=white)](docs/linux.md#cachyos-arch-manjaro-endeavouros)

## 빌드

### 필수 구성 요소

- [Rust](https://rustup.rs/) (최신 안정 버전)
- [Node.js](https://nodejs.org/) (v18+)
- [Npcap](https://npcap.com) 설치

### 빌드

```bash
npm install
npm run tauri build
```

### 개발

```bash
npm run tauri dev
```

## 커뮤니티

- [Discord](https://discord.gg/Aion2Global)
- [A2Tools.app](https://a2tools.app)

## 후원

개발을 응원해 주세요!

- <img src="wechat.png" width="150">
- ☕ [Ko-fi](https://ko-fi.com/hiddencube)
- ☕ [아이파디엔 (爱发电)](https://afdian.com/a/hiddencube)
- 🅿️ [PayPal](https://www.paypal.me/taengoo)
- 🎁 [암호화폐 기부](https://nowpayments.io/donation/thehiddencube)
- **BTC**: `1GexKhgVZPYRqpfCKydXLoNUXRRRUoAUwT`
- **ETH**: `0x38F0bc371A563A24eCa6034cFf77eB6173c7e3e7`
- **USDC**: `0xA9571Fc95666350f6DFFB8Fb80ee27eE7db46b56`

## 라이선스

[GPL-3.0](LICENSE)
