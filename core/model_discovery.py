from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests


MODELS_PATH = "/models"
CHAT_COMPLETIONS_PATH = "/chat/completions"


def normalize_models_api_url(api_url: str) -> str:
    clean_url = api_url.strip().rstrip("/")
    parsed = urlsplit(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API 地址必须是有效的 http 或 https 地址。")
    if parsed.username or parsed.password:
        raise ValueError("API 地址不能包含用户名或密码。")

    path = parsed.path.rstrip("/")
    if path.endswith(CHAT_COMPLETIONS_PATH):
        path = f"{path[:-len(CHAT_COMPLETIONS_PATH)]}{MODELS_PATH}"
    elif not path.endswith(MODELS_PATH):
        path = f"{path}{MODELS_PATH}"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def parse_model_ids(payload: Any) -> list[str]:
    candidates: Any = payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            candidates = payload["data"]
        elif isinstance(payload.get("models"), list):
            candidates = payload["models"]
        else:
            candidates = []

    if not isinstance(candidates, list):
        raise ValueError("模型接口返回格式不受支持。")

    model_ids: set[str] = set()
    for item in candidates:
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            model_id = str(item.get("id") or item.get("name") or "").strip()
        else:
            model_id = ""
        if model_id:
            model_ids.add(model_id)

    if not model_ids:
        raise ValueError("模型接口没有返回可用模型，请保留手动填写模型名。")

    return sorted(model_ids, key=str.casefold)


def api_base_from_models_url(models_url: str) -> str:
    parsed = urlsplit(models_url)
    path = parsed.path.removesuffix(MODELS_PATH).rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def root_v1_models_url(api_url: str) -> str | None:
    parsed = urlsplit(api_url.strip().rstrip("/"))
    if parsed.path not in {"", "/"}:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "/v1/models", parsed.query, ""))


def discover_models(api_url: str, api_key: str) -> dict[str, Any]:
    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("请先填写 API Key。")

    headers = {"Authorization": f"Bearer {clean_key}", "Accept": "application/json"}
    models_url = normalize_models_api_url(api_url)
    response = requests.get(models_url, headers=headers, timeout=20)
    fallback_url = root_v1_models_url(api_url)
    if response.status_code == 404 and fallback_url:
        models_url = fallback_url
        response = requests.get(models_url, headers=headers, timeout=20)
    response.raise_for_status()
    return {
        "api_url": api_base_from_models_url(models_url),
        "models_url": models_url,
        "models": parse_model_ids(response.json()),
    }
