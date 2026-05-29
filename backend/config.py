import json
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Storage
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
UPLOAD_DIR = os.path.join(STORAGE_DIR, "uploads")
ANNOTATED_DIR = os.path.join(STORAGE_DIR, "annotated")
GRADING_UPLOAD_DIR = os.path.join(STORAGE_DIR, "grading_uploads")
ANSWER_KEY_DIR = os.path.join(STORAGE_DIR, "answer_keys")
DATABASE_URL = os.path.join(STORAGE_DIR, "app.db")
PROVIDER_CONFIG_PATH = os.path.join(STORAGE_DIR, "provider_config.json")


def _load_provider_config() -> dict:
    cfg = {}
    if os.path.exists(PROVIDER_CONFIG_PATH):
        try:
            with open(PROVIDER_CONFIG_PATH) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return cfg


_provider_config = _load_provider_config()

AI_PROVIDER = _provider_config.get("ai_provider") or os.getenv("AI_PROVIDER", "volces")
VOLCES_API_KEY = _provider_config.get("volces_api_key") or os.getenv("VOLCES_API_KEY", os.getenv("API_KEY", ""))
VOLCES_EP_ID = _provider_config.get("volces_ep_id") or os.getenv("VOLCES_EP_ID", os.getenv("EP_ID", ""))
MODELSCOPE_API_KEY = _provider_config.get("modelscope_api_key") or os.getenv("MODELSCOPE_API_KEY", "")
MODELSCOPE_MODEL = _provider_config.get("modelscope_model") or os.getenv("MODELSCOPE_MODEL", "moonshotai/Kimi-K2.6:DashScope")


def save_provider_config(settings: dict):
    global AI_PROVIDER, VOLCES_API_KEY, VOLCES_EP_ID, MODELSCOPE_API_KEY, MODELSCOPE_MODEL
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(PROVIDER_CONFIG_PATH, "w") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    AI_PROVIDER = settings.get("ai_provider", AI_PROVIDER)
    VOLCES_API_KEY = settings.get("volces_api_key", VOLCES_API_KEY)
    VOLCES_EP_ID = settings.get("volces_ep_id", VOLCES_EP_ID)
    MODELSCOPE_API_KEY = settings.get("modelscope_api_key", MODELSCOPE_API_KEY)
    MODELSCOPE_MODEL = settings.get("modelscope_model", MODELSCOPE_MODEL)
