from fastapi import APIRouter, HTTPException

from backend.models import PromptResponse, PromptCreate, PromptUpdate
from backend.database import get_prompts, get_prompt, update_prompt, create_prompt

router = APIRouter()


@router.get("/prompts", response_model=list[PromptResponse])
def list_prompts(subject: str | None = None, stage: str | None = None):
    rows = get_prompts(subject=subject, stage=stage)
    return [PromptResponse(**r) for r in rows]


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
def get_one_prompt(prompt_id: int):
    row = get_prompt(prompt_id)
    if row is None:
        raise HTTPException(404, "提示词模板不存在")
    return PromptResponse(**row)


@router.put("/prompts/{prompt_id}", response_model=PromptResponse)
def update_one_prompt(prompt_id: int, body: PromptUpdate):
    existing = get_prompt(prompt_id)
    if existing is None:
        raise HTTPException(404, "提示词模板不存在")

    analysis_prompt = body.analysis_prompt if body.analysis_prompt is not None else existing["analysis_prompt"]
    grading_prompt = body.grading_prompt if body.grading_prompt is not None else existing["grading_prompt"]
    answer_extraction_prompt = body.answer_extraction_prompt if body.answer_extraction_prompt is not None else existing["answer_extraction_prompt"]

    success = update_prompt(prompt_id, analysis_prompt, grading_prompt, answer_extraction_prompt)
    if not success:
        raise HTTPException(500, "更新提示词失败")

    return PromptResponse(**get_prompt(prompt_id))


@router.post("/prompts", response_model=PromptResponse)
def create_one_prompt(body: PromptCreate):
    prompt_id = create_prompt(
        body.subject, body.stage,
        body.analysis_prompt or "",
        body.grading_prompt or "",
        body.answer_extraction_prompt or "",
    )
    return PromptResponse(**get_prompt(prompt_id))
