<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>角色运营</h1>
        <p>{{ list.length }} 位角色 · 立绘为原创同人演绎（AI 绘制），非官方素材</p>
      </div>
      <div class="a-head-actions">
        <select v-model="cat" class="a-select">
          <option value="">全部分类</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="sort" class="a-select">
          <option value="sessions">按会话数</option>
          <option value="messages">按消息数</option>
          <option value="emotions">按情绪记录</option>
          <option value="name">按名称</option>
        </select>
        <button class="a-btn ghost" @click="load">刷新</button>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd"><h3>角色使用总览 <span class="sub">会话数</span></h3><span class="a-tag">{{ list.length }} 位</span></div>
        <div class="a-card-bd"><div ref="barEl" class="a-chart sm"></div></div>
      </div>
      <div class="a-card">
        <div class="a-card-hd"><h3>分类分布</h3></div>
        <div class="a-card-bd">
          <div v-for="c in categoryStats" :key="c.name" class="cat-row">
            <div class="cat-name">{{ c.name }}</div>
            <div class="a-bar cat-bar"><i :style="{ width: c.pct + '%' }"></i></div>
            <div class="cat-num">{{ c.count }} 位 · {{ c.sessions }} 会话</div>
          </div>
        </div>
      </div>
    </div>

    <div class="a-card">
      <div class="a-card-hd">
        <div class="a-toolbar">
          <div class="a-search"><input v-model="kw" class="a-input" placeholder="搜索角色 / 作品 / 标签" /></div>
          <span class="a-tag">{{ filtered.length }} 个结果</span>
        </div>
      </div>
      <div class="a-card-bd">
        <div class="p-grid">
          <div v-for="p in filtered" :key="p.persona_id" class="p-card">
            <div class="p-cover">
              <img v-if="p.avatar" :src="p.avatar" :alt="p.name" loading="lazy" />
              <span class="p-cat">{{ p.category }}</span>
            </div>
            <div class="p-body">
              <div class="p-name">{{ p.name }}<span>{{ p.work }}</span></div>
              <div class="p-tag">{{ p.emoji }} {{ p.tagline || p.category }}</div>
              <div class="p-stats">
                <div><b>{{ p.sessions }}</b><span>会话</span></div>
                <div><b>{{ p.messages }}</b><span>消息</span></div>
                <div><b>{{ p.emotions }}</b><span>情绪</span></div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!filtered.length" class="a-empty">没有匹配的角色</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../../api'

const list = ref([])
const cat = ref('')
const sort = ref('sessions')
const kw = ref('')
const barEl = ref(null)
let barChart = null
const categories = ['治愈陪伴', '趣味互动', '3D 陪伴', '动漫角色', '游戏角色']

const filtered = computed(() => {
  let arr = list.value.filter((p) => {
    if (cat.value && p.category !== cat.value) return false
    if (!kw.value) return true
    const k = kw.value.toLowerCase()
    return [p.name, p.work, p.category].some((s) => (s || '').toLowerCase().includes(k))
  })
  arr = [...arr]
  if (sort.value === 'name') arr.sort((a, b) => a.name.localeCompare(b.name, 'zh'))
  else arr.sort((a, b) => (b[sort.value] || 0) - (a[sort.value] || 0))
  return arr
})

const categoryStats = computed(() => {
  const totalSessions = Math.max(1, list.value.reduce((s, p) => s + p.sessions, 0))
  return categories.map((c) => {
    const arr = list.value.filter((p) => p.category === c)
    const sessions = arr.reduce((s, p) => s + p.sessions, 0)
    return { name: c, count: arr.length, sessions, pct: Math.round((sessions / totalSessions) * 100) }
  })
})

function renderBar() {
  if (!barEl.value) return
  barChart = barChart || echarts.init(barEl.value)
  const top = [...list.value].sort((a, b) => a.sessions - b.sessions).slice(-10)
  barChart.setOption({
    grid: { left: 66, right: 24, top: 10, bottom: 18 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f6f2fd' } }, axisLabel: { fontSize: 11, color: '#9a94ab' } },
    yAxis: { type: 'category', data: top.map((p) => p.name), axisTick: { show: false }, axisLine: { lineStyle: { color: '#ece7f6' } }, axisLabel: { fontSize: 11, color: '#6f6885' } },
    series: [{
      type: 'bar', data: top.map((p) => p.sessions), barWidth: 10,
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#b9aaff' }, { offset: 1, color: '#7c6fd0' },
        ]),
      },
    }],
  })
}

async function load() {
  const { data } = await api.get('/admin/personas')
  list.value = data
  await nextTick()
  renderBar()
}
function onResize() { barChart?.resize() }
onMounted(() => { load(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); barChart?.dispose() })
</script>

<style scoped>
.cat-row { display: flex; align-items: center; gap: 12px; padding: 9px 0; }
.cat-name { width: 66px; font-size: 12.5px; color: #5c5573; flex: none; }
.cat-bar { flex: 1; }
.cat-num { width: 108px; text-align: right; font-size: 11.5px; color: var(--text-soft); flex: none; }
.p-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
@media (max-width: 1280px) { .p-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 900px) { .p-grid { grid-template-columns: repeat(2, 1fr); } }
</style>