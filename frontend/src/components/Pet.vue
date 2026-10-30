<template>
  <div class="pet-root" :style="{ left: pos.x + 'px', top: pos.y + 'px' }">

    <!-- 气泡 -->
    <transition name="pop">
      <div v-if="bubble" class="pet-bubble">{{ bubble }}</div>
    </transition>

    <!-- 爱心粒子 -->
    <transition-group name="heart" tag="div" class="hearts">
      <span v-for="h in hearts" :key="h.id" class="heart" :style="{ left: h.left + 'px' }">❤</span>
    </transition-group>

    <!-- 宠物本体（可拖动 / 点击） -->
    <div v-show="!conf.collapsed" class="pet-hit" :class="{ dragging, happy, eating, sleeping }"
         @pointerdown="onDown" @pointermove="onMove" @pointerup="onUp"
         @pointercancel="onUp" :title="`拖我 / 摸摸${species.name}`">
      <svg class="pet-svg" viewBox="0 0 120 120" :style="{ '--p1': species.c1, '--p2': species.c2, '--belly': species.belly }">
        <!-- 尾巴/耳朵等（按物种） -->
        <g v-if="species.id === 'whale'" class="tail">
          <path d="M100 66 q18 -16 20 0 q-2 16 -20 0 z" fill="var(--p2)"/>
        </g>
        <g v-if="species.id === 'cat'" class="cat-ear">
          <path d="M34 34 l10 -16 10 14 z" fill="var(--p1)"/>
          <path d="M86 34 l-10 -16 -10 14 z" fill="var(--p1)"/>
        </g>
        <g v-if="species.id === 'bunny'" class="bunny-ear">
          <ellipse cx="46" cy="20" rx="7" ry="20" fill="var(--p1)"/>
          <ellipse cx="74" cy="20" rx="7" ry="20" fill="var(--p1)"/>
        </g>
        <g v-if="species.id === 'dino'">
          <path d="M40 40 l6 -10 6 8 l6 -10 6 8 l6 -10 6 8" fill="none" stroke="var(--p2)" stroke-width="4" stroke-linejoin="round"/>
        </g>

        <!-- 身体 -->
        <ellipse cx="60" cy="70" rx="40" ry="34" fill="var(--p1)"/>
        <ellipse cx="60" cy="80" rx="30" ry="22" fill="var(--belly)" opacity="0.9"/>

        <!-- 企鹅白肚 -->
        <ellipse v-if="species.id === 'penguin'" cx="60" cy="74" rx="24" ry="28" fill="#fff"/>

        <!-- 眼睛（会眨眼/跟随光标） -->
        <g class="eyes">
          <g v-for="ex in [45, 75]" :key="ex">
            <ellipse :cx="ex" cy="66" rx="7" ry="9" fill="#2b2b3a"/>
            <circle :cx="ex + look.dx" :cy="66 + look.dy" r="2.4" fill="#fff" opacity="0.92"/>
          </g>
        </g>

        <!-- 腮红 -->
        <ellipse cx="34" cy="80" rx="7" ry="4.5" fill="#f59fb0" opacity="0.55"/>
        <ellipse cx="86" cy="80" rx="7" ry="4.5" fill="#f59fb0" opacity="0.55"/>

        <!-- 嘴巴 -->
        <path d="M54 80 q6 6 12 0" fill="none" stroke="#2b2b3a" stroke-width="2" stroke-linecap="round"/>
        <path v-if="species.id === 'chick' || species.id === 'penguin'"
              d="M56 82 l4 6 l4 -6 z" fill="#f0a020"/>

        <!-- 猫胡须 -->
        <g v-if="species.id === 'cat'" stroke="#8b869b" stroke-width="1.5" stroke-linecap="round">
          <line x1="24" y1="78" x2="40" y2="80"/><line x1="24" y1="84" x2="40" y2="84"/>
          <line x1="96" y1="78" x2="80" y2="80"/><line x1="96" y1="84" x2="80" y2="84"/>
        </g>

        <!-- 鲸鱼喷水 -->
        <g v-if="species.id === 'whale'" class="spout" :class="{ on: eating || boing }">
          <circle cx="60" cy="34" r="3" fill="#bfe3ff"/>
          <circle cx="54" cy="26" r="2.4" fill="#bfe3ff"/>
          <circle cx="66" cy="26" r="2.4" fill="#bfe3ff"/>
        </g>

        <!-- 睡觉 Z -->
        <text v-if="sleeping" x="92" y="40" class="zzz">z</text>
      </svg>
    </div>

    <!-- 工具栏 -->
    <div v-show="!conf.collapsed" class="pet-tools">
      <button class="tool" @click="toggleChooser" title="换宠物">🐾</button>
      <button class="tool" @click="feed" title="投喂">🍎</button>
      <button class="tool" @click="toggleSleep" :title="sleeping ? '叫醒' : '哄睡'">{{ sleeping ? '☀' : '🌙' }}</button>
      <button class="tool" @click="collapse" title="收起">—</button>
    </div>

    <!-- 选择面板 -->
    <div v-if="showChooser" class="pet-chooser card">
      <div class="pc-head">选择桌面宠物</div>
      <div class="pc-grid">
        <button v-for="p in speciesList" :key="p.id" class="pc-opt"
                :class="{ active: p.id === species.id }" @click="choose(p)">
          <span class="pc-dot" :style="{ background: p.c1 }"></span>
          <span class="pc-name">{{ p.name }}</span>
        </button>
      </div>
      <p class="pc-tip">拖拽移动 · 点击摸摸 · 🍎 投喂 · 🌙 哄睡</p>
    </div>

    <!-- 收起后的入口 -->
    <button v-if="conf.collapsed" class="expand" @click="wakeCollapse">🐾</button>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'

const speciesList = [
  { id: 'whale', name: '大肥鱼', c1: '#7fb0e8', c2: '#5e93d6', belly: '#eaf3ff' },
  { id: 'cat', name: '奶牛猫', c1: '#f0b45a', c2: '#e0993a', belly: '#ffe6bd' },
  { id: 'bunny', name: '小白兔', c1: '#f0c0d0', c2: '#e5a6bd', belly: '#ffffff' },
  { id: 'penguin', name: '企鹅', c1: '#54627d', c2: '#3d4a63', belly: '#ffffff' },
  { id: 'dino', name: '小恐龙', c1: '#8fd0a8', c2: '#6fb98a', belly: '#ddf3e6' },
  { id: 'chick', name: '小鸡', c1: '#f5d060', c2: '#e6b93e', belly: '#fff6cc' },
]

const petId = ref(localStorage.getItem('eh_pet') || 'whale')
const species = computed(() => speciesList.find((p) => p.id === petId.value) || speciesList[0])

const affinity = ref(Number(localStorage.getItem('eh_pet_affinity') || 0))
const bubble = ref('')
const boing = ref(false)
const eating = ref(false)
const sleeping = ref(false)
const dragging = ref(false)
const happy = ref(false)
const showChooser = ref(false)
const hearts = ref([])
const look = reactive({ dx: 0, dy: 0 })

// 位置持久化
const conf = reactive({
  collapsed: localStorage.getItem('eh_pet_collapsed') === '1',
})
const pos = reactive(loadPos())
function loadPos() {
  try {
    const s = JSON.parse(localStorage.getItem('eh_pet_pos') || 'null')
    if (s && typeof s.x === 'number') return { x: s.x, y: s.y }
  } catch (e) { /* ignore */ }
  return { x: Math.max(20, window.innerWidth - 150), y: Math.max(20, window.innerHeight - 240) }
}

const LINES = ['摸摸我～好舒服呀', '今天也要开开心心的哦', '累了就休息一下嘛', '我一直在陪着你呢',
  '深呼吸，一切都会好的', '你已经很棒啦！', '要不要和我聊聊天？', '嘿嘿，被摸头了呢']
function rand(a) { return a[Math.floor(Math.random() * a.length)] }
let bubbleTimer = null
function say(t, ms = 3000) { bubble.value = t; clearTimeout(bubbleTimer); bubbleTimer = setTimeout(() => (bubble.value = ''), ms) }

// 拖动
let draggingState = null
function onDown(e) {
  if (conf.collapsed) return
  draggingState = { sx: e.clientX, sy: e.clientY, ox: pos.x, oy: pos.y, moved: false }
  dragging.value = false
  window.addEventListener('pointermove', onWinMove)
  window.addEventListener('pointerup', onWinUp)
}
function onWinMove(e) {
  if (!draggingState) return
  const dx = e.clientX - draggingState.sx
  const dy = e.clientY - draggingState.sy
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) { dragging.value = true; draggingState.moved = true; wake() }
  if (dragging.value) {
    pos.x = clamp(draggingState.ox + dx, 0, window.innerWidth - 96)
    pos.y = clamp(draggingState.oy + dy, 0, window.innerHeight - 96)
  }
}
function onWinUp() {
  window.removeEventListener('pointermove', onWinMove)
  window.removeEventListener('pointerup', onWinUp)
  if (draggingState && draggingState.moved) {
    localStorage.setItem('eh_pet_pos', JSON.stringify({ x: pos.x, y: pos.y }))
    say('呼…换个地方待着也不错～', 1800)
  } else {
    petting()
  }
  dragging.value = false
  draggingState = null
}
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }
// 移动端 pointermove 直接在元素上也可
function onMove(e) { trackLook(e) }
function onUp() { /* 由 window 处理 */ }

// 眼睛跟随光标
function trackLook(e) {
  const svg = document.querySelector('.pet-root .pet-hit')
  if (!svg) return
  const r = svg.getBoundingClientRect()
  const cx = r.left + r.width / 2
  const cy = r.top + r.height / 2
  const dx = (e.clientX - cx) / r.width
  const dy = (e.clientY - cy) / r.height
  look.dx = clamp(dx * 3.5, -3, 3)
  look.dy = clamp(dy * 3, -2.5, 2.5)
}

function petting() {
  wake()
  affinity.value += 1
  localStorage.setItem('eh_pet_affinity', String(affinity.value))
  happy.value = true; boing.value = true
  setTimeout(() => { happy.value = false; boing.value = false }, 500)
  spawnHearts(3)
  let line = rand(LINES)
  if (affinity.value === 5) line = '我们已经是好朋友啦！(⁎˃ᴗ˂⁎)'
  else if (affinity.value === 10) line = '呜哇，好感度满满了～谢谢你！'
  else if (affinity.value === 20) line = '你是我最喜欢的铲屎官啦～'
  say(line)
}
function feed() {
  wake()
  affinity.value += 2
  localStorage.setItem('eh_pet_affinity', String(affinity.value))
  eating.value = true; boing.value = true
  setTimeout(() => { eating.value = false; boing.value = false }, 700)
  spawnHearts(4)
  say('谢谢投喂！好好吃～ (๑´ڡ`๑)')
}
function toggleSleep() { sleeping.value ? wake() : sleep() }
function sleep() { sleeping.value = true; say('好困…我先眯一会儿 zzz', 2000) }
function wake() { if (sleeping.value) { sleeping.value = false; say('呀，我醒啦！', 1400) } }

function collapse() { conf.collapsed = true; localStorage.setItem('eh_pet_collapsed', '1') }
function wakeCollapse() { conf.collapsed = false; localStorage.setItem('eh_pet_collapsed', '0') }

function choose(p) {
  petId.value = p.id
  localStorage.setItem('eh_pet', p.id)
  showChooser.value = false
  say(`你好呀，我是${p.name}！以后我陪你啦～`)
}
function toggleChooser() { showChooser.value = !showChooser.value }

let hid = 0
function spawnHearts(n) {
  for (let i = 0; i < n; i++) {
    const id = ++hid
    hearts.value.push({ id, left: 20 + Math.random() * 50 })
    setTimeout(() => { hearts.value = hearts.value.filter((h) => h.id !== id) }, 900)
  }
}

let idleTimer = null
const onGlobMove = (e) => { if (!dragging.value) trackLook(e) }
onMounted(() => {
  idleTimer = setInterval(() => {
    if (!bubble.value && !sleeping.value && Math.random() < 0.4) say(rand(LINES), 3500)
  }, 28000)
  window.addEventListener('mousemove', onGlobMove)
  window.addEventListener('resize', () => {
    pos.x = clamp(pos.x, 0, window.innerWidth - 96)
    pos.y = clamp(pos.y, 0, window.innerHeight - 96)
  })
})
onBeforeUnmount(() => {
  clearTimeout(bubbleTimer); clearInterval(idleTimer)
  window.removeEventListener('mousemove', onGlobMove)
  window.removeEventListener('pointermove', onWinMove)
  window.removeEventListener('pointerup', onWinUp)
})
</script>

<style scoped>
.pet-root { position: fixed; width: 96px; height: 96px; z-index: 90; user-select: none; touch-action: none; }

.pet-hit { width: 96px; height: 96px; cursor: grab; position: relative; }
.pet-hit.dragging { cursor: grabbing; }
.pet-hit.dragging .pet-svg { animation: none; transform: scale(1.06); }

.pet-svg { width: 100%; height: 100%; overflow: visible; animation: float 3.2s ease-in-out infinite; transform-origin: 50% 70%; }
.pet-hit.happy .pet-svg, .pet-hit.eating .pet-svg { animation: boing .5s ease; }

/* 眨眼 */
.eyes { animation: blink 5.5s infinite; transform-box: fill-box; transform-origin: center; }
.pet-hit.sleeping .eyes { animation: none; transform: scaleY(.12); }
.pet-hit.dragging .eyes { animation: none; }

/* 尾巴/耳朵动效 */
.tail { animation: wag 1.8s ease-in-out infinite; transform-box: fill-box; transform-origin: left center; }
.bunny-ear { animation: earwobble 3s ease-in-out infinite; transform-box: fill-box; transform-origin: bottom center; }
.spout { opacity: 0; transition: opacity .2s; }
.spout.on { opacity: 1; }
.zzz { font-size: 16px; fill: #8b869b; font-weight: 700; animation: zfloat 2s ease-in-out infinite; }

@keyframes float { 0%,100% { transform: translateY(0) rotate(-1deg); } 50% { transform: translateY(-8px) rotate(1deg); } }
@keyframes boing { 0% { transform: scale(1); } 30% { transform: scale(1.18, .86); } 60% { transform: scale(.92, 1.1); } 100% { transform: scale(1); } }
@keyframes blink { 0%,92%,100% { transform: scaleY(1); } 96% { transform: scaleY(.12); } }
@keyframes wag { 0%,100% { transform: rotate(-8deg); } 50% { transform: rotate(10deg); } }
@keyframes earwobble { 0%,100% { transform: rotate(-4deg); } 50% { transform: rotate(4deg); } }
@keyframes zfloat { 0%,100% { opacity: .3; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-6px); } }

.pet-bubble { position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
  max-width: 180px; background: #fff; border: 1px solid var(--border); border-radius: 14px;
  padding: 8px 12px; font-size: 13px; color: var(--text); box-shadow: var(--shadow); white-space: nowrap; }
.pet-bubble::after { content: ''; position: absolute; bottom: -7px; left: 50%; transform: translateX(-50%);
  border: 7px solid transparent; border-top-color: #fff; }

.hearts { position: absolute; inset: 0; pointer-events: none; overflow: visible; }
.heart { position: absolute; bottom: 60px; color: #f0637b; font-size: 15px; }
.heart-enter-active { transition: all .9s ease-out; }
.heart-enter-from { opacity: 1; transform: translateY(0) scale(.6); }
.heart-enter-to { opacity: 0; transform: translateY(-42px) scale(1.1); }

.pet-tools { position: absolute; top: calc(100% + 6px); left: 50%; transform: translateX(-50%);
  display: flex; gap: 5px; opacity: 0; transition: opacity .2s; }
.pet-root:hover .pet-tools { opacity: 1; }
.tool { width: 26px; height: 26px; border-radius: 50%; border: 1px solid var(--border); background: #fff;
  font-size: 12px; cursor: pointer; box-shadow: var(--shadow); padding: 0; }
.tool:hover { background: var(--primary-soft); }

.pet-chooser { position: absolute; bottom: calc(100% + 50px); left: 50%; transform: translateX(-50%);
  width: 230px; padding: 12px; z-index: 5; }
.pc-head { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
.pc-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.pc-opt { display: flex; flex-direction: column; align-items: center; gap: 4px; border: 1px solid var(--border);
  background: #fbfaff; border-radius: 10px; padding: 8px 4px; cursor: pointer; }
.pc-opt.active { border-color: var(--primary); background: var(--primary-soft); }
.pc-dot { width: 22px; height: 22px; border-radius: 50%; box-shadow: inset 0 -3px 4px rgba(0,0,0,.12); }
.pc-name { font-size: 11px; }
.pc-tip { font-size: 11px; color: var(--text-soft); margin-top: 10px; text-align: center; }

.expand { position: absolute; top: 0; left: 0; width: 44px; height: 44px; border-radius: 50%;
  border: 1px solid var(--border); background: #fff; font-size: 18px; cursor: pointer; box-shadow: var(--shadow); }

.pop-enter-active, .pop-leave-active { transition: all .25s; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateX(-50%) translateY(6px); }
</style>