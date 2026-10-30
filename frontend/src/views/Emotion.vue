<template>
  <div class="profile-page">
    <header class="topbar">
      <div class="tb-left">
        <router-link to="/" class="back">← 返回聊天</router-link>
        <span class="tb-title">我的情绪档案</span>
      </div>
      <div class="tb-range">
        <button v-for="r in ranges" :key="r.value"
                :class="{ active: days === r.value }" @click="setRange(r.value)">
          {{ r.label }}
        </button>
      </div>
    </header>

    <div class="container" v-if="loaded">
      <!-- 今日小结 -->
      <div class="card daily">
        <div class="daily-l">
          <div class="d-title">🌤 今日情绪小结</div>
          <p class="d-text">{{ daily.push_text }}</p>
          <p class="d-tip">💡 {{ daily.tip }}</p>
        </div>
        <div class="daily-mood">
          <div class="dm-num">{{ Math.round(daily.mood * 100) }}</div>
          <div class="dm-label">心情指数</div>
        </div>
      </div>

      <!-- 概览指标 -->
      <div class="stats">
        <div class="card stat">
          <div class="num">{{ profile.total_records }}</div><div class="lbl">情绪记录(次)</div>
        </div>
        <div class="card stat">
          <div class="num">{{ profile.dominant_emotion }}</div><div class="lbl">最常情绪</div>
        </div>
        <div class="card stat">
          <div class="num">{{ Math.round(profile.positive_ratio * 100) }}%</div><div class="lbl">正向占比</div>
        </div>
        <div class="card stat">
          <div class="num">{{ profile.streak_days }}</div><div class="lbl">连续记录(天)</div>
        </div>
      </div>

      <!-- 情绪日历热力图 -->
      <div class="card block">
        <h3>情绪日历 · 近 {{ heatWeeks }} 周</h3>
        <div class="heatmap">
          <div class="hm-weekdays">
            <span v-for="w in ['一','二','三','四','五','六','日']" :key="w">{{ w }}</span>
          </div>
          <div class="hm-grid">
            <div v-for="(cell, i) in heatCells" :key="i" class="hm-cell"
                 :class="{ empty: !cell.date }"
                 :style="{ background: cell.date ? moodColor(cell.mood) : 'transparent' }"
                 :title="cell.date ? `${cell.date} 心情 ${Math.round(cell.mood*100)} 记录${cell.count}次 ${cell.emotion||''}` : ''">
            </div>
          </div>
        </div>
        <div class="hm-legend">低 <span class="lg" style="background:#e8e1f4"></span>
          <span class="lg" style="background:#c9bff0"></span>
          <span class="lg" style="background:#a998e6"></span>
          <span class="lg" style="background:#8a76db"></span> 高</div>
      </div>

      <div class="two-col">
        <!-- 情绪分布 -->
        <div class="card block">
          <h3>情绪分布</h3>
          <div ref="pieEl" class="chart"></div>
        </div>
        <!-- 心情波动趋势 -->
        <div class="card block">
          <h3>心情波动趋势</h3>
          <div ref="lineEl" class="chart"></div>
        </div>
      </div>

      <div class="two-col">
        <!-- 时段分布 -->
        <div class="card block">
          <h3>易情绪波动的时段</h3>
          <div ref="barEl" class="chart"></div>
        </div>
        <!-- 呼吸放松 -->
        <div class="card block breathe-card">
          <h3>跟我一起放松一下</h3>
          <div class="breathe" :class="{ active: breathing }"
               :style="breatheStyle" @click="toggleBreathe">
            <span>{{ breathing ? breatheText : '点击开始' }}</span>
          </div>
          <p class="breathe-tip">跟着圆圈吸气 4 秒、屏息 4 秒、呼气 4 秒，慢慢让身体松下来。</p>
        </div>
      </div>

      <!-- 情绪波动事件 -->
      <div class="card block">
        <h3>情绪波动记录（时间 · 事件）</h3>
        <div v-if="profile.events.length" class="events">
          <div v-for="(e, i) in profile.events" :key="i" class="event">
            <span class="ev-time">{{ e.time }}</span>
            <span class="ev-emo">{{ emotionIcon(e.emotion) }} {{ e.emotion }}</span>
            <span v-if="e.intent" class="ev-intent">{{ e.intent }}</span>
            <span class="ev-trigger">{{ e.trigger || '（未记录具体事件）' }}</span>
          </div>
        </div>
        <p v-else class="no-data">还没有明显的情绪波动记录，继续记录就能看到啦。</p>
      </div>

      <!-- 角色陪伴 · 情绪联动 -->
      <div v-if="personaStats.items.length" class="card block">
        <h3>🎭 角色陪伴 · 情绪联动</h3>
        <p class="calib-note2">你和不同角色的聊天都会记录进同一份情绪档案，下面是陪你最多的小伙伴：</p>
        <div class="ps-list">
          <div v-for="p in personaStats.items" :key="p.persona_id" class="ps-item">
            <span class="ps-emoji">{{ p.emoji }}</span>
            <span class="ps-name">{{ p.name }}</span>
            <span class="ps-meta">{{ p.sessions }} 段对话 · {{ p.emotions }} 条情绪</span>
          </div>
        </div>
      </div>

      <!-- 个人情绪校准 -->
      <div class="card block">
        <div class="ins-head">
          <h3>🎯 个人情绪校准</h3>
          <span class="calib-count">已校准 {{ calibration.total }} 次</span>
        </div>
        <p class="calib-note2">{{ calibration.note }}</p>
        <div v-if="calibration.pairs.length" class="calib-pairs">
          <span v-for="(p, i) in calibration.pairs" :key="i" class="calib-pair">
            {{ p.from }} → {{ p.to }} <b>×{{ p.count }}</b>
          </span>
        </div>
        <div v-if="calibration.recent.length" class="calib-recent">
          <div v-for="(c, i) in calibration.recent" :key="i" class="cr-item">
            <span class="cr-time">{{ c.time }}</span>
            <span class="cr-change">{{ c.original }} → {{ c.corrected }}</span>
            <span class="cr-text">{{ c.text }}</span>
          </div>
        </div>
        <p v-else class="no-data">还没有校准记录。在聊天里点击消息下方的情绪标签即可校准。</p>
      </div>

      <!-- AI 情绪洞察 -->
      <div class="card block insight">
        <div class="ins-head">
          <h3>🤖 AI 情绪洞察</h3>
          <button class="gen-btn" :disabled="insightLoading" @click="genInsight">
            {{ insightLoading ? '分析中…' : (insight ? '重新生成' : '生成洞察') }}
          </button>
        </div>
        <div v-if="insight" class="ins-body">
          <p class="ins-text">{{ insight.text }}</p>
          <div class="ins-tags">
            <span v-for="(h, i) in insight.highlights" :key="i" class="ins-tag">{{ h }}</span>
          </div>
          <div class="ins-src">分析来源：{{ insight.source === 'llm' ? '大模型' : '本地规则引擎' }}</div>
        </div>
        <p v-else class="no-data">点击「生成洞察」，让 AI 帮你回顾这段时间的情绪起伏，并给出贴心建议。</p>
      </div>
    </div>

    <div v-else class="loading">情绪档案加载中…</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'

const ranges = [
  { label: '7天', value: 7 }, { label: '30天', value: 30 },
  { label: '90天', value: 90 }, { label: '一年', value: 365 },
]
const days = ref(90)
const profile = ref(null)
const daily = ref({ mood: 0.5, push_text: '', tip: '' })
const calibration = ref({ total: 0, pairs: [], recent: [], note: '', effective: false })
const personaStats = ref({ total_sessions: 0, items: [] })
const insight = ref(null)
const insightLoading = ref(false)
const loaded = ref(false)
const pieEl = ref(null), lineEl = ref(null), barEl = ref(null)
let pieChart, lineChart, barChart

const heatWeeks = 13
const heatCells = computed(() => {
  if (!profile.value) return []
  const map = {}
  for (const h of profile.value.heatmap) map[h.date] = h
  // 从本周一往回 heatWeeks 周
  const cells = []
  const today = new Date()
  const dow = (today.getDay() + 6) % 7 // 0=Mon
  const start = new Date(today)
  start.setDate(today.getDate() - dow - (heatWeeks - 1) * 7)
  for (let w = 0; w < heatWeeks; w++) {
    for (let d = 0; d < 7; d++) {
      const cur = new Date(start)
      cur.setDate(start.getDate() + w * 7 + d)
      const key = cur.toISOString().slice(0, 10)
      const rec = map[key]
      if (rec) cells.push({ date: key, mood: rec.mood, count: rec.count, emotion: rec.emotion })
      else cells.push({ date: null })
    }
  }
  return cells
})

function moodColor(m) {
  if (m >= 0.68) return '#8a76db'
  if (m >= 0.55) return '#a998e6'
  if (m >= 0.45) return '#c9bff0'
  return '#e8e1f4'
}
function emotionIcon(t) {
  return ({ 喜悦: '😊', 平静: '😌', 感恩: '🥰', 期待: '✨', 悲伤: '🥺',
   焦虑: '😰', 愤怒: '😠', 恐惧: '😨', 孤独: '🫂', 委屈: '😢', 低落: '🌧️', 中性: '🌤️' })[t] || '🌤️'
}

// 呼吸放松
const breathing = ref(false)
const breatheText = ref('吸气')
const breatheStyle = ref({})
let breatheTimer = null
function toggleBreathe() {
  if (breathing.value) {
    breathing.value = false
    clearTimeout(breatheTimer)
    breatheStyle.value = {}
    breatheText.value = '点击开始'
    return
  }
  breathing.value = true
  const cycle = () => {
    breatheText.value = '吸气'
    breatheStyle.value = { transform: 'scale(1.35)', transition: 'transform 4s ease-in-out' }
    breatheTimer = setTimeout(() => {
      breatheText.value = '屏息'
      breatheStyle.value = { transform: 'scale(1.35)', transition: 'transform 4s' }
      breatheTimer = setTimeout(() => {
        breatheText.value = '呼气'
        breatheStyle.value = { transform: 'scale(0.8)', transition: 'transform 4s ease-in-out' }
        breatheTimer = setTimeout(() => { if (breathing.value) cycle() }, 4000)
      }, 4000)
    }, 4000)
  }
  cycle()
}

function renderCharts() {
  const dist = profile.value.distribution || []
  pieChart = echarts.init(pieEl.value)
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll', textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie', radius: ['35%', '62%'], label: { show: false },
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      data: dist,
      color: ['#7c6fd0', '#f59fb0', '#6f9fdc', '#8fd0a8', '#e0a86f',
              '#c17bd6', '#f0b45a', '#6fb8c9', '#d67b9e', '#9b9b9b'],
    }],
  })

  const tl = profile.value.timeline || []
  lineChart = echarts.init(lineEl.value)
  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: tl.map((t) => t.date.slice(5)), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', min: 0, max: 1 },
    series: [{
      type: 'line', smooth: true, data: tl.map((t) => t.mood),
      lineStyle: { color: '#7c6fd0', width: 2 }, itemStyle: { color: '#7c6fd0' },
      areaStyle: { opacity: 0.08 },
    }],
  })

  const tod = profile.value.time_of_day || []
  barChart = echarts.init(barEl.value)
  barChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: tod.map((t) => t.slot), axisLabel: { fontSize: 1 } },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: tod.map((t) => t.count),
      itemStyle: { color: '#f59fb0', borderRadius: [6, 6, 0, 0] } }],
  })
}

function onResize() { pieChart?.resize(); lineChart?.resize(); barChart?.resize() }

async function loadProfile() {
  const [p, d, c, ps] = await Promise.all([
    api.get(`/emotion/profile?days=${days.value}`),
    api.get('/emotion/daily'),
    api.get('/emotion/calibration'),
    api.get('/emotion/persona-stats'),
  ])
  profile.value = p.data
  daily.value = d.data
  calibration.value = c.data
  personaStats.value = ps.data
  loaded.value = true
  await nextTick()
  pieChart?.dispose(); lineChart?.dispose(); barChart?.dispose()
  renderCharts()
}

async function setRange(v) {
  days.value = v
  await loadProfile()
}

async function genInsight() {
  insightLoading.value = true
  try {
    const { data } = await api.get(`/emotion/insight?days=${days.value}`)
    insight.value = data
  } catch (e) { /* 忽略 */ } finally {
    insightLoading.value = false
  }
}

onMounted(() => { loadProfile(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  clearTimeout(breatheTimer)
  pieChart?.dispose(); lineChart?.dispose(); barChart?.dispose()
})
</script>

<style scoped>
.profile-page { min-height: 100vh; background: var(--bg); }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
.tb-left { display: flex; align-items: center; gap: 16px; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }
.tb-range button {
  border: 1px solid var(--border); background: #fff; border-radius: 8px;
  padding: 6px 12px; margin-left: 6px; font-size: 13px; color: var(--text-soft);
}
.tb-range button.active { background: var(--primary); color: #fff; border-color: var(--primary); }

.container { max-width: 1080px; margin: 22px auto; padding: 0 20px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); }

.daily { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; gap: 20px;
  background: linear-gradient(135deg, #f3eeff, #fff2f5); }
.d-title { font-size: 15px; font-weight: 600; color: var(--primary); margin-bottom: 6px; }
.d-text { font-size: 14px; line-height: 1.7; }
.d-tip { font-size: 13px; color: var(--text-soft); margin-top: 6px; }
.daily-mood { text-align: center; flex-shrink: 0; }
.dm-num { font-size: 40px; font-weight: 700; color: var(--primary); }
.dm-label { font-size: 12px; color: var(--text-soft); }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }
.stat { padding: 16px; text-align: center; }
.stat .num { font-size: 22px; font-weight: 700; color: var(--primary); }
.stat .lbl { font-size: 12px; color: var(--text-soft); margin-top: 4px; }

.block { padding: 18px 20px; margin-top: 16px; }
.block h3 { font-size: 15px; margin-bottom: 14px; }

.heatmap { overflow-x: auto; }
.hm-weekdays { display: flex; gap: 4px; margin-left: 0; color: var(--text-soft); font-size: 11px; margin-bottom: 4px; }
.hm-weekdays span { width: 15px; text-align: center; }
.hm-grid { display: grid; grid-template-rows: repeat(7, 15px); grid-auto-flow: column; grid-auto-columns: 15px; gap: 4px; }
.hm-cell { width: 15px; height: 15px; border-radius: 3px; }
.hm-cell.empty { background: transparent !important; }
.hm-legend { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-soft); margin-top: 10px; }
.hm-legend .lg { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart { height: 260px; }

.breathe-card { display: flex; flex-direction: column; align-items: center; }
.breathe {
  width: 110px; height: 110px; border-radius: 50%; margin: 10px 0 16px;
  background: radial-gradient(circle, #efeaff, #d9cff5);
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; color: var(--primary); cursor: pointer; user-select: none;
  box-shadow: 0 6px 20px rgba(124,111,208,.2);
}
.breathe-tip { font-size: 12px; color: var(--text-soft); text-align: center; }

.events { display: flex; flex-direction: column; gap: 8px; }
.event { display: flex; align-items: center; gap: 10px; font-size: 13px; padding: 8px 12px; background: #faf8ff; border-radius: 10px; }
.ev-time { color: var(--text-soft); flex-shrink: 0; }
.ev-emo { flex-shrink: 0; }
.ev-intent { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--primary-soft); color: var(--primary); flex-shrink: 0; }
.ev-trigger { flex: 1; color: var(--text); }

.ins-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.gen-btn { border: none; background: var(--primary); color: #fff; border-radius: 8px; padding: 8px 16px; font-size: 13px; }
.gen-btn:disabled { opacity: .6; }
.ins-body .ins-text { font-size: 14px; line-height: 1.8; }
.ins-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.ins-tag { font-size: 12px; background: var(--primary-soft); color: var(--primary); padding: 4px 10px; border-radius: 12px; }
.ins-src { font-size: 12px; color: var(--text-soft); margin-top: 12px; }

.calib-count { font-size: 13px; color: var(--primary); background: var(--primary-soft);
  padding: 4px 12px; border-radius: 12px; }
.calib-note2 { font-size: 13px; color: var(--text-soft); margin-bottom: 12px; }
.calib-pairs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.calib-pair { font-size: 12px; background: #faf8ff; border: 1px solid var(--border);
  padding: 4px 10px; border-radius: 12px; }
.calib-pair b { color: var(--primary); }
.calib-recent { display: flex; flex-direction: column; gap: 6px; }
.cr-item { display: flex; align-items: center; gap: 10px; font-size: 13px;
  padding: 7px 12px; background: #faf8ff; border-radius: 9px; }
.cr-time { color: var(--text-soft); flex-shrink: 0; }
.cr-change { color: var(--primary); flex-shrink: 0; font-weight: 500; }
.cr-text { color: var(--text-soft); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ps-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
@media (max-width: 600px) { .ps-list { grid-template-columns: 1fr; } }
.ps-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; background: #faf8ff; border-radius: 10px; }
.ps-emoji { font-size: 20px; }
.ps-name { font-size: 14px; font-weight: 600; }
.ps-meta { font-size: 12px; color: var(--text-soft); margin-left: auto; }

.no-data { color: var(--text-soft); font-size: 14px; padding: 12px 0; }
.loading { text-align: center; color: var(--text-soft); padding: 80px 0; }

@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
}
</style>