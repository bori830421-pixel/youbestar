import unittest

from server import build_user_visible_reply


class ChatReplyTest(unittest.TestCase):
    def test_reply_prefers_natural_response(self):
        result = build_user_visible_reply("你好，我在。", "none", "无操作")

        self.assertIn("# ✅ 回复", result)
        self.assertIn("## 🔍 结果", result)
        self.assertIn("你好，我在。", result)

    def test_reply_uses_tool_result_when_response_is_empty(self):
        result = build_user_visible_reply("", "official.query_weather", "汕头未来1天天气预报")

        self.assertIn("# ✅ 查询结果", result)
        self.assertIn("汕头未来1天天气预报", result)

    def test_reply_has_fallback_for_no_action_without_response(self):
        result = build_user_visible_reply("", "none", "无操作")

        self.assertIn("# ✅ 回复", result)
        self.assertIn("我在。你可以继续说。", result)


if __name__ == "__main__":
    unittest.main()
