<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>情绪分析</h1>
        <p>平台情绪分布、变化趋势与高风险识别记录</p>
      </div>
      <div class="a-head-actions">
        <select v-model="days" class="a-select" @change="load">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
          <option :value="365">近一年</option>
        </select>
        <button class="a-btn ghost" @click="load">刷新</button>
      </div>
    </div>

    <div class="a-kpis">
      <div class="a-kpi" style="--kpi-tint:#f1ecff;--kpi-color:#7c6fd0">
        <div class="k-top"><span class="k-ico">◔</span>情绪记录</div>
        <div class="k-num">{{ records.length }}</div>
        <div class="k-foot">统计周期内</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#ffeef4;--kpi-color:#e0618a">
        <div class="k-top"><span class="k-ico">◑</span>负向占比</div>
        <div class="k-num">{{ negRatio }}%</div>
        <div class="k-foot">悲伤 / 焦虑 / 愤怒等</div>
      </div>
      <div class="a-kpi warn" style="--kpi-tint:#fff4e8;--kpi-color:#d68a2e">
        <div class="k-top"><span class="k-ico">!</span>高风险记录</div>
        <div class="k-num">{{ stats.totals?.high_risk ?? 0 }}</div>
        <div class="k-foot">近 {{ days }} 天</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b">
        <div class="k-top"><span class="k-ico">✦</span>用户校准</div>
        <div class="k-num">{{ stats.totals?.calibrations ?? 0 }}</div>
        <div class="k-foot">用户主动纠正次数</div>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd">
          <h3>情绪趋势 <span class="sub">平均强度 / 记录条数</span></h3>
          <span class="a-tag blue">近 {{ days }} 天</span>
        </div>
        <div class="a-card-bd"><div ref="trendEl" class="a-chart"></div></div>
      </div>
      <div class="a-card">
        <div class="a-card-hd"><h3>情绪构成</h3></div>
        <div class="a-card-bd"><div ref="pieEl" class="a-chart"></div></div>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd">
          <h3>最新情绪记录</h3>
          <span class="a-tag">{{ filtered.length }} 条</span>
        </div>
        <div class="a-card-bd" style="padding-top:8px">
          <div class="a-toolbar" style="margin-bottom:8px">
            <select v-model="emoFilter" class="a-select">
              <option value="">全部情绪</option>
              <option v-for="e in emotionTypes" :key="e" :value="e">{{ e }}</option>
            </select>
            <div class="a-search"><input v-model="kw" class="a-input" placeholder="搜索触发原话" style="width:180px" /></div>
          </div>
          <div class="rec-list">
            <div v-for="r in filtered.slice(0, 60)" :key="r.id" class="rec-row">
              <span class="rec-emo" :class="polar(r)">{{ r.emotion_type }}</span>
              <div class="rec-main">
                <b>{{ userName(r.user_id) }}</b>
                <span class="rec-trigger">{{ r.trigger || '—' }}</span>
              </div>
              <span class="rec-score" :class="polar(r)">{{ (r.score ?? 0).toFixed(2) }}</span>
              <span class="rec-time">{{ fmtTime(r.created_at) }}</span>
            </div>
            <div v-if="!filtered.length" class="a-empty">暂无记录</div>
          </div>
        </div>
      </div>

      <div class="a-card">
        <div class="a-card-hd"><h3>需重点关注用户</h3><span class="a-tag danger">近 {{ days }} 天</span></div>
        <div class="a-card-bd risk-list">
          <div v-for="r in stats.risk_users" :key="r.user_id" class="risk-row">
            <div class="risk-ava">{{ (r.nickname || '友')[0] }}</div>
            <div class="risk-meta"><b>{{ r.nickname || '未命名' }}</b><span>{{ r.phone }}</span></div>
            <div class="risk-bar"><i :style="{ width: riskPct(r.count) }"></i></div>
            <span class="a-tag danger">{{ r.count }} 次</span>
          </div>
          <div v-if="!stats.risk_users?.length" class="a-empty"><span class="e-ico">☘</span>该周期内无明显高风险</div>
          <p class="risk-note">提示：高风险识别用于提醒运营关注，不构成医学判断，请以关怀与转介专业帮助为主。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../../api'

const days = ref(7)
const records = ref([])
const stats = ref({})
const usersMap = ref({})
const kw = ref('')
const emoFilter = ref('')
const trendEl = ref(null)
const pieEl = ref(null)
let trendChart = null
let pieChart = null

const emotionTypes = ['喜悦', '平静', '感恩', '期待', '悲伤', '焦虑', '愤怒', '恐惧', '孤独', '委屈', '低落', '中性']
const negRatio = computed(() => {
  if (!records.value.length) return 0
  const neg = records.value.filter((r) => r.polarity < 0).length
  return Math.round((neg / records.value.length) * 100)
})
const filtered = computed(() => records.value.filter((r) => {
  if (emoFilter.value && r.emotion_type !== emoFilter.value) return false
  if (kw.value && !(r.trigger || '').includes(kw.value)) return false
  return true
}))
const maxRisk = computed(() => Math.max(1, ...(stats.value.risk_users || []).map((r) => r.count)))
const riskPct = (n) => `${Math.round((n / maxRisk.value) * 100)}%`
const userName = (id) => usersMap.value[id] || `用户 ${id}`
const polar = (r) => (r.polarity > 0 ? 'pos' : r.polarity < 0 ? 'neg' : 'neu')
const fmtTime = (s) => (s ? new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')

function render() {
  const tl = stats.value.emotion_trend || []
  if (trendEl.value) {
    trendChart = trendChart || echarts.init(trendEl.value)
    const byDate = {}
    records.value.forEach((r) => {
      const d = (r.created_at || '').slice(0, 10)
      if (d) byDate[d] = (byDate[d] || 0) + 1
    })
    trendChart.setOption({
      grid: { left: 40, right: 44, top: 34, bottom: 26 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0, itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#8b869b' } },
      xAxis: { type: 'category', data: tl.map((x) => x.date.slice(5)), axisTick: { show: false }, axisLine: { lineStyle: { color: '#ece7f6' } }, axisLabel: { fontSize: 11, color: '#9a94ab' } },
      yAxis: [
        { type: 'value', min: 0, max: 1, name: '强度', nameTextStyle: { fontSize: 10, color: '#9a94ab' }, splitLine: { lineStyle: { color: '#f6f2fd' } }, axisLabel: { fontSize: 11, color: '#9a94ab' } },
        { type: 'value', name: '条数', nameTextStyle: { fontSize: 10, color: '#9a94ab' }, splitLine: { show: false }, axisLabel: { fontSize: 11, color: '#9a94ab' } },
      ],
      series: [
        { name: '平均强度', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5, data: tl.map((x) => x.avg_score), lineStyle: { width: 2.4, color: '#7c6fd0' }, itemStyle: { color: '#7c6fd0' }, areaStyle: { color: 'rgba(124,111,208,.16)' } },
        { name: '记录条数', type: 'bar', yAxisIndex: 1, barWidth: 8, data: tl.map((x) => byDate[x.date] || 0), itemStyle: { color: 'rgba(240,160,182,.75)', borderRadius: [4, 4, 0, 0] } },
      ],
    })
  }
  if (pieEl.value) {
    pieChart = pieChart || echarts.init(pieEl.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { type: 'scroll', orient: 'vertical', right: 0, top: 'middle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#8b869b' } },
      series: [{
        type: 'pie', radius: ['52%', '74%'], center: ['36%', '52%'],
        itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 5 },
        label: { show: false },
        data: stats.value.emotion_distribution || [],
      }],
    })
  }
}

async function load() {
  const [s, e, u] = await Promise.all([
    api.get(`/admin/stats?days=${days.value}`),
    api.get(`/admin/emotions?days=${days.value}`),
    api.get('/admin/users?page_size=200'),
  ])
  stats.value = s.data
  records.value = e.data
  usersMap.value = Object.fromEntries(u.data.items.map((x) => [x.id, x.nickname]))
  await nextTick()
  render()
}

function onResize() { trendChart?.resize(); pieChart?.resize() }
onMounted(() => { load(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  trendChart?.dispose(); pieChart?.dispose()
})
</script>

<style scoped>
.rec-list { max-height: 420px; overflow-y: auto; }
.rec-row { display: flex; align-items: center; gap: 10px; padding: 9px 2px; border-bottom: 1px dashed #f3eefc; font-size: 12.5px; }
.rec-row:last-child { border-bottom: none; }
.rec-emo { width: 52px; text-align: center; padding: 3px 0; border-radius: 7px; font-size: 12px; flex: none; }
.rec-emo.pos { background: #e9f8ef; color: #2f9e6b; }
.rec-emo.neg { background: #fdeef0; color: #d9536b; }
.rec-emo.neu { background: #f4f1fa; color: #7d7694; }
.rec-main { flex: 1; min-width: 0; }
.rec-main b { font-weight: 600; margin-right: 6px; }
.rec-trigger { color: var(--text-soft); display: inline-block; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
.rec-score { font-weight: 600; width: 34px; text-align: right; }
.rec-score.pos { color: #2f9e6b; }
.rec-score.neg { color: #d9536b; }
.rec-score.neu { color: #8b869b; }
.rec-time { color: var(--text-soft); font-size: 11.5px; width: 86px; text-align: right; flex: none; }
.risk-list { display: flex; flex-direction: column; gap: 12px; }
.risk-row { display: flex; align-items: center; gap: 10px; }
.risk-ava { width: 30px; height: 30px; border-radius: 50%; background: #fdeef0; color: #d9536b; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; flex: none; }
.risk-meta { width: 110px; flex: none; }
.risk-meta b { display: block; font-size: 13px; }
.risk-meta span { font-size: 11.5px; color: var(--text-soft); }
.risk-bar { flex: 1; height: 6px; background: #f8eef1; border-radius: 4px; overflow: hidden; }
.risk-bar i { display: block; height: 100%; background: linear-gradient(90deg, #f3a9b8, #d9536b); border-radius: 4px; }
.risk-note { font-size: 11.5px; color: var(--text-soft); background: #faf8ff; padding: 8px 10px; border-radius: 8px; line-height: 1.6; margin-top: 4px; }
</style>