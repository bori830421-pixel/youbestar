import unittest

from core.loop import agent_loop
from memory.memory import Memory


class AgentLoopTest(unittest.TestCase):
    def test_unregistered_action_is_reported_as_unknown_tool(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 测试未注册动作。\nAction: not_registered\nParams: {}"

        _, _, action, params, result = agent_loop(FakeLLM(), Memory(), "测试")

        self.assertEqual(action, "local.not_registered")
        self.assertEqual(params, {})
        self.assertEqual(result, "未知工具：local.not_registered")


if __name__ == "__main__":
    unittest.main()
