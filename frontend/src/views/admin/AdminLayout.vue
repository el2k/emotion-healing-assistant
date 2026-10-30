<template>
  <div class="adm">
    <!-- 侧边目录 -->
    <aside class="side">
      <div class="brand">
        <div class="logo">☾</div>
        <div class="brand-txt">
          <b>治愈助手</b>
          <small>Admin Console</small>
        </div>
      </div>

      <div class="nav-scroll">
        <template v-for="g in nav" :key="g.label">
          <div class="nav-label">{{ g.label }}</div>
          <router-link v-for="it in g.items" :key="it.path" :to="it.path"
                       class="nav-item" :class="{ active: route.path === it.path }">
            <span class="nav-ico"><AdmIcon :name="it.icon" :size="17" /></span>
            <span class="nav-txt">{{ it.name }}</span>
            <span class="nav-dot"></span>
          </router-link>
        </template>
      </div>

      <div class="side-foot">
        <router-link to="/" class="back-chat">
          <AdmIcon name="arrow-left" :size="15" /><span>返回聊天前台</span>
        </router-link>
        <div class="me">
          <div class="me-ava">{{ (auth.nickname || '管')[0] }}</div>
          <div class="me-meta">
            <b>{{ auth.nickname || '管理员' }}</b>
            <small>超级管理员</small>
          </div>
          <button class="me-out" title="退出登录" @click="logout">⏻</button>
        </div>
      </div>
    </aside>

    <!-- 右侧 -->
    <div class="main">
      <header class="top">
        <div class="crumb">
          <span class="root">管理平台</span>
          <span class="sep">/</span>
          <span class="cur">{{ route.meta.title || '数据看板' }}</span>
        </div>
        <div class="top-right">
          <span class="llm" :class="{ on: llm.enabled }">
            <i></i>{{ llm.enabled ? 'AI 深度模式' : '本地规则引擎' }}
          </span>
          <router-link to="/" class="ghost-btn">前台预览</router-link>
        </div>
      </header>

      <main class="body">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { api } from '../../api'
import AdmIcon from '../../components/AdmIcon.vue'
import '../../assets/admin.css'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const llm = reactive({ enabled: false })

const nav = [
  {
    label: '总览',
    items: [{ name: '数据看板', path: '/admin/dashboard', icon: 'grid' }],
  },
  {
    label: '用户与情绪',
    items: [
      { name: '用户管理', path: '/admin/users', icon: 'users' },
      { name: '情绪分析', path: '/admin/emotions', icon: 'heart' },
    ],
  },
  {
    label: '内容与角色',
    items: [
      { name: '角色运营', path: '/admin/personas', icon: 'masks' },
      { name: '社区审核', path: '/admin/forum', icon: 'message' },
      { name: '会话抽查', path: '/admin/sessions', icon: 'layers' },
    ],
  },
  {
    label: '系统',
    items: [{ name: '系统信息', path: '/admin/system', icon: 'sliders' }],
  },
]

function logout() {
  if (!confirm('确定退出管理平台吗？')) return
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    const { data } = await api.get('/admin/system')
    llm.enabled = !!data.llm?.enabled
  } catch (e) { /* 忽略 */ }
})
</script>

<style scoped>
.adm { display: flex; min-height: 100vh; background: #f6f4fb; }
.side {
  width: 228px; flex: none; background: linear-gradient(180deg, #241f38 0%, #1c182d 100%);
  color: #cfc9e6; display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh;
}
.brand { display: flex; align-items: center; gap: 10px; padding: 20px 18px 16px; }
.logo {
  width: 34px; height: 34px; border-radius: 10px; flex: none;
  background: linear-gradient(135deg, #8f7ee8, #f59fb0); color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 18px;
  box-shadow: 0 6px 16px rgba(143, 126, 232, .35);
}
.brand-txt b { display: block; color: #fff; font-size: 15px; letter-spacing: .5px; }
.brand-txt small { font-size: 10.5px; color: #8d85ab; letter-spacing: 1.2px; text-transform: uppercase; }

.nav-scroll { flex: 1; overflow-y: auto; padding: 4px 10px 10px; }
.nav-label {
  font-size: 10.5px; color: #7d759e; letter-spacing: 1px;
  padding: 14px 10px 6px; text-transform: uppercase;
}
.nav-item {
  position: relative; display: flex; align-items: center; gap: 10px;
  padding: 9px 10px; border-radius: 9px; color: #bdb6d6; font-size: 13.5px;
  margin-bottom: 2px; transition: all .16s;
}
.nav-item:hover { background: rgba(255, 255, 255, .06); color: #fff; }
.nav-item.active { background: rgba(143, 126, 232, .18); color: #fff; }
.nav-item.active .nav-ico { color: #b9aaff; }
.nav-item.active .nav-dot {
  position: absolute; right: 9px; width: 5px; height: 5px; border-radius: 50%;
  background: #b9aaff; box-shadow: 0 0 8px #b9aaff;
}
.nav-ico { display: flex; color: #8f86b3; }

.side-foot { padding: 12px 12px 16px; border-top: 1px solid rgba(255, 255, 255, .06); }
.back-chat {
  display: flex; align-items: center; gap: 8px; font-size: 12.5px;
  color: #a79fc4; padding: 7px 8px; border-radius: 8px; margin-bottom: 8px;
}
.back-chat:hover { background: rgba(255, 255, 255, .06); color: #fff; }
.me { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 10px; background: rgba(255,255,255,.05); }
.me-ava {
  width: 32px; height: 32px; border-radius: 50%; flex: none;
  background: linear-gradient(135deg, #8f7ee8, #f59fb0); color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600;
}
.me-meta { flex: 1; min-width: 0; }
.me-meta b { display: block; color: #fff; font-size: 13px; }
.me-meta small { font-size: 11px; color: #8d85ab; }
.me-out { border: none; background: transparent; color: #8d85ab; font-size: 15px; padding: 4px; border-radius: 6px; }
.me-out:hover { color: #ff9fb0; background: rgba(255, 255, 255, .06); }

.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.top {
  height: 58px; flex: none; background: rgba(255, 255, 255, .86); backdrop-filter: blur(10px);
  border-bottom: 1px solid #efeaf8; display: flex; align-items: center;
  justify-content: space-between; padding: 0 26px; position: sticky; top: 0; z-index: 20;
}
.crumb { font-size: 13px; display: flex; align-items: center; gap: 8px; }
.crumb .root { color: var(--text-soft); }
.crumb .sep { color: #cfc7e4; }
.crumb .cur { font-weight: 600; }
.top-right { display: flex; align-items: center; gap: 12px; }
.llm { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #8b869b; background: #f5f2fc; padding: 5px 11px; border-radius: 20px; }
.llm i { width: 6px; height: 6px; border-radius: 50%; background: #b9b3c9; }
.llm.on { color: #2f9e6b; background: #e9f8ef; }
.llm.on i { background: #34b47a; box-shadow: 0 0 6px #34b47a; }
.ghost-btn { font-size: 12.5px; padding: 6px 12px; border: 1px solid #e6dff5; border-radius: 8px; color: var(--text); }
.ghost-btn:hover { border-color: var(--primary); color: var(--primary); }

.body { padding: 22px 26px 34px; flex: 1; }

@media (max-width: 900px) {
  .side { width: 64px; }
  .brand-txt, .nav-txt, .nav-label, .back-chat span, .me-meta { display: none; }
  .brand { justify-content: center; padding: 16px 8px; }
  .nav-item { justify-content: center; }
  .nav-item.active .nav-dot { display: none; }
  .me { justify-content: center; background: transparent; }
  .me-out { display: none; }
}
</style>