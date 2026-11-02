<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>疗愈室数据</h1>
        <p>心理疗愈室使用情况、疾病方向分布与高风险关注 · 数据不包含消息正文</p>
      </div>
      <div class="a-head-actions">
        <select v-model="days" class="a-select" @change="load">
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
          <option :value="365">近一年</option>
        </select>
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <div class="risk-banner">
      ⚠️ 疗愈室面向明确疾病状态的用户。出现高风险记录时应以关怀与转介为主（全国心理援助热线
      <b>12356</b>），本页数据仅用于运营关注，不构成医学判断。
    </div>

    <div class="a-kpis">
      <div class="a-kpi" style="--kpi-tint:#eef3ff;--kpi-color:#4a6bd0">
        <div class="k-top"><span class="k-ico">🩺</span>疗愈会话</div>
        <div class="k-num">{{ data.totals?.sessions ?? 0 }}</div>
        <div class="k-foot">参与用户 {{ data.totals?.users ?? 0 }} 人</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#f0ecff;--kpi-color:#7c6fd0">
        <div class="k-top"><span class="k-ico">💬</span>疗愈消息</div>
        <div class="k-num">{{ data.totals?.messages ?? 0 }}</div>
        <div class="k-foot">情绪记录 {{ data.totals?.emotions ?? 0 }} 条</div>
      </div>
      <div class="a-kpi warn" style="--kpi-tint:#fff4e8;--kpi-color:#d68a2e">
        <div class="k-top"><span class="k-ico">!</span>高风险记录</div>
        <div class="k-num">{{ data.totals?.high_risk ?? 0 }}</div>
        <div class="k-foot">近 {{ days }} 天，负向且强度 ≥ 0.7</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b">
        <div class="k-top"><span class="k-ico">✦</span>覆盖疾病方向</div>
        <div class="k-num">{{ data.by_target?.length ?? 0 }}</div>
        <div class="k-foot">共 {{ data.experts?.length ?? 0 }} 位专家在岗</div>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd">
          <h3>疾病方向分布 <span class="sub">疗愈会话数</span></h3>
          <span class="a-tag blue">近 {{ days }} 天</span>
        </div>
        <div class="a-card-bd"><div ref="barEl" class="a-chart sm"></div></div>
      </div>

      <div class="a-card">
        <div class="a-card-hd"><h3>高风险用户 <span class="sub">疗愈室会话内</span></h3></div>
        <div class="a-card-bd risk-list">
          <div v-for="u in data.risk_users" :key="u.user_id" class="risk-row">
            <div class="risk-ava">!</div>
            <div class="risk-meta">
              <b>{{ u.nickname || '未命名' }}</b>
              <span>{{ u.phone }} · {{ u.targets }}</span>
            </div>
            <span class="a-tag danger">{{ u.count }} 次</span>
          </div>
          <div v-if="!data.risk_users?.length" class="a-empty">
            <span class="e-ico">☘</span>近 {{ days }} 天疗愈室没有高风险记录
          </div>
        </div>
      </div>
    </div>

    <!-- 专家使用 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>专家使用情况</h3>
        <span class="a-tag">{{ data.experts?.length ?? 0 }} 位</span>
      </div>
      <div class="a-card-bd" style="padding-top:8px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead>
              <tr><th>专家</th><th>对应状态</th><th>会话</th><th>用户</th><th>消息</th><th>高风险</th></tr>
            </thead>
            <tbody>
              <tr v-for="e in data.experts" :key="e.persona_id">
                <td>
                  <div class="a-user-cell">
                    <img v-if="e.avatar" :src="e.avatar" class="a-ava" alt="" />
                    <div class="cell-main">{{ e.emoji }} {{ e.name }}</div>
                  </div>
                </td>
                <td><span class="a-tag">{{ e.target }}</span><div class="cell-sub">{{ e.work }}</div></td>
                <td><b class="n">{{ e.sessions }}</b></td>
                <td><b class="n">{{ e.users }}</b></td>
                <td><b class="n">{{ e.messages }}</b></td>
                <td>
                  <span v-if="e.high_risk" class="a-tag danger">{{ e.high_risk }} 次</span>
                  <span v-else class="a-tag off">0</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 最近高风险明细 -->
    <div v-if="data.recent_risk?.length" class="a-card">
      <div class="a-card-hd">
        <h3>最近高风险记录</h3>
        <span class="a-tag danger">需运营关注</span>
      </div>
      <div class="a-card-bd" style="padding-top:8px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead><tr><th>时间</th><th>用户</th><th>状态方向</th><th>情绪</th><th>触发原话</th></tr></thead>
            <tbody>
              <tr v-for="r in data.recent_risk" :key="r.time + r.user_id">
                <td class="cell-sub">{{ fmtTime(r.time) }}</td>
                <td>
                  <div class="cell-main">{{ r.user || '未命名' }}</div>
                  <div class="cell-sub">{{ r.phone }}</div>
                </td>
                <td><span class="a-tag">{{ r.target }}</span><div class="cell-sub">{{ r.expert }}</div></td>
                <td><span class="a-tag danger">{{ r.emotion }} {{ r.score }}</span></td>
                <td class="cell-sub">{{ r.trigger || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 最近会话 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>最近疗愈会话</h3>
        <span class="a-tag">{{ data.recent_sessions?.length ?? 0 }} 条</span>
      </div>
      <div class="a-card-bd" style="padding-top:8px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead><tr><th>会话</th><th>专家</th><th>用户</th><th>消息数</th><th>最后更新</th></tr></thead>
            <tbody>
              <tr v-for="s in data.recent_sessions" :key="s.id">
                <td>
                  <div class="cell-main">#{{ s.id }} {{ s.title || '新的对话' }}</div>
                </td>
                <td>
                  <div class="a-user-cell">
                    <img v-if="s.avatar" :src="s.avatar" class="a-ava" alt="" />
                    <div>
                      <div class="cell-main">{{ s.expert }}</div>
                      <div class="cell-sub">{{ s.target }}</div>
                    </div>
                  </div>
                </td>
                <td>
                  <div class="cell-main">{{ s.nickname }}</div>
                  <div class="cell-sub">UID {{ s.user_id }}</div>
                </td>
                <td><b class="n">{{ s.messages }}</b></td>
                <td class="cell-sub">{{ fmtTime(s.updated_at) }}</td>
              </tr>
              <tr v-if="!data.recent_sessions?.length">
                <td colspan="5"><div class="a-empty">暂无疗愈室会话</div></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../../api'

const days = ref(90)
const loading = ref(false)
const data = reactive({ totals: {}, by_target: [], experts: [], risk_users: [], recent_risk: [], recent_sessions: [] })
const barEl = ref(null)
let barChart = null

const fmtTime = (s) => (s ? new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')

function renderBar() {
  if (!barEl.value) return
  barChart = barChart || echarts.init(barEl.value)
  const rows = (data.by_target || []).slice().sort((a, b) => a.sessions - b.sessions)
  barChart.setOption({
    grid: { left: 84, right: 26, top: 10, bottom: 16 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f6f2fd' } }, axisLabel: { fontSize: 11, color: '#9a94ab' } },
    yAxis: { type: 'category', data: rows.map((x) => x.target), axisTick: { show: false }, axisLine: { lineStyle: { color: '#ece7f6' } }, axisLabel: { fontSize: 12, color: '#6f6885' } },
    series: [{
      type: 'bar', data: rows.map((x) => x.sessions), barWidth: 10,
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#a8c0f0' }, { offset: 1, color: '#4a6bd0' },
        ]),
      },
    }],
  })
}

async function load() {
  loading.value = true
  try {
    const { data: d } = await api.get(`/admin/heal?days=${days.value}`)
    Object.assign(data, d)
    await nextTick()
    renderBar()
  } finally {
    loading.value = false
  }
}

function onResize() { barChart?.resize() }
onMounted(() => { load(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', onResize); barChart?.dispose() })
</script>

<style scoped>
.risk-banner {
  font-size: 12.5px; color: #8a5a48; background: #fdf6ee; border: 1px dashed #eccfae;
  border-radius: 10px; padding: 10px 14px; line-height: 1.8;
}
.risk-banner b { color: #d9536b; }
.n { font-weight: 700; color: #4a4360; }
.risk-list { display: flex; flex-direction: column; gap: 10px; min-height: 120px; }
.risk-row { display: flex; align-items: center; gap: 10px; }
.risk-ava {
  width: 30px; height: 30px; border-radius: 50%; background: #fdeef0; color: #d9536b;
  display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex: none;
}
.risk-meta { flex: 1; min-width: 0; }
.risk-meta b { display: block; font-size: 13px; }
.risk-meta span { font-size: 11.5px; color: var(--text-soft); }
</style>