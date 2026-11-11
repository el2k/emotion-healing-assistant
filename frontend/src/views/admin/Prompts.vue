<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>提示词管理</h1>
        <p>角色卡提示词外置于 prompts/personas.md · 单角色左编辑右实时渲染 · 保存热生效 · 自动备份可回滚</p>
      </div>
      <div class="a-head-actions">
        <span v-if="file.updated_at" class="src-time">源文件更新于 {{ timeText(file.updated_at) }}</span>
        <button class="a-btn ghost" :disabled="loading" @click="load">刷新</button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="p-tabs">
      <button v-for="t in tabs" :key="t.id" class="p-tab" :class="{ on: tab === t.id }"
              @click="tab = t.id">{{ t.label }}</button>
    </div>

    <!-- ============ Tab 1: 角色提示词（单角色：左编辑 / 右实时渲染） ============ -->
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
            <span class="pe-emoji">{{ titleEmoji }}</span>
            <b>{{ titleName }}</b>
            <span class="mdc-id">{{ current.readonly.id }}</span>
            <span class="mdc-cat">{{ current.readonly.category }}</span>
            <span v-if="current.readonly.heal_target" class="mdc-heal">{{ current.readonly.heal_target }}</span>
            <span v-if="current.readonly.model_3d" class="mdc-3d">3D</span>
          </div>
          <div class="pe-actions">
            <span class="save-state" :class="{ warn: personaMd !== personaDraft }">
              {{ personaMd === personaDraft ? '已同步' : '有未保存修改' }}
            </span>
            <button class="a-btn ghost" :disabled="saving || personaMd === personaDraft" @click="resetPersona">放弃修改</button>
            <button class="a-btn" :disabled="saving || personaMd === personaDraft" @click="savePersona">
              {{ saving ? '校验保存中…' : '保存（热生效）' }}
            </button>
          </div>
        </div>

        <p v-if="personaError" class="md-error">⚠ {{ personaError }}</p>

        <div class="pe-md-split">
          <div class="md-edit-pane">
            <div class="pane-hd">Markdown 源码 · 本角色</div>
            <textarea ref="mdEditorRef" v-model="personaMd" class="md-editor" spellcheck="false" wrap="off"
                      placeholder="## 角色名&#10;- id: xxx&#10;- personality: ……"></textarea>
          </div>
          <div class="md-preview-pane">
            <div class="pane-hd">
              实时渲染
              <span v-if="unknownLines" class="pane-warn">⚠ {{ unknownLines }} 行格式异常（保存会被拒绝）</span>
              <span v-else class="pane-ok">✓ 格式正确</span>
            </div>
            <div class="md-preview">
              <div v-for="(b, bi) in previewBlocks" :key="bi" class="mdc-card">
                <template v-if="b.type === 'card'">
                  <div class="mdc-title">
                    <span class="mdc-name">{{ b.title }}</span>
                    <span v-for="f in b.fields.filter(x => x.key === 'id')" :key="'id'" class="mdc-id">{{ f.val }}</span>
                    <span v-for="f in b.fields.filter(x => x.key === 'category')" :key="'cat'" class="mdc-cat">{{ f.val }}</span>
                    <span v-for="f in b.fields.filter(x => x.key === 'heal_target')" :key="'ht'" class="mdc-heal">{{ f.val }}</span>
                    <span v-for="f in b.fields.filter(x => x.key === 'model_3d')" :key="'3d'" class="mdc-3d">3D</span>
                  </div>
                  <div v-for="(f, fi) in b.fields.filter(x => !['id','category','heal_target','model_3d'].includes(x.key))"
                       :key="fi" class="mdc-field" :class="{ list: f.items }">
                    <span class="mdc-key">{{ fieldLabel(f.key) }}</span>
                    <span v-if="f.items" class="mdc-chips">
                      <span v-for="(it, ii) in f.items" :key="ii" class="mdc-chip">{{ it }}</span>
                      <span v-if="!f.items.length" class="mdc-empty">（空列表）</span>
                    </span>
                    <span v-else class="mdc-val">{{ f.val }}</span>
                  </div>
                </template>
                <div v-else class="mdc-raw">
                  <span class="mdc-raw-line">{{ b.line }}</span>
                  <span class="mdc-raw-badge">第 {{ b.lineNo }} 行</span>
                </div>
              </div>
              <p v-if="!previewBlocks.length" class="mdc-empty-all">左侧输入 Markdown，右侧实时渲染该角色卡</p>
            </div>
          </div>
        </div>

        <div class="pe-sys">
          <button class="sys-toggle" @click="showSys = !showSys">
            {{ showSys ? '▾ 收起' : '▸ 预览' }}最终系统提示词（注入大模型的完整文本）
          </button>
          <pre v-if="showSys" class="sys-body">{{ sysPrompt }}</pre>
        </div>
        <p class="md-format-tip">
          单角色编辑：本页只编辑当前角色的一个块。『## 角色名』为标题；『- 字段: 值』单值；行尾无值 + 缩进『  - 项』为列表。
          id / category / work / heal_target 为技术字段不可修改；保存时逐行校验，自动备份并热生效。
        </p>
      </div>
      <div v-else class="a-empty" style="padding:40px">← 从左侧选择一个角色开始编辑</div>
    </div>

    <!-- ============ Tab 2: 安全守则（只读） ============ -->
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

    <!-- ============ Tab 3: 历史版本 ============ -->
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
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api'

const tabs = [
  { id: 'personas', label: '📋 角色提示词' },
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

/* ===== 单角色编辑器状态 ===== */
const current = ref(null)
const personaMd = ref('')
const personaDraft = ref('')
const personaError = ref('')
const sysPrompt = ref('')
const showSys = ref(false)
const mdEditorRef = ref(null)

/* ===== 实时渲染（单角色 Markdown → 角色卡片） ===== */
const previewBlocks = ref([])
const unknownLines = ref(0)
const titleName = ref('')
const titleEmoji = ref('🎭')
let renderTimer = null

const FIELD_LABELS = {
  name: '名称', emoji: 'Emoji', work: '来源', tag: '标签', desc: '简介', color: '主题色',
  personality: '性格', speech: '说话风格', cares: '在意的事',
  catchphrases: '口头禅', 'voice.pos': '正向语料', 'voice.neg': '负向语料', 'voice.neu': '中性语料',
}
function fieldLabel(key) {
  return FIELD_LABELS[key] || key
}

function formatErr(e, fallback) {
  const d = e.response?.data || {}
  const base = d.detail || fallback
  return d.error_type ? `${base}（${d.error_type}${d.request_id ? ' · ' + d.request_id : ''}）` : base
}

function renderMarkdown(text) {
  const blocks = []
  const lines = text.split('\n')
  let inComment = false
  let cur = null
  let pendingField = null
  let unknown = 0
  let firstTitle = ''
  let firstEmoji = ''

  lines.forEach((line, idx) => {
    const s = line.trim()
    const lineNo = idx + 1
    if (inComment) {
      if (s.includes('-->')) inComment = false
      return
    }
    if (s.startsWith('<!--')) {
      if (!s.includes('-->')) inComment = true
      return
    }
    if (!s) return
    if (line.startsWith('## ')) {
      cur = { type: 'card', title: line.slice(3).trim(), fields: [] }
      blocks.push(cur)
      pendingField = null
      if (!firstTitle) firstTitle = cur.title
      return
    }
    if (!cur) {
      blocks.push({ type: 'raw', line: s, lineNo })
      unknown += 1
      return
    }
    if (/^\s{2,}- /.test(line) && pendingField) {
      pendingField.items.push(line.replace(/^\s+- /, '').trim())
      return
    }
    if (line.startsWith('- ')) {
      const body = line.slice(2)
      const i = body.indexOf(':')
      if (i < 0) {
        blocks.push({ type: 'raw', line: s, lineNo })
        unknown += 1
        return
      }
      const key = body.slice(0, i).trim()
      const val = body.slice(i + 1).trim()
      pendingField = null
      if (key === 'emoji' && val && !firstEmoji) firstEmoji = val
      if (val === '') {
        const f = { key, items: [] }
        cur.fields.push(f)
        pendingField = f
      } else {
        cur.fields.push({ key, val })
      }
      return
    }
    blocks.push({ type: 'raw', line: s, lineNo })
    unknown += 1
  })

  previewBlocks.value = blocks
  unknownLines.value = unknown
  titleName.value = firstTitle
  titleEmoji.value = firstEmoji || '🎭'
}

watch(personaMd, (v) => {
  clearTimeout(renderTimer)
  renderTimer = setTimeout(() => renderMarkdown(v), 250)
})

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

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/admin/prompts/overview')
    file.value = data.file
    guards.value = data.guards
    backups.value = data.backups || []
    personaIndex.value = data.personas || []
  } catch (e) { /* 忽略 */ } finally {
    loading.value = false
  }
}

async function openPersona(pid) {
  personaError.value = ''
  try {
    const { data } = await api.get(`/admin/prompts/persona/${pid}/markdown`)
    current.value = data
    personaMd.value = data.markdown
    personaDraft.value = data.markdown
    sysPrompt.value = data.system_prompt || ''
    renderMarkdown(data.markdown)
  } catch (e) {
    personaError.value = formatErr(e, '加载角色失败')
  }
}

function resetPersona() {
  personaMd.value = personaDraft.value
  personaError.value = ''
  renderMarkdown(personaMd.value)
}

async function savePersona() {
  if (!current.value) return
  personaError.value = ''
  saving.value = true
  try {
    const pid = current.value.readonly.id
    const { data } = await api.put(`/admin/prompts/persona/${pid}/markdown`,
                                    { markdown: personaMd.value })
    personaDraft.value = personaMd.value
    sysPrompt.value = data.system_prompt || sysPrompt.value
    // 同步左侧列表的显示名/emoji（名称可能在 Markdown 里被改）
    const idx = personaIndex.value.findIndex((p) => p.id === pid)
    if (idx >= 0) {
      personaIndex.value[idx].name = titleName.value || personaIndex.value[idx].name
      personaIndex.value[idx].emoji = titleEmoji.value || personaIndex.value[idx].emoji
    }
    alert(`已保存并热生效（备份：${data.backup || '无'}）`)
    await load()
  } catch (e) {
    personaError.value = formatErr(e, '保存失败')
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
.p-side { width: 242px; flex: none; max-height: 80vh; overflow-y: auto; position: sticky; top: 76px; }
.p-search { width: 100%; border: 1px solid #e6dff5; border-radius: 9px; padding: 8px 12px; font-size: 13px; outline: none; margin-bottom: 10px; }
.p-search:focus { border-color: #7c6fd0; }
.p-cat { font-size: 11px; color: #9a94ab; padding: 10px 6px 4px; letter-spacing: .5px; }
.p-item { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; border: none; background: transparent; padding: 7px 10px; border-radius: 9px; cursor: pointer; font-size: 13px; color: #4a4360; }
.p-item:hover { background: #f6f2fc; }
.p-item.on { background: #f0ecff; color: #5f54a3; font-weight: 600; }
.p-emoji { flex: none; }
.p-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-heal { flex: none; font-size: 10px; color: #2f9e6b; background: #e9f8ef; padding: 1px 6px; border-radius: 8px; }

/* 单角色编辑器 */
.p-editor { flex: 1; min-width: 0; }
.pe-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 12px; flex-wrap: wrap; }
.pe-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pe-title b { font-size: 16px; color: #33284f; }
.pe-emoji { font-size: 20px; }
.pe-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.save-state { font-size: 11.5px; color: #2f9e6b; background: #e9f8ef; padding: 3px 10px; border-radius: 10px; }
.save-state.warn { color: #d68a2e; background: #fff4e8; }
.md-error { color: #d9536b; font-size: 12.5px; background: #fdeef0; border: 1px solid #f4ccd4; border-radius: 10px; padding: 9px 14px; margin: 0 0 10px; white-space: pre-wrap; }

.pe-md-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; min-height: 54vh; }
@media (max-width: 1100px) { .pe-md-split { grid-template-columns: 1fr; } }
.md-edit-pane, .md-preview-pane { display: flex; flex-direction: column; border: 1px solid #efeaf8; border-radius: 12px; overflow: hidden; min-height: 320px; }
.pane-hd {
  flex: none; display: flex; justify-content: space-between; align-items: center;
  padding: 8px 13px; font-size: 12px; color: #6f6885; font-weight: 600;
  background: #faf8fe; border-bottom: 1px solid #f1ecfa;
}
.pane-hd .pane-ok { color: #2f9e6b; font-weight: 500; font-size: 11px; }
.pane-hd .pane-warn { color: #d68a2e; font-weight: 500; font-size: 11px; }
.md-editor {
  flex: 1; width: 100%; min-height: 52vh; border: none; outline: none; resize: none;
  padding: 13px 15px; font-family: 'Cascadia Code', Consolas, monospace; font-size: 12.5px;
  line-height: 1.72; background: #fdfcff; color: #3a3545; white-space: pre; overflow: auto; tab-size: 2;
}
.md-editor:focus { background: #fffdfd; }
.md-preview { flex: 1; overflow-y: auto; padding: 12px; background: #fbf9fe; max-height: 62vh; min-height: 46vh; }

/* 渲染后的角色卡片 */
.mdc-card { background: #fff; border: 1px solid #eee9f7; border-radius: 12px; padding: 13px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(80, 60, 140, .04); }
.mdc-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding-bottom: 9px; margin-bottom: 9px; border-bottom: 1px solid #f4f0fb; }
.mdc-name { font-size: 15px; font-weight: 700; color: #33284f; }
.mdc-id { font-family: Consolas, monospace; font-size: 10.5px; color: #5f54a3; background: #f0ecff; padding: 2px 8px; border-radius: 8px; }
.mdc-cat { font-size: 10.5px; color: #7c6fd0; background: #f0ecff; padding: 2px 8px; border-radius: 8px; }
.mdc-heal { font-size: 10.5px; color: #2f9e6b; background: #e9f8ef; padding: 2px 8px; border-radius: 8px; }
.mdc-3d { font-size: 10.5px; color: #2a7fa8; background: #e8f4fb; padding: 2px 8px; border-radius: 8px; }
.mdc-field { display: flex; gap: 10px; align-items: flex-start; padding: 3.5px 0; font-size: 12.5px; line-height: 1.75; }
.mdc-key { flex: none; width: 76px; color: #9a94ab; font-size: 11.5px; padding-top: 1px; }
.mdc-val { color: #4a4360; flex: 1; min-width: 0; word-break: break-word; }
.mdc-field.list .mdc-key { padding-top: 4px; }
.mdc-chips { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; }
.mdc-chip { font-size: 11.5px; color: #4a4360; background: #f6f2fc; border: 1px solid #ebe3f8; padding: 2px 9px; border-radius: 10px; line-height: 1.6; }
.mdc-empty { font-size: 11px; color: #c0bbd0; }
.mdc-raw { display: flex; align-items: baseline; gap: 8px; padding: 6px 4px; font-size: 12px; color: #9a7b52; }
.mdc-raw-line { font-family: Consolas, monospace; color: #b26a1d; }
.mdc-raw-badge { flex: none; font-size: 10px; color: #d68a2e; background: #fff4e8; padding: 1px 7px; border-radius: 8px; }
.mdc-empty-all { text-align: center; color: #b9b3c9; font-size: 12.5px; padding: 60px 0; }
.md-format-tip { font-size: 11.5px; color: #9a94ab; line-height: 1.7; margin: 10px 0 0; }

/* 系统提示词折叠面板 */
.pe-sys { margin-top: 12px; }
.sys-toggle { border: none; background: transparent; color: #6f63b8; font-size: 12.5px; cursor: pointer; padding: 4px 0; }
.sys-toggle:hover { color: #5f54a3; }
.sys-body {
  margin: 6px 0 0; background: #241f38; color: #d8d2ec; border-radius: 12px; padding: 14px 16px;
  font-size: 12px; line-height: 1.8; white-space: pre-wrap; word-break: break-word;
  max-height: 40vh; overflow-y: auto; font-family: 'Cascadia Code', Consolas, monospace;
}

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