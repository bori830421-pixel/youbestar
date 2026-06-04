from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    thread_id: str
    user_input: str
    allow_chat: bool = True
    model_reply: str = ""
    thought: str = ""
    intent: str = ""
    plan: list[str] = field(default_factory=list)
    action: str = "none"
    params: dict[str, Any] = field(default_factory=dict)
    observation: str = "无操作"
    reflection: str = ""
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

    @classmethod
    def from_state(cls, state: AgentState) -> "AgentResult":
        return cls(
            reply=state.reply,
            model_reply=state.model_reply,
            thought=state.thought,
            action=state.action,
            params=state.params,
            action_result=state.observation,
            response=state.response,
            runtime_nodes=list(state.runtime_nodes),
            thread_id=state.thread_id,
            step_count=state.step_count,
        )
