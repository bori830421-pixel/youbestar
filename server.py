from io import BytesIO
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_system.evolution_policy import is_self_evolution_enabled
from agent_system.server import management_router, router as skills_router, self_evolution_router
from core.agent_runtime import AgentRuntime
from core.config import ModelConfig, load_config, save_config_file
from core.llm import LLM
from core.loop import agent_loop
from core.model_discovery import discover_models
from core.ui_interactions import build_chat_interaction
from core.ui_formatter import format_agent_reply, observation_to_text
from memory.memory import DEFAULT_STORAGE_PATH, Memory
from tools.business_records_tool import run as run_business_records
from tools.excel_feedback_store import save_excel_feedback
from tools.excel_preview_tool import preview_excel_file, save_uploaded_excel
from tools.reference_product_tool import run as run_reference_product


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    allowChat: bool = True
    allowTools: bool = True
    allowSkills: bool = True
    allowSelfEvolution: bool = False
    threadId: str = Field(default="default", min_length=1, max_length=200)


class ChatResponse(BaseModel):
    reply: str
    model_reply: str
    thought: str
    action: str
    params: dict[str, object]
    action_result: str
    action_payload: object | None = None
    response: str
    interactions: list[dict[str, object]] = Field(default_factory=list)
    memory_candidate: dict[str, object] | None = None


class ConfigSaveResponse(BaseModel):
    status: str
    config: ModelConfig


class ModelDiscoveryRequest(BaseModel):
    api_url: str
    api_key: str
    wire_api: str = "chat_completions"


class ModelDiscoveryResponse(BaseModel):
    api_url: str
    models_url: str
    models: list[str]


class MemoryConfirmRequest(BaseModel):
    index: int = -1


class MemoryContextResponse(BaseModel):
    short_term: list[dict[str, object]]
    long_term: list[dict[str, object]]
    pending: list[dict[str, object]]


class BusinessRecordQueryRequest(BaseModel):
    type: str = ""
    record_type: str = ""
    query: str = ""
    business_key: str = ""
    filters: dict[str, object] = Field(default_factory=dict)
    limit: int = 20


class BusinessRecordUpsertRequest(BaseModel):
    id: str = ""
    record_id: str = ""
    type: str = ""
    record_type: str = ""
    title: str = ""
    source: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    fields: dict[str, object] = Field(default_factory=dict)
    business_key: str = ""
    actor: str = "operator"


class ExcelFeedbackRequest(BaseModel):
    headers: list[str] = Field(default_factory=list)
    sheet_name: str = ""
    category: str = ""
    previous_category: str = ""
    field_mappings: dict[str, str] = Field(default_factory=dict)
    scope: str = "template"
    actor: str = "operator"


class ReferenceProductRequest(BaseModel):
    url: str = ""
    source_url: str = ""
    reference_url: str = ""
    html: str = ""
    capture_id: str = ""
    match_id: str = ""
    query: str = ""
    keyword: str = ""
    skus: list[dict[str, object]] = Field(default_factory=list)
    bindings: list[dict[str, object]] = Field(default_factory=list)
    reference_product: dict[str, object] = Field(default_factory=dict)
    capture: dict[str, object] = Field(default_factory=dict)
    candidate: dict[str, object] = Field(default_factory=dict)
    record_id: str = ""
    business_key: str = ""
    sku: str = ""
    sku_name: str = ""
    source_sku_id: str = ""
    image_url: str = ""
    source_url_for_bind: str = ""
    confirmed: bool = False
    create_missing: bool = False
    mode: str = "internal"
    export_mode: str = ""
    margin_rate: object = 0
    margin_percent: object = 0
    decimal_places: int = 2
    embed_images: bool = False
    include_images: bool = False
    fields: list[str] = Field(default_factory=list)
    output_path: str = ""
    output_dir: str = ""
    filename: str = ""
    max_bytes: int = 0
    older_than_days: int = 0
    actor: str = "operator"


app = FastAPI(title="Youbestar AI Agent")
memory = Memory(storage_path=DEFAULT_STORAGE_PATH)
agent_runtime = AgentRuntime()
USE_AGENT_RUNTIME = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills_router)
app.include_router(self_evolution_router)
app.include_router(management_router)


def build_user_visible_reply(response: str, action: str, action_result: str) -> str:
    return format_agent_reply(action, response, action_result)


def run_legacy_agent_loop(
    llm: LLM,
    user_message: str,
    allow_chat: bool,
    allow_tools: bool = True,
    allow_skills: bool = True,
    allow_self_evolution: bool = False,
) -> ChatResponse:
    model_reply, thought, action, params, action_result, user_response = agent_loop(
        llm,
        memory,
        user_message,
        allow_chat,
        allow_tools=allow_tools,
        allow_skills=allow_skills,
        allow_self_evolution=allow_self_evolution,
    )
    interaction = build_chat_interaction(action, action_result)
    return ChatResponse(
        reply=build_user_visible_reply(user_response, action, action_result),
        model_reply=model_reply,
        thought=thought,
        action=action,
        params=params,
        action_result=observation_to_text(action_result),
        action_payload=action_result if isinstance(action_result, (dict, list)) else None,
        response=user_response,
        interactions=[interaction] if interaction else [],
    )


def run_agent_runtime(
    llm: LLM,
    user_message: str,
    allow_chat: bool,
    allow_tools: bool = True,
    allow_skills: bool = True,
    allow_self_evolution: bool = False,
    thread_id: str = "default",
    history: list[dict[str, str]] | None = None,
) -> ChatResponse:
    result = agent_runtime.run(
        llm,
        memory,
        user_message,
        allow_chat=allow_chat,
        allow_tools=allow_tools,
        allow_skills=allow_skills,
        allow_self_evolution=allow_self_evolution,
        thread_id=thread_id,
        history=history,
    )
    memory_candidate = memory.detect_business_memory_candidate(
        user_message,
        result.action,
        result.action_result,
        module="general",
    )
    return ChatResponse(
        reply=result.reply,
        model_reply=result.model_reply,
        thought=result.thought,
        action=result.action,
        params=result.params,
        action_result=result.action_result,
        action_payload=result.action_payload,
        response=result.response,
        interactions=result.interactions,
        memory_candidate=memory_candidate if memory_candidate.get("ok") else None,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse("index.html")


@app.get("/config", response_model=ModelConfig)
def read_model_config() -> ModelConfig:
    return load_config()


@app.post("/config", response_model=ConfigSaveResponse)
def save_model_config(config: ModelConfig) -> ConfigSaveResponse:
    saved_config = save_config_file(config)
    return ConfigSaveResponse(status="ok", config=saved_config)


@app.post("/models/discover", response_model=ModelDiscoveryResponse)
def discover_model_list(request: ModelDiscoveryRequest) -> ModelDiscoveryResponse:
    try:
        result = discover_models(request.api_url, request.api_key)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"模型列表请求失败：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModelDiscoveryResponse(**result)


@app.post("/files/excel/preview")
async def upload_excel_preview(request: Request, filename: str = "") -> dict[str, object]:
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Excel 文件不能为空。")
    try:
        saved_path = save_uploaded_excel(filename or "uploaded.xlsx", BytesIO(content))
        result = preview_excel_file(saved_path)
        interaction = build_chat_interaction("official.preview_excel", result)
        if interaction:
            result["interactions"] = [interaction]
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Excel 读取失败：{exc}") from exc


@app.post("/files/excel/feedback")
def save_excel_correction_feedback(request: ExcelFeedbackRequest) -> dict[str, object]:
    result = save_excel_feedback(request.model_dump())
    if result.get("ok") is False:
        raise HTTPException(status_code=400, detail=str(result.get("message") or "Excel 修正反馈保存失败。"))
    return result


@app.get("/business-records/types")
def read_business_record_types() -> dict[str, object]:
    return run_business_records({"operation": "list_types"})


@app.post("/business-records/query")
def query_business_records(request: BusinessRecordQueryRequest) -> dict[str, object]:
    return run_business_records(
        {
            "operation": "query",
            "record_type": request.record_type or request.type,
            "query": request.query,
            "business_key": request.business_key,
            "filters": request.filters,
            "limit": request.limit,
        }
    )


@app.post("/business-records/upsert")
def upsert_business_record(request: Request, payload: BusinessRecordUpsertRequest) -> dict[str, object]:
    source_ip = request.client.host if request.client else ""
    fields = dict(payload.fields or {})
    if payload.title and "title" not in fields:
        fields["title"] = payload.title
    if payload.content and "content" not in fields:
        fields["content"] = payload.content
    result = run_business_records(
        {
            "operation": "upsert",
            "id": payload.record_id or payload.id,
            "record_type": payload.record_type or payload.type or "general",
            "title": payload.title,
            "content": payload.content,
            "source": payload.source,
            "tags": payload.tags,
            "fields": fields,
            "business_key": payload.business_key,
            "actor": payload.actor or "operator",
            "source_ip": source_ip,
        }
    )
    if result.get("ok") is False:
        raise HTTPException(status_code=400, detail=str(result.get("error") or "保存记录失败"))
    return result


def _reference_payload(payload: ReferenceProductRequest | None, operation: str, request: Request | None = None) -> dict[str, object]:
    data = payload.model_dump() if payload else {}
    if data.get("reference_url") and not data.get("url"):
        data["url"] = data["reference_url"]
    if data.get("source_url") and not data.get("url"):
        data["url"] = data["source_url"]
    if data.get("source_url_for_bind") and not data.get("source_url"):
        data["source_url"] = data["source_url_for_bind"]
    data["operation"] = operation
    if request and request.client:
        data["source_ip"] = request.client.host
    return {key: value for key, value in data.items() if value not in (None, "", [], {})}


@app.post("/reference-products/capture")
def capture_reference_product(request: Request, payload: ReferenceProductRequest) -> dict[str, object]:
    return run_reference_product(_reference_payload(payload, "capture", request))


@app.post("/reference-products/match")
def match_reference_product(request: Request, payload: ReferenceProductRequest) -> dict[str, object]:
    return run_reference_product(_reference_payload(payload, "match", request))


@app.post("/reference-products/confirm-bind")
def confirm_bind_reference_product(request: Request, payload: ReferenceProductRequest) -> dict[str, object]:
    return run_reference_product(_reference_payload(payload, "confirm_bind", request))


@app.post("/reference-products/export-excel")
def export_reference_product_excel(request: Request, payload: ReferenceProductRequest) -> dict[str, object]:
    return run_reference_product(_reference_payload(payload, "export_excel", request))


@app.get("/reference-products/cache-status")
def reference_product_cache_status() -> dict[str, object]:
    return run_reference_product({"operation": "cache_status"})


@app.get("/reference-products/cache/status")
def reference_product_cache_status_alias() -> dict[str, object]:
    return reference_product_cache_status()


@app.post("/reference-products/cleanup-cache")
def cleanup_reference_product_cache(payload: ReferenceProductRequest | None = None) -> dict[str, object]:
    return run_reference_product(_reference_payload(payload, "cleanup_cache"))


@app.post("/reference-products/cache/cleanup")
def cleanup_reference_product_cache_alias(payload: ReferenceProductRequest | None = None) -> dict[str, object]:
    return cleanup_reference_product_cache(payload)


@app.get("/memory/context", response_model=MemoryContextResponse)
def read_memory_context(module: str | None = None) -> MemoryContextResponse:
    context = memory.get_model_context(module)
    return MemoryContextResponse(
        short_term=context["short_term"],
        long_term=context["long_term"],
        pending=memory.pending_as_dicts(),
    )


@app.post("/memory/confirm")
def confirm_memory_candidate(request: MemoryConfirmRequest) -> dict[str, object]:
    result = memory.confirm_pending(request.index)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@app.post("/memory/reject")
def reject_memory_candidate(request: MemoryConfirmRequest) -> dict[str, object]:
    result = memory.reject_pending(request.index)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        llm = LLM(load_config())
        allow_self_evolution = request.allowSelfEvolution and is_self_evolution_enabled()
        if USE_AGENT_RUNTIME:
            return run_agent_runtime(
                llm,
                user_message,
                request.allowChat,
                allow_tools=request.allowTools,
                allow_skills=request.allowSkills,
                allow_self_evolution=allow_self_evolution,
                thread_id=request.threadId,
                history=[item.model_dump() for item in request.history],
            )
        return run_legacy_agent_loop(
            llm,
            user_message,
            request.allowChat,
            allow_tools=request.allowTools,
            allow_skills=request.allowSkills,
            allow_self_evolution=allow_self_evolution,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Model API request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

