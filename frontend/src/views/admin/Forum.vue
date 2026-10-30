<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>社区审核</h1>
        <p>正能量社区的帖子与评论内容巡检，违规内容可一键下架</p>
      </div>
      <div class="a-head-actions">
        <div class="a-search"><input v-model="q" class="a-input" placeholder="搜索标题 / 正文 / 评论" @keyup.enter="search" /></div>
        <button class="a-btn ghost" @click="search">搜索</button>
      </div>
    </div>

    <div class="a-card">
      <div class="a-card-hd">
        <div class="tabs">
          <button class="tab" :class="{ on: tab === 'posts' }" @click="switchTab('posts')">
            帖子 <span>{{ postTotal }}</span>
          </button>
          <button class="tab" :class="{ on: tab === 'comments' }" @click="switchTab('comments')">
            评论 <span>{{ commentTotal }}</span>
          </button>
        </div>
        <span class="a-tag">仅管理员可见</span>
      </div>

      <!-- 帖子 -->
      <div v-if="tab === 'posts'" class="a-card-bd" style="padding-top: 10px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead>
              <tr><th>内容</th><th>作者</th><th>互动</th><th>发布时间</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="p in posts" :key="p.id">
                <td style="max-width: 520px">
                  <div class="post-cell">
                    <img v-if="p.cover" :src="p.cover" class="post-thumb" alt="" />
                    <div v-else class="post-thumb empty-thumb">文</div>
                    <div class="post-meta">
                      <div class="cell-main">{{ p.title }}</div>
                      <div class="cell-sub">{{ p.excerpt || '（无正文）' }}</div>
                      <div v-if="p.tags" class="tags"><span v-for="t in p.tags.split(',').filter(Boolean)" :key="t" class="a-tag">{{ t }}</span></div>
                    </div>
                  </div>
                </td>
                <td><div class="cell-main">{{ p.author }}</div></td>
                <td class="cell-sub">♥ {{ p.likes }} · 💬 {{ p.comments }}</td>
                <td class="cell-sub">{{ fmtTime(p.created_at) }}</td>
                <td class="actions"><button class="a-btn mini danger" @click="askDelete('post', p)">下架</button></td>
              </tr>
              <tr v-if="!posts.length"><td colspan="5"><div class="a-empty"><span class="e-ico">📭</span>暂无帖子</div></td></tr>
            </tbody>
          </table>
        </div>
        <div class="a-pager">
          <span class="pg-info">共 {{ postTotal }} 条 · 第 {{ postPage }} 页</span>
          <button :disabled="postPage <= 1" @click="goPost(postPage - 1)">上一页</button>
          <button :disabled="posts.length < 20" @click="goPost(postPage + 1)">下一页</button>
        </div>
      </div>

      <!-- 评论 -->
      <div v-else class="a-card-bd" style="padding-top: 10px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead><tr><th>评论内容</th><th>所属帖子</th><th>作者</th><th>时间</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="c in comments" :key="c.id">
                <td style="max-width: 460px"><div class="comment-text">{{ c.content }}</div></td>
                <td class="cell-sub">#{{ c.post_id }} {{ c.post_title }}</td>
                <td class="cell-main">{{ c.author }}</td>
                <td class="cell-sub">{{ fmtTime(c.created_at) }}</td>
                <td class="actions"><button class="a-btn mini danger" @click="askDelete('comment', c)">删除</button></td>
              </tr>
              <tr v-if="!comments.length"><td colspan="5"><div class="a-empty"><span class="e-ico">💬</span>暂无评论</div></td></tr>
            </tbody>
          </table>
        </div>
        <div class="a-pager">
          <span class="pg-info">共 {{ commentTotal }} 条 · 第 {{ commentPage }} 页</span>
          <button :disabled="commentPage <= 1" @click="goComment(commentPage - 1)">上一页</button>
          <button :disabled="comments.length < 20" @click="goComment(commentPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <div v-if="delTarget" class="a-modal-mask">
      <div class="a-modal">
        <h4>{{ delTarget.type === 'post' ? '下架帖子' : '删除评论' }}</h4>
        <p v-if="delTarget.type === 'post'">确定下架「{{ delTarget.item.title }}」吗？该帖子的点赞与评论会一并删除，且不可恢复。</p>
        <p v-else>确定删除这条评论吗？操作不可恢复。</p>
        <div class="a-modal-ft">
          <button class="a-btn ghost" @click="delTarget = null">取消</button>
          <button class="a-btn danger" @click="doDelete">确认{{ delTarget.type === 'post' ? '下架' : '删除' }}</button>
        </div>
      </div>
    </div>

    <transition name="fade"><div v-if="toastMsg" class="a-toast">{{ toastMsg }}</div></transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api'

const tab = ref('posts')
const q = ref('')
const posts = ref([])
const comments = ref([])
const postTotal = ref(0)
const commentTotal = ref(0)
const postPage = ref(1)
const commentPage = ref(1)
const delTarget = ref(null)
const toastMsg = ref('')

const fmtTime = (s) => (s ? new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')
function toast(m) { toastMsg.value = m; setTimeout(() => { toastMsg.value = '' }, 2200) }

async function loadPosts() {
  const { data } = await api.get('/admin/posts', { params: { q: q.value, page: postPage.value, page_size: 20 } })
  posts.value = data.items
  postTotal.value = data.total
}
async function loadComments() {
  const { data } = await api.get('/admin/comments', { params: { q: q.value, page: commentPage.value, page_size: 20 } })
  comments.value = data.items
  commentTotal.value = data.total
}
function switchTab(t) { tab.value = t; t === 'posts' ? loadPosts() : loadComments() }
function search() { postPage.value = 1; commentPage.value = 1; tab.value === 'posts' ? loadPosts() : loadComments() }
function goPost(p) { postPage.value = p; loadPosts() }
function goComment(p) { commentPage.value = p; loadComments() }

function askDelete(type, item) { delTarget.value = { type, item } }
async function doDelete() {
  const { type, item } = delTarget.value
  delTarget.value = null
  if (type === 'post') {
    await api.delete(`/admin/posts/${item.id}`)
    toast('帖子已下架')
    loadPosts()
  } else {
    await api.delete(`/admin/comments/${item.id}`)
    toast('评论已删除')
    loadComments()
  }
}

onMounted(loadPosts)
</script>

<style scoped>
.tabs { display: flex; gap: 6px; }
.tab {
  border: none; background: #f6f2fd; color: #7a7290; border-radius: 9px;
  padding: 7px 16px; font-size: 13px; font-weight: 500;
}
.tab.on { background: var(--primary); color: #fff; box-shadow: 0 4px 12px rgba(124,111,208,.25); }
.tab span { font-size: 11.5px; opacity: .8; margin-left: 4px; }
.post-cell { display: flex; gap: 10px; align-items: center; }
.post-thumb { width: 52px; height: 52px; border-radius: 9px; object-fit: cover; flex: none; background: #f3eefc; }
.post-thumb.empty-thumb { display: flex; align-items: center; justify-content: center; color: #b3a9d6; font-size: 14px; }
.post-meta { min-width: 0; }
.post-meta .cell-main, .post-meta .cell-sub { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tags { display: flex; gap: 4px; margin-top: 4px; flex-wrap: wrap; }
.comment-text { font-size: 12.5px; line-height: 1.6; color: #4a4360; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>