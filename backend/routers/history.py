import json
import os

from fastapi import APIRouter, HTTPException

from backend.database import get_result, get_history, update_layout, get_image_path, delete_result
from backend.models import HistoryItem, AnalysisResponse, LayoutResult

router = APIRouter()


def _extract_preview_bboxes(layout: dict) -> list[dict]:
    bboxes = []
    for section in layout.get("sections", []):
        for problem in section.get("problems", []):
            for area in problem.get("answer_areas", []):
                bboxes.append(area["bbox"])
    return bboxes[:50]


@router.get("/history", response_model=list[HistoryItem])
def list_history():
    items = []
    for row in get_history():
        layout = json.loads(row["layout_json"])
        title = layout.get("paper_info", {}).get("title", row["original_filename"])
        sections_count = len(layout.get("sections", []))
        problems_count = sum(len(s.get("problems", [])) for s in layout.get("sections", []))
        areas_count = sum(
            len(p.get("answer_areas", []))
            for s in layout.get("sections", [])
            for p in s.get("problems", [])
        )

        run_id = row["run_id"]
        items.append(HistoryItem(
            run_id=run_id,
            title=title,
            original_image_url=f"/static/uploads/{os.path.basename(row['image_path'])}",
            image_width=row["image_width"],
            image_height=row["image_height"],
            created_at=row["created_at"],
            sections_count=sections_count,
            problems_count=problems_count,
            areas_count=areas_count,
            preview_bboxes=_extract_preview_bboxes(layout),
        ))
    return items


@router.get("/result/{run_id}", response_model=AnalysisResponse)
def get_analysis_result(run_id: str):
    row = get_result(run_id)
    if row is None:
        raise HTTPException(404, "记录不存在")

    layout = json.loads(row["layout_json"])

    from backend.models import LayoutResult
    parsed = LayoutResult(**layout)

    return AnalysisResponse(
        run_id=run_id,
        paper_info=parsed.paper_info,
        sections=parsed.sections,
        original_image_url=f"/static/uploads/{os.path.basename(row['image_path'])}",
        image_width=row["image_width"],
        image_height=row["image_height"],
        created_at=row["created_at"],
    )


@router.put("/result/{run_id}/layout", response_model=AnalysisResponse)
def update_analysis_layout(run_id: str, layout: LayoutResult):
    row = get_result(run_id)
    if row is None:
        raise HTTPException(404, "记录不存在")

    layout_dict = layout.model_dump(exclude_none=True)
    update_layout(run_id, layout_dict)

    return AnalysisResponse(
        run_id=run_id,
        paper_info=layout.paper_info,
        sections=layout.sections,
        original_image_url=f"/static/uploads/{os.path.basename(row['image_path'])}",
        image_width=row["image_width"],
        image_height=row["image_height"],
        created_at=row["created_at"],
    )


@router.delete("/result/{run_id}")
def delete_analysis_result(run_id: str):
    row = get_result(run_id)
    if row is None:
        raise HTTPException(404, "记录不存在")

    if os.path.exists(row["image_path"]):
        os.remove(row["image_path"])

    delete_result(run_id)
    return {"ok": True}
