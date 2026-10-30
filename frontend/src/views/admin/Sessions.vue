<template>
  <div class="adm-page">
    <div class="a-head">
      <div>
        <h1>会话抽查</h1>
        <p>用于运营巡检的会话列表（不含消息正文，保护用户隐私）</p>
      </div>
      <div class="a-head-actions">
        <div class="a-search"><input v-model="q" class="a-input" placeholder="搜索会话标题 / 用户昵称" @keyup.enter="search" /></div>
        <button class="a-btn ghost" @click="search">搜索</button>
      </div>
    </div>

    <div class="a-card">
      <div class="a-card-hd">
        <h3>全部会话</h3>
        <span class="a-tag">{{ total }} 条</span>
      </div>
      <div class="a-card-bd" style="padding-top: 10px">
        <div class="a-table-wrap">
          <table class="a-table">
            <thead><tr><th>会话</th><th>角色</th><th>用户</th><th>消息数</th><th>创建时间</th><th>最后更新</th></tr></thead>
            <tbody>
              <tr v-for="s in items" :key="s.id">
                <td>
                  <div class="cell-main">#{{ s.id }} {{ s.title || '新的对话' }}</div>
                  <div class="cell-sub">会话 ID {{ s.id }}</div>
                </td>
                <td>
                  <div class="persona-cell">
                    <img v-if="s.persona_avatar" :src="s.persona_avatar" class="persona-ava" alt="" />
                    <span>{{ s.persona_name }}</span>
                  </div>
                </td>
                <td>
                  <div class="cell-main">{{ s.nickname }}</div>
                  <div class="cell-sub">UID {{ s.user_id }}</div>
                </td>
                <td><span class="msg-num">{{ s.messages }}</span></td>
                <td class="cell-sub">{{ fmtTime(s.created_at) }}</td>
                <td class="cell-sub">{{ fmtTime(s.updated_at) }}</td>
              </tr>
              <tr v-if="!items.length"><td colspan="6"><div class="a-empty"><span class="e-ico">💬</span>暂无会话</div></td></tr>
            </tbody>
          </table>
        </div>
        <div class="a-pager">
          <span class="pg-info">第 {{ page }} / {{ pages }} 页</span>
          <button :disabled="page <= 1" @click="go(page - 1)">上一页</button>
          <button :disabled="page >= pages" @click="go(page + 1)">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const q = ref('')
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const fmtTime = (s) => (s ? new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—')

async function load() {
  const { data } = await api.get('/admin/sessions', { params: { q: q.value, page: page.value, page_size: pageSize } })
  items.value = data.items
  total.value = data.total
}
function search() { page.value = 1; load() }
function go(p) { page.value = p; load() }
onMounted(load)
</script>

<style scoped>
.persona-cell { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.persona-ava { width: 28px; height: 28px; border-radius: 8px; object-fit: cover; background: #f3eefc; }
.msg-num { font-weight: 700; color: #5f54a3; }
</style>