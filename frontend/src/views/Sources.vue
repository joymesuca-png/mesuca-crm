<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">线索来源管理</h1>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon> 新增来源
      </el-button>
    </div>

    <el-card>
      <el-table :data="sources" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="来源名称" min-width="160" />
        <el-table-column prop="type" label="类型" width="140">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="showDialog" :title="isEdit ? '编辑线索来源' : '新增线索来源'" width="480px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="来源名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：Google 搜索、LinkedIn" />
        </el-form-item>
        <el-form-item label="来源类型" prop="type">
          <el-select v-model="form.type" placeholder="选择类型" style="width:100%">
            <el-option label="搜索引擎" value="search_engine" />
            <el-option label="社交媒体" value="social_media" />
            <el-option label="B2B 平台" value="b2b_platform" />
            <el-option label="地图" value="map" />
            <el-option label="海关数据" value="customs_data" />
            <el-option label="展会" value="exhibition" />
            <el-option label="手动录入" value="manual" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简要描述该来源渠道" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submit" :loading="saving">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getSources, createSource, updateSource, deleteSource } from '../api'

const loading = ref(false)
const saving = ref(false)
const sources = ref([])
const showDialog = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  type: '',
  description: '',
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入来源名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择来源类型', trigger: 'change' }]
}

const typeTag = (t) => {
  const m = { search_engine: '', social_media: 'primary', b2b_platform: 'warning', map: 'success', customs_data: 'danger', exhibition: 'info', manual: '', other: 'info' }
  return m[t] || 'info'
}
const typeLabel = (t) => {
  const m = { search_engine: '搜索引擎', social_media: '社交媒体', b2b_platform: 'B2B 平台', map: '地图', customs_data: '海关数据', exhibition: '展会', manual: '手动录入', other: '其他' }
  return m[t] || t
}

const fetchSources = async () => {
  loading.value = true
  try {
    const res = await getSources()
    sources.value = res.data || []
  } catch {
    ElMessage.error('获取来源列表失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  isEdit.value = false
  editingId.value = null
  resetForm()
  showDialog.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.type = row.type
  form.description = row.description || ''
  form.is_active = row.is_active
  showDialog.value = true
}

const resetForm = () => {
  form.name = ''
  form.type = ''
  form.description = ''
  form.is_active = true
  formRef.value?.resetFields()
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await updateSource(editingId.value, { ...form })
      ElMessage.success('更新成功')
    } else {
      await createSource({ ...form })
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    fetchSources()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除来源"${row.name}"？删除后使用该来源的线索不受影响。`, '确认删除', { type: 'warning' })
    await deleteSource(row.id)
    ElMessage.success('删除成功')
    fetchSources()
  } catch { /* cancelled */ }
}

onMounted(fetchSources)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { font-size: 22px; color: #303133; }
</style>