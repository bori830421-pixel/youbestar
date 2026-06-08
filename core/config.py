import json
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field


DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
CHAT_COMPLETIONS_PATH = "/chat/completions"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "youbestar.json"


class ModelProfile(BaseModel):
    id: str = ""
    name: str = ""
    api_url: str = ""
    model: str = ""
    api_key: str = ""


class ModelConfig(BaseModel):
    api_url: str = ""
    model: str = ""
    api_key: str = ""
    current_profile_id: str = ""
    profiles: list[ModelProfile] = Field(default_factory=list)


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
        current_profile_id="default",
    )


def load_config() -> ModelConfig:
    if not CONFIG_FILE.exists():
        return default_config()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read youbestar.json: {exc}") from exc

    return activate_current_profile(ModelConfig(**data))


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


def clean_profile(profile: ModelProfile) -> ModelProfile | None:
    api_url = clean_optional(profile.api_url) or ""
    model = clean_optional(profile.model) or ""
    api_key = clean_optional(profile.api_key) or ""
    profile_id = clean_optional(profile.id) or clean_optional(profile.name) or api_url
    if not (api_url or model or api_key):
        return None
    return ModelProfile(
        id=profile_id or "default",
        name=clean_optional(profile.name) or profile_id or "默认接口",
        api_url=api_url,
        model=model,
        api_key=api_key,
    )


def clean_profiles(profiles: list[ModelProfile]) -> list[ModelProfile]:
    clean_items: list[ModelProfile] = []
    seen: set[str] = set()
    for profile in profiles:
        clean_item = clean_profile(profile)
        if not clean_item or clean_item.id in seen:
            continue
        clean_items.append(clean_item)
        seen.add(clean_item.id)
    return clean_items


def profile_from_config(config: ModelConfig, profile_id: str = "default") -> ModelProfile:
    return ModelProfile(
        id=profile_id,
        name="默认接口",
        api_url=clean_optional(config.api_url) or "",
        model=clean_optional(config.model) or "",
        api_key=clean_optional(config.api_key) or "",
    )


def activate_current_profile(config: ModelConfig) -> ModelConfig:
    current_profile_id = clean_optional(config.current_profile_id)
    if not current_profile_id:
        return config
    profile = next((item for item in config.profiles if item.id == current_profile_id), None)
    if not profile:
        return config
    return ModelConfig(
        api_url=clean_optional(profile.api_url) or clean_optional(config.api_url) or "",
        model=clean_optional(profile.model) or clean_optional(config.model) or "",
        api_key=clean_optional(profile.api_key) or clean_optional(config.api_key) or "",
        current_profile_id=current_profile_id,
        profiles=config.profiles,
    )


def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def save_config_file(config: ModelConfig) -> ModelConfig:
    current_profile_id = clean_optional(config.current_profile_id) or "default"
    profiles = clean_profiles(config.profiles)
    clean_config = ModelConfig(
        api_url=clean_optional(config.api_url) or "",
        model=clean_optional(config.model) or "",
        api_key=clean_optional(config.api_key) or "",
        current_profile_id=current_profile_id,
        profiles=profiles,
    )
    require_complete_config(clean_config)

    if not clean_config.profiles:
        clean_config.profiles = [profile_from_config(clean_config, current_profile_id)]
    elif not any(profile.id == current_profile_id for profile in clean_config.profiles):
        clean_config.profiles.append(profile_from_config(clean_config, current_profile_id))

    try:
        CONFIG_FILE.write_text(
            json.dumps(model_to_dict(clean_config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write youbestar.json: {exc}") from exc

    return clean_config
