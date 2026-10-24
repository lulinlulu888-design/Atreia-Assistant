<script setup lang="ts">
import { Activity, ArrowDown, ArrowRight, ArrowUpRight, Check, Download, Github, Languages, Radar, RotateCcw, ShieldCheck } from 'lucide-vue-next'
import release from '../release.json'
const repo = 'https://github.com/lulinlulu888-design/Atreia-Assistant'
const size = (release.size / 1024 / 1024).toFixed(1)
useHead({ script: [{ type: 'application/ld+json', innerHTML: JSON.stringify({
  '@context': 'https://schema.org', '@type': 'SoftwareApplication', name: '亚特雷亚助手',
  alternateName: 'Atreia Assistant', url: 'https://a2go.cc/', operatingSystem: 'Windows x64',
  applicationCategory: 'UtilitiesApplication', softwareVersion: release.version,
  downloadUrl: release.url, offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
}) }] })
const features = [
  { id: 'localization', index: '01 / LOCALIZATION', title: '用熟悉的语言，探索亚特雷亚。', text: 'Steam / Global 与 PURPLE 简体中文汉化，沿用国服《永恒之塔》的常用名称与术语。检测、安装、备份与还原，各有清晰的边界。', points: ['检测客户端与游戏目录', '安装前备份，支持还原', '持续核对人物、任务与物品译名'], image: 'localization-2.0.59.jpg', width: 603, height: 501, caption: '2.0.59 真实汉化窗口', icon: Languages },
  { id: 'combat', index: '02 / COMBAT ANALYTICS', title: '每一份输出，清楚呈现。', text: '独立的 DPS 战斗统计浮窗，查看伤害、治疗与技能贡献。战斗结束后，回看保存在本机的战斗记录。', points: ['伤害、治疗、护盾与技能明细', '战后回看本地历史记录', '按需开启，不自动上传战斗数据'], image: '', width: 0, height: 0, caption: '', icon: Activity },
  { id: 'radar', index: '03 / EXPLORATION', title: '隐藏宝箱，小窗随行。', text: '与 DPS 共用 Rust、Tauri 和 Npcap 技术路线的实验性雷达。独立开关，紧凑浮窗；识别连接、角色坐标与附近宝箱记录。', points: ['紧凑浮窗，独立外观与提示音设置', '点击开启直接启动，可随时暂停', '可与战斗统计、汉化窗口同时运行'], image: 'radar-2.0.59.jpg', width: 210, height: 240, caption: '2.0.59 真实雷达窗口 · 未开启采集', icon: Radar },
]
</script>

<template>
  <div>
    <a class="skip" href="#main">跳转到正文</a>
    <header class="header"><a class="brand" href="#top"><img src="/assets/brand/atreia-icon.png" width="38" height="38" alt=""><strong>亚特雷亚助手</strong></a><nav aria-label="主导航"><a href="#features">功能</a><a href="#updates">更新</a><a href="#help">指南</a><a href="#download">下载</a></nav><a :href="repo" class="source" aria-label="GitHub 开源仓库" title="GitHub 开源仓库"><Github :size="21" /><span>开源项目</span></a></header>
    <main id="main">
      <section id="top" class="hero"><img class="scenery" src="/assets/hero-atreia.jpg" width="1536" height="1024" alt="" fetchpriority="high"><div class="hero-copy"><img src="/assets/brand/atreia-emblem.png" width="96" height="96" alt="亚特雷亚助手羽翼标志"><p class="eyebrow">ATREIA ASSISTANT</p><h1>亚特雷亚助手</h1><p class="tagline">读懂世界，了解每一场战斗。</p><p class="intro">AION2《永恒之塔2》免费开源社区工具<br>简体中文汉化 · DPS 战斗统计 · 隐藏宝箱雷达</p><div class="actions"><a class="button primary" :href="release.url"><Download :size="20" />下载 Windows {{ release.version }}</a><a class="button secondary" href="#features">认识助手<ArrowRight :size="20" /></a></div><p class="release-meta">Windows x64 · {{ size }} MB · 整合安装包</p></div><a class="next" href="#updates" aria-label="查看最新更新"><ArrowDown :size="20" /></a></section>
      <section class="benefits" aria-label="助手特点"><div><Languages /><strong>熟悉的国服用语</strong></div><div><Activity /><strong>独立战斗统计</strong></div><div><RotateCcw /><strong>备份与还原</strong></div><div><ShieldCheck /><strong>数据在本机处理</strong></div></section>
      <section id="updates" class="updates wrap"><div><p class="eyebrow">LATEST RELEASE</p><h2>持续打磨，每一处细节。</h2></div><article><p class="version">{{ release.version }} <span>正式版本</span></p><h3>{{ release.title }}</h3><p>{{ release.summary }}</p><a :href="`${repo}/releases/tag/v${release.version}`">查看更新说明 <ArrowUpRight :size="17" /></a></article></section>
      <div id="features"><section v-for="(feature, index) in features" :id="feature.id" :key="feature.id" class="feature" :class="{ reverse: index % 2 === 1 }"><div class="feature-inner wrap"><div class="feature-copy"><p class="eyebrow">{{ feature.index }}</p><h2>{{ feature.title }}</h2><p>{{ feature.text }}</p><ul><li v-for="point in feature.points" :key="point"><Check :size="19" />{{ point }}</li></ul><p v-if="feature.id === 'radar'" class="notice">实验功能：角色定位已在本地实机观察成功；可见宝箱标记与距离尚未完成现场验收。普通步行不保证刷新坐标，旧定位会标注为参考位置。不承诺全地图扫描或游戏规则豁免。</p><a v-if="feature.id !== 'radar'" :href="`/guides/${feature.id}.html`">查看使用指南<ArrowRight :size="18" /></a></div><figure v-if="feature.image" class="screenshot" :class="{ compact: feature.id === 'radar' }"><img :src="`/assets/screenshots/${feature.image}`" :width="feature.width" :height="feature.height" :alt="feature.caption" loading="lazy"><figcaption>{{ feature.caption }}</figcaption></figure><div v-else class="combat-facts"><Activity :size="36" /><h3>专注战斗本身</h3><dl><div><dt>实时统计</dt><dd>伤害、治疗与技能贡献</dd></div><div><dt>战后回看</dt><dd>本地记录与技能明细</dd></div><div><dt>各自独立</dt><dd>雷达、统计与汉化同时运行</dd></div></dl></div></div></section></div>
      <section class="workspace wrap"><div><p class="eyebrow">YOUR ADVENTURE, YOUR WAY</p><h2>各自独立，也能并肩。</h2><p>从同一个主界面出发，只开启你需要的功能。关闭主窗口可留在系统托盘，已开启的独立工具继续运行。</p></div><figure class="screenshot"><img src="/assets/screenshots/launcher-2.0.59.jpg" width="683" height="531" alt="2.0.59 真实软件主界面，三个独立功能入口" loading="lazy"><figcaption>2.0.59 真实运行截图 · 主界面</figcaption></figure></section>
      <section id="help" class="help wrap"><p class="eyebrow">GET STARTED</p><h2>开始下一次冒险。</h2><div class="guide-links"><a href="/guides/localization.html"><Languages /><span><strong>汉化安装与还原</strong><small>Steam / Global · PURPLE</small></span><ArrowUpRight /></a><a href="/guides/combat.html"><Activity /><span><strong>DPS 统计使用指南</strong><small>Npcap · 独立浮窗 · 本地记录</small></span><ArrowUpRight /></a><a :href="`${repo}/issues`"><Github /><span><strong>问题反馈</strong><small>向开源社区提交问题</small></span><ArrowUpRight /></a></div></section>
      <section id="download" class="download"><div class="wrap"><img src="/assets/brand/atreia-emblem.png" width="68" height="68" alt=""><div><p class="eyebrow">READY FOR YOUR NEXT ADVENTURE</p><h2>下载亚特雷亚助手</h2><p>免费、开源，为每一次冒险。</p></div><a class="button primary" :href="release.url"><Download :size="20" />下载 Windows {{ release.version }}</a></div></section>
    </main><footer class="wrap"><span>亚特雷亚助手 · 非官方社区工具</span><a :href="repo">GitHub 开源项目</a><p>AION2 及相关游戏商标归其权利人所有。本工具不隶属于游戏运营商。</p></footer>
  </div>
</template>
