<template>
  <transition name="drawer">
    <div v-if="show" class="trace-mask" @click.self="$emit('close')">
      <div class="trace-drawer">
        <div class="tr-head">
          <div>
            <div class="tr-title">🔬 处理链路</div>
            <div class="tr-sub">
              这条回复是这样一步步生成的（全程透明，LLM 不再是黑盒）
              <template v-if="data">
                · {{ data.node_count }} 个节点 · 总耗时 {{ data.total_ms }}ms
              </template>
            </div>
          </div>
          <button class="tr-close" @click="$emit('close')">✕</button>
        </div>

        <div class="tr-body">
          <div v-if="loading" class="tr-empty">轨迹加载中…（落库为异步，稍等片刻）</div>
          <div v-else-if="error" class="tr-empty tr-err">⚠ {{ error }}</div>
          <template v-else-if="data">
            <!-- 左：节点路径 -->
            <div class="tr-left">
              <div
                v-for="n in data.nodes" :key="n.order"
                class="tr-node" :class="{ sel: active && active.order === n.order, fail: !n.result }"
                @click="active = n"
              >
                <div class="tr-node-bar" :style="{ height: barHeight(n.duration_ms) + 'px' }"></div>
                <div class="tr-node-main">
                  <div class="tr-node-line1">
                    <span class="tr-type" :class="typeClass(n.node_type)">{{ n.node_type }}</span>
                    <b>{{ n.node_name }}</b>
                    <span class="tr-ms">{{ n.duration_ms }}ms</span>
                    <span v-if="!n.result" class="tr-fail">失败</span>
                  </div>
                  <div v-if="n.detail && n.detail.model" class="tr-node-line2">
                    模型 {{ n.detail.model }}<template v-if="n.detail.tokens"> · {{ n.detail.tokens }} tokens</template>
                  </div>
                </div>
              </div>
            </div>

            <!-- 右：选中节点详情 -->
            <div class="tr-right">
              <template v-if="active">
                <div class="tr-detail-hd">
                  <b>{{ active.node_name }}</b>
                  <span class="tr-type" :class="typeClass(active.node_type)">{{ active.node_type }}</span>
                  <span class="tr-ms">{{ active.duration_ms }}ms</span>
                </div>
                <p v-if="active.error" class="tr-detail-err">⚠ {{ active.error }}</p>
                <div class="tr-panel">
                  <div class="tr-panel-hd">
                    <span>{{ inputLabel(active) }}</span>
                    <button v-if="hasText(active.input)" class="tr-copy" @click="copy(active.input)">复制</button>
                  </div>
                  <!-- LLM 节点的入参是 messages 数组：逐条展示 role + 内容 -->
                  <template v-if="active.node_key === 'LLM_REPLY' && Array.isArray(active.input?.messages)">
                    <div v-for="(m, i) in active.input.messages" :key="i" class="tr-msg">
                      <span class="tr-msg-role" :class="m.role">{{ m.role }}</span>
                      <div class="tr-msg-content">{{ m.content }}</div>
                    </div>
                    <div v-if="active.input.user_message" class="tr-msg-mini">用户消息：{{ active.input.user_message }}</div>
                    <div v-if="active.input.model" class="tr-msg-mini">请求模型：{{ active.input.model }}</div>
                  </template>
                  <pre v-else-if="hasText(active.input)" class="tr-json">{{ pretty(active.input) }}</pre>
                  <div v-else class="tr-none">—</div>
                </div>
                <div class="tr-panel">
                  <div class="tr-panel-hd">
                    <span>出参</span>
                    <button v-if="hasText(active.output)" class="tr-copy" @click="copy(active.output)">复制</button>
                  </div>
                  <pre v-if="hasText(active.output)" class="tr-json tr-json-out">{{ pretty(active.output) }}</pre>
                  <div v-else class="tr-none">—</div>
                </div>
              </template>
              <div v-else class="tr-empty">← 点击左侧节点查看详情</div>
            </div>
          </template>
        </div>

        <div class="tr-foot">
          轨迹为你自己的对话链路，仅你与管理员可见 ·
          剧透提醒：LLM_REPLY 节点包含了发给模型的完整提示词与你的长期画像
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  show: { type: Boolean, default: false },
  traceId: { type: String, default: '' },
})
defineEmits(['close'])

const loading = ref(false)
const data = ref(null)
const error = ref('')
const active = ref(null)

async function load(traceId) {
  if (!traceId) return
  loading.value = true
  error.value = ''
  data.value = null
  active.value = null
  // 异步落库：最多重试 6 次（每次 ~0.7s）
  for (let i = 0; i < 6; i++) {
    try {
      const { data: d } = await api.get(`/chat/trace/${traceId}`)
      data.value = d
      active.value = d.nodes && d.nodes.length ? d.nodes[d.nodes.length - 2] || d.nodes[0] : null
      loading.value = false
      return
    } catch (e) {
      if (e.response?.status !== 404) {
        error.value = e.response?.data?.detail || '轨迹查询失败'
        loading.value = false
        return
      }
      await new Promise((r) => setTimeout(r, 700))
    }
  }
  error.value = '轨迹尚未就绪（异步落库中），请稍后再试'
  loading.value = false
}

watch(() => props.show, (v) => { if (v && props.traceId) load(props.traceId) })
watch(() => props.traceId, (v) => { if (props.show && v) load(v) })

function typeClass(t) {
  return {
    LLM: 'is-llm', Emotion: 'is-emo', Intent: 'is-intent', Memory: 'is-mem',
    Flow: 'is-flow', Persist: 'is-persist', Fallback: 'is-fb', Tool: 'is-tool',
    General: 'is-gen',
  }[t] || 'is-gen'
}
function barHeight(ms) {
  const max = Math.max(...(data.value?.nodes || []).map((n) => n.duration_ms), 1)
  return Math.max(6, Math.round(ms / max * 44))
}
function inputLabel(n) {
  return n.node_key === 'LLM_REPLY' ? '入参 · 发给模型的完整内容' : '入参'
}
function hasText(v) {
  return v !== null && v !== undefined && v !== '' && !(typeof v === 'object' && !Object.keys(v).length)
}
function pretty(v) {
  if (typeof v === 'string') return v
  try { return JSON.stringify(v, null, 2) } catch (e) { return String(v) }
}
async function copy(v) {
  try {
    await navigator.clipboard.writeText(pretty(v))
  } catch (e) { /* 忽略 */ }
}
</script>

<style scoped>
.trace-mask { position: fixed; inset: 0; background: rgba(30, 25, 48, .38); backdrop-filter: blur(2px); display: flex; justify-content: flex-end; z-index: 160; }
.trace-drawer { width: min(880px, 94vw); height: 100%; background: #fbf9fe; display: flex; flex-direction: column; box-shadow: -12px 0 40px rgba(40, 30, 70, .18); }

.tr-head { flex: none; padding: 18px 22px 14px; background: #fff; border-bottom: 1px solid #efeaf8; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.tr-title { font-size: 17px; font-weight: 700; color: #33284f; }
.tr-sub { font-size: 12px; color: #8b869b; margin-top: 4px; line-height: 1.6; }
.tr-close { border: none; background: #f6f2fc; color: #6f6885; width: 30px; height: 30px; border-radius: 9px; cursor: pointer; font-size: 14px; }
.tr-close:hover { background: #efe8fa; }

.tr-body { flex: 1; display: flex; min-height: 0; }
.tr-left { width: 300px; flex: none; overflow-y: auto; padding: 14px; border-right: 1px solid #f1ecfa; background: #f8f5fd; }
.tr-right { flex: 1; min-width: 0; overflow-y: auto; padding: 16px 18px; }

.tr-node { display: flex; gap: 9px; padding: 7px 8px; border-radius: 10px; cursor: pointer; margin-bottom: 3px; align-items: stretch; }
.tr-node:hover { background: #f1ecfa; }
.tr-node.sel { background: #ece5fa; }
.tr-node-bar { width: 4px; flex: none; border-radius: 2px; background: #d9d0ef; }
.tr-node.sel .tr-node-bar { background: #7c6fd0; }
.tr-node.fail .tr-node-bar { background: #d9536b; }
.tr-node-main { min-width: 0; flex: 1; }
.tr-node-line1 { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.tr-node-line1 b { font-size: 12.5px; color: #3a3545; font-weight: 600; }
.tr-ms { font-size: 10.5px; color: #9a94ab; font-family: Consolas, monospace; margin-left: auto; }
.tr-node-line2 { font-size: 10.5px; color: #8b869b; margin-top: 3px; font-family: Consolas, monospace; }
.tr-fail { font-size: 10px; color: #d9536b; background: #fdeef0; padding: 0 6px; border-radius: 7px; }

.tr-type { flex: none; font-size: 10px; padding: 1px 7px; border-radius: 7px; font-weight: 600; font-family: Consolas, monospace; }
.tr-type.is-llm { color: #2a7fa8; background: #e8f4fb; }
.tr-type.is-emo { color: #d9536b; background: #fdeef0; }
.tr-type.is-intent { color: #d68a2e; background: #fff4e8; }
.tr-type.is-mem { color: #2f9e6b; background: #e9f8ef; }
.tr-type.is-flow { color: #7c6fd0; background: #f0ecff; }
.tr-type.is-persist { color: #6f6885; background: #f1eef7; }
.tr-type.is-fb { color: #b26a1d; background: #fff4e8; }
.tr-type.is-tool { color: #2e9e8f; background: #e5f7f4; }
.tr-type.is-gen { color: #9a94ab; background: #f6f4f8; }

.tr-detail-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
.tr-detail-hd b { font-size: 15px; color: #33284f; }
.tr-detail-err { font-size: 12.5px; color: #d9536b; background: #fdeef0; border-radius: 8px; padding: 8px 12px; }

.tr-panel { background: #fff; border: 1px solid #efeaf8; border-radius: 12px; margin-bottom: 12px; overflow: hidden; }
.tr-panel-hd { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: #faf8fe; border-bottom: 1px solid #f1ecfa; font-size: 12px; color: #6f6885; font-weight: 600; }
.tr-copy { border: none; background: #f0ecff; color: #6f63b8; font-size: 10.5px; border-radius: 7px; padding: 3px 9px; cursor: pointer; }
.tr-copy:hover { background: #e4dcf9; }
.tr-json { margin: 0; padding: 12px; font-size: 11.5px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; color: #3a3545; font-family: 'Cascadia Code', Consolas, monospace; max-height: 34vh; overflow-y: auto; }
.tr-json-out { color: #2f6e4f; background: #fbfefc; }
.tr-none { padding: 16px; text-align: center; color: #b9b3c9; font-size: 12px; }

/* LLM messages 分条展示 */
.tr-msg { display: flex; gap: 9px; padding: 9px 12px; border-bottom: 1px solid #f6f2fc; align-items: flex-start; }
.tr-msg:last-of-type { border-bottom: none; }
.tr-msg-role { flex: none; font-size: 10px; padding: 2px 7px; border-radius: 7px; font-family: Consolas, monospace; margin-top: 2px; font-weight: 600; }
.tr-msg-role.system { color: #7c6fd0; background: #f0ecff; }
.tr-msg-role.user { color: #2a7fa8; background: #e8f4fb; }
.tr-msg-role.assistant { color: #2f9e6b; background: #e9f8ef; }
.tr-msg-content { font-size: 11.5px; line-height: 1.75; color: #3a3545; white-space: pre-wrap; word-break: break-word; max-height: 180px; overflow-y: auto; }
.tr-msg-mini { padding: 6px 12px; font-size: 11px; color: #8b869b; background: #faf8fe; border-top: 1px solid #f1ecfa; }

.tr-empty { padding: 60px 20px; text-align: center; color: #9a94ab; font-size: 13px; width: 100%; }
.tr-err { color: #d9536b; }

.tr-foot { flex: none; padding: 10px 22px; font-size: 11px; color: #9a94ab; background: #fff; border-top: 1px solid #efeaf8; line-height: 1.6; }

.drawer-enter-active, .drawer-leave-active { transition: opacity .18s ease; }
.drawer-enter-active .trace-drawer, .drawer-leave-active .trace-drawer { transition: transform .22s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .trace-drawer, .drawer-leave-to .trace-drawer { transform: translateX(30px); }
</style>