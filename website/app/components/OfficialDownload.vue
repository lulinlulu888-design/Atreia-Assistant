<script setup lang="ts">
import { Download } from 'lucide-vue-next'
import release from '../../release.json'

const pending = ref(false)
const failed = ref(false)
let requestId = ''

async function download(event: Event) {
  event.preventDefault()
  if (pending.value) return
  pending.value = true
  failed.value = false
  requestId ||= crypto.randomUUID()
  try {
    const response = await $fetch<{ download_url: string }>('/api/download', {
      method: 'POST', body: new URLSearchParams({ version: release.version, request_id: requestId }),
      headers: { Accept: 'application/json' }, timeout: 10000, retry: 0,
    })
    if (response.download_url !== release.url) throw new Error('Unexpected installer destination')
    window.location.assign(response.download_url)
    requestId = ''
    window.dispatchEvent(new Event('atreia-download'))
  } catch {
    failed.value = true
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="official-download">
    <form action="/api/download" method="post" @submit="download">
      <input type="hidden" name="version" :value="release.version">
      <button class="button primary" type="submit" :disabled="pending" :aria-busy="pending">
        <Download :size="20" />{{ pending ? '正在准备下载...' : `下载 Windows ${release.version}` }}
      </button>
    </form>
    <a v-if="failed" :href="release.url" class="download-fallback">下载服务暂不可用，直接下载</a>
  </div>
</template>
