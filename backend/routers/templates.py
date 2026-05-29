import asyncio
import json
import os
import uuid
import shutil
import concurrent.futures

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from backend.config import UPLOAD_DIR, ANSWER_KEY_DIR
from backend.models import (
    TemplateListItem, TemplateDetail, TemplateCreate, TemplateUpdate,
    StandardAnswer,
)
from backend.analysis.engine import call_ai_analysis_batched
from backend.analysis.grading_engine import call_ai_extract_answers, call_ai_extract_answers_from_text
from backend.database import (
    save_result, get_result as db_get_result,
    create_template, get_template, list_templates, update_template, delete_template,
    get_prompt_by_subject_stage,
)

router = APIRouter()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _fmt_sse(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _run_create_template_pipeline(queue: asyncio.Queue, image_path: str,
                                  original_filename: str, run_id: str,
                                  subject: str, stage: str, name: str,
                                  standard_answers_json: str,
                                  answer_key_contents: bytes | None,
                                  answer_key_filename: str | None):
    def on_progress(phase: str, message: str, extra: dict | None = None):
        payload = {"phase": phase, "message": message}
        if extra:
            payload.update(extra)
        try:
            queue.put_nowait(("status", payload))
        except Exception:
            pass

    try:
        prompt = get_prompt_by_subject_stage(subject, stage)
        analysis_prompt = prompt["analysis_prompt"] if prompt else None

        on_progress("analyzing", "正在分析试卷版面结构...")
        layout_dict = call_ai_analysis_batched(image_path, prompt_text=analysis_prompt, on_progress=on_progress)

        img = Image.open(image_path)
        img_w, img_h = img.size
        save_result(run_id, original_filename, image_path, layout_dict, img_w, img_h)

        sections_count = len(layout_dict.get("sections", []))
        problems_count = sum(len(s.get("problems", [])) for s in layout_dict.get("sections", []))
        areas_count = sum(
            len(p.get("answer_areas", []))
            for s in layout_dict.get("sections", [])
            for p in s.get("problems", [])
        )
        on_progress("analysis_done",
                     f"版面分析完成：识别到 {sections_count} 大题、{problems_count} 小题、{areas_count} 个作答区",
                     {"sections_count": sections_count, "problems_count": problems_count, "areas_count": areas_count})

        ext = os.path.splitext(original_filename or "image.jpg")[1] or ".jpg"
        image_filename = f"{run_id}{ext}"
        queue.put_nowait(("analysis_result", {
            "run_id": run_id,
            "analysis_result": layout_dict,
            "image_url": f"/static/uploads/{image_filename}",
            "image_width": img_w,
            "image_height": img_h,
        }))

        standard_answers: list[dict] = []
        if standard_answers_json:
            try:
                standard_answers = json.loads(standard_answers_json)
            except json.JSONDecodeError:
                pass

        answer_image_path = None
        if answer_key_contents and answer_key_filename:
            _ensure_dir(ANSWER_KEY_DIR)
            ans_ext = os.path.splitext(answer_key_filename or "answer.jpg")[1] or ".jpg"
            ans_filename = f"{run_id}_answer{ans_ext}"
            answer_image_path = os.path.join(ANSWER_KEY_DIR, ans_filename)
            with open(answer_image_path, "wb") as f:
                f.write(answer_key_contents)

            if prompt and prompt.get("answer_extraction_prompt"):
                try:
                    on_progress("extracting", "正在从答案图片提取标准答案...")
                    extracted = call_ai_extract_answers(
                        answer_image_path, prompt["answer_extraction_prompt"],
                        on_progress=on_progress
                    )
                    for a in extracted.get("answers", []):
                        if a not in standard_answers:
                            standard_answers.append({
                                "problem_key": str(a.get("problem_number", "")),
                                "correct_answer": a.get("answer", ""),
                                "section_hint": a.get("section_hint", ""),
                            })
                    on_progress("extraction_done", f"答案提取完成，共 {len(standard_answers)} 条标准答案")
                except Exception as e:
                    on_progress("warning", f"答案图片提取失败：{e}")

        template_id = uuid.uuid4().hex[:12]
        template_image_path = os.path.join(UPLOAD_DIR, f"template_{template_id}{ext}")
        shutil.copy(image_path, template_image_path)

        create_template(
            template_id=template_id,
            name=name,
            subject=subject,
            stage=stage,
            run_id=run_id,
            standard_answers=standard_answers if standard_answers else None,
            image_path=f"/static/uploads/template_{template_id}{ext}",
        )

        queue.put_nowait(("template_created", {
            "template_id": template_id,
            "name": name,
            "subject": subject,
            "stage": stage,
            "run_id": run_id,
            "standard_answers": standard_answers,
        }))
        queue.put_nowait(("done", {"template_id": template_id, "run_id": run_id}))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/templates/from-image")
async def create_template_from_image(
    file: UploadFile = File(...),
    name: str = Form(...),
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
    standard_answers_json: str = Form(default=""),
    standard_answer_image: UploadFile | None = None,
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传原试卷图片")

    _ensure_dir(UPLOAD_DIR)

    run_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{run_id}{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    ans_contents = None
    ans_filename = None
    if standard_answer_image:
        ans_contents = await standard_answer_image.read()
        ans_filename = standard_answer_image.filename

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_create_template_pipeline,
        queue, image_path, file.filename or filename, run_id,
        subject, stage, name,
        standard_answers_json, ans_contents, ans_filename,
    )

    async def event_stream():
        while True:
            event_type, data = await queue.get()
            yield _fmt_sse(event_type, data)
            if event_type in ("done", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/templates", response_model=TemplateListItem)
def api_create_template(body: TemplateCreate):
    row = db_get_result(body.run_id) if body.run_id else None
    if body.run_id and not row:
        raise HTTPException(404, "分析记录不存在")

    template_id = uuid.uuid4().hex[:12]
    create_template(
        template_id=template_id,
        name=body.name,
        subject=body.subject,
        stage=body.stage,
        run_id=body.run_id or "",
        standard_answers=[a.model_dump() for a in body.standard_answers] if body.standard_answers else None,
        image_path=None,
    )

    t = get_template(template_id)
    if not t:
        raise HTTPException(500, "模板创建失败")
    return TemplateListItem(**t)


@router.get("/templates", response_model=list[TemplateListItem])
def api_list_templates(subject: str | None = None, stage: str | None = None):
    items = list_templates(subject=subject, stage=stage)
    return [TemplateListItem(**item) for item in items]


@router.get("/templates/{template_id}", response_model=TemplateDetail)
def api_get_template(template_id: str):
    t = get_template(template_id)
    if t is None:
        raise HTTPException(404, "模板不存在")
    return TemplateDetail(**t)


def _run_extract_answers_pipeline(queue: asyncio.Queue, template_id: str,
                                  answer_text: str,
                                  answer_image_path: str | None):
    def on_progress(phase: str, message: str, extra: dict | None = None):
        payload = {"phase": phase, "message": message}
        if extra:
            payload.update(extra)
        try:
            queue.put_nowait(("status", payload))
        except Exception:
            pass

    try:
        tpl = get_template(template_id)
        if not tpl:
            queue.put_nowait(("error", {"message": "模板不存在"}))
            return

        layout_json_str = tpl.get("layout_json")
        if not layout_json_str:
            queue.put_nowait(("error", {"message": "模板无版面布局数据"}))
            return

        layout = json.loads(layout_json_str)
        subject = tpl.get("subject", "数学")
        stage = tpl.get("stage", "小学")
        prompt = get_prompt_by_subject_stage(subject, stage)

        standard_answers: list[dict] = []

        if answer_image_path:
            if prompt and prompt.get("answer_extraction_prompt"):
                on_progress("extracting", "正在从答案图片提取标准答案...")
                extracted = call_ai_extract_answers(
                    answer_image_path, prompt["answer_extraction_prompt"],
                    on_progress=on_progress,
                )
                for a in extracted.get("answers", []):
                    standard_answers.append({
                        "problem_key": str(a.get("problem_number", a.get("problem_key", ""))),
                        "correct_answer": a.get("answer", a.get("correct_answer", "")),
                        "section_hint": a.get("section_hint", ""),
                    })
            else:
                on_progress("warning", "未找到对应学科的答案提取提示词，跳过图片提取")

        if answer_text and answer_text.strip():
            on_progress("extracting_text", "正在从文本解析标准答案...")
            extracted = call_ai_extract_answers_from_text(
                answer_text.strip(), layout, on_progress=on_progress,
            )
            for a in extracted.get("answers", []):
                key = a.get("problem_key", "")
                existing_keys = {sa["problem_key"] for sa in standard_answers}
                if key and key in existing_keys:
                    idx = next(i for i, sa in enumerate(standard_answers) if sa["problem_key"] == key)
                    standard_answers[idx]["correct_answer"] = a.get("correct_answer", "")
                else:
                    standard_answers.append({
                        "problem_key": key,
                        "correct_answer": a.get("correct_answer", ""),
                        "section_hint": a.get("section_hint", ""),
                    })

        if standard_answers:
            update_template(template_id, standard_answers=standard_answers)

        tpl = get_template(template_id)
        updated_json = tpl.get("standard_answers_json") if tpl else None
        answers_list = json.loads(updated_json) if updated_json else standard_answers

        queue.put_nowait(("answers_extracted", {"answers": answers_list}))
        queue.put_nowait(("done", {"template_id": template_id, "answers_count": len(answers_list)}))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/templates/{template_id}/extract-answers")
async def extract_template_answers(
    template_id: str,
    answer_text: str = Form(default=""),
    answer_image: UploadFile | None = None,
):
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(404, "模板不存在")

    ans_image_path = None
    if answer_image:
        _ensure_dir(ANSWER_KEY_DIR)
        contents = await answer_image.read()
        ans_ext = os.path.splitext(answer_image.filename or "answer.jpg")[1] or ".jpg"
        ans_filename = f"{template_id}_extract_{uuid.uuid4().hex[:8]}{ans_ext}"
        ans_image_path = os.path.join(ANSWER_KEY_DIR, ans_filename)
        with open(ans_image_path, "wb") as f:
            f.write(contents)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_extract_answers_pipeline,
        queue, template_id, answer_text, ans_image_path,
    )

    async def event_stream():
        while True:
            event_type, data = await queue.get()
            yield _fmt_sse(event_type, data)
            if event_type in ("done", "error"):
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/templates/{template_id}", response_model=TemplateDetail)
def api_update_template(template_id: str, body: TemplateUpdate):
    kwargs = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.standard_answers is not None:
        kwargs["standard_answers"] = [a.model_dump() for a in body.standard_answers]

    ok = update_template(template_id, **kwargs) if kwargs else True
    if not ok:
        raise HTTPException(404, "模板不存在")

    t = get_template(template_id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return TemplateDetail(**t)


@router.delete("/templates/{template_id}")
def api_delete_template(template_id: str):
    ok = delete_template(template_id)
    if not ok:
        raise HTTPException(404, "模板不存在")
    return {"ok": True}
