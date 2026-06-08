import json
from pathlib import Path

from fastapi import HTTPException


SETTINGS_FILE = Path(__file__).with_name("self_evolution_settings.json")


def is_self_evolution_enabled() -> bool:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"self_evolution_settings.json 不是有效 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="self_evolution_settings.json 必须是对象。")
    return data.get("enabled") is True


def set_self_evolution_enabled(enabled: bool) -> dict[str, bool]:
    SETTINGS_FILE.write_text(json.dumps({"enabled": bool(enabled)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"enabled": bool(enabled)}


def require_self_evolution_enabled() -> None:
    if not is_self_evolution_enabled():
        raise HTTPException(status_code=403, detail="自我进化未开启。")
