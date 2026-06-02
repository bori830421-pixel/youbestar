import json
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel


DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
CHAT_COMPLETIONS_PATH = "/chat/completions"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "youbestar.json"


class ModelConfig(BaseModel):
    api_url: str = ""
    model: str = ""
    api_key: str = ""


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean_value = value.strip()
    return clean_value or None


def normalize_chat_api_url(api_url: str) -> str:
    clean_url = api_url.strip().rstrip("/")
    if not clean_url:
        return f"{DEFAULT_API_BASE_URL}{CHAT_COMPLETIONS_PATH}"
    if clean_url.endswith(CHAT_COMPLETIONS_PATH):
        return clean_url
    return f"{clean_url}{CHAT_COMPLETIONS_PATH}"


def default_config() -> ModelConfig:
    return ModelConfig(
        api_url=os.getenv("OPENAI_API_URL") or os.getenv("OPENAI_BASE_URL", DEFAULT_API_BASE_URL),
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )


def load_config() -> ModelConfig:
    if not CONFIG_FILE.exists():
        return default_config()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read youbestar.json: {exc}") from exc

    return ModelConfig(**data)


def require_complete_config(config: ModelConfig) -> None:
    missing = []
    if not clean_optional(config.api_url):
        missing.append("API 地址")
    if not clean_optional(config.model):
        missing.append("模型名")
    if not clean_optional(config.api_key):
        missing.append("API Key")

    if missing:
        raise HTTPException(status_code=400, detail=f"请先补全配置：{', '.join(missing)}")


def save_config_file(config: ModelConfig) -> ModelConfig:
    clean_config = ModelConfig(
        api_url=clean_optional(config.api_url) or "",
        model=clean_optional(config.model) or "",
        api_key=clean_optional(config.api_key) or "",
    )
    require_complete_config(clean_config)

    try:
        CONFIG_FILE.write_text(
            json.dumps(clean_config.dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write youbestar.json: {exc}") from exc

    return clean_config
