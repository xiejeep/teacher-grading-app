import json
import sqlite3
from datetime import datetime, timezone

from backend.config import DATABASE_URL

DEFAULT_ANALYSIS_PROMPT = """你是一位经验丰富的小学数学老师，擅长分析数学试卷的版面结构。
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

DEFAULT_GRADING_PROMPT = """你是一位经验丰富的{subject}老师，负责批改学生试卷。
请仔细审阅这张学生作答的试卷图片和给定的版面结构信息。

你需要逐题判断每个作答区域中学生填写的内容是否正确。

{standard_answers_section}

版面结构信息（JSON格式，包含所有题目的作答区域坐标）：
{layout_json}

输出 JSON 结构（必须严格按照此结构，返回所有题目）：
{{
  "paper_info": {{"title": "...", "grade": "...", "subject": "{subject}"}},
  "sections": [
    {{
      "section_number": 1,
      "title": "一、...",
      "problems": [
        {{
          "problem_number": 1,
          "problem_text": "题目文字",
          "area_gradings": [
            {{
              "area_index": 0,
              "student_answer": "学生在作答区填写的内容",
              "correct_answer": "该空的正确答案",
              "is_correct": true,
              "score": 5,
              "max_score": 5,
              "comment": "批改评语（可选）"
            }}
          ],
          "problem_total_score": 5,
          "problem_max_score": 5
        }}
      ]
    }}
  ],
  "total_score": 85,
  "total_max_score": 100
}}

 注意：
- area_index 对应版面结构中 answer_areas 数组的索引（从0开始）
- student_answer 是从图片作答区中识别出的学生填写内容，如果作答区为空则填"（未作答）"
- is_correct 根据参考答案和题目要求判断是否正确
- 对于计算题，关注过程和最终结果
- comment 必须以老师对学生的口吻写（如"做得很棒！""注意计算步骤哦""这个规律找对了"），不要写推理过程
- 所有 JSON 字段必须使用英文双引号，不能使用中文引号
- 返回严格 JSON，不含任何额外解释或 markdown 标记"""

DEFAULT_EXTRACTION_PROMPT = """你是一位教育工作者，需要从答案图片中提取参考答案信息。
请仔细阅读这张答案图片，提取每道题的正确答案。

输出 JSON 格式：
{{
  "answers": [
    {{"problem_number": 1, "answer": "A", "section_hint": "一、选择题"}},
    {{"problem_number": 2, "answer": "12", "section_hint": "二、填空题"}},
    {{"problem_number": 3, "answer": "x=5", "section_hint": "三、计算题"}}
  ],
  "note": "如有需要额外说明的地方"
}}

注意：
- problem_number 是题号
- answer 是该题的正确答案
- section_hint 是题目所属大题类型，用于辅助匹配
- 如果图片中包含多道题，请全部提取
- 返回严格 JSON，不含任何额外解释或 markdown 标记"""

PROMPT_SEED_DATA = [
    ("数学", "小学", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("数学", "初中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("数学", "高中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("语文", "小学", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("语文", "初中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("语文", "高中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("英语", "小学", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("英语", "初中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
    ("英语", "高中", DEFAULT_ANALYSIS_PROMPT, DEFAULT_GRADING_PROMPT, DEFAULT_EXTRACTION_PROMPT),
]


def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    import os as _os
    from backend.config import UPLOAD_DIR, ANNOTATED_DIR, GRADING_UPLOAD_DIR, ANSWER_KEY_DIR
    for d in [UPLOAD_DIR, ANNOTATED_DIR, GRADING_UPLOAD_DIR, ANSWER_KEY_DIR]:
        _os.makedirs(d, exist_ok=True)

    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_runs (
            run_id TEXT PRIMARY KEY,
            original_filename TEXT NOT NULL,
            image_path TEXT NOT NULL,
            annotated_path TEXT NOT NULL,
            layout_json TEXT NOT NULL,
            image_width INTEGER NOT NULL,
            image_height INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grading_runs (
            grading_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '数学',
            stage TEXT NOT NULL DEFAULT '小学',
            standard_answers_json TEXT,
            standard_answer_image TEXT,
            grading_result_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exam_templates (
            template_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            stage TEXT NOT NULL,
            run_id TEXT NOT NULL,
            standard_answers_json TEXT,
            image_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            stage TEXT NOT NULL,
            analysis_prompt TEXT NOT NULL,
            grading_prompt TEXT NOT NULL,
            answer_extraction_prompt TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(subject, stage)
        )
    """)

    now = datetime.now(timezone.utc).isoformat()
    for subject, stage, ap, gp, ep in PROMPT_SEED_DATA:
        conn.execute(
            "INSERT OR IGNORE INTO prompts (subject, stage, analysis_prompt, grading_prompt, answer_extraction_prompt, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (subject, stage, ap, gp, ep, now),
        )

    conn.commit()
    conn.close()


def save_result(run_id: str, filename: str, image_path: str,
                layout: dict, img_w: int, img_h: int):
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO analysis_runs (run_id, original_filename, image_path, annotated_path, layout_json, image_width, image_height, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, filename, image_path, "", json.dumps(layout, ensure_ascii=False), img_w, img_h, now),
    )
    conn.commit()
    conn.close()


def get_result(run_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_history() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT run_id, original_filename, image_path, layout_json, image_width, image_height, created_at FROM analysis_runs ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_layout(run_id: str, layout: dict):
    conn = get_db()
    conn.execute(
        "UPDATE analysis_runs SET layout_json = ? WHERE run_id = ?",
        (json.dumps(layout, ensure_ascii=False), run_id),
    )
    conn.commit()
    conn.close()


def get_image_path(run_id: str) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT image_path FROM analysis_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return row["image_path"]


def delete_result(run_id: str) -> bool:
    conn = get_db()
    cursor = conn.execute("DELETE FROM analysis_runs WHERE run_id = ?", (run_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def save_grading(grading_id: str, run_id: str, subject: str, stage: str,
                 standard_answers: dict | None, answer_image_path: str | None) -> str:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO grading_runs (grading_id, run_id, subject, stage, standard_answers_json, standard_answer_image, grading_result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (grading_id, run_id, subject, stage,
         json.dumps(standard_answers, ensure_ascii=False) if standard_answers else None,
         answer_image_path, None, now),
    )
    conn.commit()
    conn.close()
    return grading_id


def save_grading_result(grading_id: str, result: dict):
    conn = get_db()
    conn.execute(
        "UPDATE grading_runs SET grading_result_json = ? WHERE grading_id = ?",
        (json.dumps(result, ensure_ascii=False), grading_id),
    )
    conn.commit()
    conn.close()


def get_grading(grading_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM grading_runs WHERE grading_id = ?", (grading_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_grading_history() -> list[dict]:
    conn = get_db()
    rows = conn.execute("""
        SELECT g.grading_id, g.run_id, g.subject, g.stage, g.grading_result_json, g.created_at,
               a.original_filename, a.image_path
        FROM grading_runs g
        JOIN analysis_runs a ON g.run_id = a.run_id
        ORDER BY g.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_grading(grading_id: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT run_id, standard_answer_image FROM grading_runs WHERE grading_id = ?", (grading_id,)).fetchone()
    if row is None:
        conn.close()
        return False
    conn.execute("DELETE FROM grading_runs WHERE grading_id = ?", (grading_id,))
    conn.commit()
    conn.close()
    return True


def get_prompts(subject: str | None = None, stage: str | None = None) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM prompts WHERE 1=1"
    params: list = []
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    if stage:
        query += " AND stage = ?"
        params.append(stage)
    query += " ORDER BY subject, stage"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_prompt(prompt_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_prompt_by_subject_stage(subject: str, stage: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM prompts WHERE subject = ? AND stage = ?", (subject, stage)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def update_prompt(prompt_id: int, analysis_prompt: str, grading_prompt: str, answer_extraction_prompt: str) -> bool:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "UPDATE prompts SET analysis_prompt = ?, grading_prompt = ?, answer_extraction_prompt = ?, updated_at = ? WHERE id = ?",
        (analysis_prompt, grading_prompt, answer_extraction_prompt, now, prompt_id),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def create_prompt(subject: str, stage: str, analysis_prompt: str, grading_prompt: str, answer_extraction_prompt: str) -> int:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO prompts (subject, stage, analysis_prompt, grading_prompt, answer_extraction_prompt, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (subject, stage, analysis_prompt, grading_prompt, answer_extraction_prompt, now),
    )
    prompt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return prompt_id


def create_template(template_id: str, name: str, subject: str, stage: str,
                    run_id: str, standard_answers: dict | None,
                    image_path: str | None) -> str:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO exam_templates (template_id, name, subject, stage, run_id, standard_answers_json, image_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (template_id, name, subject, stage, run_id,
         json.dumps(standard_answers, ensure_ascii=False) if standard_answers else None,
         image_path, now, now),
    )
    conn.commit()
    conn.close()
    return template_id


def get_template(template_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT t.*, a.layout_json, a.image_path as analysis_image_path, a.image_width, a.image_height "
        "FROM exam_templates t JOIN analysis_runs a ON t.run_id = a.run_id "
        "WHERE t.template_id = ?", (template_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def list_templates(subject: str | None = None, stage: str | None = None) -> list[dict]:
    conn = get_db()
    query = "SELECT t.*, a.image_path as analysis_image_path FROM exam_templates t JOIN analysis_runs a ON t.run_id = a.run_id WHERE 1=1"
    params: list = []
    if subject:
        query += " AND t.subject = ?"
        params.append(subject)
    if stage:
        query += " AND t.stage = ?"
        params.append(stage)
    query += " ORDER BY t.updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_template(template_id: str, name: str | None = None,
                    standard_answers: dict | None = None) -> bool:
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    fields = ["updated_at = ?"]
    values: list = [now]
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if standard_answers is not None:
        fields.append("standard_answers_json = ?")
        values.append(json.dumps(standard_answers, ensure_ascii=False))
    values.append(template_id)
    cursor = conn.execute(
        f"UPDATE exam_templates SET {', '.join(fields)} WHERE template_id = ?",
        values,
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_template(template_id: str) -> bool:
    conn = get_db()
    cursor = conn.execute("DELETE FROM exam_templates WHERE template_id = ?", (template_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
