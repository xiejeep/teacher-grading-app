<template>
  <div v-if="!gradingResult" class="empty-state">
    <el-icon :size="32" color="#c0c4cc"><Document /></el-icon>
    <p>暂无批改结果</p>
  </div>
  <div v-else>
    <el-collapse v-model="activeSections" class="section-collapse">
      <el-collapse-item
        v-for="(section, si) in displayResult.sections"
        :key="si"
        :name="si"
      >
        <template #title>
          <div style="display: flex; align-items: center; gap: 8px; width: 100%;">
            <span class="section-title">{{ section.title || '第' + section.section_number + '大题' }}</span>
            <span style="font-size: 12px; color: #909399;">{{ section.problems.length }} 题</span>
          </div>
        </template>

        <div
          v-for="(problem, pi) in section.problems"
          :key="pi"
          class="graded-problem-row"
        >
          <div class="problem-header">
            <span class="problem-number">{{ section.section_number }}.{{ problem.problem_number }}</span>
            <span class="problem-text">{{ problem.problem_text || getProblemText(section._orig_section_idx ?? si, pi) || '' }}</span>
            <el-tag
              :type="problem.problem_total_score === problem.problem_max_score ? 'success' : 'danger'"
              size="small"
              effect="plain"
            >
              {{ problem.problem_total_score }}/{{ problem.problem_max_score }}
            </el-tag>
          </div>

          <div v-for="(ag, ai) in problem.area_gradings" :key="ai" class="area-grading-row">
            <div class="ag-left">
              <el-icon :size="16" :color="ag.is_correct === true ? '#67C23A' : ag.is_correct === false ? '#F56C6C' : '#909399'">
                <CircleCheck v-if="ag.is_correct === true" />
                <CircleClose v-else-if="ag.is_correct === false" />
                <QuestionFilled v-else />
              </el-icon>
              <span class="ag-label">作答区 {{ ag.area_index + 1 }}</span>
            </div>
            <div class="ag-detail">
              <div v-if="ag.student_answer" class="ag-row">
                <span class="ag-tag student">学生答案</span>
                <span class="ag-value">{{ ag.student_answer }}</span>
              </div>
              <div v-if="ag.correct_answer" class="ag-row">
                <span class="ag-tag correct">正确答案</span>
                <span class="ag-value">{{ ag.correct_answer }}</span>
              </div>
              <div v-if="ag.comment" class="ag-row">
                <span class="ag-tag comment">评语</span>
                <span class="ag-value" style="color: #909399;">{{ ag.comment }}</span>
              </div>
            </div>
            <div class="ag-actions">
              <el-button text size="small" type="primary" @click="openEditDialog(si, pi, ai)">修正</el-button>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <div style="margin-top: 16px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; text-align: center;">
      <span style="font-size: 16px; font-weight: 600;">
        答对：
        <span :style="{ color: scorePercent >= 60 ? '#67C23A' : '#F56C6C' }">
          {{ displayResult.correct_count }} / {{ displayResult.total_areas }} 个作答区
        </span>
      </span>
    </div>

    <el-dialog v-model="dialogVisible" title="修正作答区" width="480px" append-to-body>
      <el-form v-if="editForm" label-position="top" size="small">
        <el-form-item label="批改结果">
          <el-radio-group v-model="editForm.is_correct">
            <el-radio :value="true" style="color: #67C23A;">正确</el-radio>
            <el-radio :value="false" style="color: #F56C6C;">错误</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="得分">
              <el-input-number v-model="editForm.score" :min="0" :max="editForm.max_score" :precision="1" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="满分">
              <el-input-number v-model="editForm.max_score" :min="0" :precision="1" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="学生答案">
          <el-input v-model="editForm.student_answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="正确答案">
          <el-input v-model="editForm.correct_answer" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="editForm.comment" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false" :disabled="saving">取消</el-button>
        <el-button type="primary" @click="confirmEdit" :loading="saving">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { Document, CircleCheck, CircleClose, QuestionFilled } from '@element-plus/icons-vue'
import type { GradingResult, AnalysisResponse } from '@/types'
import { updateGradingResult } from '@/api'

const props = defineProps<{
  gradingResult: GradingResult
  gradingId?: string
  analysisResult: AnalysisResponse | null
}>()

const emit = defineEmits<{
  saved: [result: GradingResult]
}>()

function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

const activeSections = ref<number[]>([])
const saving = ref(false)

const displayResult = reactive<GradingResult>(deepClone(props.gradingResult))

watch(() => props.gradingResult, (val) => {
  if (val && !saving.value) {
    Object.assign(displayResult, deepClone(val))
  }
}, { deep: true })

const scorePercent = computed(() => {
  if (!displayResult.total_areas) return 0
  return Math.round((displayResult.correct_count / displayResult.total_areas) * 100)
})

const dialogVisible = ref(false)
const editForm = ref<{
  sectionIdx: number
  problemIdx: number
  areaIdx: number
  is_correct: boolean | null
  score: number
  max_score: number
  student_answer: string
  correct_answer: string
  comment: string
} | null>(null)

function openEditDialog(si: number, pi: number, ai: number) {
  const ag = displayResult.sections[si].problems[pi].area_gradings[ai]
  editForm.value = {
    sectionIdx: si,
    problemIdx: pi,
    areaIdx: ai,
    is_correct: ag.is_correct,
    score: ag.score,
    max_score: ag.max_score,
    student_answer: ag.student_answer,
    correct_answer: ag.correct_answer,
    comment: ag.comment,
  }
  dialogVisible.value = true
}

function recalcProblem(si: number, pi: number) {
  const problem = displayResult.sections[si].problems[pi]
  let total = 0
  let maxTotal = 0
  for (const ag of problem.area_gradings) {
    total += ag.max_score > 0 ? ag.score : 0
    maxTotal += ag.max_score
  }
  problem.problem_total_score = total
  problem.problem_max_score = maxTotal
}

function recalcAll() {
  let totalScore = 0
  let totalMax = 0
  let correct = 0
  let areas = 0
  for (const sec of displayResult.sections) {
    for (const p of sec.problems) {
      totalScore += p.problem_total_score
      totalMax += p.problem_max_score
      for (const ag of p.area_gradings) {
        areas += 1
        if (ag.is_correct === true) correct += 1
      }
    }
  }
  displayResult.total_score = totalScore
  displayResult.total_max_score = totalMax
  displayResult.correct_count = correct
  displayResult.total_areas = areas
}

async function confirmEdit() {
  if (!editForm.value) return
  if (!props.gradingId) {
    console.warn('gradingId is missing, update will not be saved')
    return
  }
  const { sectionIdx, problemIdx, areaIdx, ...fields } = editForm.value
  const ag = displayResult.sections[sectionIdx].problems[problemIdx].area_gradings[areaIdx]
  Object.assign(ag, fields)
  recalcProblem(sectionIdx, problemIdx)
  recalcAll()
  dialogVisible.value = false

  saving.value = true
  try {
    const resp = await updateGradingResult(props.gradingId, displayResult)
    if (resp.grading_result) {
      Object.assign(displayResult, deepClone(resp.grading_result))
    }
    emit('saved', displayResult)
  } catch (e: any) {
    console.error('保存失败:', e)
  } finally {
    saving.value = false
  }
}

function getProblemText(sectionIdx: number, problemIdx: number): string {
  if (!props.analysisResult) return ''
  const section = props.analysisResult.sections[sectionIdx]
  if (!section) return ''
  const problem = section.problems[problemIdx]
  if (!problem) return ''
  return problem.text?.slice(0, 80) ?? ''
}
</script>

<style scoped>
.graded-problem-row {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.graded-problem-row:last-child {
  border-bottom: none;
}

.problem-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.problem-number {
  font-weight: 600;
  color: #303133;
  font-size: 13px;
  min-width: 28px;
}

.problem-text {
  flex: 1;
  font-size: 13px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.area-grading-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0 6px 36px;
}

.ag-left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 80px;
  flex-shrink: 0;
}

.ag-label {
  font-size: 12px;
  color: #909399;
}

.ag-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ag-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.ag-tag {
  font-size: 11px;
  padding: 1px 5px;
  border-radius: 3px;
  flex-shrink: 0;
}

.ag-tag.student {
  background: #ecf5ff;
  color: #409eff;
}

.ag-tag.correct {
  background: #f0f9eb;
  color: #67C23A;
}

.ag-tag.comment {
  background: #fdf6ec;
  color: #e6a23c;
}

.ag-value {
  font-size: 13px;
  color: #303133;
}

.ag-actions {
  flex-shrink: 0;
  align-self: center;
  margin-left: auto;
  padding-left: 8px;
}
</style>
