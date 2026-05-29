<template>
  <div class="canvas-wrapper">
    <div v-if="!imageUrl" class="empty-canvas">
      <el-icon :size="48" color="#c0c4cc"><Picture /></el-icon>
    </div>
    <div v-else class="grading-canvas-container" ref="containerRef">
      <img
        ref="imgRef"
        :src="imageUrl"
        :alt="'学生答卷'"
        style="max-width: 100%; display: block;"
        @load="syncSize"
      />
      <svg
        v-if="ready"
        class="grading-svg-overlay"
        :width="displayW"
        :height="displayH"
        :viewBox="`0 0 ${displayW} ${displayH}`"
        xmlns="http://www.w3.org/2000/svg"
        style="position: absolute; top: 0; left: 0; pointer-events: none;"
      >
        <template v-for="(info, idx) in areaInfos" :key="idx">
          <rect
            v-if="info.gradingStatus === 'pending'"
            :x="info.x"
            :y="info.y"
            :width="info.w || 20"
            :height="info.h || 16"
            fill="rgba(144, 147, 153, 0.15)"
            stroke="#909399"
            :stroke-width="1"
            rx="2"
            stroke-dasharray="4 2"
          />
          <image
            v-if="info.gradingStatus === 'correct'"
            :href="'/duigou.svg'"
            :x="info.centerX - info.iconSize / 2"
            :y="info.centerY - info.iconSize / 2"
            :width="info.iconSize"
            :height="info.iconSize"
          />
          <image
            v-else-if="info.gradingStatus === 'wrong'"
            :href="'/cuowu.svg'"
            :x="info.centerX - info.iconSize / 2"
            :y="info.centerY - info.iconSize / 2"
            :width="info.iconSize"
            :height="info.iconSize"
          />
        </template>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import type { AnalysisResponse, GradingResult, BBox } from '@/types'

const props = defineProps<{
  imageUrl: string
  imageWidth: number
  imageHeight: number
  analysisResult: AnalysisResponse | null
  gradingResult: GradingResult | null
}>()

const containerRef = ref<HTMLElement | null>(null)
const imgRef = ref<HTMLImageElement | null>(null)
const ready = ref(false)
const displayW = ref(0)
const displayH = ref(0)

watch(() => props.imageUrl, () => {
  ready.value = false
})

onMounted(() => {
  const img = imgRef.value
  if (img && img.complete && props.imageUrl) {
    syncSize()
  }
})

function syncSize() {
  const img = imgRef.value
  if (!img) return
  displayW.value = img.clientWidth
  displayH.value = img.clientHeight
  ready.value = true
}

type GradingStatus = 'correct' | 'wrong' | 'pending'

interface AreaInfo {
  x: number
  y: number
  w: number
  h: number
  centerX: number
  centerY: number
  iconSize: number
  gradingStatus: GradingStatus
}

function calcIconSize(w: number, h: number): number {
  const raw = Math.max(Math.min(w, h), 18)
  return Math.min(raw, 48)
}

const areaInfos = computed<AreaInfo[]>(() => {
  const result: AreaInfo[] = []
  const analysis = props.analysisResult
  const grading = props.gradingResult
  if (!analysis || !displayW.value || !props.imageWidth) return result

  const scaleX = displayW.value / props.imageWidth
  const scaleY = displayH.value / props.imageHeight

  if (!grading) {
    for (const section of analysis.sections) {
      for (const problem of section.problems) {
        for (const area of problem.answer_areas) {
          const b = area.bbox
          const px = b.x * props.imageWidth * scaleX
          const py = b.y * props.imageHeight * scaleY
          const pw = (b.w * props.imageWidth * scaleX) || 20
          const ph = (b.h * props.imageHeight * scaleY) || 16
          result.push({
            x: px, y: py, w: pw, h: ph,
            centerX: px + pw / 2,
            centerY: py + ph / 2,
            iconSize: calcIconSize(pw, ph),
            gradingStatus: 'pending',
          })
        }
      }
    }
    return result
  }

  for (const section of grading.sections) {
    for (const problem of section.problems) {
      const si = section._orig_section_idx ?? (section.section_number - 1)
      const pi = problem.problem_number - 1
      const analysisSection = analysis.sections[si]
      if (!analysisSection) continue
      const analysisProblem = analysisSection.problems[pi]
      if (!analysisProblem) continue

      for (const areaGrading of problem.area_gradings) {
        const ai = areaGrading.area_index
        const answerAreas = analysisProblem.answer_areas
        if (!answerAreas || ai >= answerAreas.length) continue
        const answerArea = answerAreas[ai]
        if (!answerArea) continue

        const b = answerArea.bbox
        const px = b.x * props.imageWidth * scaleX
        const py = b.y * props.imageHeight * scaleY
        const pw = (b.w * props.imageWidth * scaleX) || 20
        const ph = (b.h * props.imageHeight * scaleY) || 16
        const isCorrect = areaGrading.is_correct

        result.push({
          x: px, y: py, w: pw, h: ph,
          centerX: px + pw / 2,
          centerY: py + ph / 2,
          iconSize: calcIconSize(pw, ph),
          gradingStatus: isCorrect === true ? 'correct' : 'wrong',
        })
      }
    }
  }

  return result
})
</script>

<style scoped>
.grading-canvas-container {
  position: relative;
  display: inline-block;
}

.grading-svg-overlay {
  pointer-events: none;
}
</style>
