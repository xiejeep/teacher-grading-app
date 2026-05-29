<template>
  <div class="result-panel">
    <div v-if="!result" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Picture /></el-icon>
      <p>上传试卷图片并点击"开始分析"查看结果</p>
    </div>

    <template v-else>
      <div class="panel-header">
        <h3>{{ result.paper_info?.title || '试卷分析结果' }}</h3>
        <el-tag v-if="result.paper_info?.subject" size="small" type="info">
          {{ result.paper_info.subject }}
        </el-tag>
        <el-tag v-if="result.paper_info?.grade" size="small" type="info" style="margin-left: 4px">
          {{ result.paper_info.grade }}
        </el-tag>
      </div>
      <el-divider style="margin: 12px 0" />

      <el-collapse
        v-for="(section, si) in result.sections"
        :key="si"
        class="section-collapse"
      >
        <el-collapse-item>
          <template #title>
            <span
              class="section-title"
              @mouseenter="store.highlightSection(si)"
              @mouseleave="store.highlightSection(null)"
            >
              {{ section.title || `第${section.section_number}大题` }}
            </span>
            <el-tag size="small" style="margin-left: 8px">
              {{ section.problems?.length || 0 }} 小题
            </el-tag>
          </template>

          <div
            v-for="(problem, pi) in section.problems"
            :key="pi"
            class="problem-row"
            :class="{ highlighted: highlightedKey === `${si}-${pi}` }"
            @mouseenter="onProblemHover(si, pi)"
            @mouseleave="onProblemLeave"
          >
            <div class="problem-header">
              <strong>{{ problem.problem_number }}.</strong>
              <span class="problem-text">{{ problem.text || '(无文字)' }}</span>
            </div>
            <div class="problem-meta">
              <span
                v-for="(blank, bi) in problem.blanks"
                :key="bi"
                class="blank-tag"
                @mouseenter.stop="onBlankHover(si, pi, bi)"
                @mouseleave.stop="store.highlightBlank(null)"
              >
                {{ blank.text || '()' }}
              </span>
              <span
                v-for="(area, ai) in problem.answer_areas"
                :key="'a' + ai"
                class="blank-tag"
                style="background: #ecf5ff; color: #409eff; border-color: #409eff"
                @mouseenter.stop="onAreaHover(si, pi, ai)"
              >
                {{ area.type }}
              </span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <el-divider />
      <div class="raw-json">
        <el-button text size="small" @click="showRaw = !showRaw">
          {{ showRaw ? '收起' : '展开' }}原始 JSON
        </el-button>
        <pre v-if="showRaw" class="json-pre">{{ JSON.stringify(result, null, 2) }}</pre>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { useAnalysisStore } from '@/stores/analysis'
import type { AnalysisResponse } from '@/types'

defineProps<{ result: AnalysisResponse | null }>()

const store = useAnalysisStore()
const showRaw = ref(false)

const highlightedKey = computed(() => store.highlightedProblem)

function onProblemHover(si: number, pi: number) {
  store.highlightProblem(`${si}-${pi}`)
  emit('hoverProblem', `${si}-${pi}`)
}

function onProblemLeave() {
  store.highlightProblem(null)
  emit('hoverProblem', null)
}

function onBlankHover(si: number, pi: number, bi: number) {
  store.highlightBlank(`${si}-${pi}-${bi}`)
}

function onAreaHover(si: number, pi: number, ai: number) {
  store.highlightBlank(`${si}-${pi}-area-${ai}`)
}

const emit = defineEmits<{
  hoverProblem: [key: string | null]
}>()
</script>

<style scoped>
.panel-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.panel-header h3 {
  font-size: 16px;
  margin: 0;
}

.problem-header {
  display: flex;
  gap: 4px;
  align-items: baseline;
}

.problem-text {
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 360px;
}

.problem-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.json-pre {
  margin-top: 8px;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
