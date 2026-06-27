<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">获客采集</h1>
      <el-button type="primary" @click="showTaskDialog = true">
        <el-icon><Plus /></el-icon> 新建采集任务
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom:20px">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" :style="{ background: card.color }">
            <el-icon :size="22"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <p class="stat-value">{{ card.value }}</p>
            <p class="stat-label">{{ card.label }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷采集入口 -->
    <el-row :gutter="16" style="margin-bottom:20px">
      <el-col :span="12">
        <el-card shadow="hover" class="channel-card" @click="openSearchCapture">
          <div class="channel-icon"><el-icon :size="36"><Search /></el-icon></div>
          <h3>搜索引擎采集</h3>
          <p>通过 Google 等搜索引擎按关键词挖掘潜在客户</p>
          <el-tag type="info" size="small">Google · Bing · DuckDuckGo</el-tag>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="channel-card" @click="openB2BCapture">
          <div class="channel-icon"><el-icon :size="36"><Connection /></el-icon></div>
          <h3>B2B 平台采集</h3>
          <p>从阿里巴巴国际站等 B2B 平台获取采购商信息</p>
          <el-tag type="warning" size="small">Alibaba · Global Sources · Made-in-China</el-tag>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="8">
        <el-card shadow="hover" class="channel-card" @click="openMapCapture">
          <div class="channel-icon"><el-icon :size="36"><Location /></el-icon></div>
          <h3>地图采集</h3>
          <p>通过 Google Maps 按区域搜索企业信息</p>
          <el-tag type="success" size="small">Google Maps</el-tag>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="channel-card" @click="openSocialCapture">
          <div class="channel-icon"><el-icon :size="36"><Share /></el-icon></div>
          <h3>社交媒体采集</h3>
          <p>从 LinkedIn、Facebook 等平台采集潜在客户</p>
          <el-tag type="primary" size="small">LinkedIn · Facebook</el-tag>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="channel-card" @click="openCustomsCapture">
          <div class="channel-icon"><el-icon :size="36"><Ship /></el-icon></div>
          <h3>海关数据</h3>
          <p>通过海关进出口数据获取目标客户</p>
          <el-tag type="danger" size="small">各国海关数据</el-tag>
        </el-card>
      </el-col>
    </el-row>

    <!-- 任务历史 -->
    <el-card style="margin-top:20px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>采集任务历史</span>
          <el-button type="danger" size="small" text @click="clearTasks" :disabled="!tasks.length">
            清空记录
          </el-button>
        </div>
      </template>
      <el-table :data="tasks" v-loading="loading" empty-text="暂无采集任务，点击上方卡片开始采集">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'search' ? 'info' : 'warning'" size="small">
              {{ row.type === 'search' ? '搜索引擎' : 'B2B平台' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="keyword" label="关键词" min-width="150" />
        <el-table-column prop="platform" label="平台" width="120">
          <template #default="{ row }">{{ row.platform || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="结果" min-width="200" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建采集弹窗 -->
    <el-dialog v-model="showTaskDialog" :title="taskDialogTitle" width="520px" @closed="resetForm">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="搜索引擎" name="search">
          <el-form :model="searchForm" :rules="searchRules" ref="searchFormRef" label-width="100px">
            <el-form-item label="关键词" prop="keyword">
              <el-input v-model="searchForm.keyword" placeholder="例如：LED lighting, auto parts（支持中英文）" />
            </el-form-item>
            <el-form-item label="目标国家" prop="country">
              <el-select v-model="searchForm.country" placeholder="不限" clearable filterable style="width:100%">
                <el-option label="美国" value="USA" />
                <el-option label="英国" value="UK" />
                <el-option label="德国" value="Germany" />
                <el-option label="法国" value="France" />
                <el-option label="日本" value="Japan" />
                <el-option label="加拿大" value="Canada" />
                <el-option label="澳大利亚" value="Australia" />
                <el-option label="巴西" value="Brazil" />
                <el-option label="印度" value="India" />
                <el-option label="不限" value="" />
              </el-select>
            </el-form-item>
            <el-form-item label="线索来源" prop="source_id">
              <el-select v-model="searchForm.source_id" placeholder="选择来源" style="width:100%">
                <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="采集数量">
              <el-input-number v-model="searchForm.max_results" :min="1" :max="100" style="width:100%" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="B2B 平台" name="b2b">
          <el-form :model="b2bForm" :rules="b2bRules" ref="b2bFormRef" label-width="100px">
            <el-form-item label="平台" prop="platform">
              <el-select v-model="b2bForm.platform" placeholder="选择平台" style="width:100%">
                <el-option label="阿里巴巴国际站" value="alibaba" />
                <el-option label="环球资源" value="globalsources" />
                <el-option label="中国制造网" value="made-in-china" />
                <el-option label="TradeKey" value="tradekey" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键词" prop="keyword">
              <el-input v-model="b2bForm.keyword" placeholder="产品关键词" />
            </el-form-item>
            <el-form-item label="线索来源" prop="source_id">
              <el-select v-model="b2bForm.source_id" placeholder="选择来源" style="width:100%">
                <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="采集数量">
              <el-input-number v-model="b2bForm.max_results" :min="1" :max="100" style="width:100%" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="showTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="startCapture" :loading="capturing">
          <el-icon><VideoPlay /></el-icon> 开始采集
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Connection, Location, Share, Ship, VideoPlay, DataLine, TrendCharts, Link, Finished } from '@element-plus/icons-vue'
import { getCaptureStats, getCaptureTasks, startSearchCapture, startB2BCapture, clearCaptureTasks, getSources } from '../api'

const loading = ref(false)
const capturing = ref(false)
const tasks = ref([])
const stats = ref({ total_tasks: 0, running_tasks: 0, completed_tasks: 0, failed_tasks: 0, total_leads_today: 0 })
const sources = ref([])

const statCards = computed(() => [
  { icon: DataLine, label: '总任务数', value: stats.value.total_tasks, color: '#409eff' },
  { icon: TrendCharts, label: '运行中', value: stats.value.running_tasks, color: '#e6a23c' },
  { icon: Finished, label: '已完成', value: stats.value.completed_tasks, color: '#67c23a' },
  { icon: Link, label: '今日线索', value: stats.value.total_leads_today, color: '#f56c6c' }
])

const statusType = (s) => ({ running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ running: '采集中', completed: '已完成', failed: '失败' }[s] || s)
const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

// 任务弹窗
const showTaskDialog = ref(false)
const activeTab = ref('search')
const taskDialogTitle = computed(() => activeTab.value === 'search' ? '搜索引擎采集' : 'B2B 平台采集')

const searchForm = reactive({ keyword: '', country: '', source_id: null, max_results: 20 })
const searchRules = {
  keyword: [{ required: true, message: '请输入搜索关键词', trigger: 'blur' }],
  source_id: [{ required: true, message: '请选择线索来源', trigger: 'change' }]
}
const b2bForm = reactive({ platform: '', keyword: '', source_id: null, max_results: 20 })
const b2bRules = {
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  keyword: [{ required: true, message: '请输入关键词', trigger: 'blur' }],
  source_id: [{ required: true, message: '请选择线索来源', trigger: 'change' }]
}
const searchFormRef = ref(null)
const b2bFormRef = ref(null)

const openSearchCapture = () => {
  activeTab.value = 'search'
  showTaskDialog.value = true
}
const openB2BCapture = () => {
  activeTab.value = 'b2b'
  showTaskDialog.value = true
}
const openMapCapture = () => ElMessage.info('地图采集功能开发中，敬请期待')
const openSocialCapture = () => ElMessage.info('社交媒体采集功能开发中，敬请期待')
const openCustomsCapture = () => ElMessage.info('海关数据采集功能开发中，敬请期待')

const onTabChange = () => { /* 切换 tab 时重置校验 */ }
const resetForm = () => {
  searchFormRef.value?.resetFields()
  b2bFormRef.value?.resetFields()
}

const startCapture = async () => {
  const refName = activeTab.value === 'search' ? 'searchFormRef' : 'b2bFormRef'
  const formRef = activeTab.value === 'search' ? searchFormRef : b2bFormRef
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  capturing.value = true
  try {
    if (activeTab.value === 'search') {
      const res = await startSearchCapture({ ...searchForm })
      ElMessage.success(res.data.message)
    } else {
      const res = await startB2BCapture({ ...b2bForm })
      ElMessage.success(res.data.message)
    }
    showTaskDialog.value = false
    fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '采集任务启动失败')
  } finally {
    capturing.value = false
  }
}

const clearTasks = async () => {
  try {
    await ElMessageBox.confirm('确定清空所有任务记录？', '确认', { type: 'warning' })
    await clearCaptureTasks()
    ElMessage.success('已清空')
    fetchData()
  } catch { /* cancelled */ }
}

const fetchData = async () => {
  loading.value = true
  try {
    const [statsRes, tasksRes] = await Promise.all([getCaptureStats(), getCaptureTasks()])
    stats.value = statsRes.data
    tasks.value = tasksRes.data.reverse()
  } catch { /* 后端未就绪时静默 */ }
  loading.value = false
}

const fetchSources = async () => {
  try {
    const res = await getSources()
    sources.value = res.data || []
  } catch { /* ignore */ }
}

onMounted(() => {
  fetchData()
  fetchSources()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { font-size: 22px; color: #303133; }

.stat-card { display: flex; align-items: center; }
.stat-card :deep(.el-card__body) { display: flex; align-items: center; gap: 14px; width: 100%; padding: 16px; }
.stat-icon { width: 48px; height: 48px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.stat-value { font-size: 22px; font-weight: 700; color: #303133; }
.stat-label { font-size: 12px; color: #909399; margin-top: 2px; }

.channel-card { cursor: pointer; text-align: center; padding: 10px; transition: all 0.2s; border: 1px solid var(--el-border-color-light); }
.channel-card:hover { border-color: #409eff; box-shadow: 0 4px 12px rgba(64,158,255,0.15); }
.channel-icon { color: #409eff; margin-bottom: 12px; }
.channel-card h3 { font-size: 15px; color: #303133; margin-bottom: 8px; }
.channel-card p { font-size: 12px; color: #909399; margin-bottom: 10px; }
</style>