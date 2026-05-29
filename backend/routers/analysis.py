import asyncio
import json
import os
import uuid
import shutil
import concurrent.futures

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image

from backend.config import UPLOAD_DIR
from backend.models import LayoutResult, AnalysisResponse
from backend.analysis.engine import call_ai_analysis, call_ai_analysis_batched
from backend.database import save_result, get_prompt_by_subject_stage

router = APIRouter()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _fmt_sse(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _run_analyze_pipeline(queue: asyncio.Queue, image_path: str,
                          original_filename: str, run_id: str,
                          subject: str, stage: str):
    def on_progress(phase: str, message: str, extra: dict | None = None):
        payload = {"phase": phase, "message": message}
        if extra:
            payload.update(extra)
        try:
            queue.put_nowait(("status", payload))
        except Exception:
            pass

    try:
        on_progress("analyzing", "正在分析试卷版面结构...")

        prompt = get_prompt_by_subject_stage(subject, stage)
        analysis_prompt = prompt["analysis_prompt"] if prompt else None

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
        queue.put_nowait(("done", {"run_id": run_id}))

    except Exception as e:
        queue.put_nowait(("error", {"message": str(e)}))


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")

    run_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{run_id}{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    img = Image.open(image_path)
    img_w, img_h = img.size

    try:
        layout_dict = call_ai_analysis(image_path)
    except Exception as e:
        raise HTTPException(500, f"AI 分析失败: {str(e)}")

    layout = LayoutResult(**layout_dict)

    from datetime import datetime, timezone
    save_result(run_id, file.filename or filename, image_path,
                layout_dict, img_w, img_h)

    return AnalysisResponse(
        run_id=run_id,
        paper_info=layout.paper_info,
        sections=layout.sections,
        original_image_url=f"/static/uploads/{filename}",
        image_width=img_w,
        image_height=img_h,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/analyze/stream")
async def analyze_stream(
    file: UploadFile = File(...),
    subject: str = Form(default="数学"),
    stage: str = Form(default="小学"),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    run_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{run_id}{ext}"
    image_path = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(image_path, "wb") as f:
        f.write(contents)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_analyze_pipeline,
        queue, image_path, file.filename or filename, run_id,
        subject, stage,
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
