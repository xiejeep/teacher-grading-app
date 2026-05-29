import axios from 'axios'
import type {
  AnalysisResponse, HistoryItem, LayoutResult,
  GradingResponse, GradingHistoryItem, GradingResult,
  PromptResponse, StandardAnswer
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 360_000,
})

export async function uploadAndAnalyze(file: File): Promise<AnalysisResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<AnalysisResponse>('/analyze', form)
  return data
}

export async function getHistory(): Promise<HistoryItem[]> {
  const { data } = await api.get<HistoryItem[]>('/history')
  return data
}

export async function getResult(runId: string): Promise<AnalysisResponse> {
  const { data } = await api.get<AnalysisResponse>(`/result/${runId}`)
  return data
}

export async function updateLayout(runId: string, layout: LayoutResult): Promise<AnalysisResponse> {
  const { data } = await api.put<AnalysisResponse>(`/result/${runId}/layout`, layout)
  return data
}

export async function deleteResult(runId: string): Promise<void> {
  await api.delete(`/result/${runId}`)
}

export async function gradeAnalyze(
  file: File,
  subject: string,
  stage: string,
  standardAnswersJson?: string,
  standardAnswerImage?: File | null,
): Promise<GradingResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('subject', subject)
  form.append('stage', stage)
  if (standardAnswersJson) {
    form.append('standard_answers_json', standardAnswersJson)
  }
  if (standardAnswerImage) {
    form.append('standard_answer_image', standardAnswerImage)
  }
  const { data } = await api.post<GradingResponse>('/grade/analyze', form)
  return data
}

export async function getGradingResult(gradingId: string): Promise<GradingResponse> {
  const { data } = await api.get<GradingResponse>(`/grade/${gradingId}`)
  return data
}

export async function getGradingHistory(): Promise<GradingHistoryItem[]> {
  const { data } = await api.get<GradingHistoryItem[]>('/grade')
  return data
}

export async function updateGradingResult(gradingId: string, gradingResult: any): Promise<GradingResponse> {
  const { data } = await api.put<GradingResponse>(`/grade/${gradingId}`, { grading_result: gradingResult })
  return data
}

export async function deleteGrading(gradingId: string): Promise<void> {
  await api.delete(`/grade/${gradingId}`)
}

export async function getPrompts(subject?: string, stage?: string): Promise<PromptResponse[]> {
  const params: Record<string, string> = {}
  if (subject) params.subject = subject
  if (stage) params.stage = stage
  const { data } = await api.get<PromptResponse[]>('/prompts', { params })
  return data
}

export async function getPrompt(promptId: number): Promise<PromptResponse> {
  const { data } = await api.get<PromptResponse>(`/prompts/${promptId}`)
  return data
}

export async function updatePrompt(
  promptId: number,
  fields: { analysis_prompt?: string; grading_prompt?: string; answer_extraction_prompt?: string }
): Promise<PromptResponse> {
  const { data } = await api.put<PromptResponse>(`/prompts/${promptId}`, fields)
  return data
}
