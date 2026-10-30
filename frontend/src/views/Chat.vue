<template>
  <div class="chat-page">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">☾</span>
        <span class="title">治愈小窝</span>
      </div>

      <div class="nav-links">
        <router-link to="/forum">🌱 社区</router-link>
        <router-link to="/personas">🎭 角色</router-link>
        <router-link to="/vrm">🎀 3D</router-link>
      </div>

      <button class="new-btn" @click="newSession">＋ 新的倾诉</button>

      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: currentId === s.id }"
          @click="openSession(s.id)"
        >
          <div class="s-main">
            <div class="s-title">
              <img v-if="personasMap[s.persona_id]?.avatar" :src="personasMap[s.persona_id].avatar" class="s-ava" alt="" />
              <template v-else>{{ personasMap[s.persona_id]?.emoji }}</template>
              {{ s.title }}
            </div>
            <div class="s-time">{{ timeText(s.updated_at) }}</div>
          </div>
          <button class="s-del" title="删除对话" @click.stop="removeSession(s)">✕</button>
        </div>
        <div v-if="!sessions.length" class="empty">还没有对话，开始第一段吧</div>
      </div>

      <div class="sidebar-foot">
        <div class="user" @click="toggleUser">
          <div class="avatar" :class="{ 'avatar-img-wrap': isImg(auth.avatar) }">
            <img v-if="isImg(auth.avatar)" :src="auth.avatar" class="avatar-img" alt="头像" />
            <template v-else>{{ auth.avatar || auth.nickname?.[0] || '友' }}</template>
          </div>
          <div class="u-meta">
            <div class="u-name">{{ auth.nickname }}</div>
            <div class="u-role">{{ auth.isAdmin ? '管理员' : '倾诉者' }}</div>
          </div>
        </div>
        <div v-if="userMenu" class="user-menu card">
          <router-link to="/account">👤 个人信息</router-link>
          <router-link to="/profile">📊 我的情绪档案</router-link>
          <router-link v-if="auth.isAdmin" to="/admin">🛠 进入管理平台</router-link>
          <a @click.prevent="logout">退出登录</a>
        </div>
      </div>
    </aside>

    <!-- 主区 -->
    <main class="chat-main">
      <header class="chat-header">
        <div>
          <div class="chat-title">
            <span v-if="currentPersona" class="persona-chip">
              <img v-if="currentPersona.avatar" :src="currentPersona.avatar" class="chip-ava" alt="" />
              <template v-else>{{ currentPersona.emoji }}</template>
              {{ currentPersona.name }}
            </span>
            <template v-if="editingTitle">
              <input ref="titleInput" v-model="titleDraft" class="title-edit" maxlength="100"
                     @keydown.enter.prevent="saveTitle" @keydown.esc="editingTitle = false"
                     @blur="saveTitle" />
            </template>
            <template v-else>
              {{ currentSession?.title || '新的对话' }}
              <button v-if="currentId" class="title-edit-btn" title="修改会话名称"
                      @click="startEditTitle">✎</button>
            </template>
          </div>
          <div class="chat-sub">每一次倾诉，都有人温柔回应</div>
        </div>
        <div class="header-right">
          <div v-if="lastEmotion" class="emotion-badge" :class="lastEmotion.polarity">
            <span>{{ emotionIcon(lastEmotion.type) }}</span> {{ lastEmotion.type }}
          </div>
          <router-link to="/profile" class="profile-link">情绪档案</router-link>
          <router-link to="/account" class="profile-link">个人信息</router-link>
        </div>
      </header>

      <div ref="msgBox" class="messages">
        <!-- 每日情绪推送卡片 -->
        <div v-if="daily && !dailyDismissed" class="daily-card">
          <div class="daily-head">
            <span class="daily-title">🌤 今日情绪小结 · {{ daily.date }}</span>
            <button class="daily-close" @click="dailyDismissed = true">✕</button>
          </div>
          <p class="daily-text">{{ daily.push_text }}</p>
          <p class="daily-tip">💡 {{ daily.tip }}</p>
        </div>

        <div v-if="!messages.length && !daily" class="welcome">
          <div class="w-emoji">🌿</div>
          <p>你好呀，我是你的治愈小窝。</p>
          <p class="w-sub">无论开心、难过还是迷茫，都可以放心说给我听。</p>
        </div>

        <div v-for="m in messages" :key="m.id" class="msg-row" :class="m.role">
          <div class="bubble">
            <img v-if="m.msg_type === 'image' && m.image_url" :src="m.image_url"
                 class="b-img" alt="图片" @click="preview = m.image_url" />
            <div v-if="m.content" class="b-text">{{ m.content }}</div>
            <div v-if="m.role === 'user' && m.emotion_type" class="b-tags">
              <span class="tag emo clickable" title="点击校准情绪" @click="openCalibrate(m)">
                {{ emotionIcon(m.emotion_type) }} {{ m.emotion_type }}
                <span class="calib-edit">✎</span>
              </span>
              <span v-if="m.calibrated" class="calib-done">已校准</span>
            </div>
          </div>
        </div>

        <div v-if="typing" class="msg-row assistant">
          <div class="bubble typing"><span></span><span></span><span></span></div>
        </div>
      </div>

      <footer class="composer">
        <button class="icon-btn" title="发送图片" @click="pickImage" :disabled="typing">🖼</button>
        <button class="icon-btn" :class="{ recording }" title="语音输入"
                @click="toggleVoice" :disabled="typing">{{ recording ? '🔴' : '🎤' }}</button>
        <textarea
          v-model="draft"
          rows="2"
          :placeholder="recording ? '正在聆听…请说话' : '把心里话放在这里…（回车发送）'"
          @keydown.enter.exact.prevent="send"
        ></textarea>
        <button class="send-btn" @click="send" :disabled="typing || !draft.trim()">
          {{ typing ? '…' : '发送' }}
        </button>
        <input ref="fileInput" type="file" accept="image/*" hidden @change="onFileChange" />
      </footer>
    </main>

    <!-- 图片预览 -->
    <div v-if="preview" class="img-modal" @click="preview = ''">
      <img :src="preview" alt="预览" />
    </div>

    <!-- 轻提示 -->
    <transition name="fade">
      <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>
    </transition>

    <!-- 情绪校准弹窗 -->
    <div v-if="showCalib" class="calib-mask" @click.self="showCalib = false">
      <div class="calib-modal card">
        <h4>这条消息更接近哪种情绪？</h4>
        <p class="calib-sub">
          系统判断为「{{ calibOriginal }}」，如果不太准，点选更贴近你感受的：
        </p>
        <div class="calib-grid">
          <button v-for="e in emotionTypes" :key="e"
                  :class="{ cur: e === calibOriginal }"
                  :disabled="calibSaving"
                  @click="doCalibrate(e)">
            {{ emotionIcon(e) }} {{ e }}
          </button>
        </div>
        <p class="calib-note">你的校准会记录到个人档案，并让后续识别更懂你。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const router = useRouter()
const auth = useAuthStore()

const sessions = ref([])
const currentId = ref(null)
const currentSession = ref(null)
const messages = ref([])
const draft = ref('')
const typing = ref(false)
const lastEmotion = ref(null)
const userMenu = ref(false)
const msgBox = ref(null)
const daily = ref(null)
const dailyDismissed = ref(false)
const preview = ref('')
const fileInput = ref(null)
const recording = ref(false)
const showCalib = ref(false)
const calibTarget = ref(null)
const calibOriginal = ref('')
const calibSaving = ref(false)
const personasMap = ref({})
const currentPersona = computed(() =>
  currentSession.value ? personasMap.value[currentSession.value.persona_id] : null)
const emotionTypes = ['喜悦', '平静', '感恩', '期待', '悲伤', '焦虑', '愤怒', '恐惧', '孤独', '委屈', '低落', '中性']
const editingTitle = ref(false)
const titleDraft = ref('')
const titleInput = ref(null)

function isImg(v) { return !!v && (v.startsWith('/uploads/') || v.startsWith('http') || v.startsWith('data:')) }

function startEditTitle() {
  if (!currentSession.value) return
  titleDraft.value = currentSession.value.title || ''
  editingTitle.value = true
  nextTick(() => titleInput.value?.focus())
}

async function saveTitle() {
  if (!editingTitle.value) return
  editingTitle.value = false
  const t = titleDraft.value.trim()
  if (!t || !currentId.value) return
  if (t === currentSession.value?.title) return
  try {
    const { data } = await api.put(`/chat/sessions/${currentId.value}`, { title: t })
    if (currentSession.value) currentSession.value.title = data.title
    const s = sessions.value.find((x) => x.id === currentId.value)
    if (s) s.title = data.title
    toast('会话名称已更新')
  } catch (e) {
    toast(e.response?.data?.detail || '重命名失败')
  }
}
let recognition = null

function polarityOf(t) {
  if (['喜悦', '平静', '感恩', '期待'].includes(t)) return 'positive'
  if (t === '中性') return 'neutral'
  return 'negative'
}

function openCalibrate(m) {
  if (!m.id || m.id > 9000000000) return
  calibTarget.value = m
  calibOriginal.value = m.emotion_type || '中性'
  showCalib.value = true
}

async function doCalibrate(type) {
  if (!calibTarget.value || calibSaving.value) return
  calibSaving.value = true
  try {
    const { data } = await api.post('/emotion/calibrate', {
      message_id: calibTarget.value.id, emotion_type: type,
    })
    const m = messages.value.find((x) => x.id === calibTarget.value.id)
    if (m) { m.emotion_type = data.corrected; m.calibrated = true }
    if (lastEmotion.value) lastEmotion.value = { type: data.corrected, polarity: polarityOf(data.corrected) }
    toast(data.calibrated ? `已校准为「${data.corrected}」，谢谢你的反馈` : '情绪已确认')
    showCalib.value = false
  } catch (e) {
    toast(e.response?.data?.detail || '校准失败，请重试')
  } finally {
    calibSaving.value = false
  }
}

function timeText(t) {
  if (!t) return ''
  const d = new Date(t)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function emotionIcon(t) {
  return ({ 喜悦: '😊', 平静: '😌', 感恩: '🥰', 期待: '✨', 悲伤: '🥺',
   焦虑: '😰', 愤怒: '😠', 恐惧: '😨', 孤独: '🫂', 委屈: '😢', 低落: '🌧️', 中性: '🌤️' })[t] || '🌤️'
}

function toggleUser() { userMenu.value = !userMenu.value }

async function loadSessions() {
  const { data } = await api.get('/chat/sessions')
  sessions.value = data
}

async function openSession(id) {
  currentId.value = id
  currentSession.value = sessions.value.find((s) => s.id === id) || null
  const { data } = await api.get(`/chat/sessions/${id}/messages`)
  messages.value = data
  const lastUser = [...data].reverse().find((m) => m.role === 'user' && m.emotion_type)
  lastEmotion.value = lastUser ? {
    type: lastUser.emotion_type,
    polarity: ({ 喜悦: 'positive', 平静: 'positive', 感恩: 'positive', 期待: 'positive' }[
      lastUser.emotion_type] || (['中性'].includes(lastUser.emotion_type) ? 'neutral' : 'negative')),
  } : null
  scrollDown()
}

async function newSession() {
  const { data } = await api.post('/chat/sessions', { title: '新的对话' })
  currentId.value = data.id
  currentSession.value = data
  messages.value = []
  lastEmotion.value = null
  await loadSessions()
}

async function removeSession(s) {
  if (!confirm(`确定删除对话「${s.title}」吗？删除后不可恢复。`)) return
  await api.delete(`/chat/sessions/${s.id}`)
  if (currentId.value === s.id) {
    currentId.value = null
    currentSession.value = null
    messages.value = []
  }
  await loadSessions()
  if (!currentId.value && sessions.value.length) await openSession(sessions.value[0].id)
}

async function send() {
  const content = draft.value.trim()
  if (!content || typing.value || !currentId.value) return
  draft.value = ''
  typing.value = true
  const tmpId = Date.now()
  messages.value.push({ id: tmpId, role: 'user', content, msg_type: 'text', emotion_type: null })
  scrollDown()
  try {
    const { data } = await api.post(`/chat/sessions/${currentId.value}/messages`, { content })
    messages.value = messages.value.filter((m) => m.id !== tmpId)
    messages.value.push({ ...data.user_message })
    messages.value.push({ ...data.reply })
    lastEmotion.value = {
      type: data.emotion.emotion_type,
      polarity: data.emotion.polarity,
    }
    await loadSessions()
    scrollDown()
  } catch (e) {
    messages.value = messages.value.filter((m) => m.id !== tmpId)
    toast('发送失败，请重试')
  } finally {
    typing.value = false
  }
}

function pickImage() { fileInput.value?.click() }

async function onFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !currentId.value) return
  typing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post('/chat/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const resp = await api.post(`/chat/sessions/${currentId.value}/messages`, {
      content: '', msg_type: 'image', image_url: data.url,
    })
    messages.value.push({ ...resp.data.user_message })
    messages.value.push({ ...resp.data.reply })
    lastEmotion.value = { type: resp.data.emotion.emotion_type, polarity: resp.data.emotion.polarity }
    await loadSessions()
    scrollDown()
  } catch (err) {
    toast('图片发送失败，请重试')
  } finally {
    typing.value = false
  }
}

function toggleVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) { toast('当前浏览器不支持语音输入，请用 Chrome/Edge'); return }
  if (recording.value) { recognition?.stop(); return }
  recognition = new SR()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.continuous = false
  const base = draft.value
  recognition.onresult = (ev) => {
    let text = ''
    for (let i = ev.resultIndex; i < ev.results.length; i++) text += ev.results[i][0].transcript
    draft.value = base + text
  }
  recognition.onstart = () => { recording.value = true }
  recognition.onerror = () => { recording.value = false; toast('语音识别出错，请重试') }
  recognition.onend = () => { recording.value = false }
  recognition.start()
}

let toastTimer = null
const toastMsg = ref('')
function toast(msg) {
  toastMsg.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 2600)
}

function scrollDown() {
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}

function logout() {
  auth.logout()
  router.push('/login')
}

async function loadDaily() {
  try {
    const { data } = await api.get('/emotion/daily')
    daily.value = data
  } catch (e) { /* 忽略 */ }
}

onMounted(async () => {
  loadDaily()
  try {
    const { data } = await api.get('/chat/personas')
    const m = {}
    data.forEach((p) => { m[p.id] = p })
    personasMap.value = m
  } catch (e) { /* 忽略 */ }
  try {
    await loadSessions()
    if (sessions.value.length) await openSession(sessions.value[0].id)
  } catch (e) { /* 忽略 */ }
})
onBeforeUnmount(() => { recognition?.stop() })
</script>

<style scoped>
.chat-page { display: flex; height: 100vh; overflow: hidden; }
.sidebar {
  width: 268px; flex-shrink: 0; background: #fff;
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 16px 12px;
}
.brand { display: flex; align-items: center; gap: 8px; padding: 4px 8px 14px; }
.brand .logo { font-size: 24px; }
.brand .title { font-weight: 700; font-size: 17px; color: var(--primary); }
.nav-links { display: flex; gap: 8px; padding: 0 4px 12px; }
.nav-links a { flex: 1; text-align: center; font-size: 13px; padding: 7px 0; border-radius: 9px; background: #faf8ff; color: var(--text-soft); }
.nav-links a:hover { background: var(--primary-soft); color: var(--primary); }
.new-btn {
  border: 1px dashed var(--primary); background: var(--primary-soft);
  color: var(--primary); border-radius: 10px; padding: 10px; font-size: 14px;
  margin-bottom: 14px; transition: all .2s;
}
.new-btn:hover { background: var(--primary); color: #fff; }
.session-list { flex: 1; overflow-y: auto; }
.session-item {
  display: flex; align-items: center; padding: 10px; border-radius: 10px;
  margin-bottom: 4px; cursor: pointer; transition: background .15s;
}
.session-item:hover { background: #faf8ff; }
.session-item:hover .s-del { opacity: 1; }
.session-item.active { background: var(--primary-soft); }
.s-main { flex: 1; min-width: 0; }
.s-title { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 5px; }
.s-ava { width: 18px; height: 18px; border-radius: 50%; object-fit: cover; flex: none; }
.s-time { font-size: 12px; color: var(--text-soft); margin-top: 2px; }
.s-del {
  opacity: 0; border: none; background: transparent; color: var(--text-soft);
  font-size: 13px; padding: 4px 6px; border-radius: 6px; transition: all .15s;
}
.s-del:hover { background: #fdeef0; color: #e0556d; }
.empty { color: var(--text-soft); font-size: 13px; text-align: center; padding: 20px 0; }

.sidebar-foot { border-top: 1px solid var(--border); padding-top: 12px; position: relative; }
.user { display: flex; align-items: center; gap: 10px; padding: 6px 8px; cursor: pointer; border-radius: 10px; }
.user:hover { background: #faf8ff; }
.avatar { width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 600;
  flex: none; overflow: hidden; }
.avatar-img-wrap { background: #f0ecff; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.u-name { font-size: 14px; font-weight: 600; }
.u-role { font-size: 12px; color: var(--text-soft); }
.user-menu { position: absolute; bottom: 60px; left: 8px; right: 8px; padding: 8px; z-index: 20; }
.user-menu a { display: block; padding: 9px; border-radius: 8px; font-size: 14px; }
.user-menu a:hover { background: var(--primary-soft); }

.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-header {
  padding: 16px 24px; background: #fff; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.chat-title { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.title-edit {
  font-size: 15px; font-weight: 600; color: var(--text);
  border: 1px solid var(--primary); border-radius: 8px;
  padding: 4px 10px; outline: none; width: 240px;
  background: #fff; box-shadow: 0 0 0 3px rgba(124, 92, 255, .1);
}
.title-edit-btn {
  border: none; background: transparent; color: var(--text-soft);
  font-size: 13px; cursor: pointer; padding: 2px 6px; border-radius: 6px;
  opacity: .5; transition: all .15s;
}
.title-edit-btn:hover { opacity: 1; background: var(--primary-soft); color: var(--primary); }
.persona-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; font-weight: 600; color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--accent)); padding: 2px 10px 2px 3px;
  border-radius: 14px; margin-right: 8px; vertical-align: middle; }
.chip-ava { width: 20px; height: 20px; border-radius: 50%; object-fit: cover; border: 1.5px solid rgba(255,255,255,.85); }
.chat-sub { font-size: 12px; color: var(--text-soft); }
.header-right { display: flex; align-items: center; gap: 12px; }
.emotion-badge { padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.emotion-badge.positive { background: #e7f7ec; color: #2f9e6b; }
.emotion-badge.negative { background: #fdeef0; color: #e0556d; }
.emotion-badge.neutral { background: #f0f0f6; color: #7b7890; }
.profile-link { font-size: 13px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 20px; }

.messages { flex: 1; overflow-y: auto; padding: 24px; }

.daily-card {
  background: linear-gradient(135deg, #f3eeff, #fff2f5);
  border: 1px solid var(--border); border-radius: 14px; padding: 16px 18px;
  margin-bottom: 20px;
}
.daily-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.daily-title { font-size: 14px; font-weight: 600; color: var(--primary); }
.daily-close { border: none; background: transparent; color: var(--text-soft); cursor: pointer; }
.daily-text { font-size: 14px; line-height: 1.7; }
.daily-tip { font-size: 13px; color: var(--text-soft); margin-top: 8px; }

.welcome { text-align: center; padding: 60px 0; color: var(--text-soft); }
.welcome .w-emoji { font-size: 40px; }
.welcome p { margin-top: 8px; }
.welcome .w-sub { font-size: 14px; }

.msg-row { display: flex; margin-bottom: 16px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.bubble { max-width: 68%; padding: 12px 16px; border-radius: 16px; font-size: 15px; word-break: break-word; }
.msg-row.user .bubble { background: linear-gradient(135deg, var(--primary), #9b8cf0); color: #fff; border-bottom-right-radius: 4px; }
.msg-row.assistant .bubble { background: #fff; border: 1px solid var(--border); border-bottom-left-radius: 4px; }
.b-img { max-width: 240px; border-radius: 10px; margin-bottom: 6px; cursor: zoom-in; display: block; }
.b-text { white-space: pre-wrap; }
.b-tags { margin-top: 8px; display: flex; align-items: center; gap: 8px; }
.tag.emo { font-size: 12px; opacity: .95; }
.tag.emo.clickable { cursor: pointer; border-bottom: 1px dashed rgba(255,255,255,.6); padding-bottom: 1px; }
.tag.emo.clickable:hover { opacity: 1; }
.calib-edit { font-size: 10px; margin-left: 3px; }
.calib-done { font-size: 11px; background: rgba(255,255,255,.28); padding: 1px 7px; border-radius: 8px; }

.calib-mask { position: fixed; inset: 0; background: rgba(30,25,45,.45); display: flex;
  align-items: center; justify-content: center; z-index: 150; padding: 20px; }
.calib-modal { width: 460px; max-width: 100%; padding: 22px 24px; }
.calib-modal h4 { font-size: 16px; margin-bottom: 6px; }
.calib-sub { font-size: 13px; color: var(--text-soft); margin-bottom: 14px; }
.calib-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.calib-grid button {
  border: 1px solid var(--border); background: #fbfaff; border-radius: 10px;
  padding: 10px 4px; font-size: 13px; transition: all .15s;
}
.calib-grid button:hover { background: var(--primary-soft); border-color: var(--primary); }
.calib-grid button.cur { background: var(--primary); color: #fff; border-color: var(--primary); }
.calib-grid button:disabled { opacity: .6; }
.calib-note { font-size: 12px; color: var(--text-soft); margin-top: 14px; text-align: center; }

.typing { display: flex; gap: 4px; padding: 14px 16px; }
.typing span { width: 6px; height: 6px; border-radius: 50%; background: var(--text-soft); animation: blink 1.2s infinite; }
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%,100% { opacity: .2; } 50% { opacity: 1; } }

.composer { display: flex; gap: 8px; padding: 14px 24px; background: #fff; border-top: 1px solid var(--border); align-items: flex-end; }
.icon-btn {
  width: 42px; height: 42px; flex-shrink: 0; border: 1px solid var(--border);
  background: #fbfaff; border-radius: 12px; font-size: 18px; transition: all .15s;
}
.icon-btn:hover { background: var(--primary-soft); }
.icon-btn.recording { background: #fdeef0; border-color: #e0556d; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(224,85,109,.4);} 50% { box-shadow: 0 0 0 6px rgba(224,85,109,0);} }
.composer textarea {
  flex: 1; resize: none; border: 1px solid var(--border); border-radius: 12px;
  padding: 11px 13px; font-size: 15px; background: #fbfaff;
}
.composer textarea:focus { outline: none; border-color: var(--primary); }
.send-btn { align-self: stretch; padding: 0 22px; border: none; border-radius: 12px; background: var(--primary); color: #fff; font-size: 15px; }
.send-btn:disabled { opacity: .5; cursor: not-allowed; }

.img-modal { position: fixed; inset: 0; background: rgba(30,25,45,.8); display: flex; align-items: center; justify-content: center; z-index: 100; cursor: zoom-out; }
.img-modal img { max-width: 90%; max-height: 90%; border-radius: 12px; }

.toast {
  position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%);
  background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px;
  border-radius: 20px; font-size: 13px; z-index: 200;
}
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>