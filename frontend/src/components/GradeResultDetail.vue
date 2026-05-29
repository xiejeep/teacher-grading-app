<template>
  <div v-if="!gradingResult" class="empty-state">
    <el-icon :size="32" color="#c0c4cc"><Document /></el-icon>
    <p>暂无批改结果</p>
  </div>
  <div v-else>
    <el-collapse v-model="activeSections" class="section-collapse">
      <el-collapse-item
        v-for="(section, si) in gradingResult.sections"
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
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <div style="margin-top: 16px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; text-align: center;">
      <span style="font-size: 16px; font-weight: 600;">
        答对：
        <span :style="{ color: scorePercent >= 60 ? '#67C23A' : '#F56C6C' }">
          {{ gradingResult.correct_count }} / {{ gradingResult.total_areas }} 个作答区
        </span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Document, CircleCheck, CircleClose, QuestionFilled } from '@element-plus/icons-vue'
import type { GradingResult, AnalysisResponse, GradedProblem } from '@/types'

const props = defineProps<{
  gradingResult: GradingResult
  analysisResult: AnalysisResponse | null
}>()

const activeSections = ref<number[]>([])

const scorePercent = computed(() => {
  if (!props.gradingResult.total_areas) return 0
  return Math.round((props.gradingResult.correct_count / props.gradingResult.total_areas) * 100)
})

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
</style>
