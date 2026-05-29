import asyncio
import json
import os
import uuid
import base64
import concurrent.futures

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from backend.config import UPLOAD_DIR, GRADING_UPLOAD_DIR, ANSWER_KEY_DIR
from backend.models import (
    GradingRequest, GradingResponse, GradingHistoryItem,
    StandardAnswer, ExtractedAnswers, GradingResult, GradedSection, GradedProblem
)
from backend.analysis.engine import call_ai_analysis, call_ai_analysis_batched
from backend.analysis.grading_engine import call_ai_grade, call_ai_extract_answers, call_ai_grade_batched
from backend.database import (
    save_result, get_result as db_get_result, save_grading, save_grading_result,
    get_grading, get_grading_history, delete_grading,
    get_prompt_by_subject_stage, get_template,
)

router = APIRouter()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _fmt_sse(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _run_pipeline(queue: asyncio.Queue, image_path: str, original_filename: str,
                  subject: str, stage: str, img_w: int, img_h: int,
                  standard_answers_json: str, answer_key_contents: bytes | None,
                  answer_key_filename: str | None, run_id: str):
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
        save_result(run_id, original_filename, image_path, layout_dict, img_w, img_h)

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
                except Exception as e:
                    on_progress("warning", f"答案图片提取失败：{e}")

        grading_id = uuid.uuid4().hex[:12]
        save_grading(grading_id, run_id, subject, stage, standard_answers, answer_image_path)

        grading_result = None
        if prompt and prompt.get("grading_prompt"):
            try:
                sections = layout_dict.get("sections", [])
                if len(sections) > 1:
                    grading_result = call_ai_grade_batched(
                        image_path, layout_dict, prompt["grading_prompt"], standard_answers,
                        on_progress=on_progress
                    )
                else:
                    grading_result = call_ai_grade(
                        image_path, layout_dict, prompt["grading_prompt"], standard_answers,
                        on_progress=on_progress
                    )
                save_grading_result(grading_id, grading_result)
            except Exception as e:
                grading_result = None
                on_progress("warning", f"批改失败：{e}")

        if grading_result:
            ext = os.path.splitext(original_filename or "image.jpg")[1] or ".jpg"
            image_filename = f"{run_id}{ext}"
            queue.put_nowait(("grading_result", {
                "grading_id": grading_id,
                "run_id": run_id,
                "grading_result": grading_result,
                "analysis_result": layout_dict,
                "image_url": f"/static/uploads/{image_filename}",
                "image_width": img_w,
                "image_height": img_h,
            }))
        queue.put_nowait(("done", {"grading_id": grading_id, "run_id": run_id}))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/grade/stream")
async def grade_stream(
    file: UploadFile = File(...),
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
    standard_answers_json: str = Form(default=""),
    standard_answer_image: UploadFile | None = None,
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传学生试卷图片")

    _ensure_dir(UPLOAD_DIR)

    run_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{run_id}{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    img = Image.open(image_path)
    img_w, img_h = img.size

    ans_contents = None
    ans_filename = None
    if standard_answer_image:
        ans_contents = await standard_answer_image.read()
        ans_filename = standard_answer_image.filename

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_pipeline,
        queue, image_path, file.filename or filename,
        subject, stage, img_w, img_h,
        standard_answers_json, ans_contents, ans_filename, run_id,
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


@router.post("/grade/analyze", response_model=GradingResponse)
async def grade_analyze(
    file: UploadFile = File(...),
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
    standard_answers_json: str = Form(default=""),
    standard_answer_image: UploadFile | None = None,
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传学生试卷图片")

    _ensure_dir(UPLOAD_DIR)
    _ensure_dir(GRADING_UPLOAD_DIR)
    _ensure_dir(ANSWER_KEY_DIR)

    run_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{run_id}{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    img = Image.open(image_path)
    img_w, img_h = img.size

    prompt = get_prompt_by_subject_stage(subject, stage)
    analysis_prompt = prompt["analysis_prompt"] if prompt else None

    try:
        layout_dict = call_ai_analysis(image_path, prompt_text=analysis_prompt)
    except Exception as e:
        raise HTTPException(500, f"版面分析失败: {str(e)}")

    from datetime import datetime, timezone
    save_result(run_id, file.filename or filename, image_path,
                layout_dict, img_w, img_h)

    standard_answers = None
    if standard_answers_json:
        try:
            standard_answers = json.loads(standard_answers_json)
        except json.JSONDecodeError:
            raise HTTPException(400, "标准答案 JSON 格式错误")

    answer_image_path = None
    if standard_answer_image:
        ans_ext = os.path.splitext(standard_answer_image.filename or "answer.jpg")[1] or ".jpg"
        ans_filename = f"{run_id}_answer{ans_ext}"
        answer_image_path = os.path.join(ANSWER_KEY_DIR, ans_filename)
        ans_contents = await standard_answer_image.read()
        with open(answer_image_path, "wb") as f:
            f.write(ans_contents)

        if prompt and prompt.get("answer_extraction_prompt"):
            try:
                extracted = call_ai_extract_answers(answer_image_path, prompt["answer_extraction_prompt"])
                for a in extracted.get("answers", []):
                    standard_answers.append({
                        "problem_key": str(a.get("problem_number", "")),
                        "correct_answer": a.get("answer", ""),
                        "section_hint": a.get("section_hint", ""),
                    })
            except Exception as e:
                print(f"答案图片提取失败: {e}")

    grading_id = uuid.uuid4().hex[:12]
    save_grading(grading_id, run_id, subject, stage, standard_answers, answer_image_path)

    if prompt and prompt.get("grading_prompt"):
        try:
            grading_result = call_ai_grade(
                image_path, layout_dict, prompt["grading_prompt"], standard_answers
            )
            save_grading_result(grading_id, grading_result)
        except Exception as e:
            grading_result = None
            print(f"批改失败: {e}")
    else:
        grading_result = None

    now = datetime.now(timezone.utc).isoformat()
    grading_parsed = GradingResult(**grading_result) if grading_result else None

    return GradingResponse(
        grading_id=grading_id,
        run_id=run_id,
        subject=subject,
        stage=stage,
        analysis_result=layout_dict,
        grading_result=grading_parsed,
        standard_answers=[StandardAnswer(
            problem_key=a.get("problem_key", ""),
            correct_answer=a.get("correct_answer", ""),
            section_hint=a.get("section_hint", ""),
        ) for a in (standard_answers or [])],
        created_at=now,
    )


@router.post("/grade/existing/{run_id}", response_model=GradingResponse)
async def grade_existing(
    run_id: str,
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
    standard_answers_json: str = Form(default=""),
    standard_answer_image: UploadFile | None = None,
):
    row = db_get_result(run_id)
    if row is None:
        raise HTTPException(404, "分析记录不存在")

    image_path = row["image_path"]
    layout_dict = json.loads(row["layout_json"])

    prompt = get_prompt_by_subject_stage(subject, stage)

    standard_answers = None
    if standard_answers_json:
        try:
            standard_answers = json.loads(standard_answers_json)
        except json.JSONDecodeError:
            raise HTTPException(400, "标准答案 JSON 格式错误")

    answer_image_path = None
    if standard_answer_image:
        _ensure_dir(ANSWER_KEY_DIR)
        ans_ext = os.path.splitext(standard_answer_image.filename or "answer.jpg")[1] or ".jpg"
        ans_filename = f"{run_id}_answer{ans_ext}"
        answer_image_path = os.path.join(ANSWER_KEY_DIR, ans_filename)
        ans_contents = await standard_answer_image.read()
        with open(answer_image_path, "wb") as f:
            f.write(ans_contents)

        if prompt and prompt.get("answer_extraction_prompt"):
            try:
                extracted = call_ai_extract_answers(answer_image_path, prompt["answer_extraction_prompt"])
                for a in extracted.get("answers", []):
                    standard_answers.append({
                        "problem_key": str(a.get("problem_number", "")),
                        "correct_answer": a.get("answer", ""),
                        "section_hint": a.get("section_hint", ""),
                    })
            except Exception as e:
                print(f"答案图片提取失败: {e}")

    grading_id = uuid.uuid4().hex[:12]
    save_grading(grading_id, run_id, subject, stage, standard_answers, answer_image_path)

    grading_result = None
    if prompt and prompt.get("grading_prompt"):
        try:
            grading_result = call_ai_grade(
                image_path, layout_dict, prompt["grading_prompt"], standard_answers
            )
            save_grading_result(grading_id, grading_result)
        except Exception as e:
            print(f"批改失败: {e}")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    grading_parsed = GradingResult(**grading_result) if grading_result else None

    return GradingResponse(
        grading_id=grading_id,
        run_id=run_id,
        subject=subject,
        stage=stage,
        analysis_result=layout_dict,
        grading_result=grading_parsed,
        standard_answers=[StandardAnswer(
            problem_key=a.get("problem_key", ""),
            correct_answer=a.get("correct_answer", ""),
            section_hint=a.get("section_hint", ""),
        ) for a in (standard_answers or [])],
        created_at=now,
    )


def build_grading_response(row: dict, grading_data: dict | None = None) -> GradingResponse:
    grading_result = None
    data = grading_data or (json.loads(row["grading_result_json"]) if row.get("grading_result_json") else None)
    if data:
        grading_result = GradingResult(**data)

    analysis_row = db_get_result(row["run_id"])
    analysis_result = None
    if analysis_row:
        analysis_result = json.loads(analysis_row["layout_json"])
        analysis_result["image_width"] = analysis_row["image_width"]
        analysis_result["image_height"] = analysis_row["image_height"]
        ext = os.path.splitext(analysis_row["original_filename"] or "image.jpg")[1] or ".jpg"
        analysis_result["original_image_url"] = f"/static/uploads/{row['run_id']}{ext}"
        analysis_result["run_id"] = row["run_id"]

    standard_answers_data = json.loads(row["standard_answers_json"]) if row.get("standard_answers_json") else []

    return GradingResponse(
        grading_id=row["grading_id"],
        run_id=row["run_id"],
        subject=row["subject"],
        stage=row["stage"],
        analysis_result=analysis_result,
        grading_result=grading_result,
        standard_answers=[StandardAnswer(
            problem_key=a.get("problem_key", ""),
            correct_answer=a.get("correct_answer", ""),
            section_hint=a.get("section_hint", ""),
        ) for a in standard_answers_data],
        created_at=row["created_at"],
    )


@router.get("/grade/{grading_id}", response_model=GradingResponse)
def get_grading_result(grading_id: str):
    row = get_grading(grading_id)
    if row is None:
        raise HTTPException(404, "批改记录不存在")
    return build_grading_response(row)


@router.get("/grade", response_model=list[GradingHistoryItem])
def list_grading_history():
    items = []
    for row in get_grading_history():
        total_score = None
        total_max = None
        correct_count = None
        total_areas = None
        sections_count = 0
        problems_count = 0
        if row.get("grading_result_json"):
            gr = json.loads(row["grading_result_json"])
            total_score = gr.get("total_score")
            total_max = gr.get("total_max_score")
            correct_count = gr.get("correct_count")
            total_areas = gr.get("total_areas")
            sections_count = len(gr.get("sections", []))
            problems_count = sum(len(s.get("problems", [])) for s in gr.get("sections", []))

        items.append(GradingHistoryItem(
            grading_id=row["grading_id"],
            run_id=row["run_id"],
            subject=row["subject"],
            stage=row["stage"],
            original_filename=row.get("original_filename", ""),
            total_score=total_score,
            total_max_score=total_max,
            correct_count=correct_count,
            total_areas=total_areas,
            sections_count=sections_count,
            problems_count=problems_count,
            created_at=row["created_at"],
        ))
    return items


@router.put("/grade/{grading_id}", response_model=GradingResponse)
def update_grading_result(grading_id: str, body: dict):
    row = get_grading(grading_id)
    if row is None:
        raise HTTPException(404, "批改记录不存在")

    grading_data = body.get("grading_result", body)
    GradingResult(**grading_data)
    save_grading_result(grading_id, grading_data)

    return build_grading_response(row, grading_data)


@router.delete("/grade/{grading_id}")
def delete_grade_result(grading_id: str):
    deleted = delete_grading(grading_id)
    if not deleted:
        raise HTTPException(404, "批改记录不存在")
    return {"ok": True}


def _run_grade_existing_pipeline(queue: asyncio.Queue, image_path: str,
                                 original_filename: str, run_id: str,
                                 layout_dict: dict, img_w: int, img_h: int,
                                 subject: str, stage: str,
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

        grading_id = uuid.uuid4().hex[:12]
        save_grading(grading_id, run_id, subject, stage, standard_answers, answer_image_path)

        grading_result = None
        if prompt and prompt.get("grading_prompt"):
            try:
                sections = layout_dict.get("sections", [])
                if len(sections) > 1:
                    grading_result = call_ai_grade_batched(
                        image_path, layout_dict, prompt["grading_prompt"], standard_answers,
                        on_progress=on_progress
                    )
                else:
                    on_progress("grading", "正在 AI 批改...")
                    grading_result = call_ai_grade(
                        image_path, layout_dict, prompt["grading_prompt"], standard_answers,
                        on_progress=on_progress
                    )
                save_grading_result(grading_id, grading_result)
            except Exception as e:
                grading_result = None
                on_progress("warning", f"批改失败：{e}")

        if grading_result:
            ext = os.path.splitext(original_filename or "image.jpg")[1] or ".jpg"
            image_filename = f"{run_id}{ext}"
            queue.put_nowait(("grading_result", {
                "grading_id": grading_id,
                "run_id": run_id,
                "grading_result": grading_result,
                "analysis_result": layout_dict,
                "image_url": f"/static/uploads/{image_filename}",
                "image_width": img_w,
                "image_height": img_h,
            }))
        queue.put_nowait(("done", {"grading_id": grading_id, "run_id": run_id}))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/grade/existing/{run_id}/stream")
async def grade_existing_stream(
    run_id: str,
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
    standard_answers_json: str = Form(default=""),
    standard_answer_image: UploadFile | None = None,
):
    row = db_get_result(run_id)
    if row is None:
        raise HTTPException(404, "分析记录不存在，请先进行版面分析")

    image_path = row["image_path"]
    layout_dict = json.loads(row["layout_json"])
    img_w = row["image_width"]
    img_h = row["image_height"]
    original_filename = row["original_filename"]

    ans_contents = None
    ans_filename = None
    if standard_answer_image:
        ans_contents = await standard_answer_image.read()
        ans_filename = standard_answer_image.filename

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_grade_existing_pipeline,
        queue, image_path, original_filename, run_id,
        layout_dict, img_w, img_h,
        subject, stage, standard_answers_json, ans_contents, ans_filename,
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


def _run_grade_with_template_pipeline(
    queue: asyncio.Queue,
    template: dict,
    student_images: list[dict],
):
    def on_progress(phase: str, message: str, extra: dict | None = None):
        payload = {"phase": phase, "message": message}
        if extra:
            payload.update(extra)
        try:
            queue.put_nowait(("status", payload))
        except Exception:
            pass

    try:
        layout_dict = json.loads(template["layout_json"])
        subject = template["subject"]
        stage = template["stage"]
        standard_answers = json.loads(template["standard_answers_json"]) if template.get("standard_answers_json") else []

        prompt = get_prompt_by_subject_stage(subject, stage)
        grading_prompt = prompt["grading_prompt"] if prompt else None

        total = len(student_images)
        completed = 0
        failed = 0
        results_summary = []

        for idx, simg in enumerate(student_images):
            student_index = idx + 1
            original_name = os.path.basename(simg["original_filename"])

            on_progress("grading_student",
                         f"正在批改第 {student_index}/{total} 份: {original_name}",
                         {"student_index": student_index, "total_students": total})

            student_run_id = simg["run_id"]
            save_result(student_run_id, simg["original_filename"], simg["image_path"],
                        layout_dict, simg["img_w"], simg["img_h"])

            grading_id = uuid.uuid4().hex[:12]
            save_grading(grading_id, student_run_id, subject, stage, standard_answers, None)

            grading_result = None
            try:
                sections = layout_dict.get("sections", [])
                if grading_prompt:
                    if len(sections) > 1:
                        grading_result = call_ai_grade_batched(
                            simg["image_path"], layout_dict, grading_prompt, standard_answers,
                            on_progress=on_progress
                        )
                    else:
                        on_progress("grading", "正在 AI 批改...")
                        grading_result = call_ai_grade(
                            simg["image_path"], layout_dict, grading_prompt, standard_answers,
                            on_progress=on_progress
                        )
                    save_grading_result(grading_id, grading_result)
            except Exception as e:
                on_progress("warning", f"第{student_index}份批改失败：{e}")
                failed += 1
                results_summary.append({
                    "filename": original_name,
                    "student_index": student_index,
                    "ok": False,
                    "error": str(e),
                })
                continue

            completed += 1
            ext = os.path.splitext(original_name or "image.jpg")[1] or ".jpg"
            image_filename = f"{student_run_id}{ext}"

            score = grading_result.get("total_score", 0) if grading_result else 0
            max_score = grading_result.get("total_max_score", 0) if grading_result else 0
            correct = grading_result.get("correct_count", 0) if grading_result else 0
            total_a = grading_result.get("total_areas", 0) if grading_result else 0

            queue.put_nowait(("grading_result", {
                "student_index": student_index,
                "total_students": total,
                "grading_id": grading_id,
                "run_id": student_run_id,
                "grading_result": grading_result,
                "analysis_result": layout_dict,
                "image_url": f"/static/uploads/{image_filename}",
                "image_width": simg["img_w"],
                "image_height": simg["img_h"],
                "filename": original_name,
            }))

            results_summary.append({
                "filename": original_name,
                "student_index": student_index,
                "ok": True,
                "grading_id": grading_id,
                "score": score,
                "max_score": max_score,
                "correct_count": correct,
                "total_areas": total_a,
            })

            on_progress("student_done",
                         f"第 {student_index}/{total} 份批改完成: {original_name} (答对 {correct}/{total_a})",
                         {"student_index": student_index, "total_students": total})

        queue.put_nowait(("done", {
            "total": total,
            "completed": completed,
            "failed": failed,
            "summary": results_summary,
        }))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/grade/with-template/{template_id}/stream")
async def grade_with_template_stream(
    template_id: str,
    files: list[UploadFile] = File(...),
):
    tpl = get_template(template_id)
    if tpl is None:
        raise HTTPException(404, "模板不存在")

    if not files:
        raise HTTPException(400, "请至少上传一份学生答卷")

    _ensure_dir(UPLOAD_DIR)

    student_images: list[dict] = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        student_run_id = uuid.uuid4().hex[:12]
        ext = os.path.splitext(f.filename or "image.jpg")[1] or ".jpg"
        filename = f"{student_run_id}{ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        contents = await f.read()
        with open(image_path, "wb") as wf:
            wf.write(contents)
        img = Image.open(image_path)
        student_images.append({
            "run_id": student_run_id,
            "image_path": image_path,
            "original_filename": f.filename or filename,
            "img_w": img.size[0],
            "img_h": img.size[1],
        })

    if not student_images:
        raise HTTPException(400, "没有有效的图片文件")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_grade_with_template_pipeline,
        queue, tpl, student_images,
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
