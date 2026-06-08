from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests


MODELS_PATH = "/models"
CHAT_COMPLETIONS_PATH = "/chat/completions"
RESPONSES_PATH = "/responses"
KNOWN_ENDPOINT_PATHS = (CHAT_COMPLETIONS_PATH, RESPONSES_PATH)


def _validated_url_parts(api_url: str):
    clean_url = api_url.strip().rstrip("/")
    parsed = urlsplit(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API 地址必须是有效的 http 或 https 地址。")
    if parsed.username or parsed.password:
        raise ValueError("API 地址不能包含用户名或密码。")
    return parsed


def normalize_models_api_url(api_url: str) -> str:
    parsed = _validated_url_parts(api_url)

    path = parsed.path.rstrip("/")
    matched_endpoint = False
    for known_path in KNOWN_ENDPOINT_PATHS:
        if path.endswith(known_path):
            path = f"{path[:-len(known_path)]}{MODELS_PATH}"
            matched_endpoint = True
            break
    if not matched_endpoint and not path.endswith(MODELS_PATH):
        path = f"{path}{MODELS_PATH}"

    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def models_url_candidates(api_url: str) -> list[str]:
    parsed = _validated_url_parts(api_url)
    path = parsed.path.rstrip("/")
    candidates: list[str] = []

    def add(candidate_path: str) -> None:
        candidate_url = urlunsplit((parsed.scheme, parsed.netloc, candidate_path, parsed.query, ""))
        if candidate_url not in candidates:
            candidates.append(candidate_url)

    if path in {"", "/"}:
        add("/v1/models")
        add(MODELS_PATH)
        return candidates

    for known_path in KNOWN_ENDPOINT_PATHS:
        if path.endswith(known_path):
            add(f"{path[:-len(known_path)]}{MODELS_PATH}")
            return candidates

    if path.endswith(MODELS_PATH):
        add(path)
        return candidates

    add(f"{path}{MODELS_PATH}")
    if not path.endswith("/v1"):
        add(f"{path}/v1/models")
    return candidates


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


def _response_status_code(response: requests.Response) -> int:
    status_code = getattr(response, "status_code", 200)
    return status_code if isinstance(status_code, int) else 200


def discover_models(api_url: str, api_key: str) -> dict[str, Any]:
    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("请先填写 API Key。")

    headers = {"Authorization": f"Bearer {clean_key}", "Accept": "application/json"}
    attempted: list[str] = []
    errors: list[str] = []

    for models_url in models_url_candidates(api_url):
        attempted.append(models_url)
        try:
            response = requests.get(models_url, headers=headers, timeout=20)
            status_code = _response_status_code(response)
            if status_code >= 400:
                errors.append(f"{models_url} -> HTTP {status_code}")
                continue
            models = parse_model_ids(response.json())
        except requests.RequestException as exc:
            errors.append(f"{models_url} -> 请求失败：{exc}")
            continue
        except ValueError as exc:
            errors.append(f"{models_url} -> {exc}")
            continue

        return {
            "api_url": api_base_from_models_url(models_url),
            "models_url": models_url,
            "models": models,
        }

    detail = "；".join(errors) or "没有可用响应"
    raise ValueError(f"模型接口没有返回可用模型，已尝试：{', '.join(attempted)}。详情：{detail}")
