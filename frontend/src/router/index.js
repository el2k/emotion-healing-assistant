import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/', name: 'chat', component: () => import('../views/Chat.vue') },
  { path: '/profile', name: 'profile', component: () => import('../views/Emotion.vue') },
  { path: '/account', name: 'account', component: () => import('../views/Account.vue') },
  { path: '/forum', name: 'forum', component: () => import('../views/Forum.vue') },
  { path: '/forum/:id', name: 'post', component: () => import('../views/PostDetail.vue') },
  { path: '/personas', name: 'personas', component: () => import('../views/Personas.vue') },
  { path: '/vrm', name: 'vrm', component: () => import('../views/VrmChat.vue') },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { admin: true },
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', name: 'admin-dashboard', component: () => import('../views/admin/Dashboard.vue'), meta: { title: '数据看板' } },
      { path: 'users', name: 'admin-users', component: () => import('../views/admin/Users.vue'), meta: { title: '用户管理' } },
      { path: 'emotions', name: 'admin-emotions', component: () => import('../views/admin/Emotions.vue'), meta: { title: '情绪分析' } },
      { path: 'personas', name: 'admin-personas', component: () => import('../views/admin/Personas.vue'), meta: { title: '角色运营' } },
      { path: 'forum', name: 'admin-forum', component: () => import('../views/admin/Forum.vue'), meta: { title: '社区审核' } },
      { path: 'sessions', name: 'admin-sessions', component: () => import('../views/admin/Sessions.vue'), meta: { title: '会话抽查' } },
      { path: 'system', name: 'admin-system', component: () => import('../views/admin/System.vue'), meta: { title: '系统信息' } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.token) {
    return { name: 'login' }
  }
  if (to.matched.some((r) => r.meta.admin) && auth.role !== 'admin') {
    return { name: 'chat' }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'chat' }
  }
})

export default router