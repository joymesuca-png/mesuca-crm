<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">客户线索</h1>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon> 新增线索
      </el-button>
    </div>

    <!-- 搜索筛选 -->
    <el-card style="margin-bottom: 16px">
      <el-form :inline="true" :model="filters" size="default">
        <el-form-item label="搜索">
          <el-input v-model="filters.search" placeholder="公司名 / 邮箱" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="国家">
          <el-input v-model="filters.country" placeholder="国家" clearable style="width: 140px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="新线索" value="new" />
            <el-option label="已联系" value="contacted" />
            <el-option label="已认证" value="qualified" />
            <el-option label="已转化" value="converted" />
            <el-option label="已流失" value="lost" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchLeads">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据表格 -->
    <el-card>
      <el-table :data="leads" stripe v-loading="loading">
        <el-table-column prop="company_name" label="公司名称" min-width="180" />
        <el-table-column prop="contact_name" label="联系人" width="100" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="country" label="国家" width="100" />
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column prop="lead_score" label="评分" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/leads/${row.id}`)">详情</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; text-align: right">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchLeads"
          @current-change="fetchLeads"
        />
      </div>
    </el-card>

    <!-- 新建弹窗 -->
    <el-dialog v-model="showCreateDialog" title="新增客户线索" width="600px" @closed="resetForm">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="公司名称" prop="company_name">
              <el-input v-model="form.company_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="form.contact_name" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="电话">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="国家">
              <el-input v-model="form.country" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="城市">
              <el-input v-model="form.city" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="行业">
              <el-input v-model="form.industry" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="网站">
          <el-input v-model="form.website" />
        </el-form-item>
        <el-form-item label="兴趣产品">
          <el-input v-model="form.product_interest" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="来源" prop="source_id">
          <el-select v-model="form.source_id" placeholder="选择来源" style="width: 100%">
            <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createLead" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getLeads, createLead as apiCreateLead, deleteLead, getSources } from '../api'

const loading = ref(false)
const leads = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const filters = reactive({ search: '', country: '', status: '' })

const statusType = (s) => {
  const map = { new: 'info', contacted: 'warning', qualified: '', converted: 'success', lost: 'danger' }
  return map[s] || 'info'
}
const statusLabel = (s) => {
  const map = { new: '新线索', contacted: '已联系', qualified: '已认证', converted: '已转化', lost: '已流失' }
  return map[s] || s
}

const fetchLeads = async () => {
  loading.value = true
  try {
    const res = await getLeads({
      page: page.value,
      page_size: pageSize.value,
      ...(filters.search && { search: filters.search }),
      ...(filters.country && { country: filters.country }),
      ...(filters.status && { status: filters.status })
    })
    leads.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取线索列表失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.search = ''
  filters.country = ''
  filters.status = ''
  page.value = 1
  fetchLeads()
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除 "${row.company_name}"？`, '确认删除', { type: 'warning' })
    await deleteLead(row.id)
    ElMessage.success('删除成功')
    fetchLeads()
  } catch { /* cancelled */ }
}

// 新建
const showCreateDialog = ref(false)
const creating = ref(false)
const formRef = ref(null)
const sources = ref([])

const form = reactive({
  company_name: '', contact_name: '', email: '', phone: '', website: '',
  country: '', city: '', industry: '', product_interest: '', source_id: null
})
const formRules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  source_id: [{ required: true, message: '请选择来源', trigger: 'change' }]
}

const resetForm = () => {
  Object.keys(form).forEach(k => form[k] = k === 'source_id' ? null : '')
  formRef.value?.resetFields()
}

const createLead = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    await apiCreateLead({ ...form })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    fetchLeads()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

// 加载来源列表
const fetchSources = async () => {
  try {
    const res = await getSources()
    sources.value = res.data || []
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchLeads()
  fetchSources()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 22px; color: #303133; }
</style>