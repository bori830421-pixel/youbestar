from typing import Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_system.server import router as skills_router
from core.agent_runtime import AgentRuntime
from core.config import ModelConfig, load_config, save_config_file
from core.langgraph_bridge import LangGraphBridge
from core.llm import LLM
from core.loop import agent_loop
from core.model_discovery import discover_models
from core.ui_formatter import format_agent_reply
from memory.memory import Memory


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    allowChat: bool = True
    threadId: str = Field(default="default", min_length=1, max_length=200)


class LangGraphChatRequest(ChatRequest):
    threadId: str = Field(min_length=1, max_length=200)


class ChatResponse(BaseModel):
    reply: str
    model_reply: str
    thought: str
    action: str
    params: dict[str, object]
    action_result: str
    response: str


class LangGraphChatResponse(ChatResponse):
    engine: Literal["langgraph"]
    thread_id: str
    graph_nodes: list[str]
    turn_count: int


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


app = FastAPI(title="Youbestar AI Agent")
memory = Memory()
agent_runtime = AgentRuntime()
langgraph_bridge = LangGraphBridge()
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
    return ChatResponse(
        reply=result.reply,
        model_reply=result.model_reply,
        thought=result.thought,
        action=result.action,
        params=result.params,
        action_result=result.action_result,
        response=result.response,
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


@app.post("/langgraph/chat", response_model=LangGraphChatResponse)
def langgraph_chat(request: LangGraphChatRequest) -> LangGraphChatResponse:
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        result = langgraph_bridge.invoke(
            LLM(load_config()),
            user_message,
            request.allowChat,
            request.threadId,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Model API request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    reply = build_user_visible_reply(result["response"], result["action"], result["action_result"])

    return LangGraphChatResponse(
        reply=reply,
        model_reply=result["model_reply"],
        thought=result["thought"],
        action=result["action"],
        params=result["params"],
        action_result=result["action_result"],
        response=result["response"],
        engine="langgraph",
        thread_id=result["thread_id"],
        graph_nodes=result["graph_nodes"],
        turn_count=result["turn_count"],
    )
