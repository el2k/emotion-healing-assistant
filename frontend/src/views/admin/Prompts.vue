<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>提示词管理</h1>
        <p>角色卡提示词外置于 prompts/personas.md · 在线编辑热生效 · 自动备份可回滚</p>
      </div>
      <div class="a-head-actions">
        <span v-if="file.updated_at" class="src-time">源文件更新于 {{ timeText(file.updated_at) }}</span>
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="p-tabs">
      <button v-for="t in tabs" :key="t.id" class="p-tab" :class="{ on: tab === t.id }"
              @click="switchTab(t.id)">{{ t.label }}</button>
    </div>

    <!-- ============ Tab 1: 角色提示词 ============ -->
    <div v-show="tab === 'personas'" class="p-flex">
      <div class="p-side card-lite">
        <input v-model="search" class="p-search" placeholder="搜索角色…" />
        <div v-for="(items, cat) in groupedPersonas" :key="cat" class="p-group">
          <div class="p-cat">{{ cat }}</div>
          <button v-for="p in items" :key="p.id" class="p-item"
                  :class="{ on: current && current.readonly.id === p.id }"
                  @click="openPersona(p.id)">
            <span class="p-emoji">{{ p.emoji }}</span>
            <span class="p-name">{{ p.name }}</span>
            <span v-if="p.heal_target" class="p-heal">{{ p.heal_target }}</span>
          </button>
        </div>
      </div>

      <div v-if="current" class="p-editor card-lite">
        <div class="pe-head">
          <div class="pe-title">
            <span class="pe-emoji">{{ form.emoji }}</span>
            <b>{{ form.name }}</b>
            <span class="pe-id">{{ current.readonly.id }} · {{ current.readonly.category }}<template v-if="current.readonly.work"> · {{ current.readonly.work }}</template></span>
          </div>
          <div class="pe-actions">
            <button class="a-btn ghost" :disabled="saving" @click="resetForm">重置</button>
            <button class="a-btn" :disabled="saving" @click="savePersona">{{ saving ? '保存中…' : '保存（热生效）' }}</button>
          </div>
        </div>

        <div class="pe-grid">
          <div class="pe-form">
            <div class="f-row2">
              <label>显示名</label><input v-model="form.name" maxlength="30" />
              <label>Emoji</label><input v-model="form.emoji" maxlength="8" />
            </div>
            <div class="f-row2">
              <label>标签</label><input v-model="form.tag" maxlength="40" />
              <label>主题色</label><input v-model="form.color" maxlength="16" placeholder="#7c6fd0" />
            </div>
            <div class="f-row1"><label>简介（角色卡片一句话）</label></div>
            <textarea v-model="form.desc" rows="2" maxlength="200"></textarea>
            <div class="f-row1"><label>性格 personality<span class="hint">驱动大模型扮演的核心人设</span></label></div>
            <textarea v-model="form.personality" rows="2" maxlength="300"></textarea>
            <div class="f-row1"><label>说话风格 speech</label></div>
            <textarea v-model="form.speech" rows="2" maxlength="300"></textarea>
            <div class="f-row1"><label>在意的事 cares</label></div>
            <input v-model="form.cares" maxlength="120" />
            <div class="f-row1"><label>口头禅 catchphrases<span class="hint">顿号「、」分隔多条</span></label></div>
            <input v-model="form.catchphraseStr" maxlength="200" placeholder="我在呢、慢慢说" />
            <div class="f-row1">
              <label>兜底语料 voice<span class="hint">LLM 故障时的角色降级语料，每行一条</span></label>
            </div>
            <div class="v-cols">
              <div><b>正向 pos</b><textarea v-model="form.voicePosStr" rows="3"></textarea></div>
              <div><b>负向 neg</b><textarea v-model="form.voiceNegStr" rows="3"></textarea></div>
              <div><b>中性 neu</b><textarea v-model="form.voiceNeuStr" rows="3"></textarea></div>
            </div>
            <p v-if="formError" class="f-err">{{ formError }}</p>
          </div>

          <div class="pe-preview">
            <div class="pp-hd">
              <b>实时预览 · 最终系统提示词</b>
              <span :class="{ saving: previewLoading }">{{ previewLoading ? '更新中…' : '随表单自动刷新' }}</span>
            </div>
            <pre class="pp-body">{{ previewText }}</pre>
          </div>
        </div>
      </div>
      <div v-else class="a-empty" style="padding:40px">← 从左侧选择一个角色开始编辑</div>
    </div>

    <!-- ============ Tab 2: Markdown 源文件 ============ -->
    <div v-show="tab === 'source'" class="card-lite p-src">
      <div class="ps-head">
        <div>
          <b>prompts/personas.md</b>
          <span class="ps-path">{{ file.path }}</span>
        </div>
        <div class="ps-actions">
          <button v-if="!srcEditing" class="a-btn ghost" @click="srcEditing = true">编辑全文</button>
          <template v-else>
            <button class="a-btn ghost" @click="cancelSource">放弃修改</button>
            <button class="a-btn" :disabled="saving" @click="saveSource">{{ saving ? '校验保存中…' : '校验并保存' }}</button>
          </template>
        </div>
      </div>
      <p class="ps-tip">格式：『## 角色名』开启角色；『- 字段: 值』单值；行尾无值 + 缩进『  - 项』为列表。保存时会校验全部 30 个角色，任何格式错误都会被拒绝（不会写坏文件），成功后立即热生效并自动备份当前版本。</p>
      <textarea v-model="srcText" class="ps-editor" :readonly="!srcEditing" spellcheck="false"></textarea>
      <p v-if="srcError" class="f-err">{{ srcError }}</p>
    </div>

    <!-- ============ Tab 3: 安全守则（只读） ============ -->
    <div v-show="tab === 'guards'" class="p-guards">
      <div class="card-lite">
        <div class="pg-hd">
          <b>🔒 全局安全底线</b>
          <span class="a-tag">只读 · 追加到每个角色的系统提示词末尾</span>
        </div>
        <pre class="pg-body">{{ guards.global }}</pre>
      </div>
      <div class="card-lite">
        <div class="pg-hd">
          <b>🩺 心理疗愈室 · 专业守则</b>
          <span class="a-tag">只读 · 仅疗愈室 7 位专家角色附加</span>
        </div>
        <pre class="pg-body">{{ guards.heal }}</pre>
      </div>
      <p class="pg-note">
        两段守则为产品安全护栏（危机识别、12356 转介、不做诊断、不谈药物），
        刻意不开放在线编辑，防止误改导致危机处置失效；如需调整请在代码评审后修改
        <code>personas.py</code> 中的 <code>_GLOBAL_GUARD</code> 与 <code>_HEAL_GUARD</code> 并重启服务。
      </p>
    </div>

    <!-- ============ Tab 4: 历史版本 ============ -->
    <div v-show="tab === 'backups'" class="card-lite">
      <div class="a-card-hd">
        <h3>历史版本 <span class="sub">每次保存自动备份，滚动保留 50 份；恢复前会先备份当前版本</span></h3>
        <span class="a-tag">{{ backups.length }} 份</span>
      </div>
      <div class="bk-table">
        <div class="bk-head"><span>备份文件</span><span>时间</span><span>大小</span><span>操作</span></div>
        <div v-for="b in backups" :key="b.name" class="bk-row">
          <span class="bk-name">{{ b.name }}</span>
          <span>{{ timeText(b.updated_at) }}</span>
          <span>{{ (b.size / 1024).toFixed(1) }} KB</span>
          <button class="mini-btn" :disabled="saving" @click="restore(b.name)">恢复此版本</button>
        </div>
        <div v-if="!backups.length" class="a-empty">还没有备份（首次编辑后自动产生）</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../../api'

const tabs = [
  { id: 'personas', label: '📋 角色提示词' },
  { id: 'source', label: '📄 Markdown 源文件' },
  { id: 'guards', label: '🔒 安全守则' },
  { id: 'backups', label: '🕘 历史版本' },
]
const tab = ref('personas')
const loading = ref(false)
const saving = ref(false)
const search = ref('')

const file = ref({})
const guards = ref({ global: '', heal: '' })
const backups = ref([])
const personaIndex = ref([])

const current = ref(null)
const formError = ref('')
const form = reactive({
  name: '', emoji: '', tag: '', desc: '', color: '',
  personality: '', speech: '', cares: '', catchphraseStr: '',
  voicePosStr: '', voiceNegStr: '', voiceNeuStr: '',
})

const previewText = ref('')
const previewLoading = ref(false)
let previewTimer = null

const srcText = ref('')
const srcEditing = ref(false)
const srcError = ref('')
const srcDraft = ref('')

const groupedPersonas = computed(() => {
  const kw = search.value.trim().toLowerCase()
  const groups = {}
  for (const p of personaIndex.value) {
    if (kw && !(p.name.toLowerCase().includes(kw) || p.id.includes(kw) || (p.tag || '').toLowerCase().includes(kw))) continue
    ;(groups[p.category] = groups[p.category] || []).push(p)
  }
  return groups
})

function timeText(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const diffMin = Math.floor((Date.now() - d) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function splitLines(s) {
  return (s || '').split('\n').map((x) => x.trim()).filter(Boolean)
}
function joinLines(arr) {
  return (arr || []).join('\n')
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/prompts/overview')
    file.value = data.file
    guards.value = data.guards
    backups.value = data.backups || []
    personaIndex.value = data.personas || []
    const { data: src } = await api.get('/admin/prompts/source')
    srcText.value = src.text
    srcDraft.value = src.text
  } catch (e) { /* 忽略 */ } finally {
    loading.value = false
  }
}

function switchTab(t) {
  tab.value = t
  if (t === 'source' && srcEditing.value) {
    // 保留草稿
  }
}

function openPersona(pid) {
  api.get(`/admin/prompts/persona/${pid}`).then(({ data }) => {
    current.value = data
    formError.value = ''
    form.name = data.persona.name
    form.emoji = data.persona.emoji || ''
    form.tag = data.persona.tag || ''
    form.desc = data.persona.desc || ''
    form.color = data.persona.color || ''
    form.personality = data.persona.personality || ''
    form.speech = data.persona.speech || ''
    form.cares = data.persona.cares || ''
    form.catchphraseStr = (data.persona.catchphrases || []).join('、')
    form.voicePosStr = joinLines(data.persona.voice?.pos)
    form.voiceNegStr = joinLines(data.persona.voice?.neg)
    form.voiceNeuStr = joinLines(data.persona.voice?.neu)
    refreshPreview()
  })
}

function buildPatch() {
  return {
    name: form.name, emoji: form.emoji, tag: form.tag, desc: form.desc, color: form.color,
    personality: form.personality, speech: form.speech, cares: form.cares,
    catchphrases: form.catchphraseStr.split('、').map((s) => s.trim()).filter(Boolean),
    voice: { pos: splitLines(form.voicePosStr), neg: splitLines(form.voiceNegStr), neu: splitLines(form.voiceNeuStr) },
  }
}

function refreshPreview() {
  if (!current.value) return
  clearTimeout(previewTimer)
  previewTimer = setTimeout(async () => {
    previewLoading.value = true
    try {
      const { data } = await api.post('/admin/prompts/preview', {
        persona_id: current.value.readonly.id, patch: buildPatch(),
      })
      previewText.value = data.system_prompt
    } catch (e) {
      previewText.value = '⚠ ' + (e.response?.data?.detail || '预览失败')
    } finally {
      previewLoading.value = false
    }
  }, 600)
}

watch(form, refreshPreview, { deep: true })

function resetForm() {
  if (current.value) openPersona(current.value.readonly.id)
}

async function savePersona() {
  if (!current.value) return
  formError.value = ''
  saving.value = true
  try {
    const pid = current.value.readonly.id
    const { data } = await api.put(`/admin/prompts/persona/${pid}`, buildPatch())
    previewText.value = data.system_prompt
    const idx = personaIndex.value.findIndex((p) => p.id === pid)
    if (idx >= 0) {
      personaIndex.value[idx].name = form.name
      personaIndex.value[idx].emoji = form.emoji
      personaIndex.value[idx].tag = form.tag
    }
    alert(`已保存并热生效（备份：${data.backup || '无'}）`)
    await load()
    openPersona(pid)
  } catch (e) {
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

function cancelSource() {
  srcEditing.value = false
  srcText.value = srcDraft.value
  srcError.value = ''
}

async function saveSource() {
  srcError.value = ''
  saving.value = true
  try {
    const { data } = await api.put('/admin/prompts/source', { text: srcText.value })
    alert(`校验通过并保存（${data.personas} 个角色，备份：${data.backup || '无'}）`)
    srcEditing.value = false
    await load()
  } catch (e) {
    srcError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function restore(name) {
  if (!confirm(`恢复到「${name}」？当前版本会先自动备份，恢复后立即生效。`)) return
  saving.value = true
  try {
    await api.post('/admin/prompts/restore', { filename: name })
    alert('已恢复并热生效')
    await load()
    if (current.value) openPersona(current.value.readonly.id)
  } catch (e) {
    alert(e.response?.data?.detail || '恢复失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.p-tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
.p-tab { border: 1px solid #e6dff5; background: #fff; color: #6f6885; border-radius: 20px; padding: 8px 20px; font-size: 13px; cursor: pointer; transition: all .15s; }
.p-tab:hover { border-color: #d9c8f5; }
.p-tab.on { background: var(--primary, #7c6fd0); color: #fff; border-color: var(--primary, #7c6fd0); box-shadow: 0 4px 12px rgba(124, 111, 208, .28); }

.src-time { font-size: 12px; color: #9a94ab; }

.p-flex { display: flex; gap: 16px; align-items: flex-start; }
.card-lite { background: #fff; border: 1px solid #efeaf8; border-radius: 16px; padding: 16px; }

/* 角色侧栏 */
.p-side { width: 242px; flex: none; max-height: 78vh; overflow-y: auto; position: sticky; top: 76px; }
.p-search { width: 100%; border: 1px solid #e6dff5; border-radius: 9px; padding: 8px 12px; font-size: 13px; outline: none; margin-bottom: 10px; }
.p-search:focus { border-color: #7c6fd0; }
.p-cat { font-size: 11px; color: #9a94ab; padding: 10px 6px 4px; letter-spacing: .5px; }
.p-item { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; border: none; background: transparent; padding: 7px 10px; border-radius: 9px; cursor: pointer; font-size: 13px; color: #4a4360; }
.p-item:hover { background: #f6f2fc; }
.p-item.on { background: #f0ecff; color: #5f54a3; font-weight: 600; }
.p-emoji { flex: none; }
.p-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-heal { flex: none; font-size: 10px; color: #2f9e6b; background: #e9f8ef; padding: 1px 6px; border-radius: 8px; }

/* 编辑器 */
.p-editor { flex: 1; min-width: 0; }
.pe-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; gap: 12px; flex-wrap: wrap; }
.pe-title { display: flex; align-items: center; gap: 8px; }
.pe-title b { font-size: 16px; color: #33284f; }
.pe-emoji { font-size: 20px; }
.pe-id { font-size: 11.5px; color: #9a94ab; font-family: Consolas, monospace; }
.pe-actions { display: flex; gap: 8px; }
.pe-grid { display: grid; grid-template-columns: 1.25fr 1fr; gap: 18px; }
@media (max-width: 1100px) { .pe-grid { grid-template-columns: 1fr; } }

.pe-form .f-row2 { display: grid; grid-template-columns: 64px 1fr 64px 1fr; gap: 8px; align-items: center; margin-bottom: 9px; }
.pe-form .f-row1 label { display: block; font-size: 12px; color: #6f6885; margin: 8px 0 4px; font-weight: 600; }
.pe-form .hint { font-weight: 400; color: #b9b3c9; margin-left: 6px; }
.pe-form input, .pe-form textarea {
  border: 1px solid #e6dff5; border-radius: 9px; padding: 8px 11px; font-size: 13px; outline: none; width: 100%;
  font-family: inherit; resize: vertical;
}
.pe-form input:focus, .pe-form textarea:focus { border-color: #7c6fd0; }
.v-cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.v-cols b { display: block; font-size: 11px; color: #9a94ab; margin-bottom: 4px; font-weight: 600; }
.f-err { color: #d9536b; font-size: 12.5px; margin-top: 10px; }

.pe-preview { position: sticky; top: 76px; align-self: start; }
.pp-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pp-hd b { font-size: 13px; color: #33284f; }
.pp-hd span { font-size: 11px; color: #b9b3c9; }
.pp-hd span.saving { color: #7c6fd0; }
.pp-body {
  background: #241f38; color: #d8d2ec; border-radius: 12px; padding: 16px; font-size: 12px;
  line-height: 1.8; white-space: pre-wrap; word-break: break-word; max-height: 66vh; overflow-y: auto;
  font-family: 'Cascadia Code', Consolas, monospace;
}

/* 源文件 */
.p-src .ps-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 12px; flex-wrap: wrap; }
.ps-head b { font-size: 14px; color: #33284f; }
.ps-path { display: block; font-size: 11px; color: #9a94ab; font-family: Consolas, monospace; margin-top: 2px; }
.ps-actions { display: flex; gap: 8px; }
.ps-tip { font-size: 12px; color: #8b869b; line-height: 1.7; margin: 6px 0 12px; }
.ps-editor {
  width: 100%; min-height: 58vh; border: 1px solid #e6dff5; border-radius: 12px; padding: 14px 16px;
  font-family: 'Cascadia Code', Consolas, monospace; font-size: 12.5px; line-height: 1.75; outline: none;
  background: #fdfcff; resize: vertical; white-space: pre; overflow-wrap: normal; overflow-x: auto;
}
.ps-editor:focus { border-color: #7c6fd0; }
.ps-editor[readonly] { background: #f8f5fd; color: #6f6885; }

/* 守则 */
.p-guards { display: flex; flex-direction: column; gap: 16px; }
.pg-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px; }
.pg-hd b { font-size: 14px; color: #33284f; }
.pg-body { background: #f8f5fd; border: 1px dashed #d9c8f5; border-radius: 12px; padding: 14px 18px; font-size: 12.5px; line-height: 2; color: #4a4360; white-space: pre-wrap; }
.pg-note { font-size: 12px; color: #9a94ab; line-height: 1.8; }
.pg-note code { background: #f0ecff; color: #5f54a3; padding: 1px 6px; border-radius: 6px; font-size: 11px; }

/* 备份 */
.bk-table { display: flex; flex-direction: column; }
.bk-head, .bk-row { display: grid; grid-template-columns: 1.8fr 1fr 0.6fr 100px; gap: 12px; padding: 9px 10px; font-size: 12.5px; align-items: center; }
.bk-head { color: #9a94ab; font-size: 11.5px; border-bottom: 1px solid #f1ecfa; }
.bk-row { border-bottom: 1px solid #f8f5fd; color: #4a4360; }
.bk-name { font-family: Consolas, monospace; font-size: 11.5px; color: #5f54a3; }
.mini-btn { border: 1px solid #e6dff5; background: #fdfcff; color: #6f63b8; border-radius: 7px; padding: 5px 10px; font-size: 11.5px; cursor: pointer; justify-self: end; }
.mini-btn:hover { border-color: #7c6fd0; }
</style>