<template>
  <div class="editor-page">
    <header class="topbar">
      <div class="tb-left">
        <router-link to="/forum" class="back">← 返回社区</router-link>
        <span class="tb-title">✏️ 写文章</span>
      </div>
      <div class="tb-actions">
        <span class="save-tip" :class="{ saved: savedAt }">{{ savedAt ? '草稿已自动保存' : '自动保存草稿' }}</span>
        <button class="btn ghost" :disabled="submitting" @click="goBack">取消</button>
        <button class="btn publish" :disabled="submitting || !canPublish" @click="publish">
          {{ submitting ? '发布中…' : '发布文章' }}
        </button>
      </div>
    </header>

    <div class="editor-body">
      <!-- 左：编辑区 -->
      <section class="edit-pane">
        <input v-model="form.title" class="big-title" maxlength="120"
               placeholder="给文章起个标题（选填）" />

        <div class="meta-row">
          <input v-model="form.tagsText" class="tag-input" placeholder="标签，用逗号分隔，如：治愈,成长,情绪管理" />
        </div>

        <div class="blocks">
          <div v-for="(b, i) in form.blocks" :key="b._id" class="block"
               :class="{ text: b.type === 'text' }">
            <div class="block-side">
              <span class="block-no">{{ i + 1 }}</span>
              <div class="block-ctrl">
                <button title="上移" :disabled="i === 0" @click="moveBlock(i, -1)">↑</button>
                <button title="下移" :disabled="i === form.blocks.length - 1" @click="moveBlock(i, 1)">↓</button>
                <button title="删除" @click="removeBlock(i)">✕</button>
              </div>
            </div>
            <div class="block-main">
              <textarea v-if="b.type === 'text'" v-model="b.text" class="block-text"
                        :rows="b.text && b.text.length > 120 ? 6 : 4"
                        placeholder="写点什么…支持多段文字与图片/视频穿插排版"></textarea>
              <template v-else>
                <div class="block-media">
                  <video v-if="b.type === 'video'" :src="b.url" controls></video>
                  <img v-else :src="b.url" alt="" />
                </div>
                <div class="media-bar">
                  <span class="media-type">{{ b.type === 'video' ? '🎬 视频块' : '🖼 图片块' }}</span>
                  <button class="mini" @click="removeBlock(i)">移除</button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <div class="add-row">
          <button class="add-btn" @click="addText">＋ 文字段落</button>
          <label class="add-btn">
            ＋ 插入图片<input type="file" accept="image/*" hidden @change="(e) => onPickMedia(e, 'image')" />
          </label>
          <label class="add-btn">
            ＋ 插入视频<input type="file" accept="video/*" hidden @change="(e) => onPickMedia(e, 'video')" />
          </label>
        </div>
        <p class="hint">图文穿插排版：文字与媒体块可自由排序，正文建议分 2~4 段。当前共 {{ form.blocks.length }} 个内容块。</p>
      </section>

      <!-- 右：实时预览 -->
      <aside class="preview-pane">
        <div class="pv-label">📱 实时预览</div>
        <div class="pv-card">
          <h2 class="pv-title">{{ form.title || '无标题' }}</h2>
          <template v-for="(b, i) in previewBlocks" :key="i">
            <p v-if="b.type === 'text'" class="pv-para">{{ b.text }}</p>
            <video v-else-if="b.type === 'video'" :src="b.url" controls class="pv-video"></video>
            <img v-else :src="b.url" class="pv-img" alt="" />
          </template>
          <div v-if="!previewBlocks.length" class="pv-empty">在左侧输入内容，这里会实时预览～</div>
          <div v-if="previewTags.length" class="pv-tags">
            <span v-for="t in previewTags" :key="t" class="pv-tag">#{{ t }}</span>
          </div>
          <div class="pv-foot">
            <span class="pv-author"><span class="avatar-mini">{{ (auth.nickname || '友')[0] }}</span>{{ auth.nickname }}</span>
            <span class="pv-stat">❤️ 0 · 💬 0</span>
          </div>
        </div>
        <div class="pv-tips">
          <b>投稿小贴士</b>
          <p>· 试试分享一件今天让你感到温暖的小事</p>
          <p>· 标签帮助同频的人找到你，建议 2~4 个</p>
          <p>· 内容请保持友善，禁止医疗建议与商业推广</p>
        </div>
      </aside>
    </div>

    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const submitting = ref(false)
const toastMsg = ref('')
const savedAt = ref(false)
let uid = 0
let toastTimer = null
let saveTimer = null

const form = reactive({ title: '', tagsText: '', blocks: [] })
function newBlock(b) { return { _id: ++uid, ...b } }

const previewBlocks = computed(() => form.blocks
  .map((b) => b.type === 'text' ? { type: 'text', text: (b.text || '').trim() } : { type: b.type, url: b.url })
  .filter((b) => b.type === 'text' ? b.text : b.url))
const previewTags = computed(() => form.tagsText.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean))
const canPublish = computed(() => !!previewBlocks.value.length)

function toast(m) { toastMsg.value = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => toastMsg.value = '', 2400) }

function addText() { form.blocks.push(newBlock({ type: 'text', text: '' })) }
function removeBlock(i) {
  form.blocks.splice(i, 1)
  if (!form.blocks.length) addText()
}
function moveBlock(i, dir) {
  const j = i + dir
  if (j < 0 || j >= form.blocks.length) return
  const arr = form.blocks
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}

async function onPickMedia(e, expect) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await api.post('/forum/upload', fd)
    form.blocks.push(newBlock({ type: data.type || expect, url: data.url }))
  } catch (err) {
    toast(err.response?.data?.detail || '上传失败')
  }
}

/* 草稿自动保存（localStorage） */
watch(form, () => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem('eh_post_draft', JSON.stringify({
        title: form.title, tagsText: form.tagsText,
        blocks: form.blocks.map(({ type, text, url }) => ({ type, text, url })),
      }))
      savedAt.value = true
      setTimeout(() => { savedAt.value = false }, 1500)
    } catch (e) { /* 忽略 */ }
  }, 800)
}, { deep: true })

function restoreDraft() {
  try {
    const raw = localStorage.getItem('eh_post_draft')
    if (!raw) return false
    const d = JSON.parse(raw)
    if (!d || (!d.title && !d.blocks?.length)) return false
    form.title = d.title || ''
    form.tagsText = d.tagsText || ''
    form.blocks = (d.blocks || []).map((b) => newBlock(b))
    if (!form.blocks.length) addText()
    return true
  } catch (e) { return false }
}

function goBack() {
  if (canPublish.value && !confirm('离开将丢失未发布的内容（草稿已自动保存），确定返回？')) return
  router.push('/forum')
}

async function publish() {
  const blocks = form.blocks
    .map((b) => b.type === 'text' ? { type: 'text', text: (b.text || '').trim() } : { type: b.type, url: b.url })
    .filter((b) => b.type === 'text' ? b.text : b.url)
  if (!blocks.length) { toast('写点文字或加张图片吧～'); return }
  submitting.value = true
  try {
    const { data } = await api.post('/forum/posts', {
      title: form.title.trim(),
      tags: previewTags.value,
      blocks,
    })
    localStorage.removeItem('eh_post_draft')
    toast('发布成功！')
    router.push(`/forum/${data.id}`)
  } catch (e) {
    toast(e.response?.data?.detail || '发布失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const restored = restoreDraft()
  if (!restored) {
    form.blocks = [newBlock({ type: 'text', text: '' })]
  } else {
    toast('已恢复上次未发布的草稿')
  }
})
</script>

<style scoped>
.editor-page { min-height: 100vh; background: var(--bg); display: flex; flex-direction: column; }
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 13px 26px; background: #fff; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; z-index: 10;
}
.tb-left { display: flex; align-items: center; gap: 16px; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }
.tb-actions { display: flex; align-items: center; gap: 10px; }
.save-tip { font-size: 12px; color: #b9b3c9; margin-right: 6px; transition: color .3s; }
.save-tip.saved { color: #2f9e6b; }
.btn { border: none; border-radius: 10px; padding: 9px 18px; font-size: 14px; cursor: pointer; }
.btn.ghost { background: #f4f1fb; color: var(--text); }
.btn.publish { background: var(--primary); color: #fff; box-shadow: 0 4px 14px rgba(124,111,208,.3); }
.btn:disabled { opacity: .55; cursor: not-allowed; }

.editor-body {
  flex: 1; display: grid; grid-template-columns: 1.35fr .85fr; gap: 22px;
  max-width: 1280px; width: 100%; margin: 0 auto; padding: 26px 24px 60px;
  align-items: start;
}
@media (max-width: 960px) { .editor-body { grid-template-columns: 1fr; } }

.edit-pane { background: #fff; border: 1px solid var(--border); border-radius: 18px; padding: 26px 28px; box-shadow: var(--shadow); }
.big-title {
  width: 100%; border: none; border-bottom: 2px solid var(--border); font-size: 24px; font-weight: 700;
  padding: 6px 2px 12px; background: transparent;
}
.big-title:focus { outline: none; border-color: var(--primary); }
.meta-row { margin: 14px 0 18px; }
.tag-input {
  width: 100%; border: 1px solid var(--border); border-radius: 12px; padding: 11px 14px;
  font-size: 14px; background: #fbfaff;
}
.tag-input:focus { outline: none; border-color: var(--primary); background: #fff; }

.blocks { display: flex; flex-direction: column; gap: 14px; }
.block { display: flex; gap: 12px; border: 1px solid var(--border); border-radius: 14px; padding: 14px; background: #fdfcff; }
.block-side { display: flex; flex-direction: column; align-items: center; gap: 8px; flex: none; }
.block-no {
  width: 22px; height: 22px; border-radius: 50%; background: var(--primary-soft); color: var(--primary);
  font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
}
.block-ctrl { display: flex; flex-direction: column; gap: 4px; }
.block-ctrl button {
  width: 26px; height: 26px; border: 1px solid #e6dff5; background: #fff; border-radius: 8px;
  font-size: 12px; color: var(--text-soft); cursor: pointer; padding: 0;
}
.block-ctrl button:disabled { opacity: .3; cursor: default; }
.block-ctrl button:hover:not(:disabled) { color: #e0556d; border-color: #f3c2cb; }
.block-main { flex: 1; min-width: 0; }
.block-text {
  width: 100%; min-height: 110px; border: none; background: transparent; font-size: 15px;
  line-height: 1.9; resize: vertical; font-family: inherit; color: var(--text);
}
.block-text:focus { outline: none; }
.block-media img, .block-media video { width: 100%; max-height: 320px; object-fit: cover; border-radius: 10px; display: block; }
.media-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.media-type { font-size: 12px; color: var(--text-soft); }
.mini { border: none; background: transparent; color: #d9536b; font-size: 12px; cursor: pointer; }

.add-row { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
.add-btn {
  border: 1.5px dashed var(--primary); background: var(--primary-soft); color: var(--primary);
  border-radius: 12px; padding: 11px 18px; font-size: 14px; cursor: pointer; transition: all .15s;
}
.add-btn:hover { background: #e5deff; }
.hint { font-size: 12.5px; color: var(--text-soft); margin-top: 10px; line-height: 1.7; }

.preview-pane { position: sticky; top: 90px; display: flex; flex-direction: column; gap: 16px; }
.pv-label { font-size: 13px; color: var(--text-soft); }
.pv-card { background: #fff; border: 1px solid var(--border); border-radius: 18px; padding: 22px; box-shadow: var(--shadow); }
.pv-title { font-size: 20px; margin-bottom: 14px; word-break: break-all; }
.pv-para { font-size: 14px; line-height: 1.9; margin-bottom: 12px; white-space: pre-wrap; }
.pv-img { width: 100%; border-radius: 12px; margin-bottom: 12px; display: block; }
.pv-video { width: 100%; border-radius: 12px; margin-bottom: 12px; background: #000; }
.pv-empty { color: var(--text-soft); font-size: 13px; padding: 26px 0; text-align: center; }
.pv-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.pv-tag { font-size: 12px; color: var(--primary); }
.pv-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border); }
.pv-author { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--text-soft); }
.avatar-mini { width: 22px; height: 22px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 11px; }
.pv-stat { font-size: 12px; color: var(--text-soft); }
.pv-tips { background: #faf8ff; border: 1px dashed #e0d9f2; border-radius: 14px; padding: 14px 16px; font-size: 12.5px; color: var(--text-soft); line-height: 2; }
.pv-tips b { color: #6f63b8; }

.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>