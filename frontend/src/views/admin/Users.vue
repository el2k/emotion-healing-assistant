<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>用户管理</h1>
        <p>共 {{ total }} 位注册用户 · 支持搜索、禁用与情绪画像查看</p>
      </div>
      <div class="a-head-actions">
        <button class="a-btn ghost" @click="load">刷新</button>
      </div>
    </div>

    <div class="a-card">
      <div class="a-card-hd">
        <div class="a-toolbar">
          <div class="a-search">
            <input v-model="q" class="a-input" placeholder="搜索手机号 / 昵称" @keyup.enter="search" />
          </div>
          <button class="a-btn ghost" @click="search">搜索</button>
          <button v-if="q" class="a-btn ghost" @click="reset">重置</button>
        </div>
        <span class="a-tag">{{ total }} 人</span>
      </div>

      <div class="a-card-bd" style="padding-top: 10px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead>
              <tr>
                <th>用户</th><th>角色</th><th>会话 / 消息</th><th>最后活跃</th><th>状态</th><th>注册时间</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in items" :key="u.id">
                <td>
                  <div class="a-user-cell">
                    <img v-if="isImg(u.avatar)" :src="u.avatar" class="a-ava" alt="" />
                    <div v-else class="a-ava">{{ (u.nickname || '友')[0] }}</div>
                    <div>
                      <div class="cell-main">{{ u.nickname || '未命名用户' }}</div>
                      <div class="cell-sub">{{ u.phone }}</div>
                    </div>
                  </div>
                </td>
                <td><span class="a-tag" :class="u.role === 'admin' ? 'warn' : ''">{{ u.role === 'admin' ? '管理员' : '用户' }}</span></td>
                <td>
                  <span class="num">{{ u.sessions }}</span><span class="unit">会话</span>
                  <span class="num" style="margin-left: 10px">{{ u.messages }}</span><span class="unit">消息</span>
                </td>
                <td class="cell-sub">{{ relTime(u.last_active) }}</td>
                <td><span class="a-tag" :class="u.is_active ? 'ok' : 'off'">{{ u.is_active ? '正常' : '已禁用' }}</span></td>
                <td class="cell-sub">{{ fmtDate(u.created_at) }}</td>
                <td class="actions">
                  <button class="a-btn mini ghost" @click="openProfile(u)">画像</button>
                  <button v-if="u.role !== 'admin'" class="a-btn mini ghost" @click="toggleActive(u)">
                    {{ u.is_active ? '禁用' : '启用' }}
                  </button>
                  <button v-if="u.role !== 'admin'" class="a-btn mini danger" @click="askDelete(u)">删除</button>
                </td>
              </tr>
              <tr v-if="!items.length">
                <td colspan="7"><div class="a-empty"><span class="e-ico">🔍</span>没有匹配的用户</div></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="a-pager">
          <span class="pg-info">第 {{ page }} / {{ pages }} 页</span>
          <button :disabled="page <= 1" @click="go(page - 1)">上一页</button>
          <button :disabled="page >= pages" @click="go(page + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- 用户画像抽屉 -->
    <div v-if="drawer" class="a-mask" @click.self="closeProfile">
      <div class="a-drawer">
        <div class="a-drawer-hd">
          <h3>用户情绪画像</h3>
          <button class="x-btn" @click="closeProfile">✕</button>
        </div>
        <div class="a-drawer-bd">
          <div class="u-profile-head">
            <div class="a-ava lg">{{ (drawer.nickname || '友')[0] }}</div>
            <div>
              <div class="up-name">{{ drawer.nickname || '未命名' }}</div>
              <div class="up-phone">{{ drawer.phone }} · 加入于 {{ fmtDate(drawer.created_at) }}</div>
            </div>
            <span class="a-tag" :class="drawer.is_active ? 'ok' : 'off'">{{ drawer.is_active ? '正常' : '已禁用' }}</span>
          </div>

          <div v-if="profile" class="profile-body">
            <div class="mini-kpis">
              <div><b>{{ profile.total_records }}</b><span>情绪记录</span></div>
              <div><b>{{ Math.round(profile.positive_ratio * 100) }}%</b><span>正向占比</span></div>
              <div><b>{{ profile.dominant_emotion }}</b><span>主导情绪</span></div>
              <div><b>{{ profile.streak_days }}</b><span>连续记录</span></div>
            </div>

            <div class="p-block">
              <h4>情绪分布</h4>
              <div ref="pieEl" class="drawer-chart"></div>
            </div>

            <div class="p-block">
              <h4>心情趋势（近 90 天）</h4>
              <div ref="lineEl" class="drawer-chart"></div>
            </div>

            <div class="p-block">
              <h4>AI 洞察</h4>
              <p class="summary">{{ profile.summary_text }}</p>
            </div>

            <div class="p-block">
              <h4>波动事件</h4>
              <div v-for="(e, i) in profile.events.slice(0, 6)" :key="i" class="event-row">
                <span class="e-time">{{ e.time }}</span>
                <span class="a-tag" :class="e.score >= 0.6 ? 'danger' : ''">{{ e.emotion }}</span>
                <span class="e-trigger">{{ e.trigger || '未记录具体事件' }}</span>
              </div>
              <div v-if="!profile.events.length" class="a-empty" style="padding: 16px 0">暂无波动事件</div>
            </div>
          </div>
          <div v-else class="a-empty">画像加载中…</div>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="delTarget" class="a-modal-mask">
      <div class="a-modal">
        <h4>删除用户</h4>
        <p>确定删除「{{ delTarget.nickname }}（{{ delTarget.phone }}）」吗？该用户的会话、消息与情绪记录会一并删除，且不可恢复。</p>
        <div class="a-modal-ft">
          <button class="a-btn ghost" @click="delTarget = null">取消</button>
          <button class="a-btn danger" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>

    <transition name="fade"><div v-if="toastMsg" class="a-toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { api } from '../../api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const q = ref('')
const drawer = ref(null)
const profile = ref(null)
const delTarget = ref(null)
const toastMsg = ref('')
const pieEl = ref(null)
const lineEl = ref(null)
let pieChart = null
let lineChart = null

const isImg = (v) => !!v && (v.startsWith('/uploads/') || v.startsWith('http') || v.startsWith('data:'))
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString('zh-CN') : '—')
const relTime = (s) => {
  if (!s) return '—'
  const t = new Date(s).getTime()
  const diff = Date.now() - t
  if (diff < 3600e3) return `${Math.max(1, Math.floor(diff / 60e3))} 分钟前`
  if (diff < 86400e3) return `${Math.floor(diff / 3600e3)} 小时前`
  if (diff < 7 * 86400e3) return `${Math.floor(diff / 86400e3)} 天前`
  return fmtDate(s)
}

function toast(m) {
  toastMsg.value = m
  setTimeout(() => { toastMsg.value = '' }, 2200)
}

async function load() {
  const { data } = await api.get('/admin/users', { params: { q: q.value, page: page.value, page_size: pageSize } })
  items.value = data.items
  total.value = data.total
}
function search() { page.value = 1; load() }
function reset() { q.value = ''; page.value = 1; load() }
function go(p) { page.value = p; load() }

async function toggleActive(u) {
  await api.put(`/admin/users/${u.id}`, { is_active: !u.is_active })
  u.is_active = !u.is_active
  toast(u.is_active ? '已启用该用户' : '已禁用该用户')
}
function askDelete(u) { delTarget.value = u }
async function doDelete() {
  const u = delTarget.value
  delTarget.value = null
  await api.delete(`/admin/users/${u.id}`)
  toast('用户已删除')
  load()
}

async function openProfile(u) {
  drawer.value = u
  profile.value = null
  try {
    const { data } = await api.get(`/admin/users/${u.id}/profile?days=90`)
    profile.value = data
    await nextTick()
    renderProfileCharts()
  } catch (e) {
    toast('画像加载失败')
  }
}
function closeProfile() {
  drawer.value = null
  profile.value = null
  pieChart?.dispose(); pieChart = null
  lineChart?.dispose(); lineChart = null
}

function renderProfileCharts() {
  if (pieEl.value && profile.value) {
    pieChart = echarts.init(pieEl.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['50%', '72%'], center: ['50%', '54%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        data: profile.value.distribution || [],
      }],
    })
  }
  if (lineEl.value && profile.value) {
    lineChart = echarts.init(lineEl.value)
    const tl = profile.value.timeline || []
    lineChart.setOption({
      grid: { left: 32, right: 12, top: 16, bottom: 24 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: tl.map((x) => x.date.slice(5)), axisLabel: { fontSize: 10, color: '#9a94ab' }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#ece7f6' } } },
      yAxis: { type: 'value', min: 0, max: 1, splitLine: { lineStyle: { color: '#f6f2fd' } }, axisLabel: { fontSize: 10, color: '#9a94ab' } },
      series: [{
        type: 'line', smooth: true, symbol: 'none', data: tl.map((x) => x.mood),
        lineStyle: { width: 2.2, color: '#7c6fd0' },
        areaStyle: { color: 'rgba(124,111,208,.16)' },
      }],
    })
  }
}

onMounted(load)
</script>

<style scoped>
.num { font-weight: 600; color: #4a4360; }
.unit { font-size: 11.5px; color: var(--text-soft); margin-left: 3px; }
.u-profile-head { display: flex; align-items: center; gap: 12px; background: #fff; border-radius: 12px; padding: 14px; }
.up-name { font-size: 15px; font-weight: 700; }
.up-phone { font-size: 12px; color: var(--text-soft); margin-top: 2px; }
.mini-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.mini-kpis div { background: #fff; border-radius: 10px; padding: 10px 6px; text-align: center; }
.mini-kpis b { display: block; font-size: 16px; color: #5f54a3; }
.mini-kpis span { font-size: 11px; color: var(--text-soft); }
.p-block { background: #fff; border-radius: 12px; padding: 14px; }
.p-block h4 { font-size: 13px; margin-bottom: 8px; }
.drawer-chart { height: 170px; }
.summary { font-size: 12.5px; color: #6f6885; line-height: 1.7; }
.event-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #f3eefc; font-size: 12px; }
.event-row:last-child { border-bottom: none; }
.e-time { color: var(--text-soft); flex: none; }
.e-trigger { color: #6f6885; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>