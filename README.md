# Volcengine Ark Quickstart

This workspace includes a minimal Responses API call for the Ark model from the PDF quickstart.

## Model

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Endpoint: `/responses`
- Model: `doubao-seed-2-0-pro-260215`
- API key environment variable: `ARK_API_KEY`

Before running the script, activate this model service in the Ark Console. If the service is not activated, Ark returns `ModelNotOpen`.

## Run

```bash
export ARK_API_KEY="your_api_key_here"
python3 ark_quickstart.py "hello"
```

Disable deep thinking when needed:

```bash
python3 ark_quickstart.py "hello" --disable-thinking
```

Print the full raw JSON:

```bash
python3 ark_quickstart.py "hello" --json
```

## Grade Paper Images

`grade_papers.py` first asks Ark to understand the full page layout and split the paper into major sections. It then crops each section, grades each crop independently, maps crop coordinates back to the original image, and draws check/cross marks on the returned answer regions.

Run one image:

```bash
export ARK_API_KEY="your_api_key_here"
python3 grade_papers.py 3.jpg --out outputs
```

Use more parallel crop grading calls:

```bash
python3 grade_papers.py 3.jpg --out outputs --workers 3
```

Run every supported image in a directory:

```bash
python3 grade_papers.py . --out outputs
```

Fallback to one whole-page grading call:

```bash
python3 grade_papers.py 3.jpg --out outputs --no-chunk
```

Verify local drawing without calling Ark:

```bash
python3 grade_papers.py 3.jpg --out outputs --mock
```

Redraw an existing report without calling Ark:

```bash
python3 grade_papers.py --redraw-report outputs/8_report.json
```

Outputs:

- `outputs/<image>_graded.png`: annotated paper image.
- `outputs/<image>_report.json`: structured grading report with per-question result, per-region answer bboxes, model source bboxes, stats, and raw model response.
- `outputs/_chunks/<image>/`: section crops used for per-section grading.

Current behavior:

- The model computes the standard answer directly from the image; no answer key file is required.
- Correct answers get a green check, incorrect answers get a red cross.
- Uncertain questions are kept in JSON and are not marked on the image.
- Multiple images are graded independently.
- By default, large images are graded in chunks to reduce single-call latency and improve layout accuracy.
- Section crops are graded in parallel with `--workers` concurrent API calls.

Answer-region policy:

- The model must read the problem requirement first, then mark only the required formal answer region.
- Student scratch work, intermediate calculations, auxiliary vertical work, and side notes are not answer regions unless the printed problem explicitly asks for them.
- Blank printed answer slots mean the student did not answer and should be marked incorrect.
- Questions without visible student work are still graded as incorrect.
- For proof, construction, word-problem, and open-response questions with no handwritten solution, mark a small cross near the question number, the formal answer start, or the blank answer area; do not cover the entire printed problem.
- For word problems, mark the final submitted expression/answer with units, not intermediate scratch values.
- Example: for “商店里有26个玩具熊，卖出17个后，又运来35个，现在商店多少个玩具熊？”, the intermediate `9` under `26-17` is scratch work; only `26-17+35=44(个)` is the answer region.

Answer-card policy:

- Ignore answer cards, answer tables, scantron areas, correction panels, scoring boxes, and analysis sidebars as answer regions.
- These areas may be used to read the student's selected answer, but marks should be drawn on the corresponding question body.
- For multiple-choice questions, mark the blank in the question text, the option mark in the body, or the question's formal answer slot, not the answer-card cell.
- If the student only filled the answer card, draw the mark near the question body's `（ ）` blank.

Fill-blank region rules:

- Printed placeholders are independent answer regions.
- Placeholders include `□`, `○`, parentheses blanks, underlines, table blanks, and similar answer slots.
- Do not merge multiple blanks into one bbox.
- `□○□=□` should produce 4 regions: first number, operator, second number, result.
- `36+8=□，先算：□○□=□，再算：□○□=□` should produce 9 regions.
- Number blanks use `type: "blank_number"`, operator circles use `type: "blank_operator"`, and equals-sign results can use `type: "result_after_equal"`.

Matching-line rules:

- Matching/connecting questions use `question_type: "matching_line"`.
- Each drawn student line is an independent answer region.
- Use `type: "matching_line"` and write `student_answer` as `left item -> right item`.
- The bbox should be near the start of each line, not the full long line, so marks do not overlap at line crossings.
- Matching-line marks are drawn more compactly than normal answer marks.

Vertical calculation grading:

- If a problem asks for vertical calculation, the model must check both the final result and the written vertical work.
- A problem is vertical calculation only when the printed instruction or its section title explicitly requires vertical calculation.
- Do not classify a word problem as vertical calculation just because the student wrote scratch vertical work.
- A vertical calculation is correct only when the final answer is correct, place-value alignment is correct, carry/borrow handling is correct, and intermediate steps match the expression.
- If the final result is right but the vertical work is wrong, the question is marked incorrect.
- Vertical calculation questions have two answer regions:
  - `result_after_equal`: the result written after the printed equals sign.
  - `vertical_work`: the full written vertical calculation area.
- The question-level `is_correct` is true only when both regions are correct.

Example model JSON for a correct vertical calculation:

```json
{
  "id": "2.1",
  "question_type": "vertical_calculation",
  "question_text": "35+44=",
  "student_answer": "79",
  "correct_answer": "79",
  "is_correct": true,
  "confidence": 0.96,
  "answer_regions": [
    {
      "type": "result_after_equal",
      "label": "等号后结果",
      "student_answer": "79",
      "correct_answer": "79",
      "is_correct": true,
      "bbox": {"x": 180, "y": 470, "w": 45, "h": 32},
      "reason": ""
    },
    {
      "type": "vertical_work",
      "label": "竖式过程",
      "student_answer": "35+44=79",
      "correct_answer": "35+44=79",
      "is_correct": true,
      "bbox": {"x": 170, "y": 510, "w": 95, "h": 160},
      "reason": ""
    }
  ],
  "vertical_work": {
    "required": true,
    "student_expression": "35+44=79",
    "alignment_correct": true,
    "carry_borrow_correct": true,
    "intermediate_steps_correct": true,
    "final_result_matches_work": true,
    "errors": []
  },
  "reason": ""
}
```

Example model JSON when the result is correct but the vertical work is wrong:

```json
{
  "id": "2.2",
  "question_type": "vertical_calculation",
  "question_text": "56+34=",
  "student_answer": "90",
  "correct_answer": "90",
  "is_correct": false,
  "confidence": 0.88,
  "answer_regions": [
    {
      "type": "result_after_equal",
      "label": "等号后结果",
      "student_answer": "90",
      "correct_answer": "90",
      "is_correct": true,
      "bbox": {"x": 340, "y": 470, "w": 45, "h": 32},
      "reason": ""
    },
    {
      "type": "vertical_work",
      "label": "竖式过程",
      "student_answer": "56+34=90",
      "correct_answer": "56+34=90",
      "is_correct": false,
      "bbox": {"x": 330, "y": 510, "w": 95, "h": 160},
      "reason": "竖式中十位和个位未按数位对齐或中间计算书写不规范"
    }
  ],
  "vertical_work": {
    "required": true,
    "student_expression": "56+34=90",
    "alignment_correct": false,
    "carry_borrow_correct": true,
    "intermediate_steps_correct": false,
    "final_result_matches_work": true,
    "errors": ["结果正确，但竖式中十位和个位未按数位对齐或中间计算书写不规范"]
  },
  "reason": "结果正确但竖式过程错误"
}
```
