import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import UPLOAD_DIR, GRADING_UPLOAD_DIR, ANSWER_KEY_DIR
from backend.database import init_db
from backend.routers import analysis, history, grading, prompts, templates, settings

app = FastAPI(title="试卷版面分析 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static/answer_keys", StaticFiles(directory=ANSWER_KEY_DIR), name="answer_keys")

app.include_router(analysis.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(grading.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


init_db()


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
