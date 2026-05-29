import requests
from fastapi import APIRouter

import backend.config as config
from backend.models import ProviderSettings, ProviderSettingsResponse
from backend.providers import reload_provider

router = APIRouter()


@router.get("/settings/provider", response_model=ProviderSettingsResponse)
def get_provider_settings():
    return ProviderSettingsResponse(
        ai_provider=config.AI_PROVIDER,
        volces_has_key=bool(config.VOLCES_API_KEY),
        volces_ep_id=config.VOLCES_EP_ID,
        modelscope_has_key=bool(config.MODELSCOPE_API_KEY),
        modelscope_model=config.MODELSCOPE_MODEL,
    )


@router.put("/settings/provider", response_model=ProviderSettingsResponse)
def update_provider_settings(body: ProviderSettings):
    settings = {}
    if body.ai_provider:
        settings["ai_provider"] = body.ai_provider
    if body.volces_api_key:
        settings["volces_api_key"] = body.volces_api_key
    if body.volces_ep_id:
        settings["volces_ep_id"] = body.volces_ep_id
    if body.modelscope_api_key:
        settings["modelscope_api_key"] = body.modelscope_api_key
    if body.modelscope_model:
        settings["modelscope_model"] = body.modelscope_model

    config.save_provider_config(settings)
    reload_provider()

    return ProviderSettingsResponse(
        ai_provider=config.AI_PROVIDER,
        volces_has_key=bool(config.VOLCES_API_KEY),
        volces_ep_id=config.VOLCES_EP_ID,
        modelscope_has_key=bool(config.MODELSCOPE_API_KEY),
        modelscope_model=config.MODELSCOPE_MODEL,
    )


@router.post("/settings/provider/test")
def test_provider_connection(body: ProviderSettings):
    try:
        if body.ai_provider == "modelscope":
            url = "https://api-inference.modelscope.cn/v1/chat/completions"
            model = body.modelscope_model or config.MODELSCOPE_MODEL
            api_key = body.modelscope_api_key or config.MODELSCOPE_API_KEY
        else:
            url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
            model = body.volces_ep_id or config.VOLCES_EP_ID
            api_key = body.volces_api_key or config.VOLCES_API_KEY

        payload = {
            "model": model,
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Hello"}],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {
            "success": True,
            "message": f"连接成功！模型: {data['choices'][0]['message']['content'][:50]}",
        }
    except requests.exceptions.Timeout:
        return {"success": False, "message": "连接超时，请检查网络或 API 地址"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)}"}
