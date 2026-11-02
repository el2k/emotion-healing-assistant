<template>
  <div class="kd-page">
    <header class="topbar">
      <router-link to="/knowledge" class="back">← 返回知识库</router-link>
    </header>

    <article v-if="a" class="article card">
      <div class="a-meta">
        <span class="a-cat" :style="{ background: '#f4f0ff', color: '#6f63b8' }">{{ a.category }}</span>
        <span class="a-read">⏱ 约 {{ a.read_minutes }} 分钟</span>
        <span class="a-views">{{ a.views }} 次阅读</span>
      </div>
      <h1 class="a-title">{{ a.title }}</h1>
      <p class="a-summary">{{ a.summary }}</p>

      <div class="a-content">
        <template v-for="(block, i) in blocks" :key="i">
          <h3 v-if="block.kind === 'h'">{{ block.text }}</h3>
          <li v-else-if="block.kind === 'li'">{{ block.text }}</li>
          <p v-else>{{ block.text }}</p>
        </template>
      </div>

      <div class="a-tags">
        <span v-for="t in a.tags" :key="t">#{{ t }}</span>
      </div>
      <div class="a-source">📌 {{ a.source }}</div>

      <div class="a-warn">
        本文为心理健康科普内容，不构成诊疗建议。如果你正在经历难以承受的痛苦，
        请联系全国心理援助热线 <b>12356</b>（24 小时）或前往医院心理科。
      </div>
    </article>
    <div v-else class="loading">加载中…</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const a = ref(null)

/* markdown-lite 渲染：## 标题 / - 列表 / 普通段落 */
const blocks = computed(() => {
  const out = []
  for (const raw of (a.value?.content || '').split('\n')) {
    const line = raw.trim()
    if (!line) continue
    if (line.startsWith('## ')) out.push({ kind: 'h', text: line.slice(3) })
    else if (line.startsWith('- ')) out.push({ kind: 'li', text: line.slice(2) })
    else out.push({ kind: 'p', text: line })
  }
  return out
})

onMounted(async () => {
  const { data } = await api.get(`/knowledge/articles/${route.params.id}`)
  a.value = data
})
</script>

<style scoped>
.kd-page { min-height: 100vh; background: var(--bg); padding-bottom: 60px; }
.topbar { padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.article { max-width: 780px; margin: 26px auto 0; padding: 34px 40px; }
.a-meta { display: flex; align-items: center; gap: 12px; font-size: 12.5px; color: var(--text-soft); }
.a-cat { font-size: 11.5px; padding: 3px 11px; border-radius: 20px; font-weight: 600; }
.a-title { font-size: 26px; line-height: 1.45; margin: 14px 0 10px; }
.a-summary { font-size: 14.5px; color: var(--text-soft); line-height: 1.8; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
.a-content { margin-top: 20px; }
.a-content h3 { font-size: 18px; margin: 22px 0 10px; color: #4a4360; }
.a-content p { font-size: 14.5px; line-height: 2.0; color: #3a3545; margin-bottom: 12px; }
.a-content li { font-size: 14.5px; line-height: 1.95; color: #3a3545; margin: 0 0 10px 20px; }
.a-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
.a-tags span { font-size: 12px; color: var(--primary); background: var(--primary-soft); padding: 3px 10px; border-radius: 14px; }
.a-source { font-size: 12.5px; color: var(--text-soft); margin-top: 14px; line-height: 1.7; }
.a-warn { font-size: 12.5px; color: #a85464; background: #fdf3f5; border: 1px dashed #f0cdd4; border-radius: 10px; padding: 12px 14px; margin-top: 20px; line-height: 1.8; }
.a-warn b { color: #d9536b; }
.loading { text-align: center; color: var(--text-soft); padding: 100px 0; }
@media (max-width: 640px) { .article { padding: 24px 20px; } }
</style>