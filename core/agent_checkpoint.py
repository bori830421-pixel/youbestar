from copy import deepcopy
from dataclasses import asdict
from typing import Protocol

from core.agent_state import AgentState


class AgentCheckpoint(Protocol):
    def record(self, state: AgentState, node_name: str) -> None:
        ...


class NullCheckpoint:
    def record(self, state: AgentState, node_name: str) -> None:
        return None


class InMemoryCheckpoint:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, state: AgentState, node_name: str) -> None:
        self.records.append(
            {
                "thread_id": state.thread_id,
                "step": state.step_count,
                "node": node_name,
                "state": deepcopy(asdict(state)),
            }
        )
