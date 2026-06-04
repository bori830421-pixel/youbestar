import unittest
from unittest.mock import patch

from core.loop import build_agent_prompt
from core.loop import agent_loop
from memory.memory import Memory


class AgentLoopTest(unittest.TestCase):
    def test_unregistered_action_is_reported_as_unknown_tool(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 测试未注册动作。\nAction: not_registered\nParams: {}"

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "测试")

        self.assertEqual(action, "local.not_registered")
        self.assertEqual(params, {})
        self.assertEqual(result, "未知工具：local.not_registered")
        self.assertEqual(response, "未知工具：local.not_registered")

    def test_prompt_disables_natural_chat_when_allow_chat_is_false(self):
        prompt = build_agent_prompt(Memory(), "你好", allow_chat=False)

        self.assertIn("当 allowChat=False 时", prompt)
        self.assertIn("你不能进行自然闲聊", prompt)
        self.assertIn("只能输出 Thought/Action/Params", prompt)
        self.assertNotIn("Response:", prompt.split("行为格式严格要求:", 1)[1])

    def test_prompt_describes_response_as_user_visible_natural_reply(self):
        prompt = build_agent_prompt(Memory(), "你好", allow_chat=True)

        self.assertIn("Response 是用户直接看到的最终回答", prompt)
        self.assertIn("自然、简洁、温暖", prompt)
        self.assertIn("不要提 Thought、Action、Params", prompt)

    def test_prompt_routes_weather_requests_to_weather_skill(self):
        prompt = build_agent_prompt(Memory(), "查询汕头天气", allow_chat=True)

        self.assertIn("official.query_weather", prompt)
        self.assertIn("查询天气、天气预报、气温、下雨情况", prompt)
        self.assertIn("Params 至少包含 city", prompt)

    def test_prompt_allows_autonomous_local_skill_install(self):
        prompt = build_agent_prompt(Memory(), "帮我写一个订单解析技能", allow_chat=True)

        self.assertIn("official.install_local_skill", prompt)
        self.assertIn("直接写入 skills/local", prompt)
        self.assertIn("不需要人工审批", prompt)

    def test_prompt_routes_project_file_writes_to_write_project_file(self):
        prompt = build_agent_prompt(Memory(), "直接在运行目录里面写一个 notes.md", allow_chat=True)

        self.assertIn("official.write_project_file", prompt)
        self.assertIn("运行目录内的普通项目文件", prompt)
        self.assertIn("Params 包含 path、content", prompt)

    def test_agent_loop_returns_response_only_when_chat_is_allowed(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 用户问候。\nAction: none\nParams: {}\nResponse: 你好！"

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "你好", allow_chat=True)

        self.assertEqual(action, "none")
        self.assertEqual(params, {})
        self.assertEqual(result, "无操作")
        self.assertEqual(response, "你好！")

    @patch("core.loop.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.loop.is_skill_enabled", return_value=True)
    @patch("core.loop.is_approved_skill", return_value=True)
    def test_agent_loop_bridges_tool_result_to_user_response(self, approved_mock, enabled_mock, run_mock):
        class FakeLLM:
            def chat(self, prompt):
                return 'Thought: 用户查询天气。\nAction: official.query_weather\nParams: {"city": "汕头"}'

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "汕头天气")

        self.assertEqual(action, "official.query_weather")
        self.assertEqual(params, {"city": "汕头"})
        self.assertEqual(result, "汕头未来1天天气预报")
        self.assertEqual(response, result)
        run_mock.assert_called_once_with("official.query_weather", {"city": "汕头"})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")


if __name__ == "__main__":
    unittest.main()
