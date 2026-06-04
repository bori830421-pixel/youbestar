from collections.abc import Callable

from core.agent_checkpoint import AgentCheckpoint, NullCheckpoint
from core.agent_nodes import AgentContext, execute_node, finalize_node, prepare_node, reflect_node
from core.agent_state import AgentResult, AgentState
from memory.memory import Memory


AgentNode = Callable[[AgentState, AgentContext], AgentState]


class AgentRuntime:
    def __init__(
        self,
        nodes: list[AgentNode] | None = None,
        checkpoint: AgentCheckpoint | None = None,
        max_steps: int = 8,
    ) -> None:
        self.nodes = nodes or [prepare_node, execute_node, reflect_node, finalize_node]
        self.checkpoint = checkpoint or NullCheckpoint()
        self.max_steps = max_steps

    def run(
        self,
        llm,
        memory: Memory,
        user_input: str,
        allow_chat: bool = True,
        thread_id: str = "default",
    ) -> AgentResult:
        state = AgentState(
            thread_id=thread_id.strip() or "default",
            user_input=user_input,
            allow_chat=allow_chat,
            history=list(memory.history),
        )
        context = AgentContext(llm=llm, memory=memory)

        for node in self.nodes:
            if state.step_count >= self.max_steps:
                state.errors.append("AgentRuntime reached max_steps.")
                break
            state = node(state, context)
            self.checkpoint.record(state, state.runtime_nodes[-1])

        return AgentResult.from_state(state)
