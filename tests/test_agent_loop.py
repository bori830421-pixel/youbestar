import unittest

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
        self.assertEqual(response, "")

    def test_prompt_disables_natural_chat_when_allow_chat_is_false(self):
        prompt = build_agent_prompt(Memory(), "你好", allow_chat=False)

        self.assertIn("当 allowChat=False 时", prompt)
        self.assertIn("你不能进行自然闲聊", prompt)
        self.assertIn("只能输出 Thought/Action/Params", prompt)
        self.assertNotIn("Response:", prompt.split("行为格式严格要求:", 1)[1])

    def test_agent_loop_returns_response_only_when_chat_is_allowed(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 用户问候。\nAction: none\nParams: {}\nResponse: 你好！"

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "你好", allow_chat=True)

        self.assertEqual(action, "none")
        self.assertEqual(params, {})
        self.assertEqual(result, "无操作")
        self.assertEqual(response, "你好！")


if __name__ == "__main__":
    unittest.main()
