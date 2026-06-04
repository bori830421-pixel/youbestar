import unittest

from server import build_user_visible_reply


class ChatReplyTest(unittest.TestCase):
    def test_reply_prefers_natural_response(self):
        self.assertEqual(
            build_user_visible_reply("你好，我在。", "none", "无操作"),
            "你好，我在。",
        )

    def test_reply_uses_tool_result_when_response_is_empty(self):
        self.assertEqual(
            build_user_visible_reply("", "official.query_weather", "汕头未来1天天气预报"),
            "汕头未来1天天气预报",
        )

    def test_reply_is_empty_for_no_action_without_response(self):
        self.assertEqual(build_user_visible_reply("", "none", "无操作"), "")


if __name__ == "__main__":
    unittest.main()
