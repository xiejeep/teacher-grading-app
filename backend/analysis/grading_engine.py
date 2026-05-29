import base64
import json
import sys

import requests
from PIL import Image

from backend.config import API_URL, API_KEY, EP_ID


def call_ai_extract_answers(image_path: str, prompt_text: str,
                            on_progress=None) -> dict:
    if on_progress:
        on_progress("extracting", "正在从答案图片中提取参考答案...")

    img = Image.open(image_path)
    img_w, img_h = img.size
    total_pixels = img_w * img_h

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": EP_ID,
        "thinking": {"type": "enabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 16384,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": prompt_text},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请提取这张答案图片中的所有参考答案信息。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "image_pixel_limit": {
                                "min_pixels": int(total_pixels * 0.92),
                                "max_pixels": int(total_pixels * 1.08),
                            },
                        },
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"答案提取 JSON 解析失败，原始返回前200字：{content[:200]}")

    if "answers" not in result:
        result["answers"] = []

    usage = data.get("usage", {})
    print(f"  [答案提取] Token: in {usage.get('prompt_tokens', '?')}, out {usage.get('completion_tokens', '?')}")

    if on_progress:
        on_progress("extraction_done", f"提取到 {len(result['answers'])} 条参考答案",
                    {"answers_count": len(result["answers"])})

    return result


def call_ai_extract_answers_from_text(answer_text: str, layout: dict,
                                      on_progress=None) -> dict:
    if on_progress:
        on_progress("extracting", "正在从文本中提取参考答案...")

    layout_json = json.dumps(layout, ensure_ascii=False)
    system_prompt = (
        "你是一个试卷答案解析助手。教师提供了一段包含参考答案的文本，"
        "以及试卷的版面结构信息（JSON格式，包含 sections > problems 的题目框架）。\n\n"
        "请根据版面结构中的题号信息，将文本中的答案匹配到对应的题目上。\n\n"
        "输出JSON格式：\n"
        '{"answers": [{"problem_key": "1.1", "correct_answer": "42", "section_hint": "一、填空题"}]}\n\n'
        "规则：\n"
        "- problem_key 格式为 section_number.problem_number（如 1.3 表示第一大题第3小题）\n"
        "- 如果文本中的答案无法匹配到具体题号，尽量按顺序匹配\n"
        "- correct_answer 保留原始内容，不要省略或改写\n"
        "- section_hint 填写该题所属的 section title"
    )

    user_text = (
        f"试卷版面结构：\n{layout_json}\n\n"
        f"教师提供的答案文本：\n{answer_text}\n\n"
        f"请提取所有参考答案，匹配到版面结构中的题目。"
    )

    payload = {
        "model": EP_ID,
        "thinking": {"type": "enabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 16384,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"文本答案提取 JSON 解析失败，原始返回前200字：{content[:200]}")

    if "answers" not in result:
        result["answers"] = []

    usage = data.get("usage", {})
    print(f"  [文本答案提取] Token: in {usage.get('prompt_tokens', '?')}, out {usage.get('completion_tokens', '?')}")

    if on_progress:
        on_progress("extraction_done", f"提取到 {len(result['answers'])} 条参考答案",
                     {"answers_count": len(result["answers"])})

    return result


def build_standard_answers_section(standard_answers: list[dict] | None) -> str:
    if not standard_answers:
        return "（本次批改未提供参考答案，请根据题目内容和常识判断学生作答是否正确）"

    lines = ["以下是教师提供的参考答案："]
    for a in standard_answers:
        hint = f" ({a.get('section_hint', '')})" if a.get('section_hint') else ""
        lines.append(f"  - 题号 {a.get('problem_key', '?')}: {a.get('correct_answer', '?')}{hint}")
    return "\n".join(lines)


def call_ai_grade(image_path: str, layout: dict, grading_prompt: str,
                  standard_answers: list[dict] | None = None,
                  on_progress=None) -> dict:
    if on_progress:
        on_progress("grading", "正在调用 AI 批改模型，请耐心等待...")

    img = Image.open(image_path)
    img_w, img_h = img.size
    total_pixels = img_w * img_h

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    answers_section = build_standard_answers_section(standard_answers)
    layout_json = json.dumps(layout, ensure_ascii=False)

    system_prompt = grading_prompt.replace("{standard_answers_section}", answers_section)
    system_prompt = system_prompt.replace("{layout_json}", layout_json)

    parent = layout.get("paper_info", {}) or {}
    for placeholder, value in [
        ("{subject}", parent.get("subject", "数学")),
        ("{img_w}", str(img_w)),
        ("{img_h}", str(img_h)),
    ]:
        system_prompt = system_prompt.replace(placeholder, value)

    payload = {
        "model": EP_ID,
        "thinking": {"type": "enabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": 32768,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请批改这张学生试卷，对照参考答案逐题判断对错，输出详细的批改结果 JSON。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "image_pixel_limit": {
                                "min_pixels": int(total_pixels * 0.92),
                                "max_pixels": int(total_pixels * 1.08),
                            },
                        },
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"  正在调用 AI 批改（{img_w}×{img_h}）...")
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    if on_progress:
        on_progress("grading", "AI 批改完成，正在解析结果...")

    choice = data["choices"][0]
    finish_reason = choice.get("finish_reason", "unknown")
    content = choice["message"]["content"]

    if finish_reason == "length":
        raise RuntimeError(
            f"AI 批改输出被截断（finish_reason=length），已返回内容长度：{len(content)} 字符"
        )

    try:
        grading = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"批改 JSON 解析失败（finish_reason={finish_reason}），原始返回前200字：{content[:200]}")

    if "sections" not in grading:
        raise RuntimeError("AI 批改返回的 JSON 缺少 sections 字段")

    usage = data.get("usage", {})
    print(f"  [批改] Token: in {usage.get('prompt_tokens', '?')}, out {usage.get('completion_tokens', '?')}, total {usage.get('total_tokens', '?')}")

    for i, sec in enumerate(grading.get("sections", []), 1):
        probs = sec.get("problems", [])
        correct_count = sum(1 for p in probs if p.get("problem_total_score", 0) == p.get("problem_max_score", 0))
        print(f"  Section {i}: {sec.get('title', '?')} - {len(probs)} 题, {correct_count} 全对")

    total = grading.get("total_score", 0)
    max_total = grading.get("total_max_score", 0)
    print(f"  总分: {total}/{max_total}")

    area_correct = 0
    area_total = 0
    for sec in grading.get("sections", []):
        for p in sec.get("problems", []):
            for ag in p.get("area_gradings", []):
                area_total += 1
                if ag.get("is_correct") is True:
                    area_correct += 1
    grading["correct_count"] = area_correct
    grading["total_areas"] = area_total

    if on_progress:
        sections_count = len(grading.get("sections", []))
        problems_count = sum(len(s.get("problems", [])) for s in grading.get("sections", []))
        on_progress("grading_done", f"批改完成：{sections_count} 大题、{problems_count} 小题，答对 {area_correct}/{area_total} 个作答区",
                    {"correct_count": area_correct, "total_areas": area_total,
                     "sections_count": sections_count, "problems_count": problems_count})

    return grading


def split_sections_into_batches(sections: list[dict], max_per_batch: int = 5) -> tuple[list[list[dict]], list[list[int]]]:
    batches = []
    batch_origins = []
    for orig_idx, section in enumerate(sections):
        problems = section.get("problems", [])
        if not problems:
            continue
        if len(problems) <= max_per_batch:
            batches.append([section])
            batch_origins.append([orig_idx])
        else:
            for i in range(0, len(problems), max_per_batch):
                sub = dict(section)
                sub["problems"] = problems[i:i + max_per_batch]
                batches.append([sub])
                batch_origins.append([orig_idx])
    return batches, batch_origins


def aggregate_batch_results(batch_results: list[dict], paper_info: dict) -> dict:
    all_sections = []
    total_score = 0
    total_max_score = 0
    area_correct = 0
    area_total = 0
    for result in batch_results:
        for s in result.get("sections", []):
            for p in s.get("problems", []):
                total_score += p.get("problem_total_score", 0) or 0
                total_max_score += p.get("problem_max_score", 0) or 0
                for ag in p.get("area_gradings", []):
                    area_total += 1
                    if ag.get("is_correct") is True:
                        area_correct += 1
            all_sections.append(s)
    for i, s in enumerate(all_sections):
        s["section_number"] = i + 1
        s.setdefault("_orig_section_idx", s.get("section_number", i + 1) - 1)
    return {
        "paper_info": paper_info,
        "sections": all_sections,
        "total_score": total_score,
        "total_max_score": total_max_score,
        "correct_count": area_correct,
        "total_areas": area_total,
    }


def call_ai_grade_batched(image_path: str, layout: dict, grading_prompt: str,
                          standard_answers: list[dict] | None = None,
                          on_progress=None) -> dict:
    img = Image.open(image_path)
    img_w, img_h = img.size
    total_pixels = img_w * img_h

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    parent = layout.get("paper_info", {}) or {}
    system_prompt = grading_prompt
    system_prompt = system_prompt.replace("{standard_answers_section}", "")
    system_prompt = system_prompt.replace("{layout_json}", "")
    for ph, val in [
        ("{subject}", parent.get("subject", "数学")),
        ("{img_w}", str(img_w)),
        ("{img_h}", str(img_h)),
    ]:
        system_prompt = system_prompt.replace(ph, val)

    sections = layout.get("sections", [])
    batches, batch_origins = split_sections_into_batches(sections)

    if len(batches) <= 1:
        return call_ai_grade(image_path, layout, grading_prompt, standard_answers, on_progress=on_progress)

    all_results = []
    messages = [{"role": "system", "content": system_prompt}]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    for i, batch in enumerate(batches):
        batch_title = batch[0].get("title", f"第{i+1}批") if batch else f"第{i+1}批"
        total_batches = len(batches)
        batch_problems = sum(len(s.get("problems", [])) for s in batch)

        if on_progress:
            on_progress(
                "batch_grading",
                f"第{i+1}/{total_batches}批: {batch_title}",
                {
                    "batch": i + 1, "total_batches": total_batches,
                    "section_title": batch_title, "problems_count": batch_problems,
                },
            )

        batch_layout = json.dumps({"sections": batch}, ensure_ascii=False)
        answers_section = build_standard_answers_section(standard_answers)

        instructions = (
            f"请批改试卷的{batch_title}部分。\n\n"
            f"{answers_section}\n\n"
            f"版面结构信息（JSON格式）：\n{batch_layout}\n\n"
            f"请输出该部分每个题目的批改结果 JSON（包含 sections 数组）。"
        )

        if i == 0:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": instructions},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "image_pixel_limit": {
                                "min_pixels": int(total_pixels * 0.92),
                                "max_pixels": int(total_pixels * 1.08),
                            },
                        },
                    },
                ],
            })
        else:
            messages.append({"role": "user", "content": instructions})

        payload = {
            "model": EP_ID,
            "thinking": {"type": "enabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": 32768,
            "temperature": 0,
            "messages": messages,
        }

        print(f"  正在调用 AI 批改 第{i+1}/{total_batches}批 ({batch_title}, {batch_problems}题)...")
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason", "unknown")
        content = choice["message"]["content"]

        if finish_reason == "length":
            raise RuntimeError(
                f"AI 批改输出被截断（finish_reason=length），已返回内容长度：{len(content)} 字符"
            )

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"批改 JSON 解析失败（finish_reason={finish_reason}），原始返回前200字：{content[:200]}")

        if "sections" not in result:
            raise RuntimeError("AI 批改返回的 JSON 缺少 sections 字段")

        orig_indices = batch_origins[i]
        for si, orig_idx in enumerate(orig_indices):
            if si < len(result["sections"]):
                result["sections"][si]["_orig_section_idx"] = orig_idx

        for gi, graded_section in enumerate(result.get("sections", [])):
            if gi < len(batch):
                batch_section = batch[gi]
                batch_problems = batch_section.get("problems", [])
                for pj, graded_problem in enumerate(graded_section.get("problems", [])):
                    if pj < len(batch_problems):
                        graded_problem["problem_number"] = batch_problems[pj]["problem_number"]

        all_results.append(result)
        messages.append({"role": "assistant", "content": content})

        usage = data.get("usage", {})
        print(f"  [批改 第{i+1}批] Token: in {usage.get('prompt_tokens', '?')}, out {usage.get('completion_tokens', '?')}")

        if on_progress:
            result_sections = len(result.get("sections", []))
            result_problems = sum(len(s.get("problems", [])) for s in result.get("sections", []))
            on_progress(
                "batch_done",
                f"第{i+1}/{total_batches}批 ({batch_title}) 完成: {result_sections}大题 {result_problems}小题",
                {
                    "batch": i + 1, "total_batches": total_batches,
                    "section_title": batch_title,
                    "sections_count": result_sections, "problems_count": result_problems,
                },
            )

        batch_title_tag = batch_title[:6]
        print(f"  {batch_title_tag}: {result_sections}大题 {result_problems}小题")

    final_result = aggregate_batch_results(all_results, parent)
    total = final_result.get("total_score", 0)
    max_total = final_result.get("total_max_score", 0)
    area_correct = final_result.get("correct_count", 0)
    area_total = final_result.get("total_areas", 0)
    sec_count = len(final_result.get("sections", []))
    prob_count = sum(len(s.get("problems", [])) for s in final_result.get("sections", []))

    if on_progress:
        on_progress("grading_done",
                    f"全部分批批改完成：{sec_count} 大题、{prob_count} 小题，答对 {area_correct}/{area_total} 个作答区",
                    {"correct_count": area_correct, "total_areas": area_total,
                     "sections_count": sec_count, "problems_count": prob_count})

    print(f"  全部批改完成: {sec_count}大题 {prob_count}小题, 答对 {area_correct}/{area_total} 个作答区")
    return final_result
