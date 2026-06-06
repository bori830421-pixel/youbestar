from typing import Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_system.server import router as skills_router
from core.agent_runtime import AgentRuntime
from core.config import ModelConfig, load_config, save_config_file
from core.llm import LLM
from core.loop import agent_loop
from core.model_discovery import discover_models
from core.ui_formatter import format_agent_reply
from memory.memory import DEFAULT_STORAGE_PATH, Memory


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    allowChat: bool = True
    threadId: str = Field(default="default", min_length=1, max_length=200)


class ChatResponse(BaseModel):
    reply: str
    model_reply: str
    thought: str
    action: str
    params: dict[str, object]
    action_result: str
    response: str
    memory_candidate: dict[str, object] | None = None


class ConfigSaveResponse(BaseModel):
    status: str
    config: ModelConfig


class ModelDiscoveryRequest(BaseModel):
    api_url: str
    api_key: str


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


def build_user_visible_reply(response: str, action: str, action_result: str) -> str:
    return format_agent_reply(action, response, action_result)


def run_legacy_agent_loop(llm: LLM, user_message: str, allow_chat: bool) -> ChatResponse:
    model_reply, thought, action, params, action_result, user_response = agent_loop(
        llm,
        memory,
        user_message,
        allow_chat,
    )
    return ChatResponse(
        reply=build_user_visible_reply(user_response, action, action_result),
        model_reply=model_reply,
        thought=thought,
        action=action,
        params=params,
        action_result=action_result,
        response=user_response,
    )


def run_agent_runtime(llm: LLM, user_message: str, allow_chat: bool, thread_id: str = "default") -> ChatResponse:
    result = agent_runtime.run(
        llm,
        memory,
        user_message,
        allow_chat=allow_chat,
        thread_id=thread_id,
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
        response=result.response,
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
        if USE_AGENT_RUNTIME:
            return run_agent_runtime(llm, user_message, request.allowChat, request.threadId)
        return run_legacy_agent_loop(llm, user_message, request.allowChat)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Model API request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

