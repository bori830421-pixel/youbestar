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

        self.assertEqual(first["graph_nodes"], ["plan", "no_action", "finish"])
        self.assertEqual(first["turn_count"], 1)
        self.assertEqual(first["action_result"], "无操作")
        self.assertEqual(first["response"], "你好！")
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

        self.assertEqual(result["graph_nodes"], ["plan", "execute_skill", "finish"])
        self.assertEqual(result["action"], "official.open_browser")
        self.assertEqual(result["action_result"], "技能执行完成")
        self.assertEqual(result["response"], "")
        run_mock.assert_called_once_with(
            "official.open_browser",
            {"url": "https://www.baidu.com"},
        )
        approved_mock.assert_called_once_with("official.open_browser")
        enabled_mock.assert_called_once_with("official.open_browser")


if __name__ == "__main__":
    unittest.main()
