<template>
  <div class="admin-page">
    <header class="admin-top">
      <div class="admin-brand">☾ 管理平台</div>
      <div class="admin-actions">
        <a @click="goChat">返回聊天</a>
        <a @click="logout">退出</a>
      </div>
    </header>

    <div class="admin-body">
      <!-- 统计卡片 -->
      <div class="stat-cards">
        <div class="card stat">
          <div class="num">{{ stats?.totals?.users ?? '-' }}</div>
          <div class="label">注册用户</div>
        </div>
        <div class="card stat">
          <div class="num">{{ stats?.totals?.sessions ?? '-' }}</div>
          <div class="label">对话会话</div>
        </div>
        <div class="card stat">
          <div class="num">{{ stats?.totals?.messages ?? '-' }}</div>
          <div class="label">消息总数</div>
        </div>
        <div class="card stat risk">
          <div class="num">{{ stats?.totals?.high_risk ?? '-' }}</div>
          <div class="label">近7天高风险</div>
        </div>
      </div>

      <div class="stat-cards">
        <div class="card stat">
          <div class="num">{{ stats?.totals?.posts ?? '-' }}</div>
          <div class="label">社区帖子</div>
        </div>
        <div class="card stat">
          <div class="num">{{ stats?.totals?.likes ?? '-' }}</div>
          <div class="label">帖子点赞</div>
        </div>
        <div class="card stat">
          <div class="num">{{ stats?.totals?.comments ?? '-' }}</div>
          <div class="label">帖子评论</div>
        </div>
        <div class="card stat">
          <div class="num">{{ stats?.totals?.calibrations ?? '-' }}</div>
          <div class="label">情绪校准次数</div>
        </div>
      </div>

      <div class="charts-row">
        <div class="card chart-card">
          <h3>情绪分布</h3>
          <div ref="pieEl" class="chart"></div>
        </div>
        <div class="card chart-card">
          <h3>情绪强度趋势（近7天）</h3>
          <div ref="lineEl" class="chart"></div>
        </div>
      </div>

      <!-- 角色使用排行 -->
      <div class="card table-card">
        <h3>🎭 角色使用排行</h3>
        <div class="persona-usage">
          <div v-for="(p, i) in personas" :key="p.persona_id" class="pu-row">
            <span class="pu-rank">{{ i + 1 }}</span>
            <span class="pu-emoji">{{ p.emoji }}</span>
            <span class="pu-name">{{ p.name }}<span class="pu-cat">{{ p.category }}</span></span>
            <div class="pu-bar"><div class="pu-fill" :style="{ width: personaBar(p.sessions) }"></div></div>
            <span class="pu-num">{{ p.sessions }} 会话 · {{ p.messages }} 消息 · {{ p.emotions }} 情绪</span>
          </div>
        </div>
      </div>

      <!-- 用户管理 -->
      <div class="card table-card">
        <h3>用户管理</h3>
        <table>
          <thead>
            <tr><th>ID</th><th>手机号</th><th>昵称</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.id }}</td>
              <td>{{ u.phone }}</td>
              <td>{{ u.nickname }}</td>
              <td>{{ u.role === 'admin' ? '管理员' : '用户' }}</td>
              <td>
                <span class="pill" :class="u.is_active ? 'on' : 'off'">
                  {{ u.is_active ? '正常' : '禁用' }}
                </span>
              </td>
              <td>{{ fmtDate(u.created_at) }}</td>
              <td>
                <button v-if="u.role !== 'admin'" class="mini-btn" @click="viewProfile(u)">画像</button>
                <button v-if="u.role !== 'admin'" class="mini-btn" @click="toggleActive(u)">
                  {{ u.is_active ? '禁用' : '启用' }}
                </button>
                <button v-if="u.role !== 'admin'" class="mini-btn danger" @click="removeUser(u)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 高风险用户 -->
      <div class="card table-card">
        <h3>需重点关注用户（近7天高风险情绪）</h3>
        <table v-if="stats?.risk_users?.length">
          <thead><tr><th>用户ID</th><th>昵称</th><th>手机号</th><th>高风险次数</th></tr></thead>
          <tbody>
            <tr v-for="r in stats.risk_users" :key="r.user_id">
              <td>{{ r.user_id }}</td><td>{{ r.nickname }}</td><td>{{ r.phone }}</td>
              <td class="warn">{{ r.count }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="no-data">近7天暂无高风险情绪记录</p>
      </div>

      <!-- 论坛数据 -->
      <div class="card table-card">
        <h3>🌱 社区论坛数据</h3>
        <div class="forum-summary">
          <div class="fs-item"><b>{{ forum?.totals?.posts ?? 0 }}</b><span>帖子</span></div>
          <div class="fs-item"><b>{{ forum?.totals?.likes ?? 0 }}</b><span>点赞</span></div>
          <div class="fs-item"><b>{{ forum?.totals?.comments ?? 0 }}</b><span>评论</span></div>
        </div>
        <div class="forum-cols">
          <div class="forum-col">
            <div class="fc-title">热门标签</div>
            <div class="hot-tags">
              <span v-for="t in (forum?.hot_tags || [])" :key="t.name" class="hot-tag">
                #{{ t.name }} <em>{{ t.count }}</em>
              </span>
              <span v-if="!(forum?.hot_tags || []).length" class="no-data">暂无</span>
            </div>
          </div>
          <div class="forum-col">
            <div class="fc-title">热门帖子（按点赞）</div>
            <div class="top-posts">
              <div v-for="p in (forum?.top_posts || [])" :key="p.id" class="tp-row">
                <span class="tp-title">{{ p.title }}</span>
                <span class="tp-meta">{{ p.author }} · ❤️ {{ p.likes }}</span>
              </div>
              <span v-if="!(forum?.top_posts || []).length" class="no-data">暂无</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 用户情绪画像弹窗 -->
    <div v-if="profileModal" class="modal-mask" @click.self="profileModal = null">
      <div class="modal card">
        <div class="modal-head">
          <h3>{{ profileModal.nickname }} 的情绪画像（近90天）</h3>
          <button class="modal-close" @click="profileModal = null">✕</button>
        </div>
        <div v-if="profileModal.data.total_records" class="modal-body">
          <div class="pm-stats">
            <div><b>{{ profileModal.data.total_records }}</b><span>记录次数</span></div>
            <div><b>{{ profileModal.data.dominant_emotion }}</b><span>最常情绪</span></div>
            <div><b>{{ Math.round(profileModal.data.positive_ratio*100) }}%</b><span>正向占比</span></div>
            <div><b>{{ profileModal.data.streak_days }}</b><span>连续天数</span></div>
          </div>
          <p class="pm-summary">{{ profileModal.data.summary_text }}</p>
          <div class="pm-dist">
            <div v-for="d in profileModal.data.distribution" :key="d.name" class="pm-bar">
              <span class="pm-name">{{ d.name }}</span>
              <div class="pm-track"><div class="pm-fill" :style="{ width: distWidth(d.value) }"></div></div>
              <span class="pm-val">{{ d.value }}</span>
            </div>
          </div>
        </div>
        <p v-else class="no-data">该用户暂无情绪记录</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const router = useRouter()
const auth = useAuthStore()
const stats = ref({})
const users = ref([])
const personas = ref([])
const forum = ref({})
const profileModal = ref(null)
const pieEl = ref(null)
const lineEl = ref(null)
let pieChart = null, lineChart = null

function fmtDate(s) { return s ? new Date(s).toLocaleDateString() : '-' }

function renderCharts() {
  const dist = stats.value.emotion_distribution || []
  pieChart = echarts.init(pieEl.value)
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { fontSize: 12 } },
    series: [{
      type: 'pie', radius: ['38%', '65%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: dist,
      color: ['#7c6fd0', '#f59fb0', '#6f9fdc', '#8fd0a8', '#e0a86f',
              '#c17bd6', '#f0b45a', '#6fb8c9', '#d67b9e', '#9b9b9b'],
    }],
  })

  const trend = stats.value.emotion_trend || []
  lineChart = echarts.init(lineEl.value)
  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: trend.map((t) => t.date), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: { fontSize: 11 } },
    series: [{
      name: '平均情绪强度', type: 'line', smooth: true, data: trend.map((t) => t.avg_score),
      lineStyle: { color: '#7c6fd0', width: 3 },
      itemStyle: { color: '#7c6fd0' },
      areaStyle: { opacity: 0.08 },
    }],
  })
}

async function load() {
  const [s, u, pe, f] = await Promise.all([
    api.get('/admin/stats'),
    api.get('/admin/users'),
    api.get('/admin/personas'),
    api.get('/admin/forum'),
  ])
  stats.value = s.data
  users.value = u.data
  personas.value = pe.data
  forum.value = f.data
  if (pieEl.value) renderCharts()
}

function personaBar(sessions) {
  const max = Math.max(1, ...personas.value.map((p) => p.sessions))
  return `${Math.round((sessions / max) * 100)}%`
}

async function toggleActive(u) {
  await api.put(`/admin/users/${u.id}`, { is_active: !u.is_active })
  await load()
}
async function removeUser(u) {
  if (!confirm(`确定删除用户「${u.nickname}」及其全部对话吗？`)) return
  await api.delete(`/admin/users/${u.id}`)
  await load()
}

function goChat() { router.push('/') }
function logout() { auth.logout(); router.push('/login') }

async function viewProfile(u) {
  const { data } = await api.get(`/admin/users/${u.id}/profile?days=90`)
  profileModal.value = { nickname: u.nickname, data }
}
function distWidth(v) {
  const dist = profileModal.value?.data?.distribution || []
  const max = Math.max(1, ...dist.map((d) => d.value))
  return `${Math.round((v / max) * 100)}%`
}

function onResize() { pieChart?.resize(); lineChart?.resize() }

onMounted(() => { load(); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => { window.removeEventListener('resize', onResize);
  pieChart?.dispose(); lineChart?.dispose() })
</script>

<style scoped>
.admin-page { min-height: 100vh; }
.admin-top {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 28px; background: #fff; border-bottom: 1px solid var(--border);
}
.admin-brand { font-size: 18px; font-weight: 700; color: var(--primary); }
.admin-actions a { margin-left: 16px; cursor: pointer; font-size: 14px; }

.admin-body { max-width: 1100px; margin: 24px auto; padding: 0 20px; }
.stat-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat { padding: 20px 24px; }
.stat .num { font-size: 30px; font-weight: 700; color: var(--primary); }
.stat.hot .num { color: #e0556d; }
.stat .label { color: var(--text-soft); font-size: 13px; margin-top: 4px; }

.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
.chart-card { padding: 18px 20px; }
.chart-card h3 { font-size: 15px; margin-bottom: 12px; }
.chart { height: 300px; }

.table-card { padding: 18px 22px; margin-top: 16px; }
.table-card h3 { font-size: 15px; margin-bottom: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); }
th { color: var(--text-soft); font-weight: 500; font-size: 13px; }
.pill { padding: 3px 10px; border-radius: 12px; font-size: 12px; }
.pill.on { background: #e7f7ec; color: #2f9e6b; }
.pill.off { background: #fdeef0; color: #e0556d; }
.mini { border: 1px solid var(--border); background: #fff; border-radius: 7px;
  padding: 4px 10px; font-size: 12px; margin-right: 6px; }
.mini:hover { background: var(--primary-soft); }
.mini.danger:hover { background: #fdeef0; color: #e0556d; }
.warn { color: #e0556d; font-weight: 600; }
.no-data, .no-reason { color: var(--text-soft); font-size: 14px; padding: 16px 0; }

.modal-mask { position: fixed; inset: 0; background: rgba(30,25,45,.5); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.modal { width: 540px; max-width: 100%; max-height: 80vh; overflow-y: auto; padding: 22px 24px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.modal-head h3 { font-size: 16px; }
.modal-close { border: none; background: transparent; font-size: 16px; color: var(--text-soft); cursor: pointer; }
.pm-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.pm-stats div { background: #faf8ff; border-radius: 10px; padding: 10px; text-align: center; }
.pm-stats b { display: block; font-size: 18px; color: var(--primary); }
.pm-stats span { font-size: 12px; color: var(--text-soft); }
.pm-summary { font-size: 13px; line-height: 1.7; background: #faf8ff; padding: 12px; border-radius: 10px; margin-bottom: 14px; }
.pm-dist { display: flex; flex-direction: column; gap: 8px; }
.pm-bar { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.pm-name { width: 42px; flex-shrink: 0; color: var(--text-soft); }
.pm-track { flex: 1; height: 12px; background: #f0ecf9; border-radius: 6px; overflow: hidden; }
.pm-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--accent)); border-radius: 6px; }
.pm-val { width: 30px; text-align: right; color: var(--text-soft); }

.persona-usage { display: flex; flex-direction: column; gap: 9px; }
.pu-row { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.pu-rank { width: 18px; color: var(--text-soft); flex-shrink: 0; }
.pu-emoji { font-size: 18px; flex-shrink: 0; }
.pu-name { width: 120px; flex-shrink: 0; display: flex; align-items: center; gap: 6px; }
.pu-cat { font-size: 11px; color: var(--primary); background: var(--primary-soft); padding: 1px 6px; border-radius: 8px; }
.pu-bar { flex: 1; height: 12px; background: #f0ecf9; border-radius: 6px; overflow: hidden; }
.pu-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--accent)); border-radius: 6px; }
.pu-num { width: 230px; text-align: right; color: var(--text-soft); font-size: 12px; flex-shrink: 0; }

.forum-summary { display: flex; gap: 16px; margin-bottom: 16px; }
.fs-item { flex: 1; background: #faf8ff; border-radius: 10px; padding: 12px; text-align: center; }
.fs-item b { display: block; font-size: 22px; color: var(--primary); }
.fs-item span { font-size: 12px; color: var(--text-soft); }
.forum-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.fc-title { font-size: 13px; color: var(--text-soft); margin-bottom: 10px; }
.hot-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.hot-tag { font-size: 13px; background: #faf8ff; padding: 4px 10px; border-radius: 10px; color: var(--primary); }
.hot-tag em { color: var(--text-soft); font-style: normal; font-size: 11px; }
.top-posts { display: flex; flex-direction: column; gap: 8px; }
.tp-row { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; padding: 6px 10px; background: #faf8ff; border-radius: 8px; }
.tp-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tp-meta { color: var(--text-soft); flex-shrink: 0; font-size: 12px; }
@media (max-width: 800px) { .forum-cols { grid-template-columns: 1fr; } .pu-num { display: none; } }

@media (max-width: 800px) {
  .stat-cards { grid-template-columns: repeat(2, 1fr); }
  .charts-row { grid-template-columns: 1fr; }
}
</style>