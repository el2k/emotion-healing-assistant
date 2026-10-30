<template>
  <div class="detail-page">
    <header class="topbar">
      <router-link to="/forum" class="back">← 返回社区</router-link>
    </header>

    <div class="container" v-if="post">
      <article class="card article">
        <div class="art-head">
          <span class="avatar">{{ post.author?.[0] || '友' }}</span>
          <div>
            <div class="art-author">{{ post.author }}</div>
            <div class="art-time">{{ fmt(post.created_at) }}</div>
          </div>
          <button v-if="post.user_id === auth.user_id || auth.isAdmin"
                  class="del-btn" @click="removePost">删除</button>
        </div>
        <h1 class="art-title">{{ post.title || '无标题' }}</h1>
        <div class="art-blocks">
          <template v-for="(b, i) in (post.blocks && post.blocks.length ? post.blocks : legacyBlocks)" :key="i">
            <p v-if="b.type === 'text'" class="art-para">{{ b.text }}</p>
            <video v-else-if="b.type === 'video'" :src="b.url" controls class="art-video"></video>
            <img v-else :src="b.url" class="art-img" @click="preview = b.url" />
          </template>
        </div>
        <div class="art-tags">
          <span v-for="t in post.tags" :key="t" class="art-tag">#{{ t }}</span>
        </div>
        <div class="art-actions">
          <button class="like-btn" :class="{ liked: post.liked }" @click="toggleLike">
            {{ post.liked ? '❤️ 已赞' : '🤍 点赞' }} · {{ post.like_count }}
          </button>
          <span class="c-count">💬 {{ post.comments.length }} 条评论</span>
        </div>
      </article>

      <div class="card comment-box">
        <h3>评论</h3>
        <div class="add-comment">
          <textarea v-model="commentText" rows="2" placeholder="说点温暖的话吧…"
                    @keydown.enter.exact.prevent="addComment"></textarea>
          <button class="btn" :disabled="!commentText.trim()" @click="addComment">发送</button>
        </div>
        <div v-if="post.comments.length" class="comments">
          <div v-for="c in post.comments" :key="c.id" class="comment">
            <span class="c-avatar">{{ c.author?.[0] || '友' }}</span>
            <div class="c-main">
              <div class="c-head">
                <span class="c-author">{{ c.author }}</span>
                <span class="c-time">{{ fmt(c.created_at) }}</span>
                <button v-if="c.mine || auth.isAdmin" class="c-del" @click="removeComment(c)">删除</button>
              </div>
              <div class="c-text">{{ c.content }}</div>
            </div>
          </div>
        </div>
        <p v-else class="no-comment">还没有评论，来抢沙发～</p>
      </div>
    </div>
    <div v-else class="loading">加载中…</div>

    <div v-if="preview" class="img-modal" @click="preview = ''"><img :src="preview" /></div>
    <transition name="fade"><div v-if="toastMsg" class="toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const post = ref(null)
const commentText = ref('')
const preview = ref('')
const toastMsg = ref('')
const legacyBlocks = computed(() => {
  const p = post.value
  if (!p) return []
  const arr = []
  if (p.content) arr.push({ type: 'text', text: p.content })
  for (const u of p.images || []) arr.push(isVideo(u) ? { type: 'video', url: u } : { type: 'image', url: u })
  return arr
})
let toastTimer = null
function toast(m) { toastMsg.value = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => toastMsg.value = '', 2400) }
function fmt(s) { return s ? new Date(s).toLocaleString('zh-CN') : '' }
function isVideo(url) { return /\.(mp4|webm|mov)(\?|$)/i.test(url || '') }

async function load() {
  const { data } = await api.get(`/forum/posts/${route.params.id}`)
  post.value = data
}

async function toggleLike() {
  const { data } = await api.post(`/forum/posts/${post.value.id}/like`)
  post.value.liked = data.liked
  post.value.like_count = data.like_count
}

async function addComment() {
  const content = commentText.value.trim()
  if (!content) return
  const { data } = await api.post(`/forum/posts/${post.value.id}/comments`, { content })
  post.value.comments.push({ ...data, mine: true })
  commentText.value = ''
}

async function removeComment(c) {
  if (!confirm('删除这条评论？')) return
  await api.delete(`/forum/comments/${c.id}`)
  post.value.comments = post.value.comments.filter(x => x.id !== c.id)
}

async function removePost() {
  if (!confirm('删除这篇文章？')) return
  await api.delete(`/forum/posts/${post.value.id}`)
  router.push('/forum')
}

onMounted(() => { load() })
</script>

<style scoped>
.detail-page { min-height: 100vh; background: var(--bg); }
.topbar { padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.container { max-width: 760px; margin: 22px auto; padding: 0 20px; }
.card { background: #fff; border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); }
.article { padding: 24px 26px; }
.art-head { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 600; }
.art-author { font-size: 14px; font-weight: 600; }
.art-time { font-size: 12px; color: var(--text-soft); }
.del-btn { margin-left: auto; border: 1px solid #f3c2cb; background: #fdeef0; color: #e0556d; border-radius: 8px; padding: 5px 12px; font-size: 12px; cursor: pointer; }
.art-title { font-size: 22px; margin-bottom: 14px; }
.art-blocks { margin: 8px 0 4px; }
.art-para { font-size: 15px; line-height: 1.95; white-space: pre-wrap; color: var(--text); margin-bottom: 14px; }
.art-img { display: block; width: 100%; border-radius: 12px; margin-bottom: 14px; cursor: zoom-in; }
.art-video { display: block; width: 100%; border-radius: 12px; margin-bottom: 14px; background: #000; }
.art-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.art-tag { font-size: 13px; color: var(--primary); }
.art-actions { display: flex; align-items: center; gap: 18px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border); }
.like-btn { border: 1px solid var(--border); background: #fbfaff; border-radius: 20px; padding: 8px 18px; font-size: 14px; cursor: pointer; }
.like-btn.liked { background: #fdeef0; border-color: #f3c2cb; color: #e0556d; }
.c-count { font-size: 13px; color: var(--text-soft); }

.comment-box { padding: 20px 24px; margin-top: 16px; }
.comment-box h3 { font-size: 15px; margin-bottom: 14px; }
.add-comment { display: flex; gap: 10px; margin-bottom: 16px; }
.add-comment textarea { flex: 1; border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; font-size: 14px; resize: none; }
.add-comment textarea:focus { outline: none; border-color: var(--primary); }
.btn { border: none; background: var(--primary); color: #fff; border-radius: 10px; padding: 0 20px; font-size: 14px; }
.btn:disabled { opacity: .6; }
.comments { display: flex; flex-direction: column; gap: 14px; }
.comment { display: flex; gap: 10px; }
.c-avatar { width: 32px; height: 32px; border-radius: 50%; background: #efeaff; color: var(--primary); display: flex; align-items: center; justify-content: center; font-weight: 600; flex-shrink: 0; }
.c-main { flex: 1; }
.c-head { display: flex; align-items: center; gap: 10px; }
.c-author { font-size: 13px; font-weight: 600; }
.c-time { font-size: 12px; color: var(--text-soft); }
.c-del { border: none; background: transparent; color: var(--text-soft); font-size: 12px; cursor: pointer; margin-left: auto; }
.c-del:hover { color: #e0556d; }
.c-text { font-size: 14px; margin-top: 3px; }
.no-comment { color: var(--text-soft); font-size: 14px; padding: 12px 0; }
.loading { text-align: center; color: var(--text-soft); padding: 80px 0; }
.img-modal { position: fixed; inset: 0; background: rgba(30,25,45,.8); display: flex; align-items: center; justify-content: center; z-index: 100; cursor: zoom-out; }
.img-modal img { max-width: 90%; max-height: 90%; border-radius: 12px; }
.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>