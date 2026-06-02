from typing import Literal

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_system.server import router as skills_router
from core.config import ModelConfig, load_config, save_config_file
from core.llm import LLM
from core.loop import agent_loop
from memory.memory import Memory


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    model_reply: str
    thought: str
    action: str
    params: dict[str, object]
    action_result: str


class ConfigSaveResponse(BaseModel):
    status: str
    config: ModelConfig


app = FastAPI(title="Youbestar AI Agent")
memory = Memory()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills_router)


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


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        llm = LLM(load_config())
        model_reply, thought, action, params, action_result = agent_loop(llm, memory, user_message)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Model API request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    reply = f"模型输出:\n{model_reply}\n\n工具执行结果:\n{action_result}"
    return ChatResponse(
        reply=reply,
        model_reply=model_reply,
        thought=thought,
        action=action,
        params=params,
        action_result=action_result,
    )
