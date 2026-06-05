import unittest
from unittest.mock import patch

from core.langgraph_bridge import LangGraphBridge


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.prompts = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class LangGraphBridgeTest(unittest.TestCase):
    def setUp(self):
        self.bridge = LangGraphBridge()

    def test_no_action_path_keeps_per_thread_state(self):
        llm = FakeLLM(
            "Thought: 用户只是问候。\n"
            "Action: none\n"
            "Params: {}\n"
            "Response: 你好！"
        )

        first = self.bridge.invoke(llm, "你好", True, "thread-no-action")
        second = self.bridge.invoke(llm, "再问一次", True, "thread-no-action")
        other_thread = self.bridge.invoke(llm, "全新线程", True, "thread-other")

        self.assertEqual(first["graph_nodes"], ["plan", "no_action", "reflect", "finish"])
        self.assertEqual(first["turn_count"], 1)
        self.assertEqual(first["action_result"], "无操作")
        self.assertIn("# ✅ 回复", first["response"])
        self.assertIn("你好！", first["response"])
        self.assertEqual(second["turn_count"], 2)
        self.assertEqual(other_thread["turn_count"], 1)
        self.assertIn("你好 -> none -> 无操作", llm.prompts[1])
        self.assertNotIn("你好 -> none -> 无操作", llm.prompts[2])

    @patch("core.langgraph_bridge.run_approved_skill", return_value="技能执行完成")
    @patch("core.langgraph_bridge.is_skill_enabled", return_value=True)
    @patch("core.langgraph_bridge.is_approved_skill", return_value=True)
    def test_approved_skill_path_runs_through_execute_node(
        self,
        approved_mock,
        enabled_mock,
        run_mock,
    ):
        llm = FakeLLM(
            "Thought: 用户要求打开网页。\n"
            "Action: official.open_browser\n"
            'Params: {"url": "https://www.baidu.com"}'
        )

        result = self.bridge.invoke(llm, "打开百度", False, "thread-tool")

        self.assertEqual(result["graph_nodes"], ["plan", "execute_skill", "reflect", "finish"])
        self.assertEqual(result["action"], "official.open_browser")
        self.assertEqual(result["action_result"], "技能执行完成")
        self.assertEqual(result["response"], "")
        run_mock.assert_called_once_with(
            "official.open_browser",
            {"url": "https://www.baidu.com"},
        )
        approved_mock.assert_called_once_with("official.open_browser")
        enabled_mock.assert_called_once_with("official.open_browser")

    @patch("core.langgraph_bridge.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.langgraph_bridge.is_skill_enabled", return_value=True)
    @patch("core.langgraph_bridge.is_approved_skill", return_value=True)
    def test_tool_result_is_bridged_to_response_when_chat_is_allowed(
        self,
        approved_mock,
        enabled_mock,
        run_mock,
    ):
        llm = FakeLLM(
            "Thought: 用户查询天气。\n"
            "Action: official.query_weather\n"
            'Params: {"city": "汕头", "days": 1}'
        )

        result = self.bridge.invoke(llm, "汕头天气", True, "thread-weather")

        self.assertEqual(result["action"], "official.query_weather")
        self.assertEqual(result["action_result"], "汕头未来1天天气预报")
        self.assertIn("# ✅ 查询结果", result["response"])
        self.assertIn("汕头未来1天天气预报", result["response"])
        run_mock.assert_called_once_with(
            "official.query_weather",
            {"city": "汕头", "days": 1},
        )
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    def test_reflect_turns_failed_tool_result_into_natural_response(self):
        llm = FakeLLM(
            "Thought: 用户想调用一个不存在的技能。\n"
            "Action: local.missing_skill\n"
            "Params: {}"
        )

        result = self.bridge.invoke(llm, "调用 missing skill", True, "thread-missing-skill")

        self.assertEqual(result["graph_nodes"], ["plan", "execute_skill", "reflect", "finish"])
        self.assertEqual(result["action"], "local.missing_skill")
        self.assertEqual(result["action_result"], "未知工具：local.missing_skill")
        self.assertIn("没有成功", result["response"])
        self.assertIn("未知工具：local.missing_skill", result["response"])
        self.assertIn("创建、启用对应技能", result["response"])


if __name__ == "__main__":
    unittest.main()
