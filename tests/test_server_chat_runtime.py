import unittest
from unittest.mock import patch

import server
from core.agent_state import AgentResult


class FakeLLM:
    pass


class ServerChatRuntimeTest(unittest.TestCase):
    def test_chat_uses_owned_agent_runtime_by_default(self):
        self.assertTrue(server.USE_AGENT_RUNTIME)

    def test_chat_request_accepts_thread_id_for_owned_runtime(self):
        request = server.ChatRequest(message="你好", threadId="chat-123")

        self.assertEqual(request.threadId, "chat-123")

    def test_run_agent_runtime_returns_chat_response_shape(self):
        result = AgentResult(
            reply="你好，我在。",
            model_reply="Thought: 用户问候。\nAction: none\nParams: {}\nResponse: 你好，我在。",
            thought="用户问候。",
            action="none",
            params={},
            action_result="无操作",
            response="你好，我在。",
            runtime_nodes=["prepare", "execute", "reflect", "finalize"],
            thread_id="default",
            step_count=4,
        )

        with patch.object(server.agent_runtime, "run", return_value=result) as run_mock:
            response = server.run_agent_runtime(FakeLLM(), "你好", True, thread_id="chat-1")

        self.assertEqual(response.reply, "你好，我在。")
        self.assertEqual(response.action, "none")
        self.assertEqual(response.action_result, "无操作")
        self.assertEqual(response.response, "你好，我在。")
        run_mock.assert_called_once_with(
            unittest.mock.ANY,
            server.memory,
            "你好",
            allow_chat=True,
            thread_id="chat-1",
        )

    @patch("server.agent_loop")
    def test_legacy_agent_loop_fallback_still_returns_chat_response_shape(self, loop_mock):
        loop_mock.return_value = (
            "Thought: 用户查询天气。\nAction: official.query_weather\nParams: {}",
            "用户查询天气。",
            "official.query_weather",
            {},
            "汕头未来1天天气预报",
            "",
        )

        response = server.run_legacy_agent_loop(FakeLLM(), "汕头天气", True)

        self.assertEqual(response.reply, "汕头未来1天天气预报")
        self.assertEqual(response.model_reply, "Thought: 用户查询天气。\nAction: official.query_weather\nParams: {}")
        self.assertEqual(response.thought, "用户查询天气。")
        self.assertEqual(response.action, "official.query_weather")
        self.assertEqual(response.params, {})
        self.assertEqual(response.action_result, "汕头未来1天天气预报")
        self.assertEqual(response.response, "")


if __name__ == "__main__":
    unittest.main()
