export interface BBox {
  x: number
  y: number
  w: number
  h: number
}

export interface AnswerArea {
  type: 'inline_blank' | 'horizontal_blank' | 'after_equal' | 'box_area'
  bbox: BBox
}

export interface Blank {
  text: string
  bbox: BBox
}

export interface Problem {
  problem_number: number
  text: string
  bbox: BBox | null
  blanks: Blank[]
  answer_areas: AnswerArea[]
}

export interface Section {
  section_number: number
  title: string
  bbox: BBox
  problems: Problem[]
}

export interface PaperInfo {
  title: string
  grade: string
  subject: string
}

export interface AnalysisResponse {
  run_id: string
  paper_info: PaperInfo
  sections: Section[]
  original_image_url: string
  image_width: number
  image_height: number
  created_at: string
}

export interface LayoutResult {
  paper_info: PaperInfo
  sections: Section[]
}

export interface HistoryItem {
  run_id: string
  title: string
  original_image_url: string
  image_width: number
  image_height: number
  created_at: string
  sections_count: number
  problems_count: number
  areas_count: number
  preview_bboxes: BBox[]
}

export interface PixelBBox {
  x: number
  y: number
  w: number
  h: number
}

export function bboxToPixel(b: BBox, imgW: number, imgH: number): PixelBBox {
  return {
    x: Math.round(b.x * imgW),
    y: Math.round(b.y * imgH),
    w: Math.round(b.w * imgW),
    h: Math.round(b.h * imgH),
  }
}

export interface StandardAnswer {
  problem_key: string
  correct_answer: string
  section_hint?: string
}

export interface AreaGrading {
  area_index: number
  student_answer: string
  correct_answer: string
  is_correct: boolean | null
  score: number
  max_score: number
  comment: string
}

export interface GradedProblem {
  problem_number: number
  problem_text: string
  area_gradings: AreaGrading[]
  problem_total_score: number
  problem_max_score: number
}

export interface GradedSection {
  section_number: number
  title: string
  problems: GradedProblem[]
  _orig_section_idx?: number
}

export interface GradingPaperInfo {
  title?: string
  grade?: string
  subject?: string
}

export interface GradingResult {
  paper_info: GradingPaperInfo
  sections: GradedSection[]
  total_score: number
  total_max_score: number
  correct_count: number
  total_areas: number
}

export interface GradingResponse {
  grading_id: string
  run_id: string
  subject: string
  stage: string
  analysis_result: AnalysisResponse | null
  grading_result: GradingResult | null
  standard_answers: StandardAnswer[]
  created_at: string
}

export interface GradingHistoryItem {
  grading_id: string
  run_id: string
  subject: string
  stage: string
  original_filename: string
  total_score: number | null
  total_max_score: number | null
  correct_count: number | null
  total_areas: number | null
  sections_count: number
  problems_count: number
  created_at: string
}

export interface PromptResponse {
  id: number
  subject: string
  stage: string
  analysis_prompt: string
  grading_prompt: string
  answer_extraction_prompt: string
  updated_at: string
}

export interface GradeAnalyzeParams {
  file: File
  subject: string
  stage: string
  standard_answers_json?: string
  standard_answer_image?: File | null
}

export interface TemplateListItem {
  template_id: string
  name: string
  subject: string
  stage: string
  run_id: string
  standard_answers_json: string | null
  image_path: string | null
  analysis_image_path: string | null
  created_at: string
  updated_at: string
}

export interface TemplateDetail {
  template_id: string
  name: string
  subject: string
  stage: string
  run_id: string
  standard_answers_json: string | null
  image_path: string | null
  layout_json: string | null
  image_width: number | null
  image_height: number | null
  created_at: string
  updated_at: string
}

export interface ProviderSettingsResponse {
  ai_provider: string
  volces_has_key: boolean
  volces_ep_id: string
  modelscope_has_key: boolean
  modelscope_model: string
}

export interface ProviderSettingsPayload {
  ai_provider: string
  volces_api_key?: string
  volces_ep_id?: string
  modelscope_api_key?: string
  modelscope_model?: string
}

export interface TestConnectionResult {
  success: boolean
  message: string
}

export interface StudentGradingResult {
  student_index: number
  total_students: number
  grading_id: string
  run_id: string
  grading_result: GradingResult | null
  analysis_result: AnalysisResponse | null
  image_url: string
  image_width: number
  image_height: number
  filename: string
}

export interface BatchGradingSummaryItem {
  filename: string
  student_index: number
  ok: boolean
  grading_id?: string
  score?: number
  max_score?: number
  correct_count?: number
  total_areas?: number
  error?: string
}
