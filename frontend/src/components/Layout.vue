<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="background: #304156">
      <div class="logo">🚀 Mesuca CRM</div>
      <el-menu
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon> 工作台
        </el-menu-item>
        <el-menu-item index="/leads">
          <el-icon><List /></el-icon> 客户线索
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background:#fff;border-bottom:1px solid #e6e6e6;display:flex;align-items:center;justify-content:space-between;padding:0 20px">
        <span class="header-title">{{ $route.meta?.title || 'Mesuca CRM' }}</span>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><UserFilled /></el-icon> {{ userName }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main style="background:#f0f2f5">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { HomeFilled, List, UserFilled, ArrowDown } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const activeMenu = computed(() => {
  if (route.path.startsWith('/leads')) return '/leads'
  return '/'
})

const userName = computed(() => {
  try { return JSON.parse(localStorage.getItem('user'))?.username || 'Admin' }
  catch { return 'Admin' }
})

const handleCommand = (cmd) => {
  if (cmd === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }
}
</script>

<style scoped>
.logo { height: 60px; line-height: 60px; text-align: center; color: #fff; font-size: 18px; font-weight: 700; letter-spacing: 1px; }
.header-title { font-size: 16px; font-weight: 600; color: #303133; }
.user-info { cursor: pointer; display: flex; align-items: center; gap: 6px; color: #606266; }
.el-menu { border-right: none; }
</style>