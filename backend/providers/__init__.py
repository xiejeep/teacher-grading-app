import backend.config as config
from backend.providers.base import BaseAIProvider


_provider_instance: BaseAIProvider | None = None


def get_provider() -> BaseAIProvider:
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    if config.AI_PROVIDER == "modelscope":
        from backend.providers.modelscope import ModelScopeProvider
        _provider_instance = ModelScopeProvider()
    else:
        from backend.providers.volces import VolcesProvider
        _provider_instance = VolcesProvider()

    provider_name = type(_provider_instance).__name__
    print(f"  [Provider] 使用 {provider_name} (AI_PROVIDER={config.AI_PROVIDER})")
    return _provider_instance


def reload_provider():
    global _provider_instance
    _provider_instance = None


__all__ = ["BaseAIProvider", "get_provider", "reload_provider"]
