<template>
  <router-view />
  <Pet v-if="showPet" />
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Pet from './components/Pet.vue'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const auth = useAuthStore()
// 管理平台属于工作场景，隐藏桌面宠物，避免遮挡表格与图表
const showPet = computed(() =>
  route.name !== 'login' && !String(route.path).startsWith('/admin'))

onMounted(() => {
  if (auth.isLogin) auth.fetchProfile()
})
</script>