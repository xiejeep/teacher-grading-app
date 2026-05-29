import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { TemplateListItem, TemplateDetail, StandardAnswer } from '@/types'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 360_000,
})

export const useTemplatesStore = defineStore('templates', () => {
  const loading = ref(false)
  const templates = ref<TemplateListItem[]>([])
  const currentTemplate = ref<TemplateDetail | null>(null)
  const error = ref<string | null>(null)

  const filteredTemplates = computed(() => {
    return (subject?: string, stage?: string) =>
      templates.value.filter(t => {
        if (subject && t.subject !== subject) return false
        if (stage && t.stage !== stage) return false
        return true
      })
  })

  async function fetchTemplates(subject?: string, stage?: string) {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (subject) params.subject = subject
      if (stage) params.stage = stage
      const { data } = await api.get<TemplateListItem[]>('/templates', { params })
      templates.value = data
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '加载模板列表失败'
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplate(templateId: string) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get<TemplateDetail>(`/templates/${templateId}`)
      currentTemplate.value = data
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '加载模板失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateTemplate(
    templateId: string,
    fields: { name?: string; standard_answers?: StandardAnswer[] }
  ) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.put<TemplateDetail>(`/templates/${templateId}`, fields)
      currentTemplate.value = data
      const idx = templates.value.findIndex(t => t.template_id === templateId)
      if (idx >= 0) {
        templates.value[idx] = {
          ...templates.value[idx],
          name: data.name,
          updated_at: data.updated_at,
        }
      }
      return data
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '更新模板失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteTemplate(templateId: string) {
    loading.value = true
    error.value = null
    try {
      await api.delete(`/templates/${templateId}`)
      templates.value = templates.value.filter(t => t.template_id !== templateId)
      if (currentTemplate.value?.template_id === templateId) {
        currentTemplate.value = null
      }
      return true
    } catch (e: any) {
      error.value = e?.response?.data?.detail ?? e.message ?? '删除模板失败'
      return false
    } finally {
      loading.value = false
    }
  }

  function clear() {
    currentTemplate.value = null
    error.value = null
  }

  return {
    loading,
    templates,
    currentTemplate,
    error,
    filteredTemplates,
    fetchTemplates,
    fetchTemplate,
    updateTemplate,
    deleteTemplate,
    clear,
  }
})
