<template>
  <div class="kb-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <span class="tb-title">📖 情绪知识库</span>
      <router-link to="/heal" class="heal-link">🩺 心理疗愈室</router-link>
    </header>

    <div class="hero">
      <h2>先理解情绪，再照顾情绪</h2>
      <p>从情绪认知到危机求助，整理成可以慢慢读的科普与实践指南。内容仅供心理教育，不构成诊疗建议。</p>
    </div>

    <!-- 分类 + 搜索 -->
    <div class="filter-bar">
      <div class="cats">
        <span class="cat-chip" :class="{ active: !activeCat }" @click="setCat('')">
          全部 <i>{{ totalCount }}</i>
        </span>
        <span v-for="c in cats" :key="c.name" class="cat-chip"
              :class="{ active: activeCat === c.name }" @click="setCat(c.name)">
          {{ c.name }} <i>{{ c.count }}</i>
        </span>
      </div>
      <div class="search-box">
        <span>🔍</span>
        <input v-model="q" placeholder="搜索标题、标签、内容…" @keyup.enter="load" />
      </div>
    </div>

    <!-- 文章卡片 -->
    <div v-if="items.length" class="grid">
      <article v-for="a in items" :key="a.id" class="k-card" @click="open(a.id)">
        <div class="k-head">
          <span class="k-cat" :style="{ background: catColor(a.category) + '22', color: catColor(a.category) }">
            {{ a.category }}
          </span>
          <span class="k-read">⏱ {{ a.read_minutes }} 分钟</span>
        </div>
        <h3 class="k-title">{{ a.title }}</h3>
        <p class="k-summary">{{ a.summary }}</p>
        <div class="k-foot">
          <div class="k-tags">
            <span v-for="t in a.tags.slice(0, 3)" :key="t">#{{ t }}</span>
          </div>
          <span class="k-views">{{ a.views }} 次阅读</span>
        </div>
      </article>
    </div>
    <div v-else class="empty">
      <span class="e-ico">📚</span>
      {{ q ? '没有找到相关内容，换个关键词试试？' : '知识库整理中…' }}
    </div>

    <div class="pager">
      <button :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span>第 {{ page }} 页</span>
      <button :disabled="items.length < pageSize" @click="go(page + 1)">下一页</button>
    </div>

    <div class="note">
      ⚠️ 知识库内容为心理健康科普，不能替代精神科诊疗与面对面心理咨询。
      如果你正在经历难以承受的痛苦，请联系全国心理援助热线 <b>12356</b>（24 小时）。
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const cats = ref([])
const items = ref([])
const activeCat = ref('')
const q = ref('')
const page = ref(1)
const pageSize = 12
const totalCount = computed(() => cats.value.reduce((s, c) => s + c.count, 0))

const CAT_COLORS = {
  '情绪认知': '#7c6fd0', '减压练习': '#2f9e6b', '焦虑应对': '#3d8fd0',
  '抑郁陪伴': '#8d7fd0', '睡眠作息': '#5f74a8', '危机求助': '#d9536b',
}
const catColor = (c) => CAT_COLORS[c] || '#7c6fd0'

async function loadCats() {
  const { data } = await api.get('/knowledge/categories')
  cats.value = data
}
async function load() {
  const { data } = await api.get('/knowledge/articles', {
    params: { category: activeCat.value, q: q.value, page: page.value, page_size: pageSize },
  })
  items.value = data.items
}
function setCat(c) { activeCat.value = c; page.value = 1; load() }
function go(p) { page.value = p; load() }
function open(id) { router.push(`/knowledge/${id}`) }

onMounted(() => { loadCats(); load() })
</script>

<style scoped>
.kb-page { min-height: 100vh; background: var(--bg); padding-bottom: 50px; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); flex: 1; }
.heal-link { font-size: 13.5px; padding: 6px 12px; border: 1px solid #f3c2cb; background: #fdeef0; color: #d9536b; border-radius: 20px; }

.hero { max-width: 1100px; margin: 26px auto 0; padding: 0 20px; }
.hero h2 { font-size: 23px; }
.hero p { color: var(--text-soft); font-size: 13.5px; margin-top: 6px; line-height: 1.7; }

.filter-bar { max-width: 1100px; margin: 18px auto 0; padding: 0 20px; display: flex; align-items: flex-start; gap: 14px; flex-wrap: wrap; }
.cats { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
.cat-chip { font-size: 13px; padding: 6px 13px; border-radius: 16px; background: #fff; border: 1px solid var(--border); color: var(--text-soft); cursor: pointer; transition: all .15s; }
.cat-chip i { font-style: normal; font-size: 11.5px; opacity: .7; margin-left: 3px; }
.cat-chip.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.cat-chip.active i { opacity: .85; }
.search-box { display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid var(--border); border-radius: 20px; padding: 8px 15px; min-width: 260px; }
.search-box input { border: none; outline: none; font-size: 13.5px; background: transparent; flex: 1; }

.grid { max-width: 1100px; margin: 18px auto 0; padding: 0 20px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 960px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
.k-card { background: #fff; border: 1px solid var(--border); border-radius: 16px; padding: 18px 20px; cursor: pointer; transition: transform .15s, box-shadow .15s; display: flex; flex-direction: column; }
.k-card:hover { transform: translateY(-3px); box-shadow: 0 12px 26px rgba(124,111,208,.14); }
.k-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.k-cat { font-size: 11.5px; padding: 3px 10px; border-radius: 20px; font-weight: 600; }
.k-read { font-size: 11.5px; color: var(--text-soft); }
.k-title { font-size: 16px; line-height: 1.5; margin-bottom: 8px; }
.k-summary { font-size: 13px; color: var(--text-soft); line-height: 1.7; flex: 1; }
.k-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }
.k-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.k-tags span { font-size: 11.5px; color: var(--primary); background: var(--primary-soft); padding: 2px 8px; border-radius: 12px; }
.k-views { font-size: 11.5px; color: var(--text-soft); }

.empty { text-align: center; color: var(--text-soft); padding: 70px 0 30px; font-size: 14px; }
.e-ico { font-size: 30px; display: block; margin-bottom: 10px; opacity: .6; }

.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 24px; }
.pager button { border: 1px solid #e6dff5; background: #fff; border-radius: 8px; padding: 7px 14px; font-size: 13px; }
.pager button:disabled { opacity: .4; }
.pager span { font-size: 12.5px; color: var(--text-soft); }

.note { max-width: 1100px; margin: 22px auto 0; padding: 0 20px; }
.note > div, .note { font-size: 12.5px; color: var(--text-soft); background: #fff; border: 1px dashed #f0cdd4; border-radius: 12px; padding: 11px 14px; line-height: 1.7; }
.note b { color: #d9536b; }
</style>