export default defineNuxtConfig({
  compatibilityDate: '2026-10-22',
  devtools: { enabled: false },
  css: ['~/assets/main.css', '~/assets/polish.css', '~/assets/downloads.css'],
  app: { head: {
    htmlAttrs: { lang: 'zh-CN' },
    title: '亚特雷亚助手官网 | AION2 汉化、DPS统计与宝箱雷达',
    meta: [
      { name: 'description', content: '亚特雷亚助手，面向永恒之塔2（AION2）玩家的免费开源 Windows 工具。Steam 与 PURPLE 简体中文汉化、DPS 战斗统计与实验性隐藏宝箱雷达。' },
      { name: 'theme-color', content: '#f4f8f7' },
      { property: 'og:title', content: '亚特雷亚助手' },
      { property: 'og:description', content: '读懂世界，了解每一场战斗。AION2 简体中文汉化、DPS 统计与隐藏宝箱雷达。' },
      { property: 'og:image', content: 'https://a2go.cc/assets/hero-atreia.jpg' },
      { property: 'og:url', content: 'https://a2go.cc/' },
      { name: 'twitter:card', content: 'summary_large_image' },
    ],
    link: [
      { rel: 'icon', type: 'image/png', href: '/assets/brand/atreia-icon.png' },
      { rel: 'canonical', href: 'https://a2go.cc/' },
    ],
  } },
  nitro: { preset: 'static', prerender: { crawlLinks: true } },
})
