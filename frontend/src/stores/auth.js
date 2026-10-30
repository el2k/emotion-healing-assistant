import { defineStore } from 'pinia'
import { api } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('eh_token') || '',
    user_id: Number(localStorage.getItem('eh_uid') || 0),
    nickname: localStorage.getItem('eh_nick') || '',
    avatar: localStorage.getItem('eh_avatar') || '',
    phone: localStorage.getItem('eh_phone') || '',
    role: localStorage.getItem('eh_role') || '',
  }),
  getters: {
    isLogin: (s) => !!s.token,
    isAdmin: (s) => s.role === 'admin',
  },
  actions: {
    setAuth(data) {
      this.token = data.token
      this.user_id = data.user_id
      this.nickname = data.nickname
      this.role = data.role
      if (data.avatar !== undefined) this.avatar = data.avatar || ''
      if (data.phone !== undefined) this.phone = data.phone || ''
      localStorage.setItem('eh_token', data.token)
      localStorage.setItem('eh_uid', String(data.user_id))
      localStorage.setItem('eh_nick', data.nickname)
      localStorage.setItem('eh_role', data.role)
      localStorage.setItem('eh_avatar', this.avatar)
      localStorage.setItem('eh_phone', this.phone)
    },
    async fetchProfile() {
      if (!this.token) return null
      try {
        const { data } = await api.get('/auth/me')
        this.setProfile({ nickname: data.nickname, avatar: data.avatar, phone: data.phone })
        if (data.role) { this.role = data.role; localStorage.setItem('eh_role', data.role) }
        return data
      } catch {
        return null
      }
    },
    setProfile(p) {
      if (p.nickname !== undefined) { this.nickname = p.nickname; localStorage.setItem('eh_nick', p.nickname) }
      if (p.avatar !== undefined) { this.avatar = p.avatar || ''; localStorage.setItem('eh_avatar', this.avatar) }
      if (p.phone !== undefined) { this.phone = p.phone || ''; localStorage.setItem('eh_phone', this.phone) }
    },
    async login(phone, password) {
      const { data } = await api.post('/auth/login', { phone, password })
      this.setAuth(data)
      return data
    },
    async register(payload) {
      const { data } = await api.post('/auth/register', payload)
      this.setAuth(data)
      return data
    },
    logout() {
      this.token = ''
      this.role = ''
      ;['eh_token', 'eh_uid', 'eh_nick', 'eh_avatar', 'eh_phone', 'eh_role']
        .forEach((k) => localStorage.removeItem(k))
    },
  },
})