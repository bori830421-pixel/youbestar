import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from agent_system.manager import load_skill_registry, normalize_skill_id


SETTINGS_FILE = Path(__file__).with_name("skill_settings.json")

BUILTIN_SKILLS = {
    "official.open_browser": {
        "type": "official",
        "title": "打开浏览器",
        "description": "根据 URL 打开系统默认浏览器。",
    },
    "official.web_query": {
        "type": "official",
        "title": "网页查询",
        "description": "根据关键词自动尝试多个搜索源；网络允许时会使用外网搜索引擎和信息源，查询热点新闻、最新事件和网页结果并返回结构化结果。",
    },
    "official.query_weather": {
        "type": "official",
        "title": "查询天气",
        "description": "根据城市名调用本地 get_weather(city) / query_weather(params) 快速返回结构化天气数据和简单提醒。",
    },
    "official.query_market_data": {
        "type": "official",
        "title": "证券行情查询",
        "description": "根据股票代码或中文名称调用本地 get_stock_price(symbol) 快速返回 A 股实时行情。",
    },
    "official.write_skill": {
        "type": "official",
        "title": "写入 Sandbox 技能",
        "description": "只允许把新技能代码写入 agent_system/sandbox。",
    },
    "official.write_skill_test": {
        "type": "official",
        "title": "写入技能测试",
        "description": "为 sandbox 技能写入受控测试用例。",
    },
    "official.request_skill_approval": {
        "type": "official",
        "title": "提交技能审批",
        "description": "测试通过后提交人工审批请求。",
    },
    "official.install_local_skill": {
        "type": "official",
        "title": "自主安装本地技能",
        "description": "直接写入或覆盖 skills/local 下的 local.* 技能并注册。",
    },
    "official.list_files": {
        "type": "official",
        "title": "列出白名单文件",
        "description": "列出受控白名单目录内的普通项目文件。",
    },
    "official.read_file": {
        "type": "official",
        "title": "读取白名单文件",
        "description": "读取受控白名单目录内的普通文本或代码文件。",
    },
    "official.write_project_file": {
        "type": "official",
        "title": "写入项目文件",
        "description": "在项目白名单目录内写入普通文本或代码文件，可用于修改运行目录内的项目文件。",
    },
}

LEGACY_SKILL_ALIASES = {
    "open_browser": "official.open_browser",
    "web_query": "official.web_query",
    "search_web": "official.web_query",
    "web_search": "official.web_query",
    "query_weather": "official.query_weather",
    "weather": "official.query_weather",
    "query_market_data": "official.query_market_data",
    "market_data": "official.query_market_data",
    "stock_quote": "official.query_market_data",
    "stock": "official.query_market_data",
    "write_skill": "official.write_skill",
    "write_skill_test": "official.write_skill_test",
    "request_skill_approval": "official.request_skill_approval",
    "install_local_skill": "official.install_local_skill",
    "install_skill": "official.install_local_skill",
    "list_files": "official.list_files",
    "read_file": "official.read_file",
    "write_project_file": "official.write_project_file",
    "write_file": "official.write_project_file",
}


def canonical_skill_name(skill_name: str) -> str:
    clean_name = skill_name.strip()
    if clean_name in LEGACY_SKILL_ALIASES:
        return LEGACY_SKILL_ALIASES[clean_name]
    return normalize_skill_id(clean_name)


def load_skill_settings() -> dict[str, bool]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"skill_settings.json 不是有效 JSON：{exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="skill_settings.json 必须是对象。")

    return {canonical_skill_name(str(name)): bool(enabled) for name, enabled in data.items()}


def save_skill_settings(settings: dict[str, bool]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def known_skill_names() -> set[str]:
    return set(load_skill_registry())


def is_skill_enabled(skill_name: str) -> bool:
    canonical_name = canonical_skill_name(skill_name)
    settings = load_skill_settings()
    return settings.get(canonical_name, True)


def set_skill_enabled(skill_name: str, enabled: bool) -> dict[str, Any]:
    canonical_name = canonical_skill_name(skill_name)
    if canonical_name not in known_skill_names():
        raise HTTPException(status_code=404, detail="技能不存在。")

    settings = load_skill_settings()
    settings[canonical_name] = enabled
    save_skill_settings(settings)
    return {"name": canonical_name, "enabled": enabled}


def enabled_builtin_skill_names() -> list[str]:
    registry = load_skill_registry()
    return [name for name, record in registry.items() if record.get("source") == "official" and is_skill_enabled(name)]


def enabled_approved_skill_names() -> list[str]:
    registry = load_skill_registry()
    return [name for name, record in registry.items() if record.get("source") != "official" and is_skill_enabled(name)]


def list_skill_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for name, record in sorted(load_skill_registry().items()):
        source = str(record.get("source", "local"))
        meta = BUILTIN_SKILLS.get(name, {})
        cards.append(
            {
                "name": name,
                "title": record.get("title") or meta.get("title") or name,
                "type": source,
                "description": record.get("description") or meta.get("description") or "已注册技能。",
                "enabled": is_skill_enabled(name),
                "approved": True,
                "source": source,
                "version": record.get("version", ""),
                "author": record.get("author", ""),
                "path": record.get("path", ""),
            }
        )

    return cards
