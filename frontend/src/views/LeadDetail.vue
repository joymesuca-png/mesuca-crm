<template>
  <div>
    <el-page-header @back="$router.push('/leads')" :content="lead?.company_name || '线索详情'" style="margin-bottom: 20px" />

    <el-row :gutter="20" v-if="lead">
      <el-col :span="16">
        <el-card>
          <template #header>基本信息</template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="公司名称">{{ lead.company_name }}</el-descriptions-item>
            <el-descriptions-item label="联系人">{{ lead.contact_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ lead.email || '-' }}</el-descriptions-item>
            <el-descriptions-item label="电话">{{ lead.phone || '-' }}</el-descriptions-item>
            <el-descriptions-item label="国家">{{ lead.country || '-' }}</el-descriptions-item>
            <el-descriptions-item label="城市">{{ lead.city || '-' }}</el-descriptions-item>
            <el-descriptions-item label="行业">{{ lead.industry || '-' }}</el-descriptions-item>
            <el-descriptions-item label="网站">
              <a v-if="lead.website" :href="lead.website" target="_blank">{{ lead.website }}</a>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="兴趣产品">{{ lead.product_interest || '-' }}</el-descriptions-item>
            <el-descriptions-item label="线索评分">{{ lead.lead_score }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusType(lead.status)">{{ statusLabel(lead.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ lead.source?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(lead.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(lead.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header>状态更新</template>
          <el-form :model="updateForm" label-width="0">
            <el-form-item>
              <el-select v-model="updateForm.status" style="width:100%" placeholder="更新状态">
                <el-option label="新线索" value="new" />
                <el-option label="已联系" value="contacted" />
                <el-option label="已认证" value="qualified" />
                <el-option label="已转化" value="converted" />
                <el-option label="已流失" value="lost" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input-number v-model="updateForm.lead_score" :min="0" :max="100" style="width:100%" placeholder="线索评分" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" style="width:100%" @click="saveUpdate" :loading="saving">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <div v-else-if="loading" style="text-align:center;padding:60px">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { getLead, updateLead } from '../api'

const route = useRoute()
const lead = ref(null)
const loading = ref(true)
const saving = ref(false)

const updateForm = ref({ status: '', lead_score: 0 })

const statusType = (s) => {
  const map = { new: 'info', contacted: 'warning', qualified: '', converted: 'success', lost: 'danger' }
  return map[s] || 'info'
}
const statusLabel = (s) => {
  const map = { new: '新线索', contacted: '已联系', qualified: '已认证', converted: '已转化', lost: '已流失' }
  return map[s] || s
}
const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

const fetchLead = async () => {
  loading.value = true
  try {
    const res = await getLead(route.params.id)
    lead.value = res.data
    updateForm.value = { status: res.data.status, lead_score: res.data.lead_score }
  } catch {
    ElMessage.error('获取线索详情失败')
  } finally {
    loading.value = false
  }
}

const saveUpdate = async () => {
  saving.value = true
  try {
    await updateLead(route.params.id, updateForm.value)
    ElMessage.success('更新成功')
    fetchLead()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchLead)
</script>