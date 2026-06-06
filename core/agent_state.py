from dataclasses import dataclass, field
from typing import Any

from core.ui_formatter import observation_to_text


@dataclass
class AgentState:
    thread_id: str
    user_input: str
    allow_chat: bool = True
    model_reply: str = ""
    thought: str = ""
    intent: dict[str, Any] = field(default_factory=dict)
    plan: list[str] = field(default_factory=list)
    action: str = "none"
    params: dict[str, Any] = field(default_factory=dict)
    observation: Any = "无操作"
    search_round: int = 0
    tool_call_count: int = 0
    max_search_round: int = 2
    max_tool_call: int = 10
    runtime_started_at: float = 0.0
    max_runtime_seconds: float = 25.0
    stop_reason: str = ""
    search_assessment: dict[str, Any] = field(default_factory=dict)
    reflection: str = ""
    answer_check: dict[str, Any] = field(default_factory=dict)
    response: str = ""
    reply: str = ""
    errors: list[str] = field(default_factory=list)
    runtime_nodes: list[str] = field(default_factory=list)
    step_count: int = 0
    history: list[dict[str, str]] = field(default_factory=list)

    def visit(self, node_name: str) -> None:
        self.runtime_nodes.append(node_name)
        self.step_count += 1


@dataclass
class AgentResult:
    reply: str
    model_reply: str
    thought: str
    action: str
    params: dict[str, Any]
    action_result: str
    response: str
    runtime_nodes: list[str]
    thread_id: str
    step_count: int
    intent: dict[str, Any] = field(default_factory=dict)
    answer_check: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = ""

    @classmethod
    def from_state(cls, state: AgentState) -> "AgentResult":
        return cls(
            reply=state.reply,
            model_reply=state.model_reply,
            thought=state.thought,
            action=state.action,
            params=state.params,
            action_result=observation_to_text(state.observation),
            response=state.response,
            intent=dict(state.intent),
            answer_check=dict(state.answer_check),
            stop_reason=state.stop_reason,
            runtime_nodes=list(state.runtime_nodes),
            thread_id=state.thread_id,
            step_count=state.step_count,
        )
