<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="brand">
        <div class="logo">☾</div>
        <h1>情绪感知治愈助手</h1>
        <p>在这里，每一份情绪都被温柔接住。</p>
      </div>

      <div class="form-wrap">
        <div class="tabs">
          <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
          <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
        </div>

        <form @submit.prevent="submit">
          <div class="field">
            <label>手机号</label>
            <input v-model="form.phone" placeholder="请输入手机号" />
          </div>
          <div v-if="mode === 'register'" class="field">
            <label>昵称</label>
            <input v-model="form.nickname" placeholder="怎么称呼你？" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="form.password" type="password" placeholder="请输入密码" />
          </div>

          <p v-if="error" class="error">{{ error }}</p>

          <button class="primary-btn" :disabled="loading">
            {{ loading ? '请稍候…' : (mode === 'login' ? '进入' : '创建账号') }}
          </button>
        </form>

        <p class="hint">
          <span v-if="mode === 'login'">还没有账号？去「注册」一个，即刻开始倾诉。</span>
          <span v-else>注册后即可开始，你的每一次倾诉都被认真对待。</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const mode = ref('login')
const loading = ref(false)
const error = ref('')
const form = reactive({ phone: '', nickname: '', password: '' })

async function submit() {
  error.value = ''
  if (!form.phone || !form.password) {
    error.value = '请填写手机号和密码'
    return
  }
  if (form.password.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.phone, form.password)
    } else {
      await auth.register({ phone: form.phone, password: form.password, nickname: form.nickname })
    }
    router.push(auth.isAdmin ? '/admin' : '/')
  } catch (e) {
    error.value = e.response?.data?.detail || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 20% 20%, #f3e8ff 0%, transparent 40%),
    radial-gradient(circle at 80% 80%, #ffe9ef 0%, transparent 40%),
    var(--bg);
  padding: 24px;
}
.login-card {
  width: 420px;
  max-width: 100%;
  padding: 36px 40px;
}
.brand { text-align: center; margin-bottom: 28px; }
.logo { font-size: 42px; }
.brand h1 { font-size: 22px; margin: 6px 0 4px; color: var(--primary); }
.brand p { color: var(--text-soft); font-size: 14px; }

.tabs { display: flex; gap: 8px; margin-bottom: 22px; }
.tabs button {
  flex: 1; padding: 9px 0; border: 1px solid var(--border);
  background: #fff; border-radius: 10px; color: var(--text-soft);
  font-size: 15px; transition: all .2s;
}
.tabs button.active { background: var(--primary); color: #fff; border-color: var(--primary); }

.field { margin-bottom: 16px; }
.field label { display: block; font-size: 13px; color: var(--text-soft); margin-bottom: 6px; }
.field input {
  width: 100%; padding: 11px 13px; border: 1px solid var(--border);
  border-radius: 10px; font-size: 15px; background: #fbfaff;
  transition: border-color .2s;
}
.field input:focus { outline: none; border-color: var(--primary); }

.primary-btn {
  width: 100%; padding: 12px; border: none; border-radius: 10px;
  background: var(--primary); color: #fff; font-size: 16px; margin-top: 6px;
  transition: opacity .2s;
}
.primary-btn:disabled { opacity: .6; cursor: not-allowed; }

.error { color: #e0556d; font-size: 13px; margin: 8px 0; }
.hint { text-align: center; color: var(--text-soft); font-size: 13px; margin-top: 18px; }
</style>