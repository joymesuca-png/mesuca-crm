<template>
  <div>
    <h1 class="page-title">工作台</h1>
    <el-row :gutter="20">
      <el-col :span="6" v-for="card in cards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" :style="{ background: card.color }">
            <el-icon :size="28"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <p class="stat-value">{{ card.value }}</p>
            <p class="stat-label">{{ card.label }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card>
          <template #header>最近线索</template>
          <el-table :data="recentLeads" stripe size="small">
            <el-table-column prop="company_name" label="公司名称" />
            <el-table-column prop="country" label="国家" width="100" />
            <el-table-column prop="industry" label="行业" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>快捷操作</template>
          <el-menu :default-active="null" class="quick-menu">
            <el-menu-item @click="$router.push('/leads')">
              <el-icon><List /></el-icon> 客户线索管理
            </el-menu-item>
            <el-menu-item>
              <el-icon><Plus /></el-icon> 新增客户线索
            </el-menu-item>
            <el-menu-item>
              <el-icon><Download /></el-icon> 导出数据
            </el-menu-item>
          </el-menu>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { List, Plus, Download, User, DataLine, Connection, TrendCharts } from '@element-plus/icons-vue'
import { getLeads } from '../api'

const cards = ref([
  { icon: User, label: '总线索数', value: 0, color: '#409eff' },
  { icon: DataLine, label: '本月新增', value: 0, color: '#67c23a' },
  { icon: Connection, label: '已转化', value: 0, color: '#e6a23c' },
  { icon: TrendCharts, label: '线索来源', value: 0, color: '#f56c6c' }
])

const recentLeads = ref([])

const statusType = (s) => {
  const map = { new: 'info', contacted: 'warning', qualified: '', converted: 'success', lost: 'danger' }
  return map[s] || 'info'
}
const statusLabel = (s) => {
  const map = { new: '新线索', contacted: '已联系', qualified: '已认证', converted: '已转化', lost: '已流失' }
  return map[s] || s
}

onMounted(async () => {
  try {
    const res = await getLeads({ page: 1, page_size: 5 })
    recentLeads.value = res.data.items || []
    cards.value[0].value = res.data.total || 0
  } catch { /* 后端未就绪时静默 */ }
})
</script>

<style scoped>
.page-title { font-size: 22px; margin-bottom: 20px; color: #303133; }
.stat-card { display: flex; align-items: center; }
.stat-card :deep(.el-card__body) { display: flex; align-items: center; gap: 16px; width: 100%; }
.stat-icon { width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #fff; }
.stat-value { font-size: 26px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.quick-menu { border: none; }
</style>