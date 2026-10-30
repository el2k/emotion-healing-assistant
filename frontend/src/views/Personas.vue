<template>
  <div class="persona-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <span class="tb-title">🎭 角色广场 · 多智能体</span>
    </header>

    <div class="intro">
      <h2>今天想和谁聊聊天？</h2>
      <p>每个角色都有自己的性格与说话方式，和你聊过的情绪都会记录到你的情绪档案里，彼此联通。</p>
    </div>

    <!-- 热门角色 -->
    <section v-if="popular.length && !search" class="section">
      <div class="sec-head"><span class="sec-title">🔥 热门角色</span><span class="sec-sub">大家都在聊</span></div>
      <div class="hot-row">
        <div v-for="(p, i) in popular" :key="p.id" class="hot-card"
             :style="{ '--pc': p.color }" @click="startChat(p)">
          <span class="rank" :class="{ top: i < 3 }">{{ i + 1 }}</span>
          <img v-if="p.avatar" :src="p.avatar" class="hot-ava" :alt="p.name" loading="lazy" />
          <div v-else class="hot-emoji">{{ p.emoji }}</div>
          <div class="hot-name">{{ p.name }}</div>
          <div class="hot-count">{{ p.chat_count }} 人在聊</div>
        </div>
      </div>
    </section>

    <!-- 分类 + 搜索 -->
    <section class="section">
      <div class="filter-bar">
        <div class="select-wrap">
          <select v-model="activeCat" class="cat-select">
            <option value="">全部分类</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="search-box">
          <span>🔍</span>
          <input v-model="search" placeholder="搜索角色名 / 作品 / 标签…" />
          <button v-if="search" @click="search = ''">✕</button>
        </div>
        <span class="result-count">共 {{ filtered.length }} 位</span>
      </div>

      <div class="grid">
        <div v-for="p in filtered" :key="p.id" class="persona-card"
             :style="{ '--pc': p.color }" @click="startChat(p)">
          <div class="pc-hero">
            <img v-if="p.avatar" :src="p.avatar" :alt="p.name" loading="lazy" />
            <div v-else class="pc-emoji">{{ p.emoji }}</div>
            <span class="pc-cat">{{ p.category }}</span>
            <span v-if="p.model_3d" class="pc-3d">3D 可互动</span>
          </div>
          <div class="pc-body">
            <div class="pc-name">{{ p.name }} <span class="pc-work">{{ p.work }}</span></div>
            <div class="pc-tag">{{ p.tag }}</div>
            <div class="pc-desc">{{ p.desc }}</div>
            <div class="pc-foot">
              <span class="pc-count">💬 {{ p.chat_count }}</span>
              <button class="pc-btn" @click.stop="startChat(p)">开始聊天</button>
            </div>
          </div>
        </div>
      </div>
      <p v-if="!filtered.length" class="empty">没有找到匹配的角色</p>
    </section>

    <div class="note card">
      🔒 所有角色均为情绪陪伴定位，保持健康、正向的交流氛围；动漫/游戏角色为同人演绎，不涉及色情或诱导亲密依赖。
    </div>

    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const personas = ref([])
const activeCat = ref('')
const search = ref('')
const toastMsg = ref('')
let toastTimer = null
let busy = false
function toast(m) { toastMsg.value = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => toastMsg.value = '', 2200) }

const categories = ['治愈陪伴', '趣味互动', '3D 陪伴', '动漫角色', '游戏角色']

const filtered = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return personas.value.filter((p) => {
    if (activeCat.value && p.category !== activeCat.value) return false
    if (!kw) return true
    return [p.name, p.tag, p.work, p.desc, p.category]
      .some((s) => (s || '').toLowerCase().includes(kw))
  })
})

const popular = computed(() =>
  [...personas.value].sort((a, b) => (b.chat_count || 0) - (a.chat_count || 0)).slice(0, 6))

async function startChat(p) {
  if (busy) return
  busy = true
  try {
    // 3D 角色进入专属 3D 互动页
    if (p.model_3d) {
      router.push('/vrm')
      return
    }
    await api.post('/chat/sessions', { title: `和${p.name}聊天`, persona_id: p.id })
    router.push('/')
  } catch (e) {
    toast('创建对话失败，请重试')
  } finally {
    busy = false
  }
}

onMounted(async () => {
  try { personas.value = (await api.get('/chat/personas')).data } catch (e) { toast('加载角色失败') }
})
</script>

<style scoped>
.persona-page { min-height: 100vh; background: var(--bg); padding-bottom: 40px; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }
.intro { max-width: 1120px; margin: 26px auto 0; padding: 0 20px; }
.intro h2 { font-size: 22px; margin-bottom: 6px; }
.intro p { color: var(--text-soft); font-size: 14px; }

.section { max-width: 1120px; margin: 22px auto 0; padding: 0 20px; }
.sec-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.sec-title { font-size: 17px; font-weight: 700; }
.sec-sub { font-size: 12px; color: var(--text-soft); }

.hot-row { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 6px; }
.hot-card { position: relative; flex-shrink: 0; width: 132px; background: #fff; border: 1px solid var(--border);
  border-radius: 16px; padding: 14px 12px 12px; text-align: center; cursor: pointer; box-shadow: var(--shadow);
  transition: transform .15s; }
.hot-card:hover { transform: translateY(-3px); }
.rank { position: absolute; top: 8px; left: 10px; font-size: 13px; font-weight: 700; color: var(--text-soft); z-index: 1; }
.rank.top { color: #e0556d; }
.hot-ava { width: 58px; height: 58px; border-radius: 50%; object-fit: cover; display: block; margin: 2px auto 0; border: 2px solid #fff; box-shadow: 0 4px 12px rgba(90,70,150,.14); }
.hot-emoji { font-size: 34px; height: 58px; line-height: 58px; }
.hot-name { font-size: 15px; font-weight: 600; margin-top: 6px; }
.hot-count { font-size: 12px; color: var(--text-soft); margin-top: 4px; }

.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.select-wrap { position: relative; }
.cat-select { appearance: none; -webkit-appearance: none; border: 1px solid var(--border);
  background: #fff url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'><path d='M2 4l4 4 4-4' fill='none' stroke='%238b869b' stroke-width='1.5'/></svg>") no-repeat right 12px center;
  border-radius: 10px; padding: 9px 34px 9px 14px; font-size: 14px; color: var(--text); cursor: pointer; }
.cat-select:focus { outline: none; border-color: var(--primary); }
.search-box { display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid var(--border);
  border-radius: 10px; padding: 8px 14px; flex: 1; max-width: 360px; }
.search-box input { flex: 1; border: none; outline: none; font-size: 14px; background: transparent; }
.search-box button { border: none; background: transparent; color: var(--text-soft); cursor: pointer; }
.result-count { font-size: 13px; color: var(--text-soft); }

.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 860px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .grid { grid-template-columns: 1fr; } }
.persona-card { background: #fff; border: 1px solid var(--border); border-radius: 18px; overflow: hidden;
  box-shadow: var(--shadow); cursor: pointer; transition: transform .15s, box-shadow .15s; position: relative; display: flex; flex-direction: column; }
.persona-card:hover { transform: translateY(-3px); box-shadow: 0 12px 30px rgba(124,111,208,.16); }
.pc-hero { position: relative; height: 158px; background: linear-gradient(160deg, #f5f0ff, #fdf1f4); }
.pc-hero img { width: 100%; height: 100%; object-fit: cover; object-position: center 26%; display: block; }
.pc-emoji { height: 100%; display: flex; align-items: center; justify-content: center; font-size: 46px; }
.pc-cat { position: absolute; top: 10px; right: 10px; font-size: 11px; color: #fff; background: var(--pc); padding: 2px 9px; border-radius: 9px; }
.pc-3d {
  position: absolute; left: 10px; bottom: 10px; font-size: 11px; font-weight: 600;
  color: #fff; background: linear-gradient(135deg, #f2a0c0, #7c6fd0);
  padding: 2px 9px; border-radius: 9px; box-shadow: 0 3px 10px rgba(124,111,208,.3);
}
.pc-body { padding: 14px 18px 16px; display: flex; flex-direction: column; flex: 1; }
.pc-name { font-size: 18px; font-weight: 700; }
.pc-work { font-size: 12px; font-weight: 400; color: var(--text-soft); margin-left: 4px; }
.pc-tag { font-size: 12px; color: var(--pc); margin-top: 2px; }
.pc-desc { font-size: 13px; color: var(--text-soft); line-height: 1.6; margin: 10px 0 14px; min-height: 42px; }
.pc-foot { display: flex; justify-content: space-between; align-items: center; margin-top: auto; }
.pc-count { font-size: 12px; color: var(--text-soft); }
.pc-btn { border: none; background: var(--pc); color: #fff; border-radius: 10px; padding: 8px 16px; font-size: 13px; cursor: pointer; }
.empty { text-align: center; color: var(--text-soft); padding: 30px 0; }
.note { max-width: 1120px; margin: 24px auto 0; padding: 14px 18px; font-size: 13px; color: var(--text-soft); }
.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>