import unittest
from unittest.mock import patch

from core.agent_checkpoint import InMemoryCheckpoint
from core.agent_runtime import AgentRuntime
from memory.memory import Memory


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class AgentRuntimeTest(unittest.TestCase):
    def test_runtime_runs_natural_chat_through_owned_nodes(self):
        runtime = AgentRuntime()
        memory = Memory()
        llm = FakeLLM(
            "Thought: 用户只是问候。\n"
            "Action: none\n"
            "Params: {}\n"
            "Response: 你好，我在。"
        )

        result = runtime.run(llm, memory, "你好", allow_chat=True, thread_id="chat-1")

        self.assertIn("# ✅ 回复", result.reply)
        self.assertIn("你好，我在。", result.response)
        self.assertEqual(result.action, "none")
        self.assertEqual(result.runtime_nodes, ["prepare", "execute", "reflect", "finalize"])
        self.assertEqual(result.step_count, 4)
        self.assertIn("你好 -> none -> 无操作", memory.get_summary())

    @patch("core.agent_nodes.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_executes_skill_and_reflects_result(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        memory = Memory()
        llm = FakeLLM(
            "Thought: 用户查询天气。\n"
            "Action: official.query_weather\n"
            'Params: {"city": "汕头", "days": 1}'
        )

        result = runtime.run(llm, memory, "汕头天气", allow_chat=True, thread_id="weather-1")

        self.assertEqual(result.action, "official.query_weather")
        self.assertEqual(result.params, {"city": "汕头", "days": 1})
        self.assertEqual(result.action_result, "汕头未来1天天气预报")
        self.assertIn("# ✅ 查询结果", result.response)
        self.assertIn("汕头未来1天天气预报", result.reply)
        run_mock.assert_called_once_with("official.query_weather", {"city": "汕头", "days": 1})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    def test_runtime_reflects_unknown_tool_as_natural_failure(self):
        runtime = AgentRuntime()
        llm = FakeLLM(
            "Thought: 用户调用一个不存在的技能。\n"
            "Action: local.missing_skill\n"
            "Params: {}"
        )

        result = runtime.run(llm, Memory(), "调用 missing skill", allow_chat=True)

        self.assertEqual(result.action, "local.missing_skill")
        self.assertEqual(result.action_result, "未知工具：local.missing_skill")
        self.assertIn("没有成功", result.response)
        self.assertIn("没有成功", result.response)
        self.assertIn("未知工具：local.missing_skill", result.reply)

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价"],
            "rows": [["香农芯创", "300475", "171.9"]],
            "summary": {"标的名称": "香农芯创", "代码": "300475", "最新价": "171.9"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_formats_structured_skill_result_without_dict_repr(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        llm = FakeLLM(
            "Thought: 用户查询证券行情。\n"
            "Action: local.query_market_data\n"
            'Params: {"symbol": "300475"}'
        )

        result = runtime.run(llm, Memory(), "查询300475最新股价", allow_chat=True)

        self.assertIn("# 🔍 证券行情查询结果", result.reply)
        self.assertIn("| **香农芯创** | **300475** | 171.9 |", result.reply)
        self.assertNotIn("{'ok': True", result.reply)
        self.assertIn("| 标的名称 | 代码 | 最新价 |", result.response)

    def test_runtime_records_checkpoints_after_each_node(self):
        checkpoint = InMemoryCheckpoint()
        runtime = AgentRuntime(checkpoint=checkpoint)
        llm = FakeLLM(
            "Thought: 用户只是问候。\n"
            "Action: none\n"
            "Params: {}\n"
            "Response: 你好。"
        )

        result = runtime.run(llm, Memory(), "你好", allow_chat=True, thread_id="checkpoint-thread")

        self.assertEqual(result.runtime_nodes, ["prepare", "execute", "reflect", "finalize"])
        self.assertEqual([record["node"] for record in checkpoint.records], result.runtime_nodes)
        self.assertEqual(checkpoint.records[0]["thread_id"], "checkpoint-thread")
        self.assertIn("你好。", checkpoint.records[-1]["state"]["reply"])


if __name__ == "__main__":
    unittest.main()
