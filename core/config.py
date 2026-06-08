import json
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field


DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_WIRE_API = "chat_completions"
CHAT_COMPLETIONS_PATH = "/chat/completions"
RESPONSES_PATH = "/responses"
CONFIG_FILE = Path(__file__).resolve().parents[1] / "youbestar.json"


class ModelProfile(BaseModel):
    id: str = ""
    name: str = ""
    api_url: str = ""
    model: str = ""
    api_key: str = ""
    wire_api: str = ""


class ModelConfig(BaseModel):
    name: str = ""
    api_url: str = ""
    model: str = ""
    api_key: str = ""
    wire_api: str = DEFAULT_WIRE_API
    current_profile_id: str = ""
    profiles: list[ModelProfile] = Field(default_factory=list)


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    clean_value = value.strip()
    return clean_value or None


def normalize_wire_api(wire_api: str | None) -> str:
    clean_value = (wire_api or DEFAULT_WIRE_API).strip().lower().replace("-", "_")
    if clean_value in {"responses", "response"}:
        return "responses"
    if clean_value in {"chat", "chat_completions", "chat/completions", "completions"}:
        return DEFAULT_WIRE_API
    raise ValueError("接口协议只支持 chat_completions 或 responses。")


def wire_api_path(wire_api: str | None) -> str:
    if normalize_wire_api(wire_api) == "responses":
        return RESPONSES_PATH
    return CHAT_COMPLETIONS_PATH


def normalize_chat_api_url(api_url: str, wire_api: str | None = DEFAULT_WIRE_API) -> str:
    clean_url = api_url.strip().rstrip("/")
    if not clean_url:
        clean_url = DEFAULT_API_BASE_URL
    endpoint_path = wire_api_path(wire_api)
    if clean_url.endswith(endpoint_path):
        return clean_url
    for known_path in (CHAT_COMPLETIONS_PATH, RESPONSES_PATH):
        if clean_url.endswith(known_path):
            clean_url = clean_url[: -len(known_path)].rstrip("/")
            break
    return f"{clean_url}{endpoint_path}"


def default_config() -> ModelConfig:
    return ModelConfig(
        name="默认接口",
        api_url=os.getenv("OPENAI_API_URL") or os.getenv("OPENAI_BASE_URL", DEFAULT_API_BASE_URL),
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        wire_api=os.getenv("OPENAI_WIRE_API", DEFAULT_WIRE_API),
        current_profile_id="default",
    )


def normalize_config_data(data: dict) -> dict:
    normalized = dict(data)
    if not normalized.get("api_url") and normalized.get("base_url"):
        normalized["api_url"] = normalized.get("base_url")
    if not normalized.get("name") and normalized.get("model_provider"):
        normalized["name"] = normalized.get("model_provider")

    provider_name = clean_optional(str(normalized.get("model_provider") or ""))
    providers = normalized.get("model_providers")
    if provider_name and isinstance(providers, dict):
        provider = providers.get(provider_name)
        if isinstance(provider, dict):
            normalized.setdefault("name", provider.get("name") or provider_name)
            normalized["api_url"] = normalized.get("api_url") or provider.get("api_url") or provider.get("base_url") or ""
            normalized["wire_api"] = normalized.get("wire_api") or provider.get("wire_api") or DEFAULT_WIRE_API

    profiles = []
    for profile in normalized.get("profiles") or []:
        if not isinstance(profile, dict):
            profiles.append(profile)
            continue
        normalized_profile = dict(profile)
        if not normalized_profile.get("api_url") and normalized_profile.get("base_url"):
            normalized_profile["api_url"] = normalized_profile.get("base_url")
        profiles.append(normalized_profile)
    if profiles:
        normalized["profiles"] = profiles

    return normalized


def load_config() -> ModelConfig:
    if not CONFIG_FILE.exists():
        return default_config()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read youbestar.json: {exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Failed to read youbestar.json: 顶层结构必须是对象。")

    data = normalize_config_data(data)
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

    try:
        normalize_wire_api(config.wire_api)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def clean_profile(profile: ModelProfile) -> ModelProfile | None:
    api_url = clean_optional(profile.api_url) or ""
    model = clean_optional(profile.model) or ""
    api_key = clean_optional(profile.api_key) or ""
    wire_api = normalize_wire_api(profile.wire_api or DEFAULT_WIRE_API)
    profile_id = clean_optional(profile.id) or clean_optional(profile.name) or api_url
    if not (api_url or model or api_key):
        return None
    return ModelProfile(
        id=profile_id or "default",
        name=clean_optional(profile.name) or profile_id or "默认接口",
        api_url=api_url,
        model=model,
        api_key=api_key,
        wire_api=wire_api,
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
        name=clean_optional(config.name) or "默认接口",
        api_url=clean_optional(config.api_url) or "",
        model=clean_optional(config.model) or "",
        api_key=clean_optional(config.api_key) or "",
        wire_api=normalize_wire_api(config.wire_api),
    )


def activate_current_profile(config: ModelConfig) -> ModelConfig:
    current_profile_id = clean_optional(config.current_profile_id)
    if not current_profile_id:
        return config
    profile = next((item for item in config.profiles if item.id == current_profile_id), None)
    if not profile:
        return config
    try:
        wire_api = normalize_wire_api(profile.wire_api or config.wire_api)
    except ValueError:
        wire_api = DEFAULT_WIRE_API
    return ModelConfig(
        name=clean_optional(profile.name) or clean_optional(config.name) or "",
        api_url=clean_optional(profile.api_url) or clean_optional(config.api_url) or "",
        model=clean_optional(profile.model) or clean_optional(config.model) or "",
        api_key=clean_optional(profile.api_key) or clean_optional(config.api_key) or "",
        wire_api=wire_api,
        current_profile_id=current_profile_id,
        profiles=config.profiles,
    )


def model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def save_config_file(config: ModelConfig) -> ModelConfig:
    current_profile_id = clean_optional(config.current_profile_id) or "default"
    try:
        profiles = clean_profiles(config.profiles)
        wire_api = normalize_wire_api(config.wire_api)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clean_config = ModelConfig(
        name=clean_optional(config.name) or "",
        api_url=clean_optional(config.api_url) or "",
        model=clean_optional(config.model) or "",
        api_key=clean_optional(config.api_key) or "",
        wire_api=wire_api,
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
