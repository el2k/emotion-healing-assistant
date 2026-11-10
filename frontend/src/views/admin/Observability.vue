<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>可观测性</h1>
        <p>请求指标 · LLM 健康与断路器 · 数据漂移检测 · 系统深度健康检查</p>
      </div>
      <div class="a-head-actions">
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
        <button v-if="breaker.state === 'open'" class="a-btn" @click="resetBreaker">
          重置断路器
        </button>
      </div>
    </div>

    <!-- 断路器告警条 -->
    <div v-if="breaker.state === 'open'" class="breaker-alert">
      ⚠️ LLM 断路器已 OPEN（连续失败 {{ breaker.failure_count }} 次）。
      当前所有回复走本地规则降级，用户不会看到失败。
      <span v-if="breaker.last_error">最近错误：{{ breaker.last_error }}</span>
    </div>

    <!-- KPI -->
    <div class="a-kpis">
      <div class="a-kpi" style="--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b">
        <div class="k-top"><span class="k-ico">⏱</span>运行时长</div>
        <div class="k-num">{{ lifetime.uptime_human || '—' }}</div>
        <div class="k-foot">{{ lifetime.total_requests }} 次请求</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#f0ecff;--kpi-color:#7c6fd0">
        <div class="k-top"><span class="k-ico">📊</span>5 分钟请求</div>
        <div class="k-num">{{ req5m.count || 0 }}</div>
        <div class="k-foot">P95 {{ req5m.p95_ms || 0 }}ms</div>
      </div>
      <div class="a-kpi" :class="{ warn: lifetime.error_rate > 5 }"
           style="--kpi-tint:#fff4e8;--kpi-color:#d68a2e">
        <div class="k-top"><span class="k-ico">!</span>错误率</div>
        <div class="k-num">{{ lifetime.error_rate || 0 }}%</div>
        <div class="k-foot">{{ lifetime.total_errors }} 次错误</div>
      </div>
      <div class="a-kpi" :class="{ warn: breaker.state !== 'closed' }"
           :style="breaker.state === 'closed'
             ? '--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b'
             : '--kpi-tint:#fdeef0;--kpi-color:#d9536b'">
        <div class="k-top"><span class="k-ico">⚡</span>LLM 断路器</div>
        <div class="k-num" style="font-size:18px">
          {{ breaker.state === 'closed' ? '正常' :
             breaker.state === 'open' ? '已断开' : '探测中' }}
        </div>
        <div class="k-foot">
          {{ llm.count || 0 }} 次调用 · 降级 {{ llm.fallbacks || 0 }} 次
        </div>
      </div>
    </div>

    <div class="a-grid-2">
      <!-- 请求指标 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>请求延迟（最近 1 小时）</h3>
          <span class="a-tag">{{ req1h.count || 0 }} 次</span>
        </div>
        <div class="a-card-bd">
          <div class="latency-row">
            <span>P50</span><b>{{ req1h.p50_ms || 0 }}ms</b>
            <span>P95</span><b class="warn" v-if="req1h.p95_ms > 2000">{{ req1h.p95_ms || 0 }}ms ⚠</b>
            <b v-else>{{ req1h.p95_ms || 0 }}ms</b>
            <span>P99</span><b>{{ req1h.p99_ms || 0 }}ms</b>
          </div>
          <div v-if="Object.keys(req1h.per_path || {}).length" class="path-table">
            <div class="pt-head"><span>路径</span><span>次数</span><span>延迟</span><span>错误率</span></div>
            <div v-for="(pd, path) in req1h.per_path" :key="path" class="pt-row">
              <span class="pt-path">{{ path }}</span>
              <span>{{ pd.count }}</span>
              <span>{{ pd.avg_ms }}ms</span>
              <span :class="{ err: pd.error_rate > 0 }">{{ pd.error_rate }}%</span>
            </div>
          </div>
          <div v-else class="a-empty">1 小时内无请求</div>
        </div>
      </div>

      <!-- LLM 指标 -->
      <div class="a-card">
        <div class="a-card-hd">
          <h3>LLM 调用（最近 1 小时）</h3>
          <span class="a-tag">{{ llm.count || 0 }} 次</span>
        </div>
        <div class="a-card-bd">
          <div class="llm-stats">
            <div><b>{{ llm.success || 0 }}</b><span>成功</span></div>
            <div><b class="err">{{ llm.failures || 0 }}</b><span>失败</span></div>
            <div><b class="fb">{{ llm.fallbacks || 0 }}</b><span>降级</span></div>
            <div><b>{{ llm.avg_ms || 0 }}ms</b><span>均延迟</span></div>
          </div>
          <div class="llm-bar">
            <div class="a-bar" v-if="llm.count">
              <i :style="{ width: ((llm.success || 0) / llm.count * 100) + '%' }"></i>
            </div>
          </div>
          <p class="llm-note">
            降级 = LLM 调用失败后自动切换到本地规则引擎（用户无感知，但回复质量降低）。
            断路器 OPEN 时跳过 LLM 调用直接走降级，避免级联超时。
          </p>
        </div>
      </div>
    </div>

    <!-- 数据漂移检测 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>数据漂移检测 <span class="sub">输入分布是否发生显著变化</span></h3>
        <span class="a-tag" :class="drift.overall_status === 'drift_detected' ? 'danger' : 'ok'">
          {{ drift.overall_status === 'drift_detected' ? '⚠ 检测到漂移' : '稳定' }}
        </span>
      </div>
      <div class="a-card-bd">
        <div class="drift-grid">
          <div class="drift-item">
            <b>情绪分布</b>
            <span :class="drift.emotion_distribution?.status">
              JSD {{ drift.emotion_distribution?.js_divergence ?? '—' }}
            </span>
            <p>{{ drift.emotion_distribution?.message }}</p>
          </div>
          <div class="drift-item">
            <b>高风险率</b>
            <span :class="drift.highrisk_rate?.status">
              {{ drift.highrisk_rate?.recent_rate ?? '—' }}% vs {{ drift.highrisk_rate?.baseline_rate ?? '—' }}%
            </span>
            <p>{{ drift.highrisk_rate?.message }}</p>
          </div>
          <div class="drift-item">
            <b>输入长度</b>
            <span :class="drift.input_length?.status">
              {{ drift.input_length?.recent_avg_len ?? '—' }} 字
            </span>
            <p>{{ drift.input_length?.message }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 深度健康 -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>深度健康检查</h3>
        <span class="a-tag" :class="health.status === 'ok' ? 'ok' : 'warn'">{{ health.status }}</span>
      </div>
      <div class="a-card-bd">
        <div class="health-grid">
          <div v-for="(chk, name) in health.checks || {}" :key="name" class="health-item">
            <span class="hc-name">{{ name }}</span>
            <span class="a-tag" :class="{
              ok: chk.status === 'ok',
              warn: chk.status === 'degraded' || chk.status === 'warn',
              danger: chk.status === 'fail',
              off: chk.status === 'unknown',
            }">{{ chk.status }}</span>
            <span class="hc-msg">{{ chk.message || '' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 请求日志（最近错误） -->
    <div class="a-card">
      <div class="a-card-hd">
        <h3>最近请求 <span class="sub">含错误详情</span></h3>
      </div>
      <div class="a-card-bd" style="padding-top:8px">
        <div class="log-table">
          <div class="lt-head"><span>路径</span><span>状态</span><span>延迟</span><span>错误</span></div>
          <div v-for="(r, i) in recentErrors" :key="i" class="lt-row">
            <span class="lt-path">{{ r.path }}</span>
            <span :class="{ err: r.status >= 500 }">{{ r.status }}</span>
            <span>{{ r.latency_ms }}ms</span>
            <span class="lt-err" :title="r.error">{{ r.error || '—' }}</span>
          </div>
          <div v-if="!recentErrors.length" class="a-empty">无请求记录</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import { api } from '../../api'

const loading = ref(false)
const data = reactive({})

const lifetime = computed(() => data.lifetime || {})
const req5m = computed(() => data.request_metrics?.last_5m || {})
const req1h = computed(() => data.request_metrics?.last_1h || {})
const llm = computed(() => data.llm_metrics || {})
const breaker = computed(() => data.llm_breaker || { state: 'closed' })
const drift = computed(() => data.drift || {})
const health = computed(() => data.health || { status: 'unknown' })

// 从 per_path 中提取最近有错误的路径
const recentErrors = computed(() => {
  const paths = req1h.value.per_path || {}
  return Object.entries(paths)
    .filter(([_, d]) => d.error_rate > 0)
    .map(([path, d]) => ({
      path, status: 500, latency_ms: d.avg_ms,
      error: `错误率 ${d.error_rate}%`,
    }))
})

async function load() {
  loading.value = true
  try {
    const { data: d } = await api.get('/admin/observability/overview')
    Object.assign(data, d)
  } catch (e) {
    console.error('观测数据加载失败', e)
  } finally {
    loading.value = false
  }
}

async function resetBreaker() {
  try {
    await api.post('/admin/observability/breaker/reset')
    load()
  } catch (e) { /* 忽略 */ }
}

onMounted(load)
</script>

<style scoped>
.breaker-alert {
  background: #fdeef0; border: 1px solid #f3c2cb; color: #a85464;
  padding: 12px 18px; border-radius: 10px; font-size: 13px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.breaker-alert span { color: #d9536b; font-size: 12px; }

.latency-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.latency-row span { font-size: 11.5px; color: var(--text-soft); }
.latency-row b { font-size: 15px; color: #5f54a3; }
.latency-row b.warn { color: #d68a2e; }

.path-table { font-size: 12.5px; }
.pt-head, .pt-row { display: grid; grid-template-columns: 1fr 50px 70px 50px; gap: 6px; padding: 4px 0; }
.pt-head { color: var(--text-soft); font-size: 11px; border-bottom: 1px solid #f0ebf9; }
.pt-row { border-bottom: 1px dashed #f5f1fb; }
.pt-path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pt-row span.err { color: #d9536b; font-weight: 600; }

.llm-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.llm-stats div { text-align: center; }
.llm-stats b { display: block; font-size: 18px; color: #5f54a3; }
.llm-stats b.err { color: #d9536b; }
.llm-stats b.fb { color: #d68a2e; }
.llm-stats span { font-size: 11px; color: var(--text-soft); }
.llm-bar { margin-top: 10px; }
.llm-note { font-size: 11.5px; color: var(--text-soft); margin-top: 10px; line-height: 1.7; }

.drift-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.drift-item { border: 1px solid #eee9f7; border-radius: 10px; padding: 12px 14px; }
.drift-item b { display: block; font-size: 13px; margin-bottom: 6px; }
.drift-item span { font-size: 13px; font-weight: 600; }
.drift-item span.stable, .drift-item span.ok { color: #2f9e6b; }
.drift-item span.drift { color: #d9536b; }
.drift-item span.insufficient_data { color: #8b869b; font-weight: 400; }
.drift-item p { font-size: 11.5px; color: var(--text-soft); margin-top: 6px; line-height: 1.6; }

.health-grid { display: flex; flex-direction: column; gap: 8px; }
.health-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #fdfcff; border-radius: 8px; border: 1px solid #f5f1fb; }
.hc-name { font-size: 13px; font-weight: 600; width: 100px; flex: none; }
.hc-msg { font-size: 12px; color: var(--text-soft); }

.log-table { font-size: 12.5px; }
.lt-head, .lt-row { display: grid; grid-template-columns: 1fr 40px 60px 1fr; gap: 6px; padding: 4px 0; }
.lt-head { color: var(--text-soft); font-size: 11px; border-bottom: 1px solid #f0ebf9; }
.lt-row { border-bottom: 1px dashed #f5f1fb; }
.lt-path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lt-row span.err { color: #d9536b; font-weight: 600; }
.lt-err { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #d9536b; font-size: 11.5px; }

@media (max-width: 900px) { .drift-grid { grid-template-columns: 1fr; } }
</style>