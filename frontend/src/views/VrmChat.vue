<template>
  <div class="vrm-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <div class="tb-title">
        <img v-if="yui.avatar" :src="yui.avatar" class="tb-ava" alt="" />
        <span>🎀 3D 陪伴 · {{ yui.name || '柚子' }}</span>
      </div>
      <label class="tts">
        <input v-model="ttsOn" type="checkbox" />
        语音朗读
      </label>
    </header>

    <div class="vrm-body">
      <!-- 左：3D 舞台 -->
      <section class="stage card">
        <div class="stage-canvas">
          <VrmGirl ref="girlEl" @poke="onPoke" />
          <transition name="fade">
            <div v-if="caption" class="caption">{{ caption }}</div>
          </transition>
        </div>
        <div class="stage-actions">
          <button v-for="a in actions" :key="a.anim" class="act-btn"
                  @click="play(a.anim, a.text)">🫳 {{ a.label }}</button>
        </div>
        <div class="stage-tip">柚子是 Three.js 程序化建模的 JK 水手服少女：会眨眼、摆马尾、跟着鼠标看人，聊天时按情绪做动作。</div>
      </section>

      <!-- 右：聊天 -->
      <section class="chat card">
        <div ref="msgBox" class="msgs">
          <div v-for="m in messages" :key="m.key" class="msg" :class="m.role">
            <img v-if="m.role === 'assistant' && yui.avatar" :src="yui.avatar" class="m-ava" alt="" />
            <div class="bubble">
              <div class="b-text">{{ m.content }}</div>
              <div v-if="m.role === 'user' && m.emotion" class="b-emo">{{ emoIcon(m.emotion) }} {{ m.emotion }}</div>
            </div>
          </div>
          <div v-if="typing" class="msg assistant">
            <img v-if="yui.avatar" :src="yui.avatar" class="m-ava" alt="" />
            <div class="bubble typing"><span></span><span></span><span></span></div>
          </div>
          <div v-if="crisis" class="crisis">⚠️ {{ crisis }}</div>
          <div v-if="!messages.length && !typing" class="hello">
            <div class="h-ava">{{ yui.emoji || '🎀' }}</div>
            <p>呀呼～我是柚子！<br />今天想跟柚子聊点什么呢？</p>
          </div>
        </div>

        <div class="chips">
          <button v-for="c in quick" :key="c" :disabled="typing" @click="send(c)">{{ c }}</button>
        </div>

        <div class="input-row">
          <input v-model="draft" placeholder="跟柚子说点什么…（回车发送）"
                 :disabled="typing" @keydown.enter.prevent="send()" />
          <button class="send" :disabled="typing || !draft.trim()" @click="send()">
            {{ typing ? '回复中…' : '发送' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import VrmGirl from '../components/VrmGirl.vue'
import { api } from '../api'

const girlEl = ref(null)
const yui = reactive({ name: '柚子', emoji: '🎀', avatar: '' })
const messages = ref([])
const draft = ref('')
const typing = ref(false)
const caption = ref('')
const crisis = ref('')
const ttsOn = ref(true)
const msgBox = ref(null)
let sessionId = null
let capTimer = null

const actions = [
  { label: '打招呼', anim: 'wave', text: '柚子元气满满地朝你挥手：呀呼～今天也辛苦啦！' },
  { label: '点点头', anim: 'nod', text: '柚子认真地点了点头。' },
  { label: '开心跳', anim: 'jump', text: '柚子原地蹦了两下，马尾也跟着飞起来！' },
  { label: '摸摸头', anim: 'pat', text: '柚子眯起眼睛蹭了蹭你的手心，好感度 +1' },
  { label: '转个圈', anim: 'spin', text: '柚子拎着裙摆转了个圈～' },
]
const quick = ['今天好累呀', '我有点emo了', '和你聊天真开心！', '陪我深呼吸一下']

/* 情绪 → 动作 + 台词 */
const REACT = {
  喜悦: ['jump', '柚子开心地蹦了起来：呀呼！'],
  期待: ['clap', '柚子搓了搓手：快说快说，柚子洗耳恭听！'],
  感恩: ['clap', '柚子轻轻拍了拍手心，眼睛弯成了月牙。'],
  平静: ['wave', '柚子朝你挥挥手，就这么安静陪着也很好。'],
  悲伤: ['sad', '柚子放轻了动作，慢慢凑近你身边。'],
  低落: ['sad', '柚子托着腮，陪你安静坐了一会儿。'],
  孤独: ['sad', '柚子握住你的手：柚子在呢，不走。'],
  委屈: ['anxious', '柚子皱起小眉头，替你感到不平。'],
  焦虑: ['anxious', '柚子放缓呼吸，示意你跟它一起深呼吸。'],
  愤怒: ['stomp', '柚子跺了跺小皮鞋：抱抱，我们慢慢说。'],
  恐惧: ['scared', '柚子缩了缩肩膀，悄悄站到你身前。'],
  中性: ['nod', '柚子点点头，听你说。'],
}
const HIGH = ['protect', '柚子神情认真起来，双手向前：别怕，你并不孤单——全国心理援助热线 12356，随时有人愿意听你说。']

const emoIcon = (e) => ({
  喜悦: '😊', 平静: '🙂', 感恩: '💗', 期待: '✨', 悲伤: '💧', 焦虑: '🌀',
  愤怒: '⚡', 恐惧: '😨', 孤独: '🌙', 委屈: '🥺', 低落: '🌧', 中性: '☁️',
}[e] || '☁️')

function showCaption(text) {
  caption.value = text
  clearTimeout(capTimer)
  capTimer = setTimeout(() => { caption.value = '' }, 3200)
}

function play(anim, text) {
  girlEl.value?.playAnim(anim)
  if (text) showCaption(text)
}

function onPoke() {
  showCaption('柚子被戳了一下，缩了缩脖子：唔？戳柚子干嘛啦～')
}

function react(emotion, highRisk) {
  const [anim, text] = highRisk ? HIGH : (REACT[emotion] || REACT.中性)
  girlEl.value?.playAnim(anim)
  showCaption(text)
}

async function loadYui() {
  try {
    const { data } = await api.get('/chat/personas')
    const p = data.find((x) => x.id === 'yui')
    if (p) Object.assign(yui, p)
  } catch (e) { /* 忽略 */ }
}

async function loadSession() {
  const { data } = await api.get('/chat/sessions')
  const mine = data.filter((s) => s.persona_id === 'yui')
  if (mine.length) {
    sessionId = mine[0].id
  } else {
    const { data: created } = await api.post('/chat/sessions',
      { title: '和柚子的3D时光', persona_id: 'yui' })
    sessionId = created.id
  }
  const { data: msgs } = await api.get(`/chat/sessions/${sessionId}/messages`)
  messages.value = msgs.map((m, i) => ({
    key: `${m.id}-${i}`, role: m.role, content: m.content,
    emotion: m.role === 'user' ? m.emotion_type : '',
  }))
  scrollToBottom()
}

async function send(preset) {
  const text = (preset || draft.value).trim()
  if (!text || typing.value) return
  draft.value = ''
  crisis.value = ''
  messages.value.push({ key: `u-${Date.now()}`, role: 'user', content: text })
  typing.value = true
  scrollToBottom()
  try {
    const { data } = await api.post(`/chat/sessions/${sessionId}/messages`, { content: text })
    messages.value.push({
      key: `a-${data.reply.id}`, role: 'assistant', content: data.reply.content,
    })
    const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
    if (lastUser) lastUser.emotion = data.emotion.emotion_type
    typing.value = false
    const risky = (data.emotion.high_risk || []).length > 0
    react(data.emotion.emotion_type, risky)
    if (risky) crisis.value = '如果你现在很难受，请记得：全国心理援助热线 12356（24小时）。你不需要独自扛。'
    girlEl.value?.speak(data.reply.content, ttsOn.value)
  } catch (e) {
    typing.value = false
    messages.value.push({ key: `e-${Date.now()}`, role: 'assistant', content: '唔…柚子刚才走神了，再说一遍好不好？' })
  }
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => { msgBox.value?.scrollTo({ top: msgBox.value.scrollHeight, behavior: 'smooth' }) })
}

onMounted(async () => {
  await loadYui()
  await loadSession()
  girlEl.value?.playAnim('wave')
  showCaption('柚子朝你挥挥手：呀呼～你来啦！')
})
</script>

<style scoped>
.vrm-page { min-height: 100vh; background: var(--bg); }
.topbar {
  display: flex; align-items: center; gap: 16px; padding: 12px 24px;
  background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10;
}
.back { font-size: 14px; }
.tb-title { display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 700; color: var(--primary); flex: 1; }
.tb-ava { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; }
.tts { font-size: 13px; color: var(--text-soft); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.tts input { accent-color: var(--primary); }

.vrm-body {
  display: grid; grid-template-columns: 1.15fr 1fr; gap: 16px;
  padding: 18px 24px 30px; max-width: 1280px; margin: 0 auto;
  align-items: stretch;
}
@media (max-width: 900px) { .vrm-body { grid-template-columns: 1fr; } }

.stage { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
.stage-canvas {
  position: relative; height: 430px;
  background: linear-gradient(180deg, #eef4ff 0%, #fdf0f5 70%, #fff 100%);
}
.caption {
  position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
  background: rgba(255, 255, 255, .92); border: 1px solid var(--border);
  padding: 8px 16px; border-radius: 20px; font-size: 13px; color: #4a4360;
  box-shadow: 0 6px 18px rgba(90, 70, 150, .12); max-width: 86%;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.stage-actions { display: flex; gap: 8px; padding: 12px 14px 4px; flex-wrap: wrap; }
.act-btn {
  flex: 1; min-width: 76px; border: 1px solid #e6dff5; background: #fbfaff;
  border-radius: 10px; padding: 8px 10px; font-size: 13px; transition: all .15s;
}
.act-btn:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); }
.stage-tip { font-size: 12px; color: var(--text-soft); padding: 6px 16px 14px; line-height: 1.6; }

.chat { display: flex; flex-direction: column; min-height: 560px; }
.msgs { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.msg { display: flex; gap: 8px; align-items: flex-start; }
.msg.user { justify-content: flex-end; }
.m-ava { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; flex: none; margin-top: 2px; }
.bubble {
  max-width: 78%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.65;
}
.msg.assistant .bubble { background: #fff; border: 1px solid var(--border); border-top-left-radius: 4px; }
.msg.user .bubble { background: var(--primary); color: #fff; border-top-right-radius: 4px; }
.b-emo { font-size: 11.5px; margin-top: 5px; opacity: .85; text-align: right; }
.typing { display: flex; gap: 4px; align-items: center; padding: 14px 16px; }
.typing span {
  width: 7px; height: 7px; border-radius: 50%; background: #c9c0e6; animation: tp 1s infinite;
}
.typing span:nth-child(2) { animation-delay: .18s; }
.typing span:nth-child(3) { animation-delay: .36s; }
@keyframes tp { 0%, 100% { transform: translateY(0); opacity: .5; } 50% { transform: translateY(-4px); opacity: 1; } }

.hello { text-align: center; color: var(--text-soft); padding: 30px 0; font-size: 14px; }
.h-ava { font-size: 40px; margin-bottom: 10px; }

.crisis {
  background: #fdeef0; color: #d9536b; border: 1px solid #f3c2cb;
  font-size: 12.5px; padding: 9px 12px; border-radius: 10px; line-height: 1.6;
}

.chips { display: flex; gap: 8px; padding: 10px 16px 0; flex-wrap: wrap; }
.chips button {
  border: 1px dashed #d9d0ef; background: #faf8ff; color: #6f63b8;
  border-radius: 20px; padding: 5px 12px; font-size: 12.5px;
}
.chips button:hover { background: var(--primary-soft); }
.chips button:disabled { opacity: .5; }

.input-row { display: flex; gap: 10px; padding: 12px 16px 16px; }
.input-row input {
  flex: 1; border: 1px solid var(--border); border-radius: 12px;
  padding: 11px 14px; font-size: 14px; outline: none; background: #fbfaff;
}
.input-row input:focus { border-color: var(--primary); background: #fff; }
.send {
  border: none; background: var(--primary); color: #fff; border-radius: 12px;
  padding: 0 22px; font-size: 14px;
}
.send:disabled { opacity: .55; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>