<template>
  <router-view />
  <Pet v-if="showPet" />
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Pet from './components/Pet.vue'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const auth = useAuthStore()
// 管理平台属于工作场景，隐藏桌面宠物，避免遮挡表格与图表
const showPet = computed(() =>
  route.name !== 'login' && !String(route.path).startsWith('/admin'))

// ---------- 路由级 favicon + 标题（每个页面都有自己的图标） ----------
const ROUTE_META = {
  login:              { emoji: '🌙', title: '登录 · 治愈小窝' },
  chat:               { emoji: '💬', title: '聊天 · 治愈小窝' },
  profile:            { emoji: '📊', title: '情绪档案 · 治愈小窝' },
  account:            { emoji: '👤', title: '个人信息 · 治愈小窝' },
  forum:              { emoji: '🌱', title: '正能量社区 · 治愈小窝' },
  'post-editor':      { emoji: '✏️', title: '写文章 · 治愈小窝' },
  post:               { emoji: '🌱', title: '帖子 · 治愈小窝' },
  personas:           { emoji: '🎭', title: '角色广场 · 治愈小窝' },
  vrm:                { emoji: '🎀', title: '3D 陪伴 · 柚子' },
  knowledge:          { emoji: '📖', title: '情绪知识库 · 治愈小窝' },
  'knowledge-detail': { emoji: '📖', title: '知识文章 · 治愈小窝' },
  heal:               { emoji: '🩺', title: '心理疗愈室 · 治愈小窝' },
  fortune:            { emoji: '🔮', title: '测测 · 八字紫微每日运势' },
  'admin-dashboard':  { emoji: '🛠', title: '数据看板 · 管理平台' },
  'admin-users':      { emoji: '👥', title: '用户管理 · 管理平台' },
  'admin-emotions':   { emoji: '💗', title: '情绪分析 · 管理平台' },
  'admin-heal':       { emoji: '🩺', title: '疗愈室数据 · 管理平台' },
  'admin-personas':   { emoji: '🎭', title: '角色运营 · 管理平台' },
  'admin-forum':      { emoji: '🧹', title: '社区审核 · 管理平台' },
  'admin-sessions':   { emoji: '🗂', title: '会话抽查 · 管理平台' },
  'admin-observability': { emoji: '📡', title: '可观测性 · 管理平台' },
  'admin-system':     { emoji: '⚙️', title: '系统信息 · 管理平台' },
}

// Canvas 画 emoji → 动态 favicon（无需图片文件）
function setFavicon(emoji) {
  try {
    let link = document.querySelector('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    const cv = document.createElement('canvas')
    cv.width = cv.height = 64
    const ctx = cv.getContext('2d')
    if (ctx) {
      ctx.clearRect(0, 0, 64, 64)
      ctx.font = '52px "Segoe UI Emoji", "Apple Color Emoji", sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(emoji, 32, 36)
      const url = cv.toDataURL('image/png')
      link.type = 'image/png'
      link.href = url
    }
  } catch (e) { /* 忽略 canvas 不支持 */ }
}

const APP_DEFAULT = { emoji: '🌙', title: '情绪感知治愈助手' }
let currentMeta = { ...APP_DEFAULT }

// ---------- 切页（离开浏览器标签页）小互动 ----------
const LEAVE_TITLES = [
  '🌙 你走了…小窝想你了',
  '💤 这里好安静呀',
  '🌱 记得回来找我聊天哦',
  '🫧 我在这里等风也等你',
]
let titleTimer = null
let leaveIdx = 0

function onLeave() {
  if (titleTimer) return
  const tick = () => { document.title = LEAVE_TITLES[leaveIdx++ % LEAVE_TITLES.length] }
  tick()
  setFavicon('🌙')
  titleTimer = setInterval(tick, 1600)
}

function onBack() {
  if (titleTimer) {
    clearInterval(titleTimer)
    titleTimer = null
  }
  document.title = currentMeta.title
  setFavicon(currentMeta.emoji)
}

onMounted(() => {
  if (auth.isLogin) auth.fetchProfile()

  const onVisibility = () => (document.hidden ? onLeave() : onBack())
  document.addEventListener('visibilitychange', onVisibility)
  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibility)
    if (titleTimer) clearInterval(titleTimer)
  })

  // 初始应用一次
  applyRouteMeta(route.name)
})

function applyRouteMeta(name) {
  const meta = ROUTE_META[name] || APP_DEFAULT
  currentMeta = meta
  document.title = meta.title
  setFavicon(meta.emoji)
}

// 路由切换 → 更新图标与标题
watch(() => route.name, (name) => {
  if (titleTimer) onBack()  // 正在切页互动时先复位
  applyRouteMeta(name)
})
</script>