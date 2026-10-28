<script setup lang="ts">
const count = ref<number | null>(null)
const unavailable = ref(false)
async function refresh() {
  try {
    const response = await $fetch<{ source: string; count: number; metric: string }>('/api/downloads', { timeout: 8000, retry: 0 })
    if (response.source !== 'official_website' || response.metric !== 'download_clicks' || !Number.isSafeInteger(response.count) || response.count < 0) throw new Error('Invalid website count')
    count.value = response.count
    unavailable.value = false
  } catch {
    unavailable.value = true
  }
}
onMounted(() => { refresh(); window.addEventListener('atreia-download', refresh) })
onUnmounted(() => window.removeEventListener('atreia-download', refresh))
</script>

<template>
  <p class="website-download-count" role="status" aria-live="polite" title="自2026年10月28日起统计官网下载按钮点击；不含历史 GitHub 下载及 S3 直链，不代表下载完成次数。">
    <span v-if="count !== null && !unavailable">下载点击次数 <strong>{{ count.toLocaleString('zh-CN') }}</strong></span>
    <span v-else>{{ unavailable ? '下载统计暂不可用' : '下载统计加载中...' }}</span>
  </p>
</template>
