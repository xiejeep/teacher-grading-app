export interface SSEHandlers {
  onStatus?: (data: { phase: string; message: string; sections_count?: number; problems_count?: number; areas_count?: number; total_score?: number; total_max_score?: number; correct_count?: number; total_areas?: number; student_index?: number; total_students?: number }) => void
  onAnalysisResult?: (data: { run_id: string; analysis_result: any; image_url?: string; image_width?: number; image_height?: number }) => void
  onGradingResult?: (data: { grading_id: string; run_id: string; grading_result: any; analysis_result: any; image_url?: string; image_width?: number; image_height?: number; student_index?: number; total_students?: number; filename?: string }) => void
  onTemplateCreated?: (data: { template_id: string; name: string; subject: string; stage: string; run_id: string; standard_answers: any[] }) => void
  onAnswersExtracted?: (data: { answers: Array<{ problem_key: string; correct_answer: string; section_hint?: string }> }) => void
  onDone?: (data: { grading_id?: string; run_id?: string; total?: number; completed?: number; failed?: number; summary?: any[]; template_id?: string; answers_count?: number }) => void
  onError?: (message: string) => void
}

function parseSSEStream(
  response: Response,
  handlers: SSEHandlers,
): void {
  const reader = response.body?.getReader()
  if (!reader) {
    handlers.onError?.('无法读取响应流')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''
  let dataStr = ''

  function dispatch() {
    if (!eventType || !dataStr) return
    try {
      const data = JSON.parse(dataStr)
      switch (eventType) {
        case 'status':
          handlers.onStatus?.(data)
          break
        case 'analysis_result':
          handlers.onAnalysisResult?.(data)
          break
        case 'grading_result':
          handlers.onGradingResult?.(data)
          break
        case 'done':
          handlers.onDone?.(data)
          break
        case 'template_created':
          handlers.onTemplateCreated?.(data)
          break
        case 'answers_extracted':
          handlers.onAnswersExtracted?.(data)
          break
        case 'error':
          handlers.onError?.(data.message || '未知错误')
          break
      }
    } catch { /* skip malformed */ }
    eventType = ''
    dataStr = ''
  }

  async function pump(): Promise<void> {
    while (true) {
      const { done, value } = await reader!.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
          dataStr = ''
        } else if (line.startsWith('data: ')) {
          dataStr = line.slice(6)
        } else if (line === '' && eventType) {
          dispatch()
        }
      }
    }

    if (eventType && dataStr) {
      dispatch()
    }
  }

  pump().catch(() => {})
}

async function handleErrorResponse(response: Response, handlers: SSEHandlers): Promise<boolean> {
  if (!response.ok) {
    const text = await response.text()
    let msg = text
    try {
      const err = JSON.parse(text)
      msg = err.detail || err.message || text
    } catch { /* use raw text */ }
    handlers.onError?.(msg)
    return true
  }
  return false
}

export function connectGradeSSE(
  formData: FormData,
  handlers: SSEHandlers,
): () => void {
  const controller = new AbortController()

  fetch('/api/grade/stream', {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (response) => {
    if (await handleErrorResponse(response, handlers)) return
    parseSSEStream(response, handlers)
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err.message || '连接失败')
    }
  })

  return () => controller.abort()
}

export function connectExtractAnswersSSE(
  templateId: string,
  handlers: SSEHandlers,
  answerText?: string,
  answerImage?: File | null,
): () => void {
  const controller = new AbortController()
  const formData = new FormData()
  if (answerText) formData.append('answer_text', answerText)
  if (answerImage) formData.append('answer_image', answerImage)

  fetch(`/api/templates/${templateId}/extract-answers`, {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (response) => {
    if (await handleErrorResponse(response, handlers)) return
    parseSSEStream(response, handlers)
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err.message || '连接失败')
    }
  })

  return () => controller.abort()
}

export function connectGradeExistingSSE(
  runId: string,
  formData: FormData,
  handlers: SSEHandlers,
): () => void {
  const controller = new AbortController()

  fetch(`/api/grade/existing/${runId}/stream`, {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (response) => {
    if (await handleErrorResponse(response, handlers)) return
    parseSSEStream(response, handlers)
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err.message || '连接失败')
    }
  })

  return () => controller.abort()
}

export function connectCreateTemplateSSE(
  file: File,
  name: string,
  handlers: SSEHandlers,
  subject?: string,
  stage?: string,
  standardAnswersJson?: string,
  standardAnswerImage?: File | null,
): () => void {
  const controller = new AbortController()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('name', name)
  if (subject) formData.append('subject', subject)
  if (stage) formData.append('stage', stage)
  if (standardAnswersJson) formData.append('standard_answers_json', standardAnswersJson)
  if (standardAnswerImage) formData.append('standard_answer_image', standardAnswerImage)

  fetch('/api/templates/from-image', {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (response) => {
    if (await handleErrorResponse(response, handlers)) return
    parseSSEStream(response, handlers)
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err.message || '连接失败')
    }
  })

  return () => controller.abort()
}

export function connectGradeWithTemplateSSE(
  templateId: string,
  files: File[],
  handlers: SSEHandlers,
): () => void {
  const controller = new AbortController()
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))

  fetch(`/api/grade/with-template/${templateId}/stream`, {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  }).then(async (response) => {
    if (await handleErrorResponse(response, handlers)) return
    parseSSEStream(response, handlers)
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      handlers.onError?.(err.message || '连接失败')
    }
  })

  return () => controller.abort()
}
