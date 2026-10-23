<script setup lang="ts">
const count = ref<number | null>(null)
const updatedAt = ref('')
const failed = ref(false)
const stale = ref(false)
onMounted(async () => {
  try {
    const result = await $fetch<{ source: string; count: number; updated_at: string }>('/stats/downloads.json', { timeout: 8000, retry: 0 })
    const timestamp = Date.parse(result.updated_at)
    if (result.source !== 'github' || !Number.isSafeInteger(result.count) || result.count < 0 || !Number.isFinite(timestamp) || timestamp > Date.now() + 300000) throw new Error('Invalid statistics')
    count.value = result.count
    updatedAt.value = new Date(timestamp).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
    stale.value = Date.now() - timestamp > 3600000
  } catch {
    failed.value = true
  }
})
</script>

<template>
  <p class="download-count" role="status" aria-live="polite">
    <span v-if="count !== null">GitHub 累计下载 <strong>{{ count.toLocaleString('zh-CN') }}</strong> 次<span v-if="stale">（缓存）</span></span>
    <span v-else>{{ failed ? '下载统计暂不可用' : '下载统计加载中...' }}</span>
    <small>仅统计 GitHub 正式安装包，不含 S3<span v-if="updatedAt"> · 更新于 {{ updatedAt }}（北京时间）</span></small>
  </p>
</template>
