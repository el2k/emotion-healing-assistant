<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>系统信息</h1>
        <p>运行环境、存储占用与大模型接入状态</p>
      </div>
      <div class="a-head-actions">
        <button class="a-btn ghost" @click="checkHealth">健康检查</button>
        <button class="a-btn ghost" @click="load">刷新</button>
      </div>
    </div>

    <div class="a-kpis">
      <div class="a-kpi" style="--kpi-tint:#f1ecff;--kpi-color:#7c6fd0">
        <div class="k-top"><span class="k-ico">◈</span>应用版本</div>
        <div class="k-num">v{{ info.version || '—' }}</div>
        <div class="k-foot">{{ info.app }}</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#e9f6ff;--kpi-color:#3d8fd0">
        <div class="k-top"><span class="k-ico">▤</span>数据库体积</div>
        <div class="k-num">{{ info.db?.size_mb ?? '—' }} <small style="font-size:13px">MB</small></div>
        <div class="k-foot">SQLite 单文件存储</div>
      </div>
      <div class="a-kpi" style="--kpi-tint:#fff4e8;--kpi-color:#d68a2e">
        <div class="k-top"><span class="k-ico">▧</span>上传文件</div>
        <div class="k-num">{{ info.uploads?.files ?? '—' }}</div>
        <div class="k-foot">共 {{ info.uploads?.size_mb ?? 0 }} MB</div>
      </div>
      <div class="a-kpi" :style="info.llm?.enabled ? '--kpi-tint:#e9f8ef;--kpi-color:#2f9e6b' : '--kpi-tint:#f5f3f8;--kpi-color:#8b869b'">
        <div class="k-top"><span class="k-ico">✦</span>大模型</div>
        <div class="k-num" style="font-size:18px">{{ info.llm?.enabled ? '已接入' : '未启用' }}</div>
        <div class="k-foot">{{ info.llm?.enabled ? info.llm.model : '本地规则引擎兜底' }}</div>
      </div>
    </div>

    <div class="a-grid-2">
      <div class="a-card">
        <div class="a-card-hd"><h3>数据规模</h3></div>
        <div class="a-card-bd">
          <div class="kv"><span>用户</span><b>{{ info.counts?.users ?? 0 }}</b></div>
          <div class="kv"><span>会话</span><b>{{ info.counts?.sessions ?? 0 }}</b></div>
          <div class="kv"><span>消息</span><b>{{ info.counts?.messages ?? 0 }}</b></div>
          <div class="kv"><span>情绪记录</span><b>{{ info.counts?.emotions ?? 0 }}</b></div>
          <div class="kv"><span>社区帖子</span><b>{{ info.counts?.posts ?? 0 }}</b></div>
          <div class="kv"><span>角色数量</span><b>{{ info.counts?.personas ?? 0 }}</b></div>
        </div>
      </div>

      <div class="a-card">
        <div class="a-card-hd"><h3>运行配置</h3><span class="a-tag" :class="health.ok ? 'ok' : 'off'">{{ health.text }}</span></div>
        <div class="a-card-bd">
          <div class="kv"><span>数据库文件</span><b class="mono">{{ info.db?.path }}</b></div>
          <div class="kv"><span>调试模式</span><b>{{ info.debug ? '开启' : '关闭' }}</b></div>
          <div class="kv"><span>模型接口</span><b class="mono">{{ info.llm?.enabled ? info.llm.base_url : '—' }}</b></div>
          <div class="kv"><span>密钥配置</span><b>{{ info.llm?.has_key ? '已配置' : '未配置' }}</b></div>
          <p class="hint">修改 <code>backend/.env</code> 中的 <code>LLM_ENABLED / LLM_API_KEY / LLM_MODEL</code> 后重启服务即可启用 AI 深度模式。</p>
        </div>
      </div>
    </div>

    <div class="a-card">
      <div class="a-card-hd"><h3>环境变量示例</h3><span class="a-tag">backend/.env</span></div>
      <div class="a-card-bd">
        <pre class="code">LLM_ENABLED=true
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-****
LLM_MODEL=gpt-4o-mini

# 管理员初始账号（首次启动自动创建）
ADMIN_PHONE=13800000000
ADMIN_PASSWORD=admin123</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../../api'

const info = reactive({ counts: {}, db: {}, uploads: {}, llm: {} })
const health = reactive({ ok: false, text: '未检查' })

async function load() {
  const { data } = await api.get('/admin/system')
  Object.assign(info, data)
}
async function checkHealth() {
  try {
    const { data } = await api.get('/health')
    health.ok = data.status === 'ok'
    health.text = health.ok ? '服务正常' : '状态异常'
  } catch (e) {
    health.ok = false
    health.text = '连接失败'
  }
}
onMounted(() => { load(); checkHealth() })
</script>

<style scoped>
.kv { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 9px 0; border-bottom: 1px dashed #f3eefc; font-size: 13px; }
.kv:last-of-type { border-bottom: none; }
.kv span { color: var(--text-soft); flex: none; }
.kv b { font-weight: 600; text-align: right; word-break: break-all; }
.mono { font-family: Consolas, "SFMono-Regular", monospace; font-size: 12px; }
.hint { font-size: 12px; color: var(--text-soft); background: #faf8ff; padding: 9px 11px; border-radius: 8px; margin-top: 10px; line-height: 1.7; }
.hint code, .code { font-family: Consolas, monospace; }
code { background: #f2eefc; color: #6f63b8; padding: 1px 5px; border-radius: 4px; font-size: 11.5px; }
.code { background: #241f38; color: #d9d3f0; padding: 14px 16px; border-radius: 10px; font-size: 12.5px; line-height: 1.8; overflow-x: auto; }
</style>