<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>数据看板</h1>
        <p>平台整体运行情况 · 数据更新于 {{ updatedAt }}</p>
      </div>
      <div class="a-head-actions">
        <select v-model="days" class="a-select" @change="load">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
        </select>
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <!-- 核心指标 -->
    <div class="a-kpis">
      <div v-for="k in kpis" :key="k.label" class="a-kpi" :class="{ warn: k.warn }"
           :style="{ '--kpi-tint': k.tint, '--kpi-color': k.color }">
        <div class="k-top"><span class="k-ico"><AdmIcon :name="k.icon" :size="15" /></span>{{ k.label }}</div>
        <div class="k-num">{{ k.value }}</div>
        <div class="k-foot">{{ k.foot }}</div>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd">
          <h3>消息与活跃趋势 <span class="sub">按天统计</span></h3>
          <span class="a-tag blue">近 {{ days }} 天</span>
        </div>
        <div class="a-card-bd"><div ref="trendEl" class="a-chart"></div></div>
      </div>

      <div class="a-card">
        <div class="a-card-hd"><h3>情绪分布</h3><span class="a-tag">共 {{ emotionTotal }} 条</span></div>
        <div class="a-card-bd"><div ref="pieEl" class="a-chart"></div></div>
      </div>
    </div>

    <div class="a-grid-3">
      <!-- 风险用户 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>需重点关注 <span class="sub">近 {{ days }} 天</span></h3>
          <router-link to="/admin/emotions" class="link">查看全部</router-link>
        </div>
        <div class="a-card-bd risk-list">
          <div v-for="r in data.risk_users" :key="r.user_id" class="risk-row">
            <div class="risk-ava">{{ (r.nickname || '友')[0] }}</div>
            <div class="risk-meta">
              <b>{{ r.nickname || '未命名用户' }}</b>
              <span>{{ r.phone }}</span>
            </div>
            <span class="a-tag danger">{{ r.count }} 次</span>
          </div>
          <div v-if="!data.risk_users?.length" class="a-empty"><span class="e-ico">☘</span>近 {{ days }} 天没有高风险记录</div>
        </div>
      </div>

      <!-- 角色热度 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>角色热度 TOP</h3>
          <router-link to="/admin/personas" class="link">角色运营</router-link>
        </div>
        <div class="a-card-bd">
          <div v-for="(p, i) in data.personas_top" :key="p.id" class="rank-row">
            <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
            <img v-if="p.avatar" :src="p.avatar" class="rank-ava" alt="" />
            <div class="rank-meta">
              <b>{{ p.name }}</b>
              <div class="a-bar"><i :style="{ width: pct(p.sessions, maxPersonaSessions) }"></i></div>
            </div>
            <span class="rank-num">{{ p.sessions }}</span>
          </div>
          <div v-if="!data.personas_top?.length" class="a-empty">暂无角色会话</div>
        </div>
      </div>

      <!-- 最新用户 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>最新注册</h3>
          <router-link to="/admin/users" class="link">用户管理</router-link>
        </div>
        <div class="a-card-bd">
          <div v-for="u in data.recent_users" :key="u.id" class="user-row">
            <img v-if="isImg(u.avatar)" :src="u.avatar" class="rank-ava round" alt="" />
            <div v-else class="rank-ava round letter">{{ (u.nickname || '友')[0] }}</div>
            <div class="rank-meta">
              <b>{{ u.nickname || '未命名' }}</b>
              <span class="phone">{{ u.phone }}</span>
            </div>
            <span class="a-tag" :class="u.role === 'admin' ? 'warn' : ''">{{ u.role === 'admin' ? '管理员' : '用户' }}</span>
          </div>
          <div v-if="!data.recent_users?.length" class="a-empty">暂无用户</div>
        </div>
      </div>
    </div>

    <!-- 今日概览 -->
    <div class="a-card today">
      <div class="today-title">今日</div>
      <div class="today-item"><b>{{ data.today?.new_users ?? 0 }}</b><span>新增用户</span></div>
      <div class="today-item"><b>{{ data.today?.messages ?? 0 }}</b><span>消息数</span></div>
      <div class="today-item"><b>{{ data.today?.active_users ?? 0 }}</b><span>活跃用户</span></div>
      <div class="today-item"><b>{{ data.totals.calibrations }}</b><span>累计校准</span></div>
      <div class="today-note">系统运行正常 · {{ data.system?.version }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import AdmIcon from '../../components/AdmIcon.vue'
import { api } from '../../api'

const days = ref(7)
const loading = ref(false)
const data = reactive({
  totals: {}, today: {}, series: [], emotion_distribution: [],
  risk_users: [], personas_top: [], recent_users: [], system: {},
})
const trendEl = ref(null)
const pieEl = ref(null)
let trendChart = null
let pieChart = null
const updatedAt = ref('—')

const emotionTotal = computed(() =>
  (data.emotion_distribution || []).reduce((s, x) => s + x.value, 0))
const maxPersonaSessions = computed(() =>
  Math.max(1, ...(data.personas_top || []).map((p) => p.sessions)))
const pct = (v, max) => `${Math.round((v / max) * 100)}%`
const isImg = (v) => !!v && (v.startsWith('/uploads/') || v.startsWith('http') || v.startsWith('data:'))

const kpis = computed(() => [
  { label: '注册用户', value: data.totals.users ?? '-', icon: 'users', tint: '#f0ecff', color: '#7c6fd0',
    foot: `今日新增 ${data.today?.new_users ?? 0}` },
  { label: '对话会话', value: data.totals.sessions ?? '-', icon: 'layers', tint: '#e9f6ff', color: '#3d8fd0',
    foot: `累计消息 ${data.totals.messages ?? 0}` },
  { label: '情绪记录', value: data.totals.emotions ?? data.emotion_distribution?.reduce((s, x) => s + x.value, 0) ?? 0, icon: 'heart',
    tint: '#ffeef4', color: '#e0618a', foot: `今日消息 ${data.today?.messages ?? 0}` },
  { label: `近 ${days.value} 天高风险`, value: data.totals.high_risk ?? 0, icon: 'spark', tint: '#fff4e8', color: '#d68a2e',
    foot: '需人工关注记录', warn: true },
])

function renderTrend() {
  if (!trendEl.value) return
  trendChart = trendChart || echarts.init(trendEl.value)
  const s = data.series || []
  trendChart.setOption({
    grid: { left: 38, right: 16, top: 36, bottom: 28 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#8b869b' } },
    xAxis: {
      type: 'category',
      data: s.map((x) => x.date.slice(5)),
      axisLine: { lineStyle: { color: '#ece7f6' } },
      axisTick: { show: false },
      axisLabel: { color: '#9a94ab', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f6f2fd' } },
      axisLabel: { color: '#9a94ab', fontSize: 11 },
    },
    series: [
      {
        name: '消息数', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
        data: s.map((x) => x.messages),
        lineStyle: { width: 2.4, color: '#7c6fd0' },
        itemStyle: { color: '#7c6fd0' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(124,111,208,.22)' },
            { offset: 1, color: 'rgba(124,111,208,0)' },
          ]),
        },
      },
      {
        name: '活跃用户', type: 'line', smooth: true, symbol: 'circle', symbolSize: 5,
        data: s.map((x) => x.active_users),
        lineStyle: { width: 2, color: '#f0a0b6' },
        itemStyle: { color: '#f0a0b6' },
      },
    ],
  })
}

function renderPie() {
  if (!pieEl.value) return
  pieChart = pieChart || echarts.init(pieEl.value)
  const palette = ['#7c6fd0', '#f0a0b6', '#8fc9e8', '#a8dcc3', '#f3c98b', '#c5a3e8', '#84b6f4', '#f49aa8', '#b8b0d8', '#9fd6c2']
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}：{c} 条（{d}%）' },
    legend: {
      type: 'scroll', orient: 'vertical', right: 0, top: 'middle',
      itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 11, color: '#8b869b' },
    },
    series: [{
      type: 'pie', radius: ['52%', '74%'], center: ['36%', '52%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 6 },
      label: { show: false },
      data: (data.emotion_distribution || []).map((x, i) => ({
        ...x, itemStyle: { color: palette[i % palette.length] },
      })),
    }],
  })
}

async function load() {
  loading.value = true
  try {
    const { data: d } = await api.get(`/admin/overview?days=${days.value}`)
    Object.assign(data, d)
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    await nextTick()
    renderTrend()
    renderPie()
  } finally {
    loading.value = false
  }
}

function onResize() {
  trendChart?.resize()
  pieChart?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  trendChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.link { font-size: 12.5px; color: var(--primary); }
.risk-list { display: flex; flex-direction: column; gap: 10px; min-height: 120px; }
.risk-row, .user-row { display: flex; align-items: center; gap: 10px; }
.risk-ava, .rank-ava.letter {
  width: 30px; height: 30px; border-radius: 50%; flex: none;
  background: #fdeef0; color: #d9536b; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
}
.risk-meta { flex: 1; min-width: 0; }
.risk-meta b, .rank-meta b { display: block; font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.risk-meta span, .phone { font-size: 11.5px; color: var(--text-soft); }

.rank-row { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }
.rank-no { width: 16px; font-size: 12px; color: #b3adc3; font-weight: 700; flex: none; }
.rank-no.top { color: #e0556d; }
.rank-ava { width: 30px; height: 30px; border-radius: 9px; object-fit: cover; flex: none; background: #f3eefc; }
.rank-ava.round { border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; }
.rank-meta { flex: 1; min-width: 0; }
.rank-meta .a-bar { margin-top: 5px; }
.rank-num { font-size: 12px; color: var(--text-soft); flex: none; }
.rank-meta span { font-size: 11.5px; color: var(--text-soft); }

.today {
  display: flex; align-items: center; gap: 30px; padding: 14px 20px; flex-wrap: wrap;
}
.today-title { font-size: 13px; font-weight: 700; color: var(--primary); background: var(--primary-soft); padding: 3px 12px; border-radius: 20px; }
.today-item b { font-size: 18px; color: #4a4360; }
.today-item span { font-size: 12px; color: var(--text-soft); margin-left: 6px; }
.today-note { margin-left: auto; font-size: 12px; color: var(--text-soft); }
</style>