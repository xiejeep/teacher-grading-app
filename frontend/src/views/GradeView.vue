<template>
  <div class="grade-page">
    <div class="page-card">
      <h3 style="margin-bottom: 20px; font-size: 18px;">试卷批改</h3>

      <div class="grade-controls">
        <div class="control-row">
          <div class="control-item">
            <span class="control-label">学科</span>
            <el-radio-group v-model="subject" :disabled="phase !== 'select-template'">
              <el-radio-button label="数学" value="数学" />
              <el-radio-button label="语文" value="语文" />
              <el-radio-button label="英语" value="英语" />
            </el-radio-group>
          </div>
          <div class="control-item">
            <span class="control-label">学段</span>
            <el-radio-group v-model="stage" :disabled="phase !== 'select-template'">
              <el-radio-button label="小学" value="小学" />
              <el-radio-button label="初中" value="初中" />
              <el-radio-button label="高中" value="高中" />
            </el-radio-group>
          </div>
        </div>
      </div>

      <!-- Step indicator -->
      <div class="step-bar">
        <div class="step" :class="{ active: phase === 'select-template', done: phase !== 'select-template' }">
          <span class="step-num">1</span>
          <span class="step-text">选择模板</span>
        </div>
        <div class="step-sep" :class="{ done: phase !== 'select-template' }" />
        <div class="step" :class="{ active: phase === 'upload-students', done: phase === 'batch-grading' || phase === 'batch-result' }">
          <span class="step-num">2</span>
          <span class="step-text">上传学生答卷</span>
        </div>
        <div class="step-sep" :class="{ done: phase === 'batch-grading' || phase === 'batch-result' }" />
        <div class="step" :class="{ active: phase === 'batch-grading' || phase === 'batch-result' }">
          <span class="step-num">3</span>
          <span class="step-text">批改结果</span>
        </div>
      </div>

      <!-- ===== Phase 1: select-template ===== -->
      <div v-if="phase === 'select-template'">
        <TemplateSelector
          :subject="subject"
          :stage="stage"
          @select="onTemplateSelect"
          @created="onTemplateSelect"
        />
      </div>

      <!-- ===== Phase 2: upload-students ===== -->
      <div v-if="phase === 'upload-students'" class="upload-students-area">
        <div class="template-info-bar">
          <div>
            <el-tag type="success" size="small">当前模板</el-tag>
            <span style="margin-left: 8px; font-weight: 600; font-size: 14px;">{{ selectedTemplateName }}</span>
            <span v-if="selectedTemplateAnswerCount > 0" style="margin-left: 8px; font-size: 12px; color: #909399;">
              {{ selectedTemplateAnswerCount }}题答案
            </span>
          </div>
          <div style="display: flex; gap: 4px;">
            <el-button text size="small" @click="toggleTemplatePreview">
              {{ showTemplatePreview ? '收起预览' : '预览模板' }}
              <el-icon style="margin-left: 4px;">
                <component :is="showTemplatePreview ? 'ArrowUp' : 'ArrowDown'" />
              </el-icon>
            </el-button>
            <el-button text size="small" type="primary" @click="enterEditMode">
              <el-icon style="margin-right: 4px;"><EditPen /></el-icon>编辑标注
            </el-button>
            <el-button text size="small" type="warning" @click="openAnswerEditor">
              <el-icon style="margin-right: 4px;"><Edit /></el-icon>编辑答案
            </el-button>
            <el-button text size="small" @click="backToSelectTemplate">切换模板</el-button>
          </div>
        </div>

        <!-- Template preview panel -->
        <el-collapse-transition>
          <div v-if="showTemplatePreview && templatePreviewData" class="template-preview-panel">
            <div v-if="templatePreviewLoading" style="text-align: center; padding: 40px; color: #909399;">
              <el-icon class="is-loading" :size="24"><Loading /></el-icon>
              <p style="margin-top: 8px;">加载模板数据...</p>
            </div>
            <div v-else class="preview-split">
              <div class="preview-canvas-col">
                <div class="preview-img-wrapper" ref="previewImgWrapper">
                  <img :src="templatePreviewImageUrl" class="preview-img" @load="onPreviewImgLoad" />
                  <svg v-if="previewReady" class="preview-svg" :width="previewDisplayW" :height="previewDisplayH"
                       :viewBox="`0 0 ${previewDisplayW} ${previewDisplayH}`">
                    <g v-for="(sec, si) in previewSections" :key="'sec-' + si">
                      <rect v-for="(area, ai) in secAreas(sec)" :key="'a-' + si + '-' + ai"
                            :x="area.bbox.x * previewDisplayW"
                            :y="area.bbox.y * previewDisplayH"
                            :width="area.bbox.w * previewDisplayW"
                            :height="area.bbox.h * previewDisplayH"
                            class="preview-area-rect"
                            :style="{ fill: sectionColors[si % sectionColors.length] + '33', stroke: sectionColors[si % sectionColors.length] }"
                      />
                    </g>
                  </svg>
                </div>
              </div>
              <div class="preview-detail-col">
                <div v-if="previewStats" class="preview-stats">
                  <span>{{ previewStats.sections }} 大题</span>
                  <span>{{ previewStats.problems }} 小题</span>
                  <span>{{ previewStats.areas }} 作答区</span>
                </div>
                <div v-for="(sec, si) in previewSections" :key="si" class="preview-section">
                  <div class="preview-section-title" :style="{ borderLeftColor: sectionColors[si % sectionColors.length] }">
                    {{ sec.title || '第' + sec.section_number + '大题' }}
                    <span style="font-weight: 400; color: #909399; margin-left: 6px;">{{ sec.problems.length }}题</span>
                  </div>
                  <div v-for="p in sec.problems" :key="p.problem_number" class="preview-problem">
                    <span class="preview-problem-num">{{ sec.section_number }}.{{ p.problem_number }}</span>
                    <span class="preview-problem-text">{{ p.text ? (p.text.length > 40 ? p.text.slice(0, 40) + '...' : p.text) : '(无文字)' }}</span>
                    <span v-if="p.answer_areas.length" class="preview-area-count">{{ p.answer_areas.length }}个作答区</span>
                  </div>
                </div>
                <div v-if="previewAnswers.length" class="preview-answers">
                  <div class="preview-section-title" style="border-left-color: #409eff;">标准答案</div>
                  <div v-for="a in previewAnswers" :key="a.problem_key" class="preview-answer-item">
                    <span class="preview-problem-num">{{ a.problem_key }}</span>
                    <span>{{ a.correct_answer }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-transition>

        <div class="batch-upload-area">
          <h4 style="margin-bottom: 8px; color: #606266;">上传学生答卷（可多选）</h4>
          <div class="upload-area" @click="triggerMultiInput" @dragover.prevent @drop.prevent="handleMultiDrop">
            <input ref="multiInputRef" type="file" accept="image/*" multiple style="display: none"
                   @change="handleMultiFileChange" />
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽学生答卷到此区域</div>
            <div class="upload-hint">支持批量上传，每张图片将依次批改</div>
          </div>
          <div v-if="studentFiles.length > 0" class="batch-file-list">
            <div v-for="(f, i) in studentFiles" :key="i" class="batch-file-item">
              <el-icon :size="16" color="#409eff"><PictureFilled /></el-icon>
              <span class="batch-file-name">{{ f.name }}</span>
              <span class="batch-file-size">{{ formatSize(f.size) }}</span>
              <el-button text size="small" type="danger" @click="removeStudentFile(i)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>

        <el-button type="primary" size="large"
                   :disabled="studentFiles.length === 0"
                   style="margin-top: 16px; width: 100%;"
                   @click="startBatchGrading">
          开始批改（共 {{ studentFiles.length }} 份）
        </el-button>
      </div>

      <!-- ===== Phase edit-template ===== -->
      <div v-if="phase === 'edit-template'">
        <div class="edit-toolbar">
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-button size="small" @click="cancelEditTemplate">
              <el-icon style="margin-right: 4px;"><RefreshLeft /></el-icon>取消编辑
            </el-button>
            <el-button type="primary" size="small" :loading="analysisStore.saving" @click="saveTemplateEdits">
              保存标注
            </el-button>
          </div>
          <div style="display: flex; gap: 4px;">
            <el-button
              :type="analysisStore.drawMode ? 'warning' : 'default'"
              size="small"
              @click="analysisStore.toggleDrawMode()"
            >
              {{ analysisStore.drawMode ? '取消绘制' : '绘制区域' }}
            </el-button>
            <el-button
              size="small"
              :disabled="!analysisStore.selectedArea"
              @click="analysisStore.deleteSelectedArea()"
            >
              删除选中
            </el-button>
          </div>
        </div>
        <div class="split-layout has-result" style="margin-top: 12px;">
          <div class="grade-canvas-col">
            <AnnotationCanvas />
          </div>
          <div class="grade-detail-col result-panel">
            <ResultDetail :result="analysisStore.result" />
          </div>
        </div>
      </div>

      <!-- ===== Phase 3: batch-grading ===== -->
      <div v-if="phase === 'batch-grading'" class="progress-panel">
        <h4 style="margin-bottom: 16px; color: #409eff;">
          <el-icon class="is-loading" style="margin-right: 6px;"><Loading /></el-icon>
          批改进行中...（{{ batchCompleted }}/{{ studentFiles.length }}）
        </h4>
        <div class="progress-timeline">
          <div v-for="(item, idx) in progressLog" :key="idx" class="progress-item"
               :class="{ active: idx === progressLog.length - 1 }">
            <div class="progress-dot" :class="item.status">
              <el-icon v-if="item.status === 'done'" :size="14"><Check /></el-icon>
              <el-icon v-else-if="item.status === 'error'" :size="14"><Close /></el-icon>
              <div v-else class="progress-spinner"></div>
            </div>
            <div class="progress-body">
              <span class="progress-phase">{{ item.phaseLabel }}</span>
              <span class="progress-msg">{{ item.message }}</span>
              <span v-if="item.detail" class="progress-detail">{{ item.detail }}</span>
            </div>
          </div>
        </div>
        <el-button type="danger" style="margin-top: 16px;" @click="cancelBatchGrading">
          停止批改
        </el-button>
      </div>

      <!-- ===== Phase 4: batch-result ===== -->
      <div v-if="phase === 'batch-result'">
        <div class="batch-result-area">
          <div class="batch-summary-header">
            <div>
              <h4 style="margin: 0; font-size: 15px;">批改完成</h4>
              <span style="font-size: 13px; color: #909399;">
                完成 {{ batchSummary?.completed ?? 0 }}/{{ batchSummary?.total ?? 0 }} 份
              </span>
            </div>
            <div style="display: flex; gap: 8px;">
              <el-button size="small" @click="resetAll">重新开始</el-button>
              <el-button size="small" type="primary" @click="continueGrading">继续批改</el-button>
            </div>
          </div>

          <el-table :data="batchResults" stripe style="width: 100%; margin-top: 12px;" @row-click="viewBatchStudentDetail">
            <el-table-column prop="student_index" label="#" width="50" />
            <el-table-column prop="filename" label="文件名" min-width="150" />
            <el-table-column label="答对/总作答区" width="140">
              <template #default="{ row }">
                <span v-if="row.grading_result && row.grading_result.total_areas != null" :style="{ color: (row.grading_result.total_areas > 0 && row.grading_result.correct_count / row.grading_result.total_areas >= 0.6) ? '#67c23a' : '#f56c6c' }">
                  {{ row.grading_result.correct_count }} / {{ row.grading_result.total_areas }}
                </span>
                <span v-else style="color: #909399;">-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.grading_result" type="success" size="small">完成</el-tag>
                <el-tag v-else type="danger" size="small">失败</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Single student detail view -->
        <div v-if="batchDetailStudent" class="grade-result-layout" style="margin-top: 24px;">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 600;">{{ batchDetailStudent.filename }} 的批改详情</span>
            <el-button text size="small" @click="batchDetailStudent = null">返回汇总</el-button>
          </div>
          <div class="split-layout has-result">
            <div class="grade-canvas-col">
              <GradingCanvas
                :image-url="batchDetailStudent.image_url"
                :image-width="batchDetailStudent.image_width"
                :image-height="batchDetailStudent.image_height"
                :analysis-result="batchDetailStudent.analysis_result"
                :grading-result="batchDetailStudent.grading_result"
              />
            </div>
            <div class="grade-detail-col result-panel">
              <GradeResultDetail
                v-if="batchDetailStudent.grading_result"
                :grading-result="batchDetailStudent.grading_result"
                :grading-id="batchDetailStudent.grading_id"
                :analysis-result="batchDetailStudent.analysis_result"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Phase history-detail ===== -->
      <div v-if="phase === 'history-detail'">
        <div v-if="historyLoading" style="text-align: center; padding: 60px; color: #909399;">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p style="margin-top: 12px;">加载批改记录...</p>
        </div>
        <div v-else-if="historyDetail" class="history-detail-area">
          <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <span style="font-weight: 600; font-size: 15px;">批改详情</span>
              <el-tag size="small" style="margin-left: 8px;">{{ historyDetail.subject }}</el-tag>
              <el-tag size="small" type="info" style="margin-left: 4px;">{{ historyDetail.stage }}</el-tag>
            </div>
            <el-button size="small" @click="resetAll">返回批改</el-button>
          </div>
          <div class="split-layout has-result">
            <div class="grade-canvas-col">
              <GradingCanvas
                v-if="historyDetail.analysis_result"
                :image-url="historyDetail.analysis_result?.original_image_url || ''"
                :image-width="historyDetail.analysis_result?.image_width || 800"
                :image-height="historyDetail.analysis_result?.image_height || 600"
                :analysis-result="historyDetail.analysis_result"
                :grading-result="historyDetail.grading_result"
              />
            </div>
            <div class="grade-detail-col result-panel">
              <GradeResultDetail
                v-if="historyDetail.grading_result"
                :grading-result="historyDetail.grading_result"
                :grading-id="historyDetail.grading_id"
                :analysis-result="historyDetail.analysis_result"
              />
              <div v-else class="empty-state" style="padding: 40px; text-align: center; color: #909399;">
                <p>无批改结果数据</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon style="margin-top: 16px;" closable @close="errorMsg = null" />
    </div>

    <!-- Answer editor dialog -->
    <el-dialog v-model="answerEditorVisible" title="编辑标准答案" width="700px" :close-on-click-modal="false">
      <input ref="answerImageInputRef" type="file" accept="image/*" style="display: none"
             @change="onAnswerImageSelect" />

      <!-- Extract progress -->
      <div v-if="answerExtracting" class="answer-extract-progress">
        <div v-for="(item, idx) in answerExtractLog" :key="idx" class="answer-extract-item"
             :class="{ active: idx === answerExtractLog.length - 1 }">
          <div class="progress-dot" :class="item.status">
            <el-icon v-if="item.status === 'done'" :size="14"><Check /></el-icon>
            <el-icon v-else-if="item.status === 'error'" :size="14"><Close /></el-icon>
            <div v-else class="progress-spinner"></div>
          </div>
          <span style="font-size: 13px; color: #606266;">{{ item.message }}</span>
        </div>
        <el-button size="small" type="danger" style="margin-top: 8px;" @click="cancelExtract">取消提取</el-button>
      </div>

      <!-- Answer list -->
      <div v-else>
        <div v-if="answerEditorEntries.length === 0" class="answer-editor-empty">
          <p style="color: #909399; margin: 0 0 12px;">暂无标准答案，可通过以下方式添加：</p>
        </div>
        <div v-else style="max-height: 40vh; overflow-y: auto;">
          <div v-for="(entry, idx) in answerEditorEntries" :key="idx" class="answer-editor-row">
            <el-input v-model="entry.problem_key" placeholder="题号" size="small" style="width: 80px;" />
            <el-input v-model="entry.correct_answer" placeholder="标准答案" size="small" style="flex: 1;" />
            <el-button text size="small" type="danger" @click="removeAnswerEntry(idx)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <el-divider style="margin: 12px 0;" />

        <!-- Action buttons -->
        <div class="answer-editor-actions">
          <el-button size="small" @click="addAnswerEntry">手动添加</el-button>
          <el-button size="small" @click="generateEmptyAnswers" :disabled="!selectedTemplateId">从版面生成</el-button>
          <el-button size="small" type="primary" @click="triggerAnswerImageInput">
            <el-icon style="margin-right: 4px;"><UploadFilled /></el-icon>从图片提取
          </el-button>
          <el-button size="small" type="warning" @click="answerTextInputVisible = !answerTextInputVisible">
            <el-icon style="margin-right: 4px;"><Edit /></el-icon>从文本提取
          </el-button>
        </div>

        <!-- Text input area (collapsible) -->
        <el-collapse-transition>
          <div v-if="answerTextInputVisible" class="answer-text-input-area">
            <el-input v-model="answerTextInput" type="textarea" :rows="6"
                      placeholder="粘贴答案文本，如：&#10;一、填空题&#10;1. 42&#10;2. 3x+5&#10;二、选择题&#10;1. A" />
            <el-button size="small" type="primary" style="margin-top: 8px;"
                       :disabled="!answerTextInput.trim()" @click="startExtractFromText">
              开始提取
            </el-button>
          </div>
        </el-collapse-transition>
      </div>

      <template #footer>
        <el-button @click="answerEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="answerEditorLoading" :disabled="answerExtracting" @click="saveAnswers">
          保存答案
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { PictureFilled, Close, Loading, Check, UploadFilled, Delete, ArrowDown, ArrowUp, Edit, EditPen, RefreshLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { connectGradeWithTemplateSSE, connectExtractAnswersSSE } from '@/utils/sse'
import type { SSEHandlers } from '@/utils/sse'
import { useTemplatesStore } from '@/stores/templates'
import { useAnalysisStore } from '@/stores/analysis'
import * as api from '@/api'
import TemplateSelector from '@/components/TemplateSelector.vue'
import GradingCanvas from '@/components/GradingCanvas.vue'
import GradeResultDetail from '@/components/GradeResultDetail.vue'
import AnnotationCanvas from '@/components/AnnotationCanvas.vue'
import ResultDetail from '@/components/ResultDetail.vue'
import { compressImage } from '@/utils/compressImage'
import type { TemplateListItem, TemplateDetail, StandardAnswer } from '@/types'

const route = useRoute()
const templatesStore = useTemplatesStore()
const analysisStore = useAnalysisStore()

const SUBJECT_KEY = 'grade_subject'
const STAGE_KEY = 'grade_stage'

function loadPersisted(key: string, fallback: string): string {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}
function persist(key: string, value: string) {
  try { localStorage.setItem(key, value) } catch { /* */ }
}

const subject = ref(loadPersisted(SUBJECT_KEY, '数学'))
const stage = ref(loadPersisted(STAGE_KEY, '小学'))
watch(subject, (v) => persist(SUBJECT_KEY, v))
watch(stage, (v) => persist(STAGE_KEY, v))

type Phase = 'select-template' | 'upload-students' | 'edit-template' | 'batch-grading' | 'batch-result' | 'history-detail'
const phase = ref<Phase>('select-template')

const errorMsg = ref<string | null>(null)

// History detail state
const historyDetail = ref<any>(null)
const historyLoading = ref(false)

// Template state
const selectedTemplateId = ref<string | null>(null)
const selectedTemplateItem = ref<TemplateListItem | null>(null)

// Student files
const studentFiles = ref<File[]>([])
const multiInputRef = ref<HTMLInputElement | null>(null)

// Batch grading state
const templateAbort = ref<(() => void) | null>(null)
const batchCompleted = ref(0)
const batchResults = ref<any[]>([])
const batchSummary = ref<any>(null)
const batchDetailStudent = ref<any>(null)

interface ProgressItem {
  phaseLabel: string
  message: string
  detail: string
  status: 'running' | 'done' | 'error'
}
const progressLog = ref<ProgressItem[]>([])

const answerEditorVisible = ref(false)
const answerEditorLoading = ref(false)
const answerEditorEntries = ref<StandardAnswer[]>([])

const answerExtracting = ref(false)
const answerExtractAbort = ref<(() => void) | null>(null)
const answerExtractLog = ref<{ message: string; status: 'running' | 'done' | 'error' }[]>([])
const answerTextInputVisible = ref(false)
const answerTextInput = ref('')
const answerImageInputRef = ref<HTMLInputElement | null>(null)

const selectedTemplateName = computed(() => selectedTemplateItem.value?.name ?? '')
const selectedTemplateAnswerCount = computed(() => {
  const json = selectedTemplateItem.value?.standard_answers_json
  if (!json) return 0
  try { return JSON.parse(json).length } catch { return 0 }
})

// Template preview state
const showTemplatePreview = ref(false)
const templatePreviewData = ref<TemplateDetail | null>(null)
const templatePreviewLoading = ref(false)
const previewImgWrapper = ref<HTMLElement | null>(null)
const previewReady = ref(false)
const previewDisplayW = ref(0)
const previewDisplayH = ref(0)

const sectionColors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399', '#9b59b6']

const templatePreviewImageUrl = computed(() => {
  if (!templatePreviewData.value) return ''
  return templatePreviewData.value.image_path || ''
})

const previewSections = computed(() => {
  if (!templatePreviewData.value?.layout_json) return []
  try {
    const layout = JSON.parse(templatePreviewData.value.layout_json)
    return layout.sections || []
  } catch { return [] }
})

const previewStats = computed(() => {
  const sections = previewSections.value
  if (!sections.length) return null
  const problems = sections.reduce((n: number, s: any) => n + (s.problems?.length || 0), 0)
  const areas = sections.reduce((n: number, s: any) =>
    n + (s.problems || []).reduce((m: number, p: any) => m + (p.answer_areas?.length || 0), 0), 0)
  return { sections: sections.length, problems, areas }
})

const previewAnswers = computed(() => {
  if (!templatePreviewData.value?.standard_answers_json) return []
  try { return JSON.parse(templatePreviewData.value.standard_answers_json) } catch { return [] }
})

function secAreas(sec: any) {
  return (sec.problems || []).flatMap((p: any) => p.answer_areas || [])
}

function onPreviewImgLoad(e: Event) {
  const img = e.target as HTMLImageElement
  previewDisplayW.value = img.clientWidth
  previewDisplayH.value = img.clientHeight
  previewReady.value = true
}

async function toggleTemplatePreview() {
  if (showTemplatePreview.value) {
    showTemplatePreview.value = false
    return
  }
  if (!selectedTemplateId.value) return
  if (templatePreviewData.value && templatePreviewData.value.template_id === selectedTemplateId.value) {
    showTemplatePreview.value = true
    return
  }
  templatePreviewLoading.value = true
  showTemplatePreview.value = true
  const data = await templatesStore.fetchTemplate(selectedTemplateId.value)
  templatePreviewData.value = data
  previewReady.value = false
  templatePreviewLoading.value = false
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}

// ===== Template selection =====

function onTemplateSelect(tpl: TemplateListItem) {
  selectedTemplateId.value = tpl.template_id
  selectedTemplateItem.value = tpl
  phase.value = 'upload-students'
}

function backToSelectTemplate() {
  selectedTemplateId.value = null
  selectedTemplateItem.value = null
  studentFiles.value = []
  showTemplatePreview.value = false
  templatePreviewData.value = null
  analysisStore.clearResult()
  phase.value = 'select-template'
}

async function enterEditMode() {
  if (!selectedTemplateId.value) return
  templatePreviewLoading.value = true
  const data = await templatesStore.fetchTemplate(selectedTemplateId.value)
  if (!data || !data.layout_json) {
    ElMessage.error('无法加载模板布局数据')
    templatePreviewLoading.value = false
    return
  }
  try {
    const layout = JSON.parse(data.layout_json)
    analysisStore.result = {
      run_id: data.run_id,
      paper_info: layout.paper_info || { title: data.name, grade: '', subject: data.subject },
      sections: layout.sections || [],
      original_image_url: data.image_path || '',
      image_width: data.image_width || 800,
      image_height: data.image_height || 600,
      created_at: data.created_at,
    }
    analysisStore.enterEdit()
    phase.value = 'edit-template'
  } catch {
    ElMessage.error('模板布局数据格式错误')
  }
  templatePreviewLoading.value = false
}

async function saveTemplateEdits() {
  await analysisStore.saveLayout()
  if (analysisStore.error) {
    ElMessage.error(analysisStore.error)
    return
  }
  templatePreviewData.value = null
  showTemplatePreview.value = false
  analysisStore.clearResult()
  phase.value = 'upload-students'
  ElMessage.success('标注已保存')
}

function cancelEditTemplate() {
  analysisStore.exitEdit()
  analysisStore.clearResult()
  phase.value = 'upload-students'
}

function openAnswerEditor() {
  if (!selectedTemplateItem.value) return
  const raw = selectedTemplateItem.value.standard_answers_json
  if (raw) {
    try { answerEditorEntries.value = JSON.parse(raw) } catch { answerEditorEntries.value = [] }
  } else {
    answerEditorEntries.value = []
  }
  answerExtracting.value = false
  answerExtractLog.value = []
  answerTextInputVisible.value = false
  answerTextInput.value = ''
  answerEditorVisible.value = true
}

async function saveAnswers() {
  if (!selectedTemplateId.value) return
  answerEditorLoading.value = true
  const result = await templatesStore.updateTemplate(selectedTemplateId.value, {
    standard_answers: answerEditorEntries.value,
  })
  answerEditorLoading.value = false
  if (result) {
    if (selectedTemplateItem.value) {
      selectedTemplateItem.value.standard_answers_json = JSON.stringify(answerEditorEntries.value)
    }
    templatePreviewData.value = null
    answerEditorVisible.value = false
    ElMessage.success('答案已保存')
  } else {
    ElMessage.error('保存答案失败')
  }
}

async function generateEmptyAnswers() {
  if (!selectedTemplateId.value) return
  let data = templatePreviewData.value
  if (!data || data.template_id !== selectedTemplateId.value) {
    data = await templatesStore.fetchTemplate(selectedTemplateId.value)
  }
  if (!data?.layout_json) {
    ElMessage.error('无法读取模板布局')
    return
  }
  try {
    const layout = JSON.parse(data.layout_json)
    const entries: StandardAnswer[] = []
    for (const sec of layout.sections || []) {
      const sectionHint = sec.title || `第${sec.section_number}大题`
      for (const p of sec.problems || []) {
        const existing = answerEditorEntries.value.find(
          e => e.problem_key === `${sec.section_number}.${p.problem_number}`
        )
        entries.push({
          problem_key: `${sec.section_number}.${p.problem_number}`,
          correct_answer: existing?.correct_answer ?? '',
          section_hint: sectionHint,
        })
      }
    }
    answerEditorEntries.value = entries
  } catch {
    ElMessage.error('版面数据格式错误')
  }
}

function addAnswerEntry() {
  answerEditorEntries.value.push({
    problem_key: '',
    correct_answer: '',
    section_hint: '',
  })
}

function removeAnswerEntry(idx: number) {
  answerEditorEntries.value.splice(idx, 1)
}

function triggerAnswerImageInput() {
  answerImageInputRef.value?.click()
}

async function onAnswerImageSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !selectedTemplateId.value) return
  if (answerImageInputRef.value) answerImageInputRef.value.value = ''
  const compressed = await compressImage(file).catch(() => file)
  startExtractAnswers(undefined, compressed)
}

function startExtractFromText() {
  if (!answerTextInput.value.trim() || !selectedTemplateId.value) return
  startExtractAnswers(answerTextInput.value.trim())
  answerTextInputVisible.value = false
  answerTextInput.value = ''
}

function startExtractAnswers(text?: string, image?: File) {
  if (!selectedTemplateId.value) return
  answerExtracting.value = true
  answerExtractLog.value = [{ message: '正在提交提取请求...', status: 'running' }]

  const handlers: SSEHandlers = {
    onStatus(data) {
      const last = answerExtractLog.value[answerExtractLog.value.length - 1]
      if (last && last.status === 'running') {
        last.message = data.message
      }
      answerExtractLog.value.push({ message: data.message, status: 'running' })
    },
    onAnswersExtracted(data) {
      const extracted = data.answers || []
      const merged = [...answerEditorEntries.value]
      for (const a of extracted) {
        const idx = merged.findIndex(e => e.problem_key === a.problem_key && a.problem_key)
        if (idx >= 0) {
          if (a.correct_answer) merged[idx].correct_answer = a.correct_answer
        } else {
          merged.push({ problem_key: a.problem_key || '', correct_answer: a.correct_answer || '', section_hint: a.section_hint || '' })
        }
      }
      answerEditorEntries.value = merged
    },
    onDone() {
      if (answerExtractLog.value.length > 0) {
        answerExtractLog.value[answerExtractLog.value.length - 1].status = 'done'
      }
      answerExtractLog.value.push({ message: '提取完成', status: 'done' })
      answerExtracting.value = false
    },
    onError(message) {
      answerExtractLog.value.push({ message, status: 'error' })
      answerExtracting.value = false
    },
  }

  answerExtractAbort.value = connectExtractAnswersSSE(selectedTemplateId.value, handlers, text, image)
}

function cancelExtract() {
  answerExtractAbort.value?.()
  answerExtracting.value = false
}

// ===== Student file upload =====

function triggerMultiInput() {
  multiInputRef.value?.click()
}

async function handleMultiFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (!files) return
  for (let i = 0; i < files.length; i++) {
    if (!files[i].type.startsWith('image/')) continue
    await addStudentFile(files[i])
  }
  if (multiInputRef.value) multiInputRef.value.value = ''
}

async function handleMultiDrop(e: DragEvent) {
  const files = e.dataTransfer?.files
  if (!files) return
  for (let i = 0; i < files.length; i++) {
    if (!files[i].type.startsWith('image/')) continue
    await addStudentFile(files[i])
  }
}

async function addStudentFile(f: File) {
  try {
    const compressed = await compressImage(f)
    studentFiles.value.push(compressed)
  } catch (e: any) {
    ElMessage.error(e.message || '图片处理失败')
  }
}

function removeStudentFile(index: number) {
  studentFiles.value.splice(index, 1)
}

// ===== Batch grading =====

function startBatchGrading() {
  if (!selectedTemplateId.value || studentFiles.value.length === 0) return
  phase.value = 'batch-grading'
  errorMsg.value = null
  progressLog.value = []
  batchResults.value = []
  batchCompleted.value = 0
  batchSummary.value = null
  batchDetailStudent.value = null

  const BATCH_PHASE_LABELS: Record<string, string> = {
    grading_student: '开始批改',
    batch_grading: '分批批改',
    batch_done: '批次完成',
    grading: 'AI 批改',
    student_done: '批改完成',
    warning: '警告',
  }

  const handlers: SSEHandlers = {
    onStatus(data) {
      if (data.phase === 'student_done') {
        batchCompleted.value++
      }
      const label = BATCH_PHASE_LABELS[data.phase] || data.phase
      const existing = progressLog.value[progressLog.value.length - 1]
      if (existing && existing.phaseLabel === label && existing.status === 'running') {
        existing.message = data.message
        if (data.student_index != null) {
          existing.detail = `第${data.student_index}/${data.total_students}份`
        }
        return
      }
      const isFinal = ['student_done', 'warning'].includes(data.phase)
      progressLog.value.push({
        phaseLabel: label,
        message: data.message,
        detail: data.student_index != null ? `第${data.student_index}/${data.total_students}份` : '',
        status: isFinal ? 'done' : 'running',
      })
    },
    onGradingResult(data) {
      batchResults.value.push(data)
    },
    onDone(data) {
      if (progressLog.value.length > 0) {
        progressLog.value[progressLog.value.length - 1].status = 'done'
      }
      batchSummary.value = data
      phase.value = 'batch-result'
    },
    onError(message) {
      errorMsg.value = message
    },
  }

  templateAbort.value = connectGradeWithTemplateSSE(selectedTemplateId.value, studentFiles.value, handlers)
}

function cancelBatchGrading() {
  templateAbort.value?.()
  phase.value = 'upload-students'
  progressLog.value = []
  batchResults.value = []
  batchCompleted.value = 0
}

function viewBatchStudentDetail(row: any) {
  batchDetailStudent.value = row
}

function continueGrading() {
  batchDetailStudent.value = null
  batchResults.value = []
  batchSummary.value = null
  studentFiles.value = []
  progressLog.value = []
  phase.value = 'upload-students'
}

function resetAll() {
  templateAbort.value?.()
  phase.value = 'select-template'
  selectedTemplateId.value = null
  selectedTemplateItem.value = null
  studentFiles.value = []
  batchResults.value = []
  batchSummary.value = null
  batchDetailStudent.value = null
  batchCompleted.value = 0
  progressLog.value = []
  errorMsg.value = null
  showTemplatePreview.value = false
  templatePreviewData.value = null
  historyDetail.value = null
  historyLoading.value = false
  analysisStore.clearResult()
}

// ===== History loading from query param =====

watch(() => route.query.grading_id, async (gid) => {
  if (!gid || typeof gid !== 'string') return
  historyLoading.value = true
  phase.value = 'history-detail'
  try {
    const resp = await api.getGradingResult(gid)
    historyDetail.value = resp
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail ?? e.message ?? '加载批改记录失败'
  } finally {
    historyLoading.value = false
  }
}, { immediate: true })

onMounted(() => {
  console.log('[init] subject=', subject.value, 'stage=', stage.value)
})
</script>

<style scoped>
.grade-page { max-width: 1400px; }

.grade-controls {
  margin-bottom: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.control-row {
  display: flex;
  gap: 32px;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  white-space: nowrap;
}

/* Step bar */
.step-bar {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: 20px;
  padding: 12px 24px;
  background: #f5f7fa;
  border-radius: 8px;
}

.step {
  display: flex;
  align-items: center;
  gap: 6px;
  opacity: 0.4;
  transition: opacity 0.2s;
}

.step.active { opacity: 1; }
.step.done { opacity: 0.7; }

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e4e7ed;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step.active .step-num { background: #409eff; }
.step.done .step-num { background: #67c23a; }

.step-text {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.step.active .step-text { color: #409eff; font-weight: 600; }

.step-sep {
  flex: 1;
  height: 2px;
  background: #e4e7ed;
  margin: 0 12px;
  transition: background 0.2s;
}

.step-sep.done { background: #67c23a; }

/* Template info bar */
.template-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f0f9eb;
  border-radius: 8px;
  margin-bottom: 16px;
}

/* Template preview */
.template-preview-panel {
  margin-bottom: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.preview-split {
  display: flex;
  min-height: 0;
}

.preview-canvas-col {
  flex: 1;
  min-width: 0;
  background: #f5f5f5;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 12px;
}

.preview-img-wrapper {
  position: relative;
  display: inline-block;
  max-width: 100%;
}

.preview-img {
  max-width: 100%;
  max-height: 50vh;
  display: block;
  border-radius: 4px;
}

.preview-svg {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.preview-area-rect {
  stroke-width: 2;
  rx: 2;
  ry: 2;
}

.preview-detail-col {
  width: 300px;
  max-height: 50vh;
  overflow-y: auto;
  padding: 14px;
  border-left: 1px solid #ebeef5;
  font-size: 13px;
}

.preview-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  color: #606266;
  font-size: 12px;
}

.preview-section {
  margin-bottom: 12px;
}

.preview-section-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  padding: 4px 8px;
  border-left: 3px solid #409eff;
  margin-bottom: 6px;
  background: #f9f9f9;
  border-radius: 0 4px 4px 0;
}

.preview-problem {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px 3px 16px;
  color: #606266;
}

.preview-problem-num {
  min-width: 30px;
  font-weight: 500;
  color: #303133;
  font-size: 12px;
}

.preview-problem-text {
  flex: 1;
  color: #606266;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-area-count {
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
}

.preview-answers {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
}

.preview-answer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 8px 2px 16px;
  font-size: 12px;
}

/* Upload area */
.upload-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
  background: #fafafa;
}
.upload-area:hover { border-color: #409eff; background: #f0f7ff; }
.upload-icon { font-size: 40px; color: #c0c4cc; }
.upload-text { font-size: 14px; color: #606266; margin-top: 8px; }
.upload-hint { font-size: 12px; color: #909399; margin-top: 4px; }

.batch-file-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}
.batch-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
}
.batch-file-name { flex: 1; color: #303133; }
.batch-file-size { color: #909399; font-size: 12px; }

/* Batch results */
.batch-result-area { margin-top: 16px; }
.batch-summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f0f9eb;
  border-radius: 8px;
}

/* Progress panel */
.progress-panel {
  margin-top: 16px;
  padding: 24px;
  background: #f5f7fa;
  border-radius: 8px;
}
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
.progress-item.active { opacity: 1; }
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
.progress-item.active .progress-dot { background: #409eff; }
.progress-dot.done { background: #67c23a; }
.progress-dot.error { background: #f56c6c; }
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
.progress-detail {
  font-size: 12px;
  color: #909399;
}

/* Result detail layout */
.split-layout { display: flex; }
.grade-canvas-col {
  flex: 1;
  min-width: 400px;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.grade-detail-col {
  width: 420px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 16px;
  border-left: 1px solid #ebeef5;
}

/* Edit toolbar */
.edit-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #ecf5ff;
  border-radius: 8px;
}

/* Answer editor */
.answer-editor-empty {
  text-align: center;
  padding: 16px 0 4px;
}
.answer-editor-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}
.answer-editor-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.answer-text-input-area {
  margin-top: 10px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}
.answer-extract-progress {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}
.answer-extract-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  opacity: 0.5;
}
.answer-extract-item.active { opacity: 1; }
</style>
