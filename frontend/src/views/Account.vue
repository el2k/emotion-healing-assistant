<template>
  <div class="account-page">
    <header class="topbar">
      <router-link to="/" class="back">← 返回聊天</router-link>
      <span class="tb-title">个人信息</span>
    </header>

    <div class="container" v-if="info">
      <!-- 个人信息卡 -->
      <div class="card profile-card">
        <div class="avatar-wrap" @click="pickAvatar" title="点击更换头像">
          <img v-if="isImg(info.avatar)" :src="info.avatar" class="avatar-img" />
          <div v-else class="avatar">{{ info.avatar || info.nickname?.[0] || '友' }}</div>
          <span class="avatar-edit">📷</span>
        </div>
        <div class="who">
          <h2>{{ info.nickname }}</h2>
          <div class="meta">
            <span class="pill" :class="info.role === 'admin' ? 'admin' : 'user'">
              {{ info.role === 'admin' ? '管理员' : '普通用户' }}
            </span>
            <span class="phone">📱 {{ info.phone }}</span>
            <span class="joined">加入于 {{ fmtDate(info.created_at) }}</span>
          </div>
        </div>
        <input ref="avatarInput" type="file" accept="image/*" hidden @change="onPickAvatar" />
      </div>

      <!-- 头像设置 -->
      <div class="card block">
        <h3>更换头像</h3>
        <div class="avatar-options">
          <button class="up-btn" @click="pickAvatar">📁 上传图片</button>
          <span class="or">或选一个 emoji：</span>
          <button v-for="e in emojiList" :key="e" class="emoji-btn"
                  :class="{ active: info.avatar === e }" @click="saveAvatar(e)">{{ e }}</button>
          <button class="clear-btn" @click="saveAvatar('')">恢复默认</button>
        </div>
      </div>

      <!-- 使用统计 -->
      <div class="stats">
        <div class="card stat"><div class="num">{{ info.stats.sessions }}</div><div class="lbl">对话数</div></div>
        <div class="card stat"><div class="num">{{ info.stats.messages }}</div><div class="lbl">消息数</div></div>
        <div class="card stat"><div class="num">{{ info.stats.emotions }}</div><div class="lbl">情绪记录</div></div>
        <div class="card stat"><div class="num">{{ info.stats.days_active }}</div><div class="lbl">活跃天数</div></div>
      </div>

      <div class="two-col">
        <!-- 修改昵称 -->
        <div class="card block">
          <h3>修改昵称</h3>
          <div class="field">
            <input v-model="nickname" maxlength="50" placeholder="输入新的昵称" />
            <button class="btn" :disabled="savingNick" @click="saveNickname">
              {{ savingNick ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>

        <!-- 修改手机号 -->
        <div class="card block">
          <h3>修改手机号</h3>
          <div class="field col">
            <input v-model="phone" maxlength="20" placeholder="新的手机号" />
            <input v-model="phonePwd" type="password" placeholder="输入登录密码确认" />
            <button class="btn" :disabled="savingPhone" @click="savePhone">
              {{ savingPhone ? '保存中…' : '更新手机号' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 修改密码 -->
      <div class="card block">
        <h3>修改密码</h3>
        <div class="field three">
          <input v-model="pwd.old" type="password" placeholder="原密码" />
          <input v-model="pwd.new" type="password" placeholder="新密码（至少6位）" />
          <button class="btn" :disabled="savingPwd" @click="savePassword">
            {{ savingPwd ? '保存中…' : '更新密码' }}
          </button>
        </div>
      </div>

      <!-- 快捷入口 -->
      <div class="card block links">
        <router-link to="/profile" class="quick">📊 我的情绪档案</router-link>
        <router-link v-if="info.role === 'admin'" to="/admin" class="quick">🛠 进入管理平台</router-link>
      </div>

      <!-- 退出当前用户 -->
      <div class="card block danger-zone">
        <div>
          <h3>退出当前用户</h3>
          <p class="dz-tip">退出后需要重新登录才能继续使用。</p>
        </div>
        <button class="logout-btn" @click="doLogout">退出登录</button>
      </div>
    </div>

    <div v-else class="loading">加载中…</div>

    <transition name="fade">
      <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const router = useRouter()
const auth = useAuthStore()
const info = ref(null)
const nickname = ref('')
const phone = ref('')
const phonePwd = ref('')
const pwd = reactive({ old: '', new: '' })
const avatarInput = ref(null)
const savingNick = ref(false)
const savingPhone = ref(false)
const savingPwd = ref(false)
const toastMsg = ref('')
let toastTimer = null

const emojiList = ['🌙', '🌿', '🌸', '🐳', '🐱', '🐰', '😊', '🍀', '⭐', '🦋']

function toast(msg) {
  toastMsg.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 2400)
}
function fmtDate(s) { return s ? new Date(s).toLocaleDateString() : '-' }
function isImg(v) { return !!v && (v.startsWith('/uploads/') || v.startsWith('http') || v.startsWith('data:')) }

async function load() {
  const { data } = await api.get('/auth/me')
  info.value = data
  nickname.value = data.nickname
  phone.value = data.phone
  auth.setProfile({ nickname: data.nickname, avatar: data.avatar, phone: data.phone })
}

function pickAvatar() { avatarInput.value?.click() }

async function onPickAvatar(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await api.post('/chat/upload', fd)
    await saveAvatar(data.url)
  } catch (err) { toast('头像上传失败') }
}

async function saveAvatar(val) {
  try {
    const { data } = await api.put('/auth/me', { avatar: val })
    info.value.avatar = data.avatar
    auth.setProfile({ avatar: data.avatar })
    toast(val ? '头像已更新' : '已恢复默认头像')
  } catch (e) {
    toast(e.response?.data?.detail || '保存失败')
  }
}

async function saveNickname() {
  if (!nickname.value.trim()) { toast('昵称不能为空'); return }
  savingNick.value = true
  try {
    const { data } = await api.put('/auth/me', { nickname: nickname.value.trim() })
    info.value.nickname = data.nickname
    auth.setProfile({ nickname: data.nickname })
    toast('昵称已更新')
  } catch (e) {
    toast(e.response?.data?.detail || '保存失败')
  } finally {
    savingNick.value = false
  }
}

async function savePhone() {
  if (!phone.value.trim()) { toast('请填写手机号'); return }
  if (!phonePwd.value) { toast('请输入登录密码确认'); return }
  savingPhone.value = true
  try {
    const { data } = await api.put('/auth/me', { phone: phone.value.trim(), old_password: phonePwd.value })
    info.value.phone = data.phone
    phone.value = data.phone
    phonePwd.value = ''
    auth.setProfile({ phone: data.phone })
    toast('手机号已更新')
  } catch (e) {
    toast(e.response?.data?.detail || '修改失败')
  } finally {
    savingPhone.value = false
  }
}

async function savePassword() {
  if (!pwd.old || !pwd.new) { toast('请填写原密码和新密码'); return }
  if (pwd.new.length < 6) { toast('新密码至少 6 位'); return }
  savingPwd.value = true
  try {
    await api.put('/auth/me', { old_password: pwd.old, new_password: pwd.new })
    pwd.old = ''; pwd.new = ''
    toast('密码已更新，请牢记新密码')
  } catch (e) {
    toast(e.response?.data?.detail || '修改失败')
  } finally {
    savingPwd.value = false
  }
}

async function doLogout() {
  if (!confirm('确定要退出当前用户吗？')) return
  try { await api.post('/auth/logout') } catch (e) { /* 忽略 */ }
  auth.logout()
  router.push('/login')
}

onMounted(() => { load() })
</script>

<style scoped>
.account-page { min-height: 100vh; background: var(--bg); }
.topbar { display: flex; align-items: center; gap: 16px; padding: 14px 28px; background: #fff; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.back { font-size: 14px; }
.tb-title { font-size: 17px; font-weight: 700; color: var(--primary); }

.container { max-width: 860px; margin: 22px auto; padding: 0 20px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); }

.profile-card { display: flex; align-items: center; gap: 20px; padding: 26px 28px; }
.avatar-wrap { position: relative; width: 72px; height: 72px; flex-shrink: 0; cursor: pointer; }
.avatar { width: 72px; height: 72px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--accent)); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 30px; font-weight: 700; }
.avatar-img { width: 72px; height: 72px; border-radius: 50%; object-fit: cover; }
.avatar-edit { position: absolute; right: -2px; bottom: -2px; width: 24px; height: 24px; border-radius: 50%; background: #fff; border: 1px solid var(--border); font-size: 12px; display: flex; align-items: center; justify-content: center; }
.who h2 { font-size: 22px; margin-bottom: 8px; }
.meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 13px; color: var(--text-soft); }
.pill { padding: 2px 10px; border-radius: 10px; font-size: 12px; }
.pill.admin { background: #efeaff; color: var(--primary); }
.pill.user { background: #e7f7ec; color: #2f9e6b; }

.avatar-options { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.up-btn { border: 1px solid var(--primary); background: var(--primary-soft); color: var(--primary); border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer; }
.or { font-size: 13px; color: var(--text-soft); }
.emoji-btn { width: 34px; height: 34px; border-radius: 8px; border: 1px solid var(--border); background: #fbfaff; font-size: 18px; cursor: pointer; }
.emoji-btn.active { border-color: var(--primary); background: var(--primary-soft); }
.clear-btn { border: none; background: transparent; color: var(--text-soft); font-size: 12px; cursor: pointer; margin-left: 4px; }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }
.stat { padding: 16px; text-align: center; }
.stat .num { font-size: 22px; font-weight: 700; color: var(--primary); }
.stat .lbl { font-size: 12px; color: var(--text-soft); margin-top: 4px; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.block { padding: 18px 20px; margin-top: 16px; }
.block h3 { font-size: 15px; margin-bottom: 14px; }
.field { display: flex; gap: 10px; }
.field.col { flex-direction: column; }
.field.three { display: grid; grid-template-columns: 1fr 1fr auto; }
.field input { flex: 1; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; font-size: 14px; background: #fbfaff; }
.field input:focus { outline: none; border-color: var(--primary); }
.btn { border: none; background: var(--primary); color: #fff; border-radius: 10px; padding: 10px 18px; font-size: 14px; white-space: nowrap; }
.btn:disabled { opacity: .6; }

.links { display: flex; gap: 12px; }
.quick { flex: 1; text-align: center; padding: 12px; border-radius: 10px; background: #faf8ff; font-size: 14px; }
.quick:hover { background: var(--primary-soft); }

.danger-zone { display: flex; align-items: center; justify-content: space-between; }
.dz-tip { font-size: 13px; color: var(--text-soft); }
.logout-btn { border: 1px solid #f3c2cb; background: #fdeef0; color: #e0556d; border-radius: 10px; padding: 10px 22px; font-size: 14px; transition: all .15s; }
.logout-btn:hover { background: #e0556d; color: #fff; border-color: #e0556d; }

.loading { text-align: center; color: var(--text-soft); padding: 80px 0; }
.toast { position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(58,53,69,.92); color: #fff; padding: 10px 18px; border-radius: 20px; font-size: 13px; z-index: 200; }
.fade-enter-active, .fade-leave-active { transition: opacity .25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 720px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .two-col { grid-template-columns: 1fr; }
  .field.three { grid-template-columns: 1fr; }
  .danger-zone { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>