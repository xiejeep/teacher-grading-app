<template>
  <div class="template-selector">
    <div class="template-selector-header">
      <span class="template-selector-label">选择试卷模板</span>
      <el-button type="primary" link size="small" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        新建模板
      </el-button>
    </div>

    <div v-if="!templatesStore.templates.length && !templatesStore.loading" class="template-empty">
      <p>暂无模板，请先上传原试卷创建模板</p>
      <el-button type="primary" size="small" @click="showCreateDialog = true">创建模板</el-button>
    </div>

    <el-radio-group v-else v-model="selectedId" class="template-list" @change="onSelect">
      <div v-for="tpl in templatesStore.templates" :key="tpl.template_id"
           class="template-item" :class="{ selected: selectedId === tpl.template_id }">
        <el-radio :value="tpl.template_id">
          <div class="template-item-content">
            <span class="template-name">{{ tpl.name }}</span>
            <span class="template-meta">{{ tpl.subject }} · {{ tpl.stage }}</span>
            <span v-if="tpl.standard_answers_json" class="template-badge">
              {{ parsedAnswerCount(tpl.standard_answers_json) }}题答案
            </span>
          </div>
        </el-radio>
        <el-button class="template-delete-btn" text size="small" type="danger"
                   @click.stop="handleDelete(tpl)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </el-radio-group>

    <!-- 创建模板对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建试卷模板" :width="560" :close-on-click-modal="false"
               @close="resetCreateForm">
      <div v-if="createPhase === 'upload'" class="create-step">
        <div class="create-form-row">
          <span class="create-label">模板名称</span>
          <el-input v-model="createName" placeholder="如：2024期中数学" size="default" />
        </div>
        <div class="create-form-row">
          <span class="create-label">学科 / 学段</span>
          <div style="display: flex; gap: 8px;">
            <el-select v-model="createSubject" style="width: 100px;">
              <el-option label="数学" value="数学" />
              <el-option label="语文" value="语文" />
              <el-option label="英语" value="英语" />
            </el-select>
            <el-select v-model="createStage" style="width: 100px;">
              <el-option label="小学" value="小学" />
              <el-option label="初中" value="初中" />
              <el-option label="高中" value="高中" />
            </el-select>
          </div>
        </div>

        <div class="create-upload-section" style="margin-top: 12px;">
          <h4 style="font-size: 13px; color: #606266; margin-bottom: 8px;">上传原试卷图片</h4>
          <ImageUploader :analyzing="createAnalyzing" @analyze="onTemplateFileSelected" />
        </div>
      </div>

      <div v-else-if="createPhase === 'analyzing'" class="create-progress">
        <h4 style="margin-bottom: 12px; color: #409eff;">
          <el-icon class="is-loading" style="margin-right: 6px;"><Loading /></el-icon>
          正在创建模板...
        </h4>
        <div class="progress-timeline">
          <div v-for="(item, idx) in createProgressLog" :key="idx" class="progress-item"
               :class="{ active: idx === createProgressLog.length - 1 }">
            <div class="progress-dot" :class="item.status">
              <el-icon v-if="item.status === 'done'" :size="14"><Check /></el-icon>
              <el-icon v-else-if="item.status === 'error'" :size="14"><Close /></el-icon>
              <div v-else class="progress-spinner"></div>
            </div>
            <div class="progress-body">
              <span class="progress-phase">{{ item.phaseLabel }}</span>
              <span class="progress-msg">{{ item.message }}</span>
            </div>
          </div>
        </div>
        <div v-if="createError" class="create-error">{{ createError }}</div>
      </div>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button v-if="createPhase === 'upload'" type="primary" :disabled="!createFile || !createName.trim()"
                   @click="startCreateTemplate">
          开始创建
        </el-button>
        <el-button v-if="createPhase === 'analyzing'" type="danger" @click="cancelCreate">
          停止
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Plus, Loading, Check, Close, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTemplatesStore } from '@/stores/templates'
import { connectCreateTemplateSSE } from '@/utils/sse'
import type { SSEHandlers } from '@/utils/sse'
import ImageUploader from '@/components/ImageUploader.vue'
import type { TemplateListItem } from '@/types'

const emit = defineEmits<{
  (e: 'select', template: TemplateListItem): void
  (e: 'created', template: TemplateListItem): void
}>()

const props = defineProps<{
  subject: string
  stage: string
}>()

const templatesStore = useTemplatesStore()
const selectedId = ref<string | null>(null)

const ANALYSIS_PHASE_LABELS: Record<string, string> = {
  analyzing: '版面分析',
  batch_analyzing: '分批分析',
  batch_analyze_done: '批次完成',
  analysis_done: '分析完成',
  extracting: '答案提取',
  extraction_done: '提取完成',
  warning: '警告',
}

interface CreateProgressItem {
  phaseLabel: string
  message: string
  status: 'running' | 'done' | 'error'
}

const showCreateDialog = ref(false)
const createPhase = ref<'upload' | 'analyzing'>('upload')
const createName = ref('')
const createSubject = ref('数学')
const createStage = ref('小学')
const createFile = ref<File | null>(null)
const createAnalyzing = ref(false)
const createAbort = ref<(() => void) | null>(null)
const createProgressLog = ref<CreateProgressItem[]>([])
const createError = ref('')

watch(() => props.subject, (s) => { createSubject.value = s })
watch(() => props.stage, (s) => { createStage.value = s })

onMounted(() => {
  templatesStore.fetchTemplates(props.subject, props.stage)
})

watch([() => props.subject, () => props.stage], ([s, g]) => {
  if (s && g) templatesStore.fetchTemplates(s, g)
})

function parsedAnswerCount(jsonStr: string | null): number {
  if (!jsonStr) return 0
  try {
    return JSON.parse(jsonStr).length
  } catch {
    return 0
  }
}

async function handleDelete(tpl: TemplateListItem) {
  try {
    await ElMessageBox.confirm(`确定删除模板「${tpl.name}」？删除后无法恢复。`, '删除模板', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const ok = await templatesStore.deleteTemplate(tpl.template_id)
    if (ok && selectedId.value === tpl.template_id) {
      selectedId.value = null
    }
  } catch {
    // user cancelled
  }
}

function onSelect(val: string) {
  const tpl = templatesStore.templates.find(t => t.template_id === val)
  if (tpl) emit('select', tpl)
}

function onTemplateFileSelected(file: File) {
  createFile.value = file
}

function startCreateTemplate() {
  if (!createFile.value || !createName.value.trim()) return
  createPhase.value = 'analyzing'
  createProgressLog.value = []
  createError.value = ''

  const handlers: SSEHandlers = {
    onStatus(data) {
      const label = ANALYSIS_PHASE_LABELS[data.phase] || data.phase
      const isFinal = ['analysis_done', 'extraction_done', 'warning'].includes(data.phase)
      createProgressLog.value.push({
        phaseLabel: label,
        message: data.message,
        status: isFinal ? 'done' : 'running',
      })
    },
    onTemplateCreated(data) {
      ElMessage.success(`模板"${data.name}"创建成功`)
      selectedId.value = data.template_id
      templatesStore.fetchTemplates(props.subject, props.stage).then(() => {
        const tpl = templatesStore.templates.find(t => t.template_id === data.template_id)
        if (tpl) emit('created', tpl)
      })
    },
    onDone() {
      createPhase.value = 'upload'
      showCreateDialog.value = false
      resetCreateForm()
    },
    onError(message) {
      createError.value = message
      if (createProgressLog.value.length > 0) {
        createProgressLog.value[createProgressLog.value.length - 1].status = 'error'
      }
    },
  }

  createAbort.value = connectCreateTemplateSSE(
    createFile.value,
    createName.value.trim(),
    handlers,
    createSubject.value,
    createStage.value,
  )
}

function cancelCreate() {
  createAbort.value?.()
  createPhase.value = 'upload'
  createProgressLog.value = []
  createError.value = ''
}

function resetCreateForm() {
  createName.value = ''
  createFile.value = null
  createPhase.value = 'upload'
  createProgressLog.value = []
  createError.value = ''
}
</script>

<style scoped>
.template-selector {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
}

.template-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.template-selector-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.template-empty {
  text-align: center;
  padding: 16px;
  color: #909399;
  font-size: 13px;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.template-item.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.template-item:hover {
  border-color: #c0c4cc;
}

.template-item:hover .template-delete-btn {
  opacity: 1;
}

.template-delete-btn {
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.template-item-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.template-meta {
  font-size: 12px;
  color: #909399;
}

.template-badge {
  font-size: 12px;
  color: #409eff;
  background: #ecf5ff;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: auto;
}

.create-form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.create-label {
  font-size: 13px;
  color: #606266;
  min-width: 80px;
}

.create-error {
  color: #f56c6c;
  font-size: 13px;
  margin-top: 12px;
}

.create-progress {
  padding: 8px 0;
}

/* shared with GradeView progress styles */
.progress-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.progress-item {
  display: flex;
  gap: 14px;
  padding: 10px 0;
  opacity: 0.5;
}

.progress-item.active {
  opacity: 1;
}

.progress-dot {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e4e7ed;
  color: #fff;
}

.progress-item.active .progress-dot {
  background: #409eff;
}

.progress-dot.done {
  background: #67c23a;
}

.progress-dot.error {
  background: #f56c6c;
}

.progress-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #fff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.progress-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.progress-phase {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.progress-msg {
  font-size: 13px;
  color: #606266;
}
</style>
