from pydantic import BaseModel, Field
from typing import Optional, Union


class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class AnswerArea(BaseModel):
    type: str
    bbox: BBox


class Blank(BaseModel):
    text: str
    bbox: BBox


class Problem(BaseModel):
    problem_number: int
    text: Optional[str] = ""
    bbox: Optional[BBox] = None
    blanks: list[Blank] = []
    answer_areas: list[AnswerArea] = []


class Section(BaseModel):
    section_number: int
    title: str
    bbox: BBox
    problems: list[Problem] = []


class PaperInfo(BaseModel):
    title: Optional[str] = ""
    grade: Optional[str] = ""
    subject: Optional[str] = ""


class LayoutResult(BaseModel):
    paper_info: PaperInfo = PaperInfo()
    sections: list[Section] = []


class AnalysisResponse(BaseModel):
    run_id: str
    paper_info: PaperInfo
    sections: list[Section]
    original_image_url: str
    image_width: int
    image_height: int
    created_at: str


class HistoryItem(BaseModel):
    run_id: str
    title: str
    original_image_url: str
    image_width: int
    image_height: int
    created_at: str
    sections_count: int
    problems_count: int
    areas_count: int
    preview_bboxes: list[BBox] = []


class StandardAnswer(BaseModel):
    problem_key: str
    correct_answer: str
    section_hint: Optional[str] = ""


class AreaGrading(BaseModel):
    area_index: int
    student_answer: str = ""
    correct_answer: str = ""
    is_correct: Optional[bool] = None
    score: float = 0.0
    max_score: float = 0.0
    comment: str = ""


class GradedProblem(BaseModel):
    problem_number: int
    problem_text: str = ""
    area_gradings: list[AreaGrading] = []
    problem_total_score: float = 0.0
    problem_max_score: float = 0.0


class GradedSection(BaseModel):
    section_number: int
    title: str
    problems: list[GradedProblem] = []


class GradingPaperInfo(BaseModel):
    title: Optional[str] = ""
    grade: Optional[str] = ""
    subject: Optional[str] = ""


class GradingResult(BaseModel):
    paper_info: GradingPaperInfo = GradingPaperInfo()
    sections: list[GradedSection] = []
    total_score: float = 0.0
    total_max_score: float = 0.0


class ExtractedAnswers(BaseModel):
    answers: list[StandardAnswer] = []
    note: str = ""


class GradingRequest(BaseModel):
    file: Optional[str] = None
    run_id: Optional[str] = None
    subject: str = "数学"
    stage: str = "小学"
    standard_answers: list[StandardAnswer] = []
    standard_answer_image: Optional[str] = None


class GradingResponse(BaseModel):
    grading_id: str
    run_id: str
    subject: str
    stage: str
    analysis_result: Optional[dict] = None
    grading_result: Optional[GradingResult] = None
    standard_answers: list[StandardAnswer] = []
    created_at: str


class GradingHistoryItem(BaseModel):
    grading_id: str
    run_id: str
    subject: str
    stage: str
    original_filename: str = ""
    total_score: Optional[float] = None
    total_max_score: Optional[float] = None
    sections_count: int = 0
    problems_count: int = 0
    created_at: str


class PromptResponse(BaseModel):
    id: int
    subject: str
    stage: str
    analysis_prompt: str
    grading_prompt: str
    answer_extraction_prompt: str
    updated_at: str


class PromptCreate(BaseModel):
    subject: str
    stage: str
    analysis_prompt: str = ""
    grading_prompt: str = ""
    answer_extraction_prompt: str = ""


class PromptUpdate(BaseModel):
    analysis_prompt: Optional[str] = None
    grading_prompt: Optional[str] = None
    answer_extraction_prompt: Optional[str] = None


class TemplateListItem(BaseModel):
    template_id: str
    name: str
    subject: str
    stage: str
    run_id: str
    standard_answers_json: Optional[str] = None
    image_path: Optional[str] = None
    analysis_image_path: Optional[str] = None
    created_at: str
    updated_at: str


class TemplateDetail(BaseModel):
    template_id: str
    name: str
    subject: str
    stage: str
    run_id: str
    standard_answers_json: Optional[str] = None
    image_path: Optional[str] = None
    layout_json: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    created_at: str
    updated_at: str


class TemplateCreate(BaseModel):
    name: str
    subject: str
    stage: str
    run_id: Optional[str] = None
    standard_answers: list[StandardAnswer] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    standard_answers: Optional[list[StandardAnswer]] = None
