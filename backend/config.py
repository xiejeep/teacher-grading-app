import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_URL = os.getenv("API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
API_KEY = os.getenv("API_KEY", "")
EP_ID = os.getenv("EP_ID", "")
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
ANNOTATED_DIR = os.path.join(STORAGE_DIR, "annotated")
GRADING_UPLOAD_DIR = os.path.join(STORAGE_DIR, "grading_uploads")
ANSWER_KEY_DIR = os.path.join(STORAGE_DIR, "answer_keys")
DATABASE_URL = os.path.join(STORAGE_DIR, "app.db")
