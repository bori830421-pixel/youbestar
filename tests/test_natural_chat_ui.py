import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class NaturalChatUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_debug_trace_is_hidden_by_default(self):
        self.assertIn("let showThoughtMode = false;", self.html)
        self.assertIn("let showToolMode = false;", self.html)

    def test_final_reply_is_rendered_before_debug_trace(self):
        response_index = self.html.index("const finalReply = message.response || message.reply || message.content || \"\";")
        thought_index = self.html.index("if (showThoughtMode)")
        tool_index = self.html.index("if (showToolMode)")

        self.assertLess(response_index, thought_index)
        self.assertLess(response_index, tool_index)

    def test_backend_reply_is_used_as_assistant_content(self):
        self.assertIn("const finalReply = data.reply || data.response || \"\";", self.html)
        self.assertIn("const assistantContent = finalReply || modelReply || actionResult;", self.html)
        self.assertNotIn("const assistantContent = `模型输出:", self.html)


if __name__ == "__main__":
    unittest.main()
