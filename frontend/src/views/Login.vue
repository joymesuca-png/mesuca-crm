<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>🚀 外贸获客系统</h2>
      <p class="subtitle">Mesuca CRM</p>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" @click="login" :loading="loading">
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <p class="hint">演示账号：admin / admin123</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: 'admin', password: 'admin123' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const login = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  // 模拟登录（后续接入真实 API）
  setTimeout(() => {
    localStorage.setItem('token', 'demo-token')
    localStorage.setItem('user', JSON.stringify({ username: form.username, role: 'admin' }))
    ElMessage.success('登录成功')
    router.push('/')
  }, 600)
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 400px;
  padding: 20px 30px;
  text-align: center;
}
.login-card h2 { color: #303133; margin-bottom: 4px; }
.subtitle { color: #909399; font-size: 14px; margin-bottom: 24px; }
.hint { color: #c0c4cc; font-size: 12px; margin-top: 12px; }
</style>