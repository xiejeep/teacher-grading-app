# AGENTS.md — 试卷批改系统

## Architecture

- **Backend**: FastAPI on `:8000` — `backend/main.py` (entry: `python run.py`)
- **Frontend**: Vue 3 + Element Plus + TypeScript — Vite dev on `:5173`, proxies `/api` + `/static` to `localhost:8000`
- **Database**: SQLite at `backend/storage/app.db` (auto-created by `init_db()`)
- **External API**: Volces Ark (豆包) vision model — configured in `backend/.env`
- `backend/storage/` is gitignored (uploads, annotated images, DB are local only)

## Commands

| Task | Command | Dir |
|------|---------|-----|
| Start backend | `python run.py` | root |
| Install frontend deps | `pnpm install` | `frontend/` |
| Start frontend dev | `pnpm dev` | `frontend/` |
| Build frontend | `pnpm build` (runs `vue-tsc -b` then `vite build`) | `frontend/` |

## Key Gotchas

- **Package manager is pnpm** (not npm/yarn) — `frontend/pnpm-lock.yaml`
- **`.env` with real API keys** exists at `backend/.env` — gitignored, but treat as sensitive
- **`backend/storage/`** dirs (`uploads/`, `annotated/`, `grading_uploads/`, `answer_keys/`) auto-created by `init_db()`
- **Normalized coordinates**: AI returns `[0.0, 1.0]` normalized coords; annotation code converts to pixel coords
- **API timeout**: Frontend axios has 360s timeout; backend AI call has 300s — analysis can be slow
- **Image compression**: `ImageUploader.vue` auto-compresses uploads (>1MB: q=0.5, >5MB: q=0.7, >10MB: blocked)
- **`backend/analysis/annotator.py`** is unused by the web API

## User Flow (Single Unified Page)

`/` is the only main page: upload student exam → select subject/stage → optional standard answers → "开始批改" →
SSE real-time progress (layout analysis → answer extraction → AI grading) → result display with checkmark/cross icons.

## SSE Endpoint

- **`POST /api/grade/stream`** — multipart form, returns `text/event-stream`
- Events: `status`, `grading_result`, `done`, `error`
- Backend uses `asyncio.Queue` + thread pool to bridge sync AI calls to async SSE stream
- Frontend SSE client: `src/utils/sse.ts` using `fetch` + `ReadableStream`

## Prompt Management

Prompts stored in `prompts` table, seeded for (数学 × 小学/初中/高中). Three prompt types per row:
- `analysis_prompt` — layout analysis system prompt (supports `{img_w}`, `{img_h}` placeholders)
- `grading_prompt` — grading system prompt (`{standard_answers_section}`, `{layout_json}`, `{subject}`)
- `answer_extraction_prompt` — extracting answers from answer key images

Managed via `/prompts` page in frontend.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/analyze` | Upload image, run AI layout analysis |
| POST | `/api/grade/stream` | SSE: analyze + grade in one stream |
| POST | `/api/grade/analyze` | Sync: analyze + grade (legacy) |
| GET | `/api/grade` | List grading history |
| GET | `/api/grade/{grading_id}` | Get one grading result |
| DELETE | `/api/grade/{grading_id}` | Delete grading record |
| GET | `/api/prompts` | List prompt templates |
| PUT | `/api/prompts/{id}` | Update prompt template |
| GET | `/api/history` | List analysis history (legacy) |
| GET | `/api/result/{run_id}` | Get one analysis result |
| PUT | `/api/result/{run_id}/layout` | Update layout data |
| DELETE | `/api/result/{run_id}` | Delete record + image |

## Standalone Scripts (root level, not part of web app)

- `ocr_extract.py` — PaddleOCR text extraction on `2.jpg`
- `img_layout_analysis.py` — AI layout analysis via Volces API (hardcoded key)
- `draw_answer_areas.py` — PaddleOCR-based answer area detection

These reference `2.jpg` directly and use `PaddleOCR` (not in `backend/requirements.txt`).

## Style / Conventions

- Backend uses Pydantic models (`backend/models.py`) for request/response shapes
- Frontend stores: `stores/analysis.ts` (analysis state), `stores/grading.ts` (grading state)
- Vue path alias `@/` maps to `src/`
- Single git branch (`master`) — no branch/PR conventions established
