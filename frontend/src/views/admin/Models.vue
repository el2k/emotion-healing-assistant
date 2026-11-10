<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>模型管理</h1>
        <p>模型池配置 · 用户可选模型 · 每模型 token 额度 / 已用 / 剩余 / 每日消耗</p>
      </div>
      <div class="a-head-actions">
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
        <button class="a-btn" @click="openCreate">+ 新增模型</button>
      </div>
    </div>

    <!-- KPI -->
    <div class="a-kpis">
      <div class="a-kpi" style="--kpi-tint:#f0ecff;--kpi-color:#7c6fd0">
        <div class="k-top"><span class="k-ico">◈</span>启用模型</div>
        <div class="k-num">{{ summary.enabled_models || 0 }}<small> / {{ summary.total_models || 0 }}</small></div>
        <div class="k-foot">用户可选 {{ summary.enabled_models || 0 }} 个</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b">
        <div class="k-top"><span class="k-ico">⚡</span>今日消耗 Token</div>
        <div class="k-num">{{ fmt(summary.tokens_today) }}</div>
        <div class="k-foot">{{ summary.calls_today || 0 }} 次调用</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#fff4e8;--kpi-color:#d68a2e">
        <div class="k-top"><span class="k-ico">Σ</span>累计消耗 Token</div>
        <div class="k-num">{{ fmt(summary.tokens_total) }}</div>
        <div class="k-foot">全模型所有调用</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#fdf1f5;--kpi-color:#d9536b">
        <div class="k-top"><span class="k-ico">◔</span>剩余额度最少</div>
        <div class="k-num" style="font-size:19px">{{ minRemainName || '—' }}</div>
        <div class="k-foot">{{ minRemainText }}</div>
      </div>
    </div>

    <!-- 模型表 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>模型池 <span class="sub">额度需与阿里云百炼控制台一致（剩余 = 额度 − 累计消耗）</span></h3>
        <span class="a-tag">{{ models.length }} 个</span>
      </div>
      <div class="a-card-bd">
        <div class="m-table">
          <div class="m-head">
            <span>模型</span><span>额度 / 已用 / 剩余</span><span>今日</span><span>累计</span><span>状态</span><span>操作</span>
          </div>
          <div v-for="m in models" :key="m.id" class="m-row">
            <div class="m-info">
              <div class="m-name">
                {{ m.display_name }}
                <i v-if="m.is_default" class="m-badge default">默认</i>
                <i v-if="!m.enabled" class="m-badge off">已停用</i>
              </div>
              <div class="m-id">{{ m.model_id }}</div>
              <div class="m-desc">{{ m.description || '—' }}</div>
            </div>
            <div class="m-quota">
              <div class="q-nums">
                <b>{{ fmt(m.free_quota_tokens) }}</b>
                <span>已用 {{ fmt(m.used_total) }}</span>
                <span class="q-remain" :class="{ warn: m.remaining !== null && m.remaining < m.free_quota_tokens * 0.1 }">
                  剩余 {{ m.remaining === null ? '未配置' : fmt(m.remaining) }}
                </span>
              </div>
              <div class="q-bar">
                <i :style="{ width: quotaPct(m) + '%' }" :class="{ warn: quotaPct(m) > 90 }"></i>
              </div>
            </div>
            <div class="m-today">
              <b>{{ fmt(m.used_today) }}</b>
              <span>{{ m.calls_today }} 次</span>
            </div>
            <div class="m-today">
              <b>{{ m.calls_total }} 次</b>
              <span>{{ m.last_used_at ? timeText(m.last_used_at) : '未使用' }}</span>
            </div>
            <div class="m-state">
              <button class="sw" :class="{ on: m.enabled }" :disabled="saving"
                      :title="m.enabled ? '点击停用（用户将看不到该模型）' : '点击启用'"
                      @click="toggleEnabled(m)"><i></i></button>
            </div>
            <div class="m-actions">
              <button v-if="!m.is_default" class="mini-btn" :disabled="saving" @click="setDefault(m)">设默认</button>
              <button class="mini-btn" :disabled="saving" @click="openEdit(m)">编辑</button>
              <button v-if="!m.is_default" class="mini-btn danger" :disabled="saving" @click="removeModel(m)">删除</button>
            </div>
          </div>
          <div v-if="!models.length" class="a-empty">暂无模型，点击右上角新增</div>
        </div>
      </div>
    </div>

    <div class="a-grid-2">
      <!-- 用量趋势 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>近 {{ days }} 天 Token 消耗</h3>
          <div class="range-tabs">
            <button v-for="d in [7, 14, 30]" :key="d" :class="{ on: days === d }"
                    @click="changeDays(d)">{{ d }}天</button>
          </div>
        </div>
        <div class="a-card-bd">
          <div v-if="byDay.length" class="bar-chart">
            <div v-for="d in byDay" :key="d.date" class="bar-col"
                 :title="`${d.date}：${d.tokens.toLocaleString()} tokens · ${d.calls} 次`">
              <div class="bar-fill" :style="{ height: barHeight(d.tokens) + '%' }"></div>
              <span class="bar-label">{{ d.date.slice(5) }}</span>
            </div>
          </div>
          <div v-else class="a-empty">近 {{ days }} 天暂无调用记录</div>
        </div>
      </div>

      <!-- 按模型汇总 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>按模型汇总 <span class="sub">近 {{ days }} 天</span></h3>
        </div>
        <div class="a-card-bd">
          <div v-if="byModel.length" class="mdl-sum-list">
            <div v-for="(b, i) in byModel" :key="b.model" class="mdl-sum">
              <span class="ms-rank">{{ i + 1 }}</span>
              <span class="ms-name">{{ b.model }}</span>
              <div class="ms-bar"><i :style="{ width: modelShare(b.tokens) + '%' }"></i></div>
              <span class="ms-num">{{ fmt(b.tokens) }} · {{ b.calls }} 次</span>
            </div>
          </div>
          <div v-else class="a-empty">暂无数据</div>
        </div>
      </div>
    </div>

    <!-- 最近调用记录 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>最近调用 <span class="sub">token 消耗明细（最新 50 条）</span></h3>
      </div>
      <div class="a-card-bd" style="padding-top:8px">
        <div class="u-table">
          <div class="u-head"><span>模型</span><span>场景</span><span>Token</span><span>状态</span><span>时间</span></div>
          <div v-for="r in recent" :key="r.id" class="u-row">
            <span class="u-model">{{ r.model }}</span>
            <span>{{ sceneText(r.scene) }}</span>
            <span class="u-tok">{{ r.total_tokens }}</span>
            <span :class="r.success ? 'u-ok' : 'u-err'">{{ r.success ? '成功' : '失败' }}</span>
            <span class="u-time">{{ timeText(r.created_at) }}</span>
          </div>
          <div v-if="!recent.length" class="a-empty">暂无调用记录</div>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="dialog.show" class="m-mask" @click.self="dialog.show = false">
      <div class="m-modal">
        <h3>{{ dialog.isEdit ? '编辑模型' : '新增模型' }}</h3>
        <div class="f-row">
          <label>模型 ID</label>
          <input v-model="dialog.model_id" :disabled="dialog.isEdit"
                 placeholder="如 qwen-plus（阿里云百炼模型名）" />
        </div>
        <div class="f-row">
          <label>展示名</label>
          <input v-model="dialog.display_name" placeholder="如 通义千问 Plus" />
        </div>
        <div class="f-row">
          <label>描述</label>
          <input v-model="dialog.description" placeholder="给用户看的一句话说明" />
        </div>
        <div class="f-row">
          <label>免费额度 Token</label>
          <input v-model.number="dialog.free_quota_tokens" type="number" min="0" step="10000" />
          <span class="f-tip">按百炼控制台填报，剩余 = 额度 − 累计消耗</span>
        </div>
        <div class="f-row">
          <label>状态</label>
          <label class="f-check"><input v-model="dialog.enabled" type="checkbox" /> 对用户开放</label>
          <label class="f-check"><input v-model="dialog.is_default" type="checkbox" :disabled="dialog.isEdit && dialog.wasDefault" /> 设为默认</label>
        </div>
        <p v-if="dialog.error" class="f-err">{{ dialog.error }}</p>
        <div class="m-modal-actions">
          <button class="a-btn ghost" @click="dialog.show = false">取消</button>
          <button class="a-btn" :disabled="saving" @click="saveDialog">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../../api'

const loading = ref(false)
const saving = ref(false)
const models = ref([])
const summary = ref({})
const byDay = ref([])
const byModel = ref([])
const recent = ref([])
const days = ref(7)

const dialog = reactive({
  show: false, isEdit: false, id: 0, wasDefault: false,
  model_id: '', display_name: '', description: '',
  free_quota_tokens: 0, enabled: true, is_default: false, error: '',
})

const minRemainName = computed(() => {
  const withQuota = models.value.filter((m) => m.remaining !== null)
  if (!withQuota.length) return ''
  const m = withQuota.reduce((a, b) => (a.remaining <= b.remaining ? a : b))
  return m.display_name
})
const minRemainText = computed(() => {
  const withQuota = models.value.filter((m) => m.remaining !== null)
  if (!withQuota.length) return '未配置额度'
  const m = withQuota.reduce((a, b) => (a.remaining <= b.remaining ? a : b))
  return `剩余 ${fmt(m.remaining)}`
})

function fmt(n) {
  if (n === null || n === undefined) return '—'
  n = Number(n)
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(n >= 1e6 ? 0 : 1) + '万'
  return n.toLocaleString()
}
function quotaPct(m) {
  if (!m.free_quota_tokens) return 0
  return Math.min(100, Math.round(m.used_total / m.free_quota_tokens * 100))
}
function barHeight(tokens) {
  const max = Math.max(...byDay.value.map((d) => d.tokens), 1)
  return Math.max(4, Math.round(tokens / max * 100))
}
function modelShare(tokens) {
  const max = Math.max(...byModel.value.map((b) => b.tokens), 1)
  return Math.max(4, Math.round(tokens / max * 100))
}
function sceneText(s) {
  return { analyze: '情绪分析', reply: '回复生成', reply_stream: '流式回复' }[s] || s
}
function timeText(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMin = Math.floor((now - d) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

async function load() {
  loading.value = true
  try {
    const [m, u] = await Promise.all([
      api.get('/admin/llm/models'),
      api.get(`/admin/llm/usage?days=${days.value}`),
    ])
    models.value = m.data.models || []
    summary.value = m.data.summary || {}
    byDay.value = u.data.by_day || []
    byModel.value = u.data.by_model || []
    recent.value = u.data.recent || []
  } catch (e) { /* 忽略 */ } finally {
    loading.value = false
  }
}

async function changeDays(d) {
  days.value = d
  await load()
}

async function toggleEnabled(m) {
  saving.value = true
  try {
    await api.put(`/admin/llm/models/${m.id}`, { enabled: !m.enabled })
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '操作失败')
  } finally { saving.value = false }
}

async function setDefault(m) {
  if (!confirm(`将「${m.display_name}」设为默认模型？所有未选择模型的用户将使用它。`)) return
  saving.value = true
  try {
    await api.put(`/admin/llm/models/${m.id}`, { is_default: true })
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '操作失败')
  } finally { saving.value = false }
}

async function removeModel(m) {
  if (!confirm(`删除模型「${m.display_name}」？历史用量记录会保留。`)) return
  saving.value = true
  try {
    await api.delete(`/admin/llm/models/${m.id}`)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  } finally { saving.value = false }
}

function openCreate() {
  Object.assign(dialog, {
    show: true, isEdit: false, id: 0, wasDefault: false,
    model_id: '', display_name: '', description: '',
    free_quota_tokens: 0, enabled: true, is_default: false, error: '',
  })
}

function openEdit(m) {
  Object.assign(dialog, {
    show: true, isEdit: true, id: m.id, wasDefault: !!m.is_default,
    model_id: m.model_id, display_name: m.display_name,
    description: m.description, free_quota_tokens: m.free_quota_tokens,
    enabled: m.enabled, is_default: m.is_default, error: '',
  })
}

async function saveDialog() {
  dialog.error = ''
  if (!dialog.model_id.trim()) { dialog.error = '请填写模型 ID'; return }
  saving.value = true
  try {
    if (dialog.isEdit) {
      await api.put(`/admin/llm/models/${dialog.id}`, {
        display_name: dialog.display_name,
        description: dialog.description,
        free_quota_tokens: dialog.free_quota_tokens,
        enabled: dialog.enabled,
        ...(dialog.is_default && !dialog.wasDefault ? { is_default: true } : {}),
      })
    } else {
      await api.post('/admin/llm/models', {
        model_id: dialog.model_id.trim(),
        display_name: dialog.display_name,
        description: dialog.description,
        free_quota_tokens: dialog.free_quota_tokens,
        enabled: dialog.enabled,
        is_default: dialog.is_default,
      })
    }
    dialog.show = false
    await load()
  } catch (e) {
    dialog.error = e.response?.data?.detail || '保存失败'
  } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.a-kpi .k-num small { font-size: 13px; color: #b9b3c9; font-weight: 500; }

/* 模型表格 */
.m-table { display: flex; flex-direction: column; }
.m-head, .m-row {
  display: grid;
  grid-template-columns: 2.2fr 2.2fr 0.9fr 1fr 58px 148px;
  gap: 14px; align-items: center;
}
.m-head { padding: 6px 10px; font-size: 11.5px; color: #9a94ab; border-bottom: 1px solid #f1ecfa; }
.m-row { padding: 13px 10px; border-bottom: 1px solid #f6f2fc; }
.m-row:last-child { border-bottom: none; }
.m-name { font-size: 14px; font-weight: 600; color: #4a4360; display: flex; align-items: center; gap: 6px; }
.m-badge { font-style: normal; font-size: 10px; padding: 1px 7px; border-radius: 8px; font-weight: 500; }
.m-badge.default { background: #f0ecff; color: #7c6fd0; }
.m-badge.off { background: #f6f4f8; color: #9a94ab; }
.m-id { font-size: 11.5px; color: #9a94ab; margin-top: 2px; font-family: Consolas, monospace; }
.m-desc { font-size: 12px; color: #8b869b; margin-top: 2px; }
.q-nums { display: flex; gap: 10px; align-items: baseline; font-size: 11.5px; color: #9a94ab; flex-wrap: wrap; }
.q-nums b { font-size: 13.5px; color: #4a4360; }
.q-remain { color: #2f9e6b; }
.q-remain.warn { color: #d9536b; font-weight: 600; }
.q-bar { height: 6px; border-radius: 3px; background: #f1ecfa; overflow: hidden; margin-top: 6px; }
.q-bar i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, #b9aaff, #7c6fd0); }
.q-bar i.warn { background: linear-gradient(90deg, #f3b3be, #d9536b); }
.m-today { text-align: left; }
.m-today b { display: block; font-size: 13px; color: #4a4360; }
.m-today span { font-size: 11px; color: #9a94ab; }
.m-state { display: flex; justify-content: center; }
.sw { width: 38px; height: 21px; border-radius: 12px; border: none; background: #e5e0f0; position: relative; cursor: pointer; transition: background .15s; padding: 0; }
.sw i { position: absolute; top: 2px; left: 2px; width: 17px; height: 17px; border-radius: 50%; background: #fff; transition: left .15s; box-shadow: 0 1px 3px rgba(0,0,0,.15); }
.sw.on { background: #7c6fd0; }
.sw.on i { left: 19px; }
.m-actions { display: flex; gap: 6px; justify-content: flex-end; }
.mini-btn { border: 1px solid #e6dff5; background: #fdfcff; color: #6f63b8; border-radius: 7px; padding: 4px 9px; font-size: 11.5px; cursor: pointer; }
.mini-btn:hover { border-color: #7c6fd0; }
.mini-btn.danger { color: #d9536b; }
.mini-btn.danger:hover { border-color: #d9536b; }
.mini-btn:disabled { opacity: .45; cursor: not-allowed; }

/* 趋势图 */
.range-tabs { display: flex; gap: 4px; }
.range-tabs button { border: 1px solid #e6dff5; background: #fff; color: #9a94ab; font-size: 11.5px; border-radius: 8px; padding: 3px 9px; cursor: pointer; }
.range-tabs button.on { background: #f0ecff; color: #7c6fd0; border-color: #d9c8f5; }
.bar-chart { display: flex; align-items: flex-end; gap: 8px; height: 168px; padding-top: 8px; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; min-width: 0; }
.bar-fill { width: 70%; max-width: 34px; border-radius: 5px 5px 2px 2px; background: linear-gradient(180deg, #b9aaff, #7c6fd0); min-height: 4px; transition: height .3s; }
.bar-label { font-size: 10px; color: #9a94ab; margin-top: 6px; white-space: nowrap; }
.mdl-sum-list { display: flex; flex-direction: column; gap: 10px; }
.mdl-sum { display: flex; align-items: center; gap: 10px; font-size: 12.5px; }
.ms-rank { width: 18px; height: 18px; border-radius: 50%; background: #f0ecff; color: #7c6fd0; font-size: 10.5px; display: flex; align-items: center; justify-content: center; flex: none; }
.ms-name { width: 118px; flex: none; color: #4a4360; font-family: Consolas, monospace; font-size: 11.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ms-bar { flex: 1; height: 8px; background: #f6f2fc; border-radius: 4px; overflow: hidden; }
.ms-bar i { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, #9fd6c2, #2f9e6b); }
.ms-num { flex: none; color: #9a94ab; font-size: 11.5px; }

/* 最近调用 */
.u-table { display: flex; flex-direction: column; }
.u-head, .u-row { display: grid; grid-template-columns: 1.6fr 1fr 0.8fr 0.7fr 1fr; gap: 10px; padding: 7px 10px; font-size: 12.5px; }
.u-head { color: #9a94ab; font-size: 11.5px; border-bottom: 1px solid #f1ecfa; }
.u-row { border-bottom: 1px solid #f8f5fd; color: #4a4360; }
.u-model { font-family: Consolas, monospace; font-size: 11.5px; color: #7c6fd0; }
.u-tok { font-weight: 600; }
.u-ok { color: #2f9e6b; } .u-err { color: #d9536b; }
.u-time { color: #9a94ab; font-size: 11.5px; }

/* 弹窗 */
.m-mask { position: fixed; inset: 0; background: rgba(30, 25, 48, .45); backdrop-filter: blur(3px); display: flex; align-items: center; justify-content: center; z-index: 200; }
.m-modal { width: 480px; max-width: 92vw; background: #fff; border-radius: 16px; padding: 22px 24px; box-shadow: 0 18px 50px rgba(40, 30, 70, .25); }
.m-modal h3 { font-size: 16px; margin-bottom: 16px; }
.f-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.f-row label { font-size: 12.5px; color: #6f6885; width: 96px; flex: none; }
.f-row input[type=text], .f-row input[type=number], .f-row input:not([type]) {
  flex: 1; border: 1px solid #e6dff5; border-radius: 9px; padding: 8px 11px; font-size: 13px; outline: none; min-width: 0;
}
.f-row input:focus { border-color: #7c6fd0; }
.f-row input:disabled { background: #f8f5fd; color: #9a94ab; }
.f-tip { font-size: 10.5px; color: #b9b3c9; width: 100%; padding-left: 106px; }
.f-check { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: #4a4360; width: auto !important; }
.f-err { color: #d9536b; font-size: 12.5px; margin-top: 4px; }
.m-modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
</style>