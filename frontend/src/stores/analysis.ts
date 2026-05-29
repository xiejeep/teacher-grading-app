import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AnalysisResponse, Section, BBox, AnswerArea } from '@/types'
import * as api from '@/api'

export interface AreaKey {
  sectionIdx: number
  problemIdx: number
  areaIdx: number
}

export const useAnalysisStore = defineStore('analysis', () => {
  const loading = ref(false)
  const result = ref<AnalysisResponse | null>(null)
  const error = ref<string | null>(null)
  const highlightedSection = ref<number | null>(null)
  const highlightedProblem = ref<string | null>(null)
  const highlightedBlank = ref<string | null>(null)

  const editMode = ref(false)
  const drawMode = ref(false)
  const selectedArea = ref<AreaKey | null>(null)
  const saving = ref(false)
  const originalSections = ref<Section[] | null>(null)

  async function analyze(file: File) {
    loading.value = true
    error.value = null
    result.value = null
    exitEdit()
    try {
      result.value = await api.uploadAndAnalyze(file)
    } catch (e: any) {
      error.value = e.response?.data?.detail ?? e.message ?? '分析失败'
    } finally {
      loading.value = false
    }
  }

  async function loadResult(runId: string) {
    loading.value = true
    error.value = null
    exitEdit()
    try {
      result.value = await api.getResult(runId)
    } catch (e: any) {
      error.value = e.response?.data?.detail ?? e.message ?? '加载失败'
    } finally {
      loading.value = false
    }
  }

  function clearResult() {
    result.value = null
    error.value = null
    highlightedSection.value = null
    highlightedProblem.value = null
    exitEdit()
  }

  function highlightSection(index: number | null) {
    highlightedSection.value = index
  }

  function highlightProblem(problemIndex: string | null) {
    highlightedProblem.value = problemIndex
  }

  function highlightBlank(key: string | null) {
    highlightedBlank.value = key
  }

  function enterEdit() {
    if (!result.value) return
    originalSections.value = JSON.parse(JSON.stringify(result.value.sections))
    editMode.value = true
    drawMode.value = false
    selectedArea.value = null
  }

  function exitEdit() {
    if (originalSections.value && result.value) {
      result.value.sections = originalSections.value
    }
    editMode.value = false
    drawMode.value = false
    selectedArea.value = null
    originalSections.value = null
  }

  function toggleDrawMode() {
    drawMode.value = !drawMode.value
    selectedArea.value = null
  }

  function selectArea(key: AreaKey | null) {
    selectedArea.value = key
  }

  function addArea(sectionIdx: number, problemIdx: number, bbox: BBox, type: AnswerArea['type']) {
    if (!result.value) return
    const section = result.value.sections[sectionIdx]
    if (!section) return
    const problem = section.problems[problemIdx]
    if (!problem) return

    const newArea: AnswerArea = { type, bbox }
    problem.answer_areas.push(newArea)
  }

  function updateArea(key: AreaKey, bbox: BBox) {
    if (!result.value) return
    const area = getAreaByKey(key)
    if (area) area.bbox = bbox
  }

  function deleteArea(key: AreaKey) {
    if (!result.value) return
    const section = result.value.sections[key.sectionIdx]
    if (!section) return
    section.problems[key.problemIdx]?.answer_areas.splice(key.areaIdx, 1)
    if (selectedArea.value && selectedArea.value.sectionIdx === key.sectionIdx &&
        selectedArea.value.problemIdx === key.problemIdx &&
        selectedArea.value.areaIdx === key.areaIdx) {
      selectedArea.value = null
    }
  }

  function deleteSelectedArea() {
    if (selectedArea.value) {
      deleteArea(selectedArea.value)
    }
  }

  function getAreaByKey(key: AreaKey): AnswerArea | null {
    if (!result.value) return null
    const section = result.value.sections[key.sectionIdx]
    if (!section) return null
    const problem = section.problems[key.problemIdx]
    if (!problem || !problem.answer_areas[key.areaIdx]) return null
    return problem.answer_areas[key.areaIdx]
  }

  async function saveLayout() {
    if (!result.value) return
    saving.value = true
    try {
      const layout = {
        paper_info: result.value.paper_info,
        sections: result.value.sections,
      }
      const updated = await api.updateLayout(result.value.run_id, layout)
      result.value = updated
      originalSections.value = null
      editMode.value = false
    } catch (e: any) {
      error.value = e.response?.data?.detail ?? e.message ?? '保存失败'
    } finally {
      saving.value = false
    }
  }

  function getAllAreas(): { key: AreaKey; area: AnswerArea }[] {
    if (!result.value) return []
    const areas: { key: AreaKey; area: AnswerArea }[] = []
    result.value.sections.forEach((section, si) => {
      section.problems.forEach((problem, pi) => {
        problem.answer_areas.forEach((area, ai) => {
          areas.push({ key: { sectionIdx: si, problemIdx: pi, areaIdx: ai }, area })
        })
      })
    })
    return areas
  }

  function getOriginalImageUrl(): string {
    if (!result.value) return ''
    return result.value.original_image_url
  }

  return {
    loading,
    result,
    error,
    highlightedSection,
    highlightedProblem,
    highlightedBlank,
    editMode,
    drawMode,
    selectedArea,
    saving,
    analyze,
    loadResult,
    clearResult,
    highlightSection,
    highlightProblem,
    highlightBlank,
    enterEdit,
    exitEdit,
    toggleDrawMode,
    selectArea,
    addArea,
    updateArea,
    deleteArea,
    deleteSelectedArea,
    getAreaByKey,
    saveLayout,
    getAllAreas,
    getOriginalImageUrl,
  }
})
