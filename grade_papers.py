#!/usr/bin/env python3
"""Grade paper images with Volcengine Ark vision responses.

The script sends each image to Ark, asks for strict JSON grading results, and
draws check/cross marks over the returned answer regions.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "doubao-seed-2-0-pro-260215"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MARK_COLOR = (220, 20, 30)


LAYOUT_PROMPT = """你是试卷版面分析助手。只做版面切分，不批改。

请将图片中的试卷切分为适合单独批改的题块，返回每个题块的 bbox。

切分规则：
- 优先按题型模块切分，而不是只按整页或整道大题切分。
- 如果同一大题下面有“1. 口算”“2. 列竖式计算”“3. 解决问题”等编号题组，每个编号题组都要单独作为 section。
- 如果页面中有连线题、看图连一连、匹配题，必须保证这些题完整包含在某个 section 中，不能因为连线较淡或靠页面底部而漏掉。
- 每个 section 应包含该题组标题、印刷题目、学生答案和必要图形，不要截断学生作答区域。
- 不要包含姓名、班级、页码。
- 不要包含答题卡、答案表、涂卡区、题号/答案横表、纠错栏、结题分析区、分数栏；这些区域不是正文题目。
- 如果页面顶部或侧边有“题号/答案”表格，只把它当作答题卡排除在 section bbox 外。
- 不要把整页合成一个 section，除非图片中确实只有一个题组。
- section 数量通常是 2 到 6 个，取决于试卷中可见题型模块数量。

坐标使用 coordinate_space={"width":1000,"height":1000}，图片左上角是 (0,0)，右下角是 (1000,1000)。

只输出 JSON：
{
  "coordinate_space": {"width": 1000, "height": 1000},
  "sections": [
    {
      "id": "section-1",
      "title": "一、基础巩固",
      "bbox": {"x": 0, "y": 100, "w": 1000, "h": 300}
    }
  ]
}
"""


GRADE_PROMPT = """你是一个严谨的小学数学试卷批改助手。读取图片，批改学生已作答且能定位的题目；不要批改姓名、班级、页码、标题。

核心流程：
1. 先读取题目要求，判断题目要求学生提交什么形式的答案。
2. 自行计算标准答案。
3. 只对题目要求的正式答题区域判断正误；学生草稿、中间计算、辅助竖式不作为答题区域。
4. 返回严格 JSON，不要 Markdown，不要解释文字。

已作答判定：
- 批改所有可见且需要作答的题目；未作答也要判错。
- 空白横线、空白括号、空白方框、空白答题区、未填写的解答题区域，表示学生未作答，应 is_correct=false。
- 不要把印刷题干、印刷图形、印刷空格当作学生答案。
- 没有学生作答痕迹的题目也要放入 questions，student_answer=""，reason 写“未作答”。
- 对解答题、证明题、作图题、应用题，如果没有看到学生手写解答或作图，仍判为错误；bbox 放在题号旁、题目下方留白处或该题正式答题起始区域，避免覆盖整道题干。

答题卡/答题栏规则：
- 如果图片中有答题卡、题号/答案表、涂卡区、选择题答题栏、纠错栏、结题分析区，不要把这些区域作为 answer_regions，也不要在这些区域画勾叉。
- 答题卡可作为读取学生答案的辅助信息，但标注 bbox 必须回到正文题目里的正式答题位置。
- 对选择题，正式答题区域通常是正文题干中的“（ ）”、答案空格、题目旁手写选项或正文选项下方的选择标记；不要使用顶部/侧边答题卡中的格子作为 bbox。
- 如果学生只在答题卡作答、正文题目没有任何作答痕迹，仍在正文题干的“（ ）”附近返回 bbox，并根据答题卡读到的选项判断正误。
- 如果正文和答题卡都有答案，以正文正式作答区域为标注位置；必要时可用答题卡辅助判断 student_answer。

竖式计算题必须特殊处理：
- 只有题目明确要求“列竖式计算”“用竖式计算”或该题所在题组标题明确要求列竖式时，question_type 才能是 "vertical_calculation"。
- 不能仅因为学生写了竖式、草稿、分步算式或中间结果，就把题目判为 vertical_calculation。
- 竖式题有两个独立答题区域，必须分别返回：
  1. result_after_equal：印刷横式等号后学生写的结果。
  2. vertical_work：下方整块竖式过程。
- 不要把这两个区域合成一个 bbox，也不要只返回其中一个。
- result_after_equal 只判断等号后的最终结果是否正确。
- vertical_work 判断竖式过程是否正确：数位对齐、运算符、进位/借位、中间步骤、最后一行结果都要与题目一致。
- 题目级 is_correct 是两个区域的汇总：两个区域都正确才为 true；任一区域错误即 false。
- 结果正确但竖式过程错误时，题目级 is_correct=false，reason="结果正确但竖式过程错误"。
- 结果正确但未列竖式时，vertical_work.is_correct=false，reason="未列竖式"。
- 等号后结果未填写时，result_after_equal.is_correct=false，reason="等号后结果未填写"。

其他题型：
- 非竖式题 question_type 可用 direct_answer、fill_blank、choice、word_problem、matching_line。
- 应用题 question_type="word_problem" 时，按题目问句定位最终作答区域，通常是最终算式/答案（含单位）。学生写在旁边或下方的中间结果、草稿竖式、辅助计算不作为 answer_regions，也不要画勾叉。
- 例如“商店里有26个玩具熊，卖出17个后，又运来35个，现在商店多少个玩具熊？”只要求最终数量，学生写的“26-17”下方中间结果“9”是草稿，不是独立答题区域；只标注最终作答“26-17+35=44(个)”。
- 填空题 question_type="fill_blank" 时必须按印刷占位符拆分答题区域。
- 每一个印刷占位符都必须是一个独立 answer_regions 项；占位符包括 □、○、（ ）、括号内空白、横线、下划线、表格空格。
- 不要把多个填空、多个方框、多个圆圈或一整行算式合并成一个 bbox。
- 例如“□○□=□”必须拆成 4 个区域：第一个数、运算符、第二个数、结果。
- 例如“36+8=□，先算：□○□=□，再算：□○□=□”必须拆成 9 个区域：最终结果 1 个，先算 4 个，再算 4 个。
- 方框内填写数字时 type="blank_number"；圆圈内填写运算符时 type="blank_operator"；等号后结果可用 type="result_after_equal"。
- 填空题题目级 is_correct 是所有占位区域的汇总：全部区域正确才为 true，任一区域错误则为 false。
- 连线题 question_type="matching_line"。
- 连线题每一条学生画出的线都是一个独立 answer_regions 项，type="matching_line"。
- 每条连线的 student_answer 写成“左侧项 -> 右侧项”，correct_answer 写正确匹配关系。
- 每条线单独判断 is_correct；题目级 is_correct 是全部连线区域的汇总。
- 连线题 bbox 不要覆盖整条长线；bbox 应放在连线起始处附近的小区域，通常是左侧起点文字/图形旁边或线条起点 40x40 到 80x80 的范围，避免多条线标注重叠。
- 如果连线从右侧开始，也选择实际线条起点附近作为 bbox。标注应画在起始端，不画在线条交叉处。
- 不要因为连线和图形距离较远就漏掉连线题；只要学生画了线，就要返回对应区域。
- 非填空、非竖式题通常只返回一个 answer_regions 项，type="answer"。

坐标：
- 使用 coordinate_space={"width":1000,"height":1000}。
- 图片左上角是 (0,0)，右下角是 (1000,1000)。
- bbox={"x":左上角x,"y":左上角y,"w":宽,"h":高}，必须落在 0..1000 内。

JSON 格式：
{
  "coordinate_space": {"width": 1000, "height": 1000},
  "questions": [
    {
      "id": "题号",
      "question_type": "vertical_calculation",
      "question_text": "35+44=",
      "student_answer": "79",
      "correct_answer": "79",
      "is_correct": true,
      "confidence": 0.95,
      "answer_regions": [
        {
          "type": "result_after_equal",
          "label": "等号后结果",
          "student_answer": "79",
          "correct_answer": "79",
          "is_correct": true,
          "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
          "reason": ""
        },
        {
          "type": "vertical_work",
          "label": "竖式过程",
          "student_answer": "35+44=79",
          "correct_answer": "35+44=79",
          "is_correct": true,
          "bbox": {"x": 0, "y": 0, "w": 10, "h": 10},
          "reason": ""
        }
      ],
      "vertical_work": {
        "required": true,
        "alignment_correct": true,
        "carry_borrow_correct": true,
        "intermediate_steps_correct": true,
        "final_result_matches_work": true,
        "errors": []
      },
      "reason": ""
    }
  ]
}

填空拆分示例：
题目“36+8=□，先算：□○□=□，再算：□○□=□”的 answer_regions 必须类似：
[
  {"type":"result_after_equal","label":"36+8的结果","student_answer":"44","correct_answer":"44","is_correct":true,"bbox":{"x":0,"y":0,"w":10,"h":10},"reason":""},
  {"type":"blank_number","label":"先算第一个数","student_answer":"6","correct_answer":"6","is_correct":true,"bbox":{"x":0,"y":0,"w":10,"h":10},"reason":""},
  {"type":"blank_operator","label":"先算运算符","student_answer":"+","correct_answer":"+","is_correct":true,"bbox":{"x":0,"y":0,"w":10,"h":10},"reason":""},
  {"type":"blank_number","label":"先算第二个数","student_answer":"8","correct_answer":"8","is_correct":true,"bbox":{"x":0,"y":0,"w":10,"h":10},"reason":""},
  {"type":"result_after_equal","label":"先算结果","student_answer":"14","correct_answer":"14","is_correct":true,"bbox":{"x":0,"y":0,"w":10,"h":10},"reason":""}
]

连线题示例：
题目“他们各自都看到了什么？请连线。”中，学生画了 4 条线，answer_regions 必须有 4 项：
[
  {"type":"matching_line","label":"青青的连线","student_answer":"青青 -> 上方图形","correct_answer":"青青 -> 正确图形","is_correct":true,"bbox":{"x":0,"y":0,"w":50,"h":50},"reason":""},
  {"type":"matching_line","label":"明明的连线","student_answer":"明明 -> 中间图形","correct_answer":"明明 -> 正确图形","is_correct":false,"bbox":{"x":0,"y":0,"w":50,"h":50},"reason":"连接对象错误"}
]
"""


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_payload(image_path: Path, model: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": image_to_data_url(image_path),
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }


def call_ark(
    image_path: Path, model: str, timeout: int, prompt: str = GRADE_PROMPT
) -> dict[str, Any]:
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("ARK_API_KEY is not set")

    body = json.dumps(build_payload(image_path, model, prompt), ensure_ascii=False).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        f"{ARK_BASE_URL}/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ark API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to call Ark API: {exc.reason}") from exc


def extract_response_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.S)
    if fenced:
        return fenced.group(1).strip()
    return stripped


def parse_grading_json(response_text: str) -> dict[str, Any]:
    text = strip_json_fence(response_text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object")
    questions = parsed.get("questions")
    if not isinstance(questions, list):
        raise ValueError("Model response JSON must contain questions[]")
    return parsed


def parse_layout_json(response_text: str) -> dict[str, Any]:
    text = strip_json_fence(response_text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Layout response JSON must be an object")
    sections = parsed.get("sections")
    if not isinstance(sections, list):
        raise ValueError("Layout response JSON must contain sections[]")
    return parsed


def load_mock_result(image_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = {
        "coordinate_space": {"width": 1000, "height": 1000},
        "questions": [
            {
                "id": "mock-1",
                "question_type": "vertical_calculation",
                "question_text": "mock vertical question",
                "student_answer": "79",
                "correct_answer": "79",
                "is_correct": True,
                "confidence": 1.0,
                "answer_regions": [
                    {
                        "type": "result_after_equal",
                        "label": "等号后结果",
                        "student_answer": "79",
                        "correct_answer": "79",
                        "is_correct": True,
                        "bbox": {"x": 250, "y": 250, "w": 70, "h": 45},
                        "reason": "",
                    },
                    {
                        "type": "vertical_work",
                        "label": "竖式过程",
                        "student_answer": "35+44=79",
                        "correct_answer": "35+44=79",
                        "is_correct": True,
                        "bbox": {"x": 230, "y": 310, "w": 110, "h": 130},
                        "reason": "",
                    },
                ],
                "reason": "",
            },
            {
                "id": "mock-2",
                "question_type": "vertical_calculation",
                "question_text": "mock vertical process incorrect question",
                "student_answer": "90",
                "correct_answer": "90",
                "is_correct": False,
                "confidence": 1.0,
                "answer_regions": [
                    {
                        "type": "result_after_equal",
                        "label": "等号后结果",
                        "student_answer": "90",
                        "correct_answer": "90",
                        "is_correct": True,
                        "bbox": {"x": 550, "y": 250, "w": 70, "h": 45},
                        "reason": "",
                    },
                    {
                        "type": "vertical_work",
                        "label": "竖式过程",
                        "student_answer": "56+34=90",
                        "correct_answer": "56+34=90",
                        "is_correct": False,
                        "bbox": {"x": 530, "y": 310, "w": 110, "h": 130},
                        "reason": "结果正确但竖式过程错误",
                    },
                ],
                "reason": "结果正确但竖式过程错误",
            },
            {
                "id": "mock-3",
                "question_text": "mock uncertain question",
                "student_answer": "",
                "correct_answer": "",
                "is_correct": None,
                "confidence": 0.0,
                "answer_bbox": {
                    "x": 400,
                    "y": 500,
                    "w": 80,
                    "h": 80,
                },
                "reason": "uncertain mock result",
            },
        ]
}
    return parsed, {"mock": True}


def offset_bbox(bbox: dict[str, int] | None, dx: int, dy: int) -> dict[str, int] | None:
    if not bbox:
        return None
    return {
        "x": bbox["x"] + dx,
        "y": bbox["y"] + dy,
        "w": bbox["w"],
        "h": bbox["h"],
    }


def normalize_answer_regions(
    question: dict[str, Any],
    image_size: tuple[int, int],
    coordinate_space: tuple[int, int],
    offset: tuple[int, int] = (0, 0),
) -> list[dict[str, Any]]:
    raw_regions = question.get("answer_regions")
    if isinstance(raw_regions, list):
        regions = [region for region in raw_regions if isinstance(region, dict)]
    else:
        regions = []

    if not regions and isinstance(question.get("answer_bbox"), dict):
        regions = [
            {
                "type": "answer",
                "label": "答案",
                "student_answer": question.get("student_answer", ""),
                "correct_answer": question.get("correct_answer", ""),
                "is_correct": question.get("is_correct"),
                "bbox": question.get("answer_bbox"),
                "reason": question.get("reason", ""),
            }
        ]

    normalized: list[dict[str, Any]] = []
    for region in regions:
        normalized_region = dict(region)
        source_bbox = normalized_region.get("bbox")
        normalized_region["source_bbox"] = source_bbox
        bbox = normalize_bbox(source_bbox, image_size, coordinate_space)
        normalized_region["bbox"] = offset_bbox(bbox, offset[0], offset[1])
        normalized.append(normalized_region)
    return normalized


def parse_coordinate_space(
    grading: dict[str, Any], image_size: tuple[int, int]
) -> tuple[int, int]:
    raw_space = grading.get("coordinate_space")
    if not isinstance(raw_space, dict):
        return image_size

    try:
        width = int(round(float(raw_space["width"])))
        height = int(round(float(raw_space["height"])))
    except (KeyError, TypeError, ValueError):
        return image_size

    if width <= 0 or height <= 0:
        return image_size
    return width, height


def normalize_bbox(
    raw_bbox: Any, image_size: tuple[int, int], coordinate_space: tuple[int, int]
) -> dict[str, int] | None:
    if not isinstance(raw_bbox, dict):
        return None

    image_width, image_height = image_size
    space_width, space_height = coordinate_space
    try:
        x = float(raw_bbox["x"])
        y = float(raw_bbox["y"])
        w = float(raw_bbox["w"])
        h = float(raw_bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None

    if w <= 0 or h <= 0:
        return None

    scale_x = image_width / space_width
    scale_y = image_height / space_height
    pixel_x = int(round(x * scale_x))
    pixel_y = int(round(y * scale_y))
    pixel_w = int(round(w * scale_x))
    pixel_h = int(round(h * scale_y))

    pixel_x = max(0, min(pixel_x, image_width - 1))
    pixel_y = max(0, min(pixel_y, image_height - 1))
    right = max(pixel_x + 1, min(pixel_x + pixel_w, image_width))
    bottom = max(pixel_y + 1, min(pixel_y + pixel_h, image_height))
    return {"x": pixel_x, "y": pixel_y, "w": right - pixel_x, "h": bottom - pixel_y}


def draw_check(
    draw: ImageDraw.ImageDraw, bbox: dict[str, int], width: int, compact: bool = False
) -> None:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    size = max(26, min(width // (36 if compact else 28), 48 if compact else 64))
    mark_width = max(4, min(width // 260, 7))
    cx = x + w // 2
    cy = y + h // 2
    half = size // 2
    points = [
        (cx - half, cy),
        (cx - size // 8, cy + half // 2),
        (cx + half, cy - half),
    ]
    draw.line(points, fill=MARK_COLOR, width=mark_width, joint="curve")


def draw_cross(
    draw: ImageDraw.ImageDraw, bbox: dict[str, int], width: int, compact: bool = False
) -> None:
    x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
    size = max(26, min(width // (36 if compact else 28), 48 if compact else 64))
    mark_width = max(4, min(width // 260, 7))
    cx = x + w // 2
    cy = y + h // 2
    half = size // 2
    draw.line(
        [(cx - half, cy - half), (cx + half, cy + half)],
        fill=MARK_COLOR,
        width=mark_width,
    )
    draw.line(
        [(cx + half, cy - half), (cx - half, cy + half)],
        fill=MARK_COLOR,
        width=mark_width,
    )


def normalize_grading(
    grading: dict[str, Any],
    image_size: tuple[int, int],
    offset: tuple[int, int] = (0, 0),
) -> dict[str, Any]:
    coordinate_space = parse_coordinate_space(grading, image_size)
    normalized_questions: list[dict[str, Any]] = []
    stats = {
        "total": 0,
        "correct": 0,
        "incorrect": 0,
        "uncertain": 0,
        "regions": 0,
        "marked": 0,
    }

    for index, raw_question in enumerate(grading.get("questions", []), start=1):
        if not isinstance(raw_question, dict):
            continue

        question = dict(raw_question)
        question.setdefault("id", str(index))
        is_correct = question.get("is_correct")
        regions = normalize_answer_regions(question, image_size, coordinate_space, offset)
        question["answer_regions"] = regions
        question["source_answer_bbox"] = question.get("answer_bbox")
        question["answer_bbox"] = regions[0]["bbox"] if regions else None
        stats["total"] += 1
        stats["regions"] += len(regions)

        if is_correct is True:
            stats["correct"] += 1
        elif is_correct is False:
            stats["incorrect"] += 1
        else:
            question["is_correct"] = None
            stats["uncertain"] += 1

        normalized_questions.append(question)

    return {
        "questions": normalized_questions,
        "stats": stats,
    }


def draw_normalized_questions(
    image_path: Path,
    questions: list[dict[str, Any]],
    output_path: Path,
    stats: dict[str, int],
) -> None:
    with Image.open(image_path) as image:
        annotated = image.convert("RGB")

    draw = ImageDraw.Draw(annotated)
    image_width = annotated.size[0]
    for question in questions:
        regions = question.get("answer_regions", [])
        if not isinstance(regions, list):
            continue
        for region in regions:
            if not isinstance(region, dict):
                continue
            region_correct = region.get("is_correct")
            bbox = region.get("bbox")
            if not bbox:
                continue
            compact = region.get("type") == "matching_line"
            if region_correct is True:
                draw_check(draw, bbox, image_width, compact=compact)
                stats["marked"] += 1
            elif region_correct is False:
                draw_cross(draw, bbox, image_width, compact=compact)
                stats["marked"] += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output_path)


def annotate_image(
    image_path: Path, grading: dict[str, Any], output_path: Path
) -> dict[str, Any]:
    with Image.open(image_path) as image:
        image_size = image.size

    normalized = normalize_grading(grading, image_size)
    draw_normalized_questions(
        image_path=image_path,
        questions=normalized["questions"],
        output_path=output_path,
        stats=normalized["stats"],
    )
    return {
        "coordinate_space": {"width": image_size[0], "height": image_size[1]},
        "questions": normalized["questions"],
        "stats": normalized["stats"],
    }


def collect_images(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {input_path}")
        return [input_path]

    if input_path.is_dir():
        images = [
            path
            for path in sorted(input_path.iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not images:
            raise ValueError(f"No supported images found in: {input_path}")
        return images

    raise ValueError(f"Input path does not exist: {input_path}")


def output_paths(image_path: Path, output_dir: Path) -> tuple[Path, Path]:
    stem = image_path.stem
    return output_dir / f"{stem}_graded.png", output_dir / f"{stem}_report.json"


def expand_bbox(
    bbox: dict[str, int], image_size: tuple[int, int], padding: int
) -> dict[str, int]:
    width, height = image_size
    x = max(0, bbox["x"] - padding)
    y = max(0, bbox["y"] - padding)
    right = min(width, bbox["x"] + bbox["w"] + padding)
    bottom = min(height, bbox["y"] + bbox["h"] + padding)
    return {"x": x, "y": y, "w": right - x, "h": bottom - y}


def get_layout_sections(
    image_path: Path, model: str, timeout: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_response = call_ark(image_path, model, timeout, prompt=LAYOUT_PROMPT)
    response_text = extract_response_text(raw_response)
    if not response_text:
        raise RuntimeError("Ark layout response did not contain text output")
    layout = parse_layout_json(response_text)

    with Image.open(image_path) as image:
        image_size = image.size
    coordinate_space = parse_coordinate_space(layout, image_size)
    padding = max(12, image_size[0] // 80)

    sections: list[dict[str, Any]] = []
    for index, raw_section in enumerate(layout.get("sections", []), start=1):
        if not isinstance(raw_section, dict):
            continue
        bbox = normalize_bbox(raw_section.get("bbox"), image_size, coordinate_space)
        if not bbox:
            continue
        bbox = expand_bbox(bbox, image_size, padding)
        if bbox["w"] < image_size[0] * 0.15 or bbox["h"] < image_size[1] * 0.04:
            continue
        sections.append(
            {
                "id": str(raw_section.get("id") or f"section-{index}"),
                "title": str(raw_section.get("title") or ""),
                "bbox": bbox,
                "source_bbox": raw_section.get("bbox"),
            }
        )

    if not sections:
        sections = [
            {
                "id": "section-1",
                "title": "full image",
                "bbox": {"x": 0, "y": 0, "w": image_size[0], "h": image_size[1]},
                "source_bbox": None,
            }
        ]
    return sections, raw_response


def crop_sections(
    image_path: Path, sections: list[dict[str, Any]], chunk_dir: Path
) -> list[dict[str, Any]]:
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[dict[str, Any]] = []
    with Image.open(image_path) as image:
        for index, section in enumerate(sections, start=1):
            bbox = section["bbox"]
            crop_box = (
                bbox["x"],
                bbox["y"],
                bbox["x"] + bbox["w"],
                bbox["y"] + bbox["h"],
            )
            crop = image.crop(crop_box)
            chunk_path = chunk_dir / f"{image_path.stem}_{index:02d}.png"
            crop.save(chunk_path)
            chunks.append({**section, "path": chunk_path})
    return chunks


def merge_stats(target: dict[str, int], source: dict[str, int]) -> None:
    for key in ("total", "correct", "incorrect", "uncertain", "regions"):
        target[key] = target.get(key, 0) + int(source.get(key, 0))


def grade_chunk(
    chunk: dict[str, Any], model: str, timeout: int
) -> dict[str, Any]:
    raw_chunk_response = call_ark(chunk["path"], model, timeout)
    response_text = extract_response_text(raw_chunk_response)
    if not response_text:
        raise RuntimeError(f"{chunk['id']} response did not contain text output")
    grading = parse_grading_json(response_text)
    with Image.open(chunk["path"]) as chunk_image:
        chunk_size = chunk_image.size
    chunk_normalized = normalize_grading(
        grading,
        chunk_size,
        offset=(chunk["bbox"]["x"], chunk["bbox"]["y"]),
    )
    for question in chunk_normalized["questions"]:
        question["section_id"] = chunk["id"]
        question["section_title"] = chunk["title"]
    return {
        "chunk": chunk,
        "raw_response": raw_chunk_response,
        "normalized": chunk_normalized,
    }


def write_report(
    report_path: Path,
    image_path: Path,
    annotated_path: Path,
    normalized: dict[str, Any],
    raw_response: dict[str, Any],
    model: str,
) -> None:
    report = {
        "image": str(image_path),
        "annotated_image": str(annotated_path),
        "model": model,
        "coordinate_space": normalized["coordinate_space"],
        "stats": normalized["stats"],
        "questions": normalized["questions"],
        "sections": normalized.get("sections", []),
        "raw_response": raw_response,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def redraw_from_report(report_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    image_path = Path(report["image"])
    annotated_path = output_path or Path(report["annotated_image"])
    questions = report.get("questions", [])
    stats = dict(report.get("stats", {}))
    stats["marked"] = 0
    draw_normalized_questions(
        image_path=image_path,
        questions=questions,
        output_path=annotated_path,
        stats=stats,
    )
    report["annotated_image"] = str(annotated_path)
    report["stats"] = stats
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"annotated": annotated_path, "stats": stats}


def process_image(image_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    annotated_path, report_path = output_paths(image_path, args.out)

    if args.mock:
        grading, raw_response = load_mock_result(image_path)
        normalized = annotate_image(image_path, grading, annotated_path)
    elif args.no_chunk:
        raw_response = call_ark(image_path, args.model, args.timeout)
        response_text = extract_response_text(raw_response)
        if not response_text:
            raise RuntimeError("Ark response did not contain text output")
        grading = parse_grading_json(response_text)
        normalized = annotate_image(image_path, grading, annotated_path)
    else:
        sections, layout_raw_response = get_layout_sections(
            image_path, args.model, args.timeout
        )
        chunk_dir = args.out / "_chunks" / image_path.stem
        chunks = crop_sections(image_path, sections, chunk_dir)

        with Image.open(image_path) as image:
            image_size = image.size

        questions: list[dict[str, Any]] = []
        stats = {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "uncertain": 0,
            "regions": 0,
            "marked": 0,
        }
        chunk_reports: list[dict[str, Any]] = []

        if args.workers <= 1 or len(chunks) <= 1:
            chunk_results = [
                grade_chunk(chunk, args.model, args.timeout) for chunk in chunks
            ]
        else:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(args.workers, len(chunks))
            ) as executor:
                chunk_results = list(
                    executor.map(
                        lambda chunk: grade_chunk(chunk, args.model, args.timeout),
                        chunks,
                    )
                )

        for chunk_result in chunk_results:
            chunk = chunk_result["chunk"]
            chunk_normalized = chunk_result["normalized"]
            questions.extend(chunk_normalized["questions"])
            merge_stats(stats, chunk_normalized["stats"])
            chunk_reports.append(
                {
                    "section": {
                        "id": chunk["id"],
                        "title": chunk["title"],
                        "bbox": chunk["bbox"],
                        "source_bbox": chunk["source_bbox"],
                        "image": str(chunk["path"]),
                    },
                    "raw_response": chunk_result["raw_response"],
                    "stats": chunk_normalized["stats"],
                }
            )

        draw_normalized_questions(
            image_path=image_path,
            questions=questions,
            output_path=annotated_path,
            stats=stats,
        )
        normalized = {
            "coordinate_space": {"width": image_size[0], "height": image_size[1]},
            "questions": questions,
            "stats": stats,
            "sections": [
                {
                    "id": chunk["id"],
                    "title": chunk["title"],
                    "bbox": chunk["bbox"],
                    "source_bbox": chunk["source_bbox"],
                    "image": str(chunk["path"]),
                }
                for chunk in chunks
            ],
        }
        raw_response = {
            "layout": layout_raw_response,
            "chunks": chunk_reports,
        }

    write_report(
        report_path=report_path,
        image_path=image_path,
        annotated_path=annotated_path,
        normalized=normalized,
        raw_response=raw_response,
        model=args.model,
    )
    return {
        "image": image_path,
        "annotated": annotated_path,
        "report": report_path,
        "stats": normalized["stats"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grade paper images with Volcengine Ark vision responses."
    )
    parser.add_argument("input", type=Path, nargs="?", help="Image file or directory to grade.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs"),
        help="Output directory for annotated images and JSON reports.",
    )
    parser.add_argument(
        "--model",
        default=ARK_MODEL,
        help=f"Ark model id. Defaults to {ARK_MODEL}.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Ark API request timeout in seconds.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use local mock grading data to verify drawing without calling Ark.",
    )
    parser.add_argument(
        "--no-chunk",
        action="store_true",
        help="Grade the whole image in one Ark call instead of layout chunking.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Parallel Ark grading calls for section crops. Defaults to 2.",
    )
    parser.add_argument(
        "--redraw-report",
        type=Path,
        help="Redraw an existing report without calling Ark.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.redraw_report:
        try:
            result = redraw_from_report(args.redraw_report)
        except Exception as exc:
            print(f"{args.redraw_report}: failed: {exc}", file=sys.stderr)
            return 1
        print(f"redrawn: {result['annotated']}")
        print(f"stats: {result['stats']}")
        return 0

    if args.input is None:
        parser.error("input is required unless --redraw-report is used")

    try:
        images = collect_images(args.input)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    failures = 0
    for image_path in images:
        try:
            result = process_image(image_path, args)
        except Exception as exc:
            failures += 1
            print(f"{image_path}: failed: {exc}", file=sys.stderr)
            continue

        stats = result["stats"]
        print(
            f"{image_path}: total={stats['total']} correct={stats['correct']} "
            f"incorrect={stats['incorrect']} uncertain={stats['uncertain']} "
            f"regions={stats.get('regions', 0)} marked={stats['marked']}"
        )
        print(f"  annotated: {result['annotated']}")
        print(f"  report: {result['report']}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
