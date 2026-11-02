<template>
  <div class="forum-page">
    <header class="topbar">
      <div class="tb-left">
        <router-link to="/" class="back">← 返回聊天</router-link>
        <span class="tb-title">🌱 正能量社区</span>
      </div>
      <button class="publish-btn" @click="router.push('/forum/new')">✏️ 发布文章</button>
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

    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const posts = ref([])
const tags = ref([])
const q = ref('')
const activeTag = ref('')
const toastMsg = ref('')
let toastTimer = null

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

async function toggleLike(p) {
  const { data } = await api.post(`/forum/posts/${p.id}/like`)
  p.liked = data.liked
  p.like_count = data.like_count
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

.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>