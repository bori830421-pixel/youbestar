from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

from agent_system.manager import is_approved_skill, run_approved_skill
from agent_system.skill_registry import is_skill_enabled
from core.loop import build_agent_prompt, bridge_tool_result_to_response, normalize_action_name
from core.parser import parse_agent_output
from memory.memory import Memory


class AgentGraphState(TypedDict, total=False):
    user_input: str
    allow_chat: bool
    model_reply: str
    thought: str
    action: str
    params: dict[str, Any]
    action_result: str
    response: str
    visited_nodes: list[str]
    turn_count: int
    history: list[dict[str, str]]


class AgentGraphContext(TypedDict):
    llm: Any


FAILURE_MARKERS = ("失败", "错误", "未知工具", "技能已关闭", "error")


def plan_node(state: AgentGraphState, runtime: Runtime[AgentGraphContext]) -> dict[str, Any]:
    allow_chat = bool(state.get("allow_chat", True))
    thread_memory = Memory()
    thread_memory.history = list(state.get("history", []))
    prompt = build_agent_prompt(thread_memory, state["user_input"], allow_chat)
    model_reply = runtime.context["llm"].chat(prompt)
    parsed = parse_agent_output(model_reply)

    return {
        "model_reply": model_reply,
        "thought": parsed["thought"],
        "action": normalize_action_name(parsed["action"]),
        "params": parsed["params"],
        "action_result": "",
        "response": parsed["response"] if allow_chat else "",
        "visited_nodes": ["plan"],
        "turn_count": int(state.get("turn_count", 0)) + 1,
    }


def route_after_plan(state: AgentGraphState) -> str:
    return "execute_skill" if state.get("action", "none") != "none" else "no_action"


def no_action_node(state: AgentGraphState) -> dict[str, Any]:
    return {
        "action_result": "无操作",
        "visited_nodes": [*state.get("visited_nodes", []), "no_action"],
    }


def execute_skill_node(state: AgentGraphState) -> dict[str, Any]:
    action = state.get("action", "none")
    params = state.get("params", {})

    if not is_approved_skill(action):
        result = f"未知工具：{action}"
    elif not is_skill_enabled(action):
        result = f"技能已关闭：{action}"
    else:
        result = str(run_approved_skill(action, params))

    return {
        "action_result": result,
        "visited_nodes": [*state.get("visited_nodes", []), "execute_skill"],
    }


def is_failed_result(result: str) -> bool:
    return any(marker.lower() in result.lower() for marker in FAILURE_MARKERS)


def reflect_node(state: AgentGraphState) -> dict[str, Any]:
    allow_chat = bool(state.get("allow_chat", True))
    action = state.get("action", "none")
    action_result = state.get("action_result", "无操作")
    response = state.get("response", "")

    if allow_chat and not response:
        if action != "none" and is_failed_result(action_result):
            response = f"我刚才尝试执行这个能力，但没有成功：{action_result}。你可以换个说法，或者让我先创建、启用对应技能。"
        elif action != "none":
            response = action_result
        else:
            response = "我在。你可以继续说。"

    return {
        "response": response if allow_chat else "",
        "visited_nodes": [*state.get("visited_nodes", []), "reflect"],
    }


def finish_node(state: AgentGraphState) -> dict[str, Any]:
    response = bridge_tool_result_to_response(
        state.get("action", "none"),
        state.get("action_result", "无操作"),
        state.get("response", ""),
        bool(state.get("allow_chat", True)),
    )
    history = [
        *state.get("history", []),
        {
            "user": state["user_input"],
            "action": state.get("action", "none"),
            "result": state.get("action_result", "无操作"),
        },
    ]
    return {
        "response": response,
        "history": history[-20:],
        "visited_nodes": [*state.get("visited_nodes", []), "finish"],
    }


class LangGraphBridge:
    def __init__(self) -> None:
        builder = StateGraph(AgentGraphState, context_schema=AgentGraphContext)
        builder.add_node("plan", plan_node)
        builder.add_node("no_action", no_action_node)
        builder.add_node("execute_skill", execute_skill_node)
        builder.add_node("reflect", reflect_node)
        builder.add_node("finish", finish_node)
        builder.add_edge(START, "plan")
        builder.add_conditional_edges(
            "plan",
            route_after_plan,
            {
                "no_action": "no_action",
                "execute_skill": "execute_skill",
            },
        )
        builder.add_edge("no_action", "reflect")
        builder.add_edge("execute_skill", "reflect")
        builder.add_edge("reflect", "finish")
        builder.add_edge("finish", END)
        self.graph = builder.compile(checkpointer=InMemorySaver())

    def invoke(
        self,
        llm: Any,
        user_input: str,
        allow_chat: bool,
        thread_id: str,
    ) -> dict[str, Any]:
        clean_thread_id = thread_id.strip()
        if not clean_thread_id:
            raise ValueError("LangGraph thread_id cannot be empty.")

        result = self.graph.invoke(
            {
                "user_input": user_input,
                "allow_chat": allow_chat,
                "visited_nodes": [],
            },
            config={"configurable": {"thread_id": clean_thread_id}},
            context={"llm": llm},
        )
        return {
            "model_reply": result.get("model_reply", ""),
            "thought": result.get("thought", ""),
            "action": result.get("action", "none"),
            "params": result.get("params", {}),
            "action_result": result.get("action_result", "无操作"),
            "response": result.get("response", "") if allow_chat else "",
            "graph_nodes": result.get("visited_nodes", []),
            "turn_count": int(result.get("turn_count", 1)),
            "thread_id": clean_thread_id,
        }
