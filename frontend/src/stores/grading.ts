import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type {
  GradingResponse, GradingResult, GradedSection, GradedProblem, AreaGrading, StandardAnswer
} from '@/types'
import * as api from '@/api'

export const useGradingStore = defineStore('grading', () => {
  const loading = ref(false)
  const result = ref<GradingResponse | null>(null)
  const error = ref<string | null>(null)

  const analysisResult = computed(() => result.value?.analysis_result ?? null)
  const gradingResult = computed(() => result.value?.grading_result ?? null)
  const standardAnswers = computed(() => result.value?.standard_answers ?? [])

  function getImageUrl(): string {
    return result.value?.analysis_result?.original_image_url ?? ''
  }

  async function analyzeAndGrade(params: {
    file: File
    subject: string
    stage: string
    standardAnswersJson?: string
    standardAnswerImage?: File | null
  }) {
    loading.value = true
    error.value = null
    try {
      const data = await api.gradeAnalyze(
        params.file,
        params.subject,
        params.stage,
        params.standardAnswersJson,
        params.standardAnswerImage,
      )
      result.value = data
      if (!data.grading_result && !data.grading_result) {
        error.value = '批改未返回结果，可能是 AI 调用失败'
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '批改请求失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loadGrading(gradingId: string) {
    loading.value = true
    error.value = null
    try {
      result.value = await api.getGradingResult(gradingId)
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '加载批改结果失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function clear() {
    result.value = null
    error.value = null
  }

  function getAreaGrading(sectionIdx: number, problemIdx: number, areaIdx: number): AreaGrading | null {
    const sections = gradingResult.value?.sections
    if (!sections || sectionIdx >= sections.length) return null
    const problems = sections[sectionIdx].problems
    if (problemIdx >= problems.length) return null
    const areas = problems[problemIdx].area_gradings
    if (areaIdx >= areas.length) return null
    return areas[areaIdx]
  }

  function getProblemGrading(sectionIdx: number, problemIdx: number): GradedProblem | null {
    const sections = gradingResult.value?.sections
    if (!sections || sectionIdx >= sections.length) return null
    const problems = sections[sectionIdx].problems
    if (problemIdx >= problems.length) return null
    return problems[problemIdx]
  }

  return {
    loading,
    result,
    error,
    analysisResult,
    gradingResult,
    standardAnswers,
    getImageUrl,
    analyzeAndGrade,
    loadGrading,
    clear,
    getAreaGrading,
    getProblemGrading,
  }
})