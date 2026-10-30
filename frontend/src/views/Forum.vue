<template>
  <div class="forum-page">
    <header class="topbar">
      <div class="tb-left">
        <router-link to="/" class="back">← 返回聊天</router-link>
        <span class="tb-title">🌱 正能量社区</span>
      </div>
      <button class="publish-btn" @click="openCompose">✏️ 发布文章</button>
    </header>

    <div class="toolbar">
      <div class="search-box">
        <span>🔍</span>
        <input v-model="q" placeholder="搜索文章、标签…" @keydown.enter="load" />
        <button v-if="q" @click="q=''; load()">✕</button>
      </div>
      <div class="tags">
        <span class="tag-chip" :class="{ active: !activeTag }" @click="setTag('')">全部</span>
        <span v-for="t in tags" :key="t.name" class="tag-chip"
              :class="{ active: activeTag === t.name }" @click="setTag(t.name)">
          #{{ t.name }}
        </span>
      </div>
    </div>

    <div v-if="posts.length" class="masonry">
      <div v-for="p in posts" :key="p.id" class="post-card" @click="openPost(p.id)">
        <div v-if="p.images && p.images.length" class="pc-cover">
          <video v-if="isVideo(p.images[0])" :src="p.images[0]" muted preload="metadata"></video>
          <img v-else :src="p.images[0]" alt="封面" />
          <span v-if="isVideo(p.images[0])" class="pc-play">▶</span>
          <span v-if="p.images.length > 1" class="pc-count">📷 {{ p.images.length }}</span>
        </div>
        <div class="pc-body">
          <h3 class="pc-title">{{ p.title || '无标题' }}</h3>
          <p class="pc-excerpt">{{ p.excerpt }}</p>
          <div class="pc-tags">
            <span v-for="t in p.tags" :key="t" class="pc-tag">#{{ t }}</span>
          </div>
          <div class="pc-foot">
            <span class="author"><span class="avatar-mini">{{ p.author?.[0] || '友' }}</span>{{ p.author }}</span>
            <span class="acts">
              <span class="act" :class="{ liked: p.liked }" @click.stop="toggleLike(p)">
                {{ p.liked ? '❤️' : '🤍' }} {{ p.like_count }}
              </span>
              <span class="act">💬 {{ p.comment_count }}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="empty">还没有文章，来发布第一篇正能量吧～</div>

    <!-- 发布弹窗：块编辑器 + 实时预览 -->
    <div v-if="showCompose" class="modal-mask" @click.self="showCompose = false">
      <div class="compose card">
        <div class="compose-head">
          <h3>发布正能量文章</h3>
          <button class="close" @click="showCompose = false">✕</button>
        </div>

        <div class="compose-body">
          <!-- 编辑区 -->
          <div class="editor">
            <input v-model="form.title" class="title-input" maxlength="120" placeholder="起个标题吧（选填）" />

            <div class="blocks">
              <div v-for="(b, i) in form.blocks" :key="b._id" class="block">
                <div class="block-ctrl">
                  <button title="上移" :disabled="i === 0" @click="moveBlock(i, -1)">↑</button>
                  <button title="下移" :disabled="i === form.blocks.length - 1" @click="moveBlock(i, 1)">↓</button>
                  <button title="删除" @click="removeBlock(i)">✕</button>
                </div>
                <template v-if="b.type === 'text'">
                  <textarea v-model="b.text" class="block-text" rows="3"
                            placeholder="写点什么…（纯文字，可插入图片让图文穿插）"></textarea>
                </template>
                <template v-else>
                  <div class="block-media">
                    <video v-if="b.type === 'video'" :src="b.url" controls></video>
                    <img v-else :src="b.url" />
                  </div>
                </template>
              </div>
            </div>

            <div class="add-row">
              <button class="add-btn" @click="addText">＋ 文字</button>
              <label class="add-btn">
                ＋ 图片/视频<input type="file" accept="image/*,video/*" hidden @change="onPickMedia" />
              </label>
              <span class="hint-mini">可交替添加，实现图文穿插</span>
            </div>

            <input v-model="form.tagsText" class="tag-input" placeholder="标签，用逗号分隔，如：治愈,成长" />
          </div>

          <!-- 实时预览 -->
          <div class="preview">
            <div class="preview-label">预览效果</div>
            <div class="preview-card">
              <h2 class="pv-title">{{ form.title || '无标题' }}</h2>
              <template v-for="(b, i) in previewBlocks" :key="i">
                <p v-if="b.type === 'text'" class="pv-para">{{ b.text }}</p>
                <video v-else-if="b.type === 'video'" :src="b.url" controls class="pv-video"></video>
                <img v-else :src="b.url" class="pv-img" />
              </template>
              <div v-if="!previewBlocks.length" class="pv-empty">在左侧输入内容，这里会实时预览～</div>
              <div class="pv-tags">
                <span v-for="t in previewTags" :key="t" class="pv-tag">#{{ t }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="compose-foot">
          <button class="btn ghost" @click="showCompose = false">取消</button>
          <button class="btn" :disabled="submitting" @click="submitPost">
            {{ submitting ? '发布中…' : '发布' }}
          </button>
        </div>
      </div>
    </div>

    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const posts = ref([])
const tags = ref([])
const q = ref('')
const activeTag = ref('')
const showCompose = ref(false)
const submitting = ref(false)
const toastMsg = ref('')
let toastTimer = null
let uid = 0

const form = reactive({ title: '', tagsText: '', blocks: [] })
function newBlock(b) { return { _id: ++uid, ...b } }
function resetForm() { form.title = ''; form.tagsText = ''; form.blocks = [newBlock({ type: 'text', text: '' })] }

const previewBlocks = computed(() => form.blocks
  .map((b) => b.type === 'text' ? { type: 'text', text: (b.text || '').trim() } : { type: b.type, url: b.url })
  .filter((b) => b.type === 'text' ? b.text : b.url))
const previewTags = computed(() => form.tagsText.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean))

function toast(m) { toastMsg.value = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => toastMsg.value = '', 2400) }
function isVideo(url) { return /\.(mp4|webm|mov)(\?|$)/i.test(url || '') }

async function load() {
  const params = new URLSearchParams()
  if (q.value) params.set('q', q.value)
  if (activeTag.value) params.set('tag', activeTag.value)
  const { data } = await api.get(`/forum/posts?${params.toString()}`)
  posts.value = data.items
  tags.value = (await api.get('/forum/tags')).data
}
function setTag(t) { activeTag.value = t; load() }
function openPost(id) { router.push(`/forum/${id}`) }
function openCompose() { resetForm(); showCompose.value = true }

function addText() { form.blocks.push(newBlock({ type: 'text', text: '' })) }
function removeBlock(i) { form.blocks.splice(i, 1); if (!form.blocks.length) addText() }
function moveBlock(i, dir) {
  const j = i + dir
  if (j < 0 || j >= form.blocks.length) return
  const arr = form.blocks
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}

async function onPickMedia(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await api.post('/forum/upload', fd)
    form.blocks.push(newBlock({ type: data.type, url: data.url }))
  } catch (err) { toast(err.response?.data?.detail || '上传失败') }
}

async function toggleLike(p) {
  const { data } = await api.post(`/forum/posts/${p.id}/like`)
  p.liked = data.liked
  p.like_count = data.like_count
}

async function submitPost() {
  const blocks = form.blocks
    .map((b) => b.type === 'text' ? { type: 'text', text: (b.text || '').trim() } : { type: b.type, url: b.url })
    .filter((b) => b.type === 'text' ? b.text : b.url)
  if (!blocks.length) { toast('写点文字或加张图片吧～'); return }
  submitting.value = true
  try {
    const tagList = form.tagsText.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
    await api.post('/forum/posts', { title: form.title.trim(), tags: tagList, blocks })
    showCompose.value = false
    toast('发布成功！')
    await load()
  } catch (e) {
    toast(e.response?.data?.detail || '发布失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => { load() })
</script>

<style scoped>
.forum-page { min-height: 100vh; background: var(--bg); }
.topbar { display: flex; justify-content: space-between; align-items: center;
  padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.tb-left { display: flex; align-items: center; gap: 16px; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }
.publish-btn { border: none; background: var(--primary); color: #fff; border-radius: 10px; padding: 9px 18px; font-size: 14px; }

.toolbar { max-width: 1180px; margin: 18px auto 0; padding: 0 20px; }
.search-box { display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid var(--border);
  border-radius: 22px; padding: 9px 16px; max-width: 460px; }
.search-box input { flex: 1; border: none; outline: none; font-size: 14px; background: transparent; }
.search-box button { border: none; background: transparent; color: var(--text-soft); cursor: pointer; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.tag-chip { font-size: 13px; padding: 5px 12px; border-radius: 14px; background: #fff;
  border: 1px solid var(--border); color: var(--text-soft); cursor: pointer; }
.tag-chip.active { background: var(--primary); color: #fff; border-color: var(--primary); }

.masonry { max-width: 1180px; margin: 16px auto 40px; padding: 0 20px; column-count: 3; column-gap: 16px; }
@media (max-width: 900px) { .masonry { column-count: 2; } }
@media (max-width: 600px) { .masonry { column-count: 1; } }
.post-card { break-inside: avoid; margin-bottom: 16px; background: #fff; border: 1px solid var(--border);
  border-radius: 16px; overflow: hidden; box-shadow: var(--shadow); cursor: pointer; transition: transform .15s; }
.post-card:hover { transform: translateY(-2px); }
.pc-cover { position: relative; }
.pc-cover img, .pc-cover video { width: 100%; display: block; max-height: 340px; object-fit: cover; background: #eee; }
.pc-play { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 34px; color: #fff; background: rgba(0,0,0,.28); }
.pc-count { position: absolute; right: 8px; bottom: 8px; background: rgba(0,0,0,.5); color: #fff;
  font-size: 11px; padding: 2px 8px; border-radius: 10px; }
.pc-body { padding: 14px 16px; }
.pc-title { font-size: 15px; margin-bottom: 8px; }
.pc-excerpt { font-size: 13px; color: var(--text-soft); line-height: 1.6; }
.pc-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pc-tag { font-size: 12px; color: var(--primary); }
.pc-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.author { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-soft); }
.avatar-mini { width: 20px; height: 20px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent));
  color: #fff; display: flex; align-items: center; justify-content: center; font-size: 11px; }
.acts { display: flex; gap: 12px; }
.act { font-size: 13px; color: var(--text-soft); }
.act.liked { color: #e0556d; }
.empty { text-align: center; color: var(--text-soft); padding: 80px 0; }

.modal-mask { position: fixed; inset: 0; background: rgba(30,25,45,.5); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.compose { width: 900px; max-width: 100%; max-height: 90vh; overflow-y: auto; padding: 22px 24px; }
.compose-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.compose-head h3 { font-size: 16px; }
.close { border: none; background: transparent; font-size: 16px; color: var(--text-soft); cursor: pointer; }
.compose-body { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 720px) { .compose-body { grid-template-columns: 1fr; } }

.title-input { width: 100%; border: none; border-bottom: 2px solid var(--border); font-size: 18px; font-weight: 600;
  padding: 8px 4px; margin-bottom: 14px; background: transparent; }
.title-input:focus { outline: none; border-color: var(--primary); }
.blocks { display: flex; flex-direction: column; gap: 12px; }
.block { position: relative; border: 1px solid var(--border); border-radius: 10px; padding: 10px 10px 10px 34px; background: #fbfaff; }
.block-ctrl { position: absolute; left: 6px; top: 8px; display: flex; flex-direction: column; gap: 2px; }
.block-ctrl button { width: 22px; height: 22px; border: 1px solid var(--border); background: #fff; border-radius: 6px;
  font-size: 11px; color: var(--text-soft); cursor: pointer; padding: 0; }
.block-ctrl button:disabled { opacity: .35; cursor: default; }
.block-ctrl button:hover:not(:disabled) { color: #e0556d; }
.block-text { width: 100%; border: none; background: transparent; font-size: 14px; resize: vertical; font-family: inherit; }
.block-text:focus { outline: none; }
.block-media img, .block-media video { width: 100%; max-height: 200px; object-fit: cover; border-radius: 8px; display: block; }
.add-row { display: flex; align-items: center; gap: 10px; margin: 14px 0; }
.add-btn { border: 1px dashed var(--primary); background: var(--primary-soft); color: var(--primary);
  border-radius: 10px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
.hint-mini { font-size: 12px; color: var(--text-soft); }
.tag-input { width: 100%; border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; font-size: 14px; }
.tag-input:focus { outline: none; border-color: var(--primary); }

.preview-label { font-size: 13px; color: var(--text-soft); margin-bottom: 10px; }
.preview-card { border: 1px solid var(--border); border-radius: 14px; padding: 18px; background: #fff; }
.pv-title { font-size: 20px; margin-bottom: 12px; }
.pv-para { font-size: 14px; line-height: 1.9; margin-bottom: 12px; white-space: pre-wrap; }
.pv-img { width: 100%; border-radius: 10px; margin-bottom: 12px; display: block; }
.pv-video { width: 100%; border-radius: 10px; margin-bottom: 12px; background: #000; }
.pv-empty { color: var(--text-soft); font-size: 13px; padding: 20px 0; }
.pv-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pv-tag { font-size: 12px; color: var(--primary); }

.compose-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.btn { border: none; background: var(--primary); color: #fff; border-radius: 10px; padding: 10px 20px; font-size: 14px; }
.btn.ghost { background: #f4f1fb; color: var(--text); }
.btn:disabled { opacity: .6; }
.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>