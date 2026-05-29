import base64
import json

from PIL import Image

from backend.providers import get_provider as _get_provider


RED = "#E53935"
LIGHT_RED = (229, 57, 53, 80)
GRAY = "#9E9E9E"
WHITE = "#FFFFFF"


def call_ai_analysis(image_path: str, prompt_text: str | None = None) -> dict:
    img = Image.open(image_path)
    img_w, img_h = img.size
    total_pixels = img_w * img_h

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    if prompt_text is not None:
        system_prompt = prompt_text.replace("{img_w}", str(img_w)).replace("{img_h}", str(img_h))
    else:
        system_prompt = f"""你是一位经验丰富的小学数学老师，擅长分析数学试卷的版面结构。
请仔细审阅这张数学试卷图片（原图尺寸：{img_w}×{img_h} 像素），以数学教师的专业视角识别以下区域：

1. **大题**：如"一、填空"、"二、选择题"、"三、计算"等，包含标题、分值说明及整体区域范围
2. **小题**：每道题的完整文字内容和范围，注意数学符号（□、÷、≈、× 等）
3. **填空位置**：括号 ()、方框 □ 等需要学生填写答案的空白处，标注所属小题
4. **作答区**：留给学生书写的空白行、横线区域、竖式计算留白、等号后面的空白等

**坐标格式——必须使用归一化坐标（0.0 到 1.0 之间的浮点数）**：
- x = 区域左上角距图片左边缘的水平距离 ÷ 图片总宽度
- y = 区域左上角距图片上边缘的垂直距离 ÷ 图片总高度
- w = 区域宽度 ÷ 图片总宽度
- h = 区域高度 ÷ 图片总高度

例如图片宽{img_w}像素、高{img_h}像素，某区域实际在像素坐标 x=640, y=853 处，宽 100px，高 50px，
则归一化后为 x=0.5, y=0.5, w≈0.078, h≈0.029。

输出 JSON 结构示例：
{{
  "paper_info": {{"title": "...", "grade": "...", "subject": "数学"}},
  "sections": [
    {{
      "section_number": 1,
      "title": "一、填空",
      "bbox": {{"x": 0.05, "y": 0.08, "w": 0.12, "h": 0.016}},
      "problems": [
        {{
          "problem_number": 1,
          "text": "题目文字",
          "bbox": {{"x": 0.05, "y": 0.10, "w": 0.68, "h": 0.018}},
          "blanks": [
            {{"text": "()", "bbox": {{"x": 0.36, "y": 0.10, "w": 0.02, "h": 0.013}}}}
          ],
          "answer_areas": [
            {{"type": "inline_blank", "bbox": {{"x": 0.36, "y": 0.10, "w": 0.02, "h": 0.013}}}}
          ]
        }}
      ]
    }}
  ]
}}

所有坐标值均使用 0.0~1.0 归一化坐标。返回严格 JSON，不含任何额外解释或 markdown 标记。

**极其重要的规则——必须严格遵守：**
1. **逐行扫描图片**，从上到下、从左到右，确保不遗漏任何一道题。每看到一个题号（1、2、3……或①②③……）就必须输出对应的小题。
2. **题号必须连续**：如果某大题下识别出题号 1、2、3、4、6，则说明你漏掉了第 5 题。请回头仔细检查图片中第 5 题的位置，补充输出。
3. **自检环节**：输出前，检查每个大题下的 problem_number 序列是否连续（如 1,2,3,4,5,6...），如果存在跳号，必须回到图片中补找遗漏的题目。
4. 计算题（如口算、竖式计算）中等号后面的答案区域也必须标注为 answer_areas。
5. 如果某道题的文字跨越多行，bbox 必须覆盖该题的所有行。
6. **【作答区识别——极其关键，必须严格区分】**：
   以下情况**不是**作答区，**禁止**标注为 answer_areas：
   - "□68÷7" 中的 □ —— 这是题目中的未知数占位符，和后面数字连写，属于题干文字
   - "□里最小" "□中最大" "□里可以填" 中的 □ —— 这是对未知数的文字描述，属于题干文字
   - 题目开头或句首的 □（如"□÷5=3"）—— 这是算式的一部分，属于题干文字
   以下情况**是**作答区，**必须**标注为 answer_areas：
   - 句末独立的 ( ) 或（ ）—— 学生填写答案的括号
   - 句末独立的 □ 且前后有空格或标点分隔（如"□里可以填 □"末尾的 □）
   - 等号 = 后面的空白或 ( )
   - 横线 _____ 上的空白
   **判断口诀：□后面紧跟数字或÷×+-等运算符 → 题干文字；□出现在句末或被括号包裹 → 作答区。**"""

    user_prompt = "请分析这张数学试卷图片的版面结构，按大题→小题→填空位置/作答区的层级输出归一化坐标 JSON。"

    image_content = _get_provider().build_image_content(image_path)
    user_content = [
        {"type": "text", "text": user_prompt},
        image_content,
    ]

    resp = _get_provider().chat_completion(
        system_prompt=system_prompt,
        user_content=user_content,
        max_tokens=32768,
        response_format={"type": "json_object"},
    )

    if resp.finish_reason == "length":
        raise RuntimeError(
            f"AI 输出被截断（finish_reason=length），请减少图片复杂度或稍后重试。"
            f"已返回内容长度：{len(resp.content)} 字符"
        )

    try:
        layout = json.loads(resp.content)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON 解析失败（finish_reason={resp.finish_reason}），原始返回前200字：{resp.content[:200]}")

    usage = resp.usage
    print(f"  Token: in {usage.get('prompt_tokens', '?')}, "
          f"out {usage.get('completion_tokens', '?')}, "
          f"total {usage.get('total_tokens', '?')}")
    print(f"  finish_reason: {resp.finish_reason}")

    if "sections" not in layout:
        raise RuntimeError("AI 返回的 JSON 缺少 sections 字段")
    if not layout["sections"]:
        raise RuntimeError("AI 返回的 sections 为空，未检测到任何题目结构")

    for i, sec in enumerate(layout["sections"], 1):
        probs = sec.get("problems", [])
        areas = sum(len(p.get("answer_areas", [])) for p in probs)
        print(f"  Section {i}: {sec.get('title', '?')} - {len(probs)} problems, {areas} answer_areas")

    return layout


OVERVIEW_PROMPT = """你是一位经验丰富的老师，擅长分析试卷的版面结构。
请仔细审阅这张试卷图片（原图尺寸：{img_w}×{img_h} 像素），第一步先识别全局结构：

1. **试卷基本信息**：标题、年级、科目
2. **所有大题**：如"一、填空"、"二、选择题"、"三、计算"等，包含标题、序号和区域范围

坐标格式——使用归一化坐标（0.0 到 1.0 之间）：
- x = 区域左上角距图片左边缘的水平距离 ÷ 图片总宽度
- y = 区域左上角距图片上边缘的垂直距离 ÷ 图片总高度
- w = 区域宽度 ÷ 图片总宽度
- h = 区域高度 ÷ 图片总高度

输出 JSON 结构：
{{
  "paper_info": {{"title": "...", "grade": "...", "subject": "数学"}},
  "sections": [
    {{"section_number": 1, "title": "一、填空", "bbox": {{"x": 0.05, "y": 0.08, "w": 0.90, "h": 0.40}}}},
    {{"section_number": 2, "title": "二、选择", "bbox": {{"x": 0.05, "y": 0.50, "w": 0.90, "h": 0.20}}}}
  ]
}}

**重要规则**：
- 必须识别出所有大题，一个都不能遗漏
- section_number 必须连续从 1 开始
- 每道大题的 bbox 需要完整覆盖该大题的全部内容（包括所有小题）
- 返回严格 JSON，不含任何额外解释或 markdown 标记"""


PER_SECTION_DETAIL_PROMPT_PREFIX = """现在是第{section_index}大题——"{section_title}"，大致位于图片的 (x={sx:.3f}, y={sy:.3f}) 到 (x={ex:.3f}, y={ey:.3f}) 区域（归一化坐标）。

请详细分析该大题区域内所有小题的题号、题目文字、填空位置和作答区坐标。"""


def call_ai_analysis_batched(image_path: str, prompt_text: str | None = None,
                             on_progress=None) -> dict:
    img = Image.open(image_path)
    img_w, img_h = img.size
    total_pixels = img_w * img_h

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # === Phase 1: Overview — identify paper info & section outlines ===
    if on_progress:
        on_progress("analyzing", "正在扫描试卷整体版面...")

    overview_system = OVERVIEW_PROMPT.format(img_w=img_w, img_h=img_h)
    image_content = _get_provider().build_image_content(image_path)
    overview_user_content = [
        {"type": "text", "text": "请识别这张试卷的所有大题标题和区域范围，不要遗漏任何大题。"},
        image_content,
    ]

    print(f"  [版面分析-概览] 正在识别大题结构...")
    resp = _get_provider().chat_completion(
        system_prompt=overview_system,
        user_content=overview_user_content,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )

    overview = json.loads(resp.content)
    sections_outline = overview.get("sections", [])
    paper_info = overview.get("paper_info", {})

    usage = resp.usage
    print(f"  [版面分析-概览] 识别到 {len(sections_outline)} 个大题, "
          f"in={usage.get('prompt_tokens','?')} out={usage.get('completion_tokens','?')}")

    if len(sections_outline) <= 1:
        if on_progress:
            on_progress("analyzing", "版面简单，使用单次分析模式...")
        return call_ai_analysis(image_path, prompt_text=prompt_text)

    # === Phase 2: Per-section detailed analysis (multi-turn) ===
    detail_system = prompt_text if prompt_text is not None else overview_system
    detail_system = detail_system.replace("{img_w}", str(img_w)).replace("{img_h}", str(img_h))

    messages = [{"role": "system", "content": detail_system}]
    all_sections = []

    for i, outline in enumerate(sections_outline):
        title = outline.get("title", f"第{i+1}大题")
        bbox = outline.get("bbox", {})
        sx = bbox.get("x", 0)
        sy = bbox.get("y", 0)
        ex = sx + bbox.get("w", 0.9)
        ey = sy + bbox.get("h", 0.3)
        total = len(sections_outline)

        if on_progress:
            on_progress("batch_analyzing",
                        f"第{i+1}/{total}批: {title}",
                        {"batch": i + 1, "total_batches": total,
                         "section_title": title})

        context = PER_SECTION_DETAIL_PROMPT_PREFIX.format(
            section_index=i + 1, section_title=title,
            sx=sx, sy=sy, ex=ex, ey=ey)

        instruction = (
            f"{context}\n\n"
            f"请输出该大题下所有小题的题号、题目文字、填空位和作答区的归一化坐标 JSON。"
        )

        if i == 0:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": instruction},
                _get_provider().build_image_content(image_path),
            ]})
        else:
            messages.append({"role": "user", "content": instruction})

        print(f"  [版面分析] 第{i+1}/{total}批 ({title})...")
        resp = _get_provider().chat_completion_with_messages(
            messages=messages,
            max_tokens=32768,
            response_format={"type": "json_object"},
        )

        if resp.finish_reason == "length":
            raise RuntimeError(
                f"第{i+1}批 ({title}) 输出被截断（finish_reason=length），已返回 {len(resp.content)} 字符")

        try:
            detail = json.loads(resp.content)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"第{i+1}批 ({title}) JSON 解析失败，前200字：{resp.content[:200]}")

        detail_sections = detail.get("sections", [])
        for s in detail_sections:
            s["_orig_section_idx"] = i
            for pj, problem in enumerate(s.get("problems", [])):
                problem["problem_number"] = pj + 1
            all_sections.append(s)

        messages.append({"role": "assistant", "content": resp.content})

        usage = resp.usage
        probs = sum(len(s.get("problems", [])) for s in detail_sections)
        print(f"  [版面分析] 第{i+1}批 ({title}): {len(detail_sections)}大题 {probs}题, "
              f"in={usage.get('prompt_tokens','?')} out={usage.get('completion_tokens','?')}")

        if on_progress:
            on_progress("batch_analyze_done",
                        f"第{i+1}/{total}批 ({title}) 完成: {probs}题",
                        {"batch": i + 1, "total_batches": total,
                         "section_title": title,
                         "problems_count": probs})

    for i, s in enumerate(all_sections):
        s["section_number"] = i + 1

    problems_count = sum(len(s.get("problems", [])) for s in all_sections)
    areas_count = sum(
        len(p.get("answer_areas", []))
        for s in all_sections
        for p in s.get("problems", [])
    )

    layout = {
        "paper_info": paper_info,
        "sections": all_sections,
    }

    if on_progress:
        on_progress("analysis_done",
                    f"版面分析完成：识别到 {len(all_sections)} 大题、{problems_count} 小题、{areas_count} 个作答区",
                    {"sections_count": len(all_sections),
                     "problems_count": problems_count,
                     "areas_count": areas_count})

    print(f"  版面分析全部完成: {len(all_sections)}大题 {problems_count}小题 {areas_count}作答区")
    return layout
