<template>
  <div class="heal-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <span class="tb-title">🩺 心理疗愈室</span>
      <router-link to="/knowledge" class="kb-link">📖 知识库</router-link>
    </header>

    <!-- 重要提示 -->
    <div class="banner card">
      <div class="bn-icon">🩺</div>
      <div>
        <h3>这里为「明确疾病状态」的用户提供专业陪伴</h3>
        <p>
          选择你正面对的状态，我们会为你匹配对应方向的专家角色。请务必了解：
          这里的角色提供<b>倾听、心理教育与陪伴</b>，<b>不做诊断、不谈药物、不替代就医</b>。
          如果正处于危机中（自伤/轻生念头），请直接联系全国心理援助热线
          <b>12356</b>（24 小时）或前往医院急诊。
        </p>
      </div>
    </div>

    <div class="intro">
      <h2>你正在面对哪一种状态？</h2>
      <p>如实选择即可。匹配后可随时在聊天页继续，所有对话同样计入你的情绪档案。</p>
    </div>

    <!-- 疾病选择 -->
    <div class="grid">
      <button v-for="d in diseases" :key="d.id" class="d-card card"
              :disabled="busy" @click="pick(d)">
        <img v-if="d.avatar" :src="d.avatar" class="d-ava" :alt="d.expert" loading="lazy" />
        <div class="d-main">
          <div class="d-name">{{ d.icon }} {{ d.name }}</div>
          <div class="d-desc">{{ d.desc }}</div>
          <div class="d-expert">
            <span class="d-dot"></span>
            匹配专家：<b>{{ d.expert }}</b> · {{ d.direction }}
          </div>
        </div>
        <span class="d-go">进入 ›</span>
      </button>
    </div>

    <div class="note card">
      <b>如何使用这个房间</b>
      <p>· 专家会优先稳定你的情绪，再陪你梳理状态，节奏由你决定，不追问细节。</p>
      <p>· 出现「消失」「解脱」之类念头时，请立刻拨打 <b>12356</b>，或让身边可信的人陪你就医。</p>
      <p>· 规律就诊与面对面咨询是最有效的路径，这里的陪伴是「路上的一盏灯」，不是「终点」。</p>
    </div>

    <!-- 进入确认 -->
    <div v-if="confirming" class="mask" @click.self="confirming = null">
      <div class="modal card">
        <h3>进入「{{ confirming.name }}」支持</h3>
        <div class="m-expert">
          <img v-if="confirming.avatar" :src="confirming.avatar" class="m-ava" alt="" />
          <div>
            <b>{{ confirming.expert }}</b>
            <span>{{ confirming.direction }} · {{ confirming.tagline }}</span>
          </div>
        </div>
        <ul class="m-list">
          <li>我理解：这里的对话是陪伴与心理教育，<b>不构成诊断或治疗</b>。</li>
          <li>我理解：如需评估与治疗，应前往医院精神科/心理科或正规心理咨询机构。</li>
          <li>我理解：出现自伤或轻生念头时，应立即拨打 12356 或就医。</li>
        </ul>
        <div class="m-actions">
          <button class="btn ghost" @click="confirming = null">再想想</button>
          <button class="btn main" :disabled="busy" @click="start">
            {{ busy ? '正在安排…' : '我已了解，开始倾诉' }}
          </button>
        </div>
      </div>
    </div>

    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const busy = ref(false)
const confirming = ref(null)
const toastMsg = ref('')
const personas = ref([])
let toastTimer = null

function toast(m) { toastMsg.value = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => toastMsg.value = '', 2400) }

/* 疾病 → 专家映射（与后端 personas.py 的疗愈室角色一一对应） */
const DISEASES = [
  { id: 'heal_dep', name: '抑郁状态', icon: '🌧', desc: '情绪持续低落、提不起劲、觉得自己没价值', expert: '林静之', direction: '精神科背景 · 抑郁方向' },
  { id: 'heal_anx', name: '焦虑与惊恐', icon: '🌀', desc: '反复担忧、坐立不安、惊恐发作的心跳与失控感', expert: '陈以宁', direction: 'CBT 治疗师 · 焦虑与惊恐' },
  { id: 'heal_soc', name: '社交焦虑', icon: '🫂', desc: '被看着就不自在、事后反复回想自己哪里做错了', expert: '方岚', direction: '社交焦虑方向' },
  { id: 'heal_ocd', name: '强迫与反刍', icon: '🔁', desc: '停不下来的念头、反复检查与仪式行为', expert: '周明远', direction: '强迫方向 · ERP 视角' },
  { id: 'heal_ptsd', name: '创伤后应激', icon: '🌙', desc: '闪回、噩梦、警觉过度，过去总在此时此刻重播', expert: '苏晚晴', direction: '创伤知情 · 应激方向' },
  { id: 'heal_eat', name: '进食困扰', icon: '🍮', desc: '与食物、体重和镜子之间令人疲惫的关系', expert: '温言', direction: '进食与身材焦虑方向' },
  { id: 'heal_bip', name: '情绪起伏', icon: '⛵', desc: '情绪的高低起伏、睡眠节律紊乱、高效期透支', expert: '柯一帆', direction: '双相与睡眠节律方向' },
]

const diseases = ref(DISEASES)

onMounted(async () => {
  try {
    const { data } = await api.get('/chat/personas')
    personas.value = data
    diseases.value = DISEASES.map((d) => {
      const p = data.find((x) => x.id === d.id)
      return { ...d, avatar: p?.avatar || '', tagline: p?.tag || '' }
    })
  } catch (e) { /* 忽略 */ }
})

function pick(d) { confirming.value = d }

async function start() {
  const d = confirming.value
  busy.value = true
  try {
    await api.post('/chat/sessions', {
      title: `疗愈室 · ${d.name}`,
      persona_id: d.id,
    })
    toast('已为你安排好，请慢慢说')
    router.push('/')
  } catch (e) {
    toast(e.response?.data?.detail || '创建失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.heal-page { min-height: 100vh; background: linear-gradient(180deg, #f2f6ff 0%, var(--bg) 240px); padding-bottom: 56px; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 14px 28px; background: rgba(255,255,255,.9); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: #4a6bd0; flex: 1; }
.kb-link { font-size: 13.5px; padding: 6px 12px; border: 1px solid #d9e2f8; background: #eef3ff; color: #4a6bd0; border-radius: 20px; }

.banner { max-width: 1020px; margin: 20px auto 0; padding: 16px 20px; display: flex; gap: 14px; border-color: #d9e2f8; background: #f7faff; }
.bn-icon { font-size: 26px; flex: none; }
.banner h3 { font-size: 15px; margin-bottom: 6px; color: #2c3f66; }
.banner p { font-size: 12.8px; color: #56617a; line-height: 1.8; }
.banner b { color: #d9536b; }

.intro { max-width: 1020px; margin: 22px auto 14px; padding: 0 4px; }
.intro h2 { font-size: 19px; }
.intro p { font-size: 13px; color: var(--text-soft); margin-top: 4px; }

.grid { max-width: 1020px; margin: 0 auto; display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
@media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
.d-card { display: flex; align-items: center; gap: 14px; padding: 16px 18px; text-align: left; cursor: pointer; transition: transform .15s, box-shadow .15s, border-color .15s; border: 1px solid var(--border); background: #fff; }
.d-card:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 12px 26px rgba(74,107,208,.12); border-color: #c9d6f2; }
.d-card:disabled { opacity: .6; cursor: wait; }
.d-ava { width: 56px; height: 56px; border-radius: 50%; object-fit: cover; flex: none; background: #eef2fa; }
.d-main { flex: 1; min-width: 0; }
.d-name { font-size: 15.5px; font-weight: 700; color: #2c3f66; }
.d-desc { font-size: 12.5px; color: var(--text-soft); margin-top: 4px; line-height: 1.6; }
.d-expert { font-size: 12px; color: #4a6bd0; margin-top: 8px; display: flex; align-items: center; gap: 6px; }
.d-expert b { font-weight: 700; }
.d-dot { width: 6px; height: 6px; border-radius: 50%; background: #4a6bd0; flex: none; }
.d-go { font-size: 13px; color: #9fb0d8; flex: none; }

.note { max-width: 1020px; margin: 18px auto 0; padding: 14px 18px; background: #fff; }
.note b { font-size: 13px; color: #2c3f66; display: block; margin-bottom: 6px; }
.note p { font-size: 12.5px; color: var(--text-soft); line-height: 1.9; }
.note b, .banner b { color: #d9536b; }
.note p b { color: #d9536b; font-weight: 600; }
.note > b { color: #2c3f66; }

.mask { position: fixed; inset: 0; background: rgba(28, 34, 58, .45); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.modal { width: 460px; max-width: 100%; padding: 24px 26px; }
.modal h3 { font-size: 16px; margin-bottom: 14px; }
.m-expert { display: flex; align-items: center; gap: 12px; background: #f7faff; border: 1px solid #d9e2f8; border-radius: 12px; padding: 12px 14px; margin-bottom: 14px; }
.m-ava { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; flex: none; }
.m-expert b { display: block; font-size: 14.5px; }
.m-expert span { font-size: 12px; color: var(--text-soft); }
.m-list { margin: 0 0 4px 18px; }
.m-list li { font-size: 12.8px; color: #56617a; line-height: 1.95; }
.m-list b { color: #d9536b; }
.m-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.btn { border: none; border-radius: 10px; padding: 10px 18px; font-size: 13.5px; cursor: pointer; }
.btn.ghost { background: #f1eefa; color: var(--text); }
.btn.main { background: #4a6bd0; color: #fff; box-shadow: 0 4px 14px rgba(74,107,208,.3); }
.btn:disabled { opacity: .6; cursor: wait; }

.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(44, 52, 80, .94); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>