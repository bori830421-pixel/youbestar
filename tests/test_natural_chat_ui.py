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

    def test_markdown_images_render_as_thumbnail_images(self):
        self.assertIn("img.markdown-image", self.html)
        self.assertIn("const tokenPattern = /!\\[([^\\]]*)\\]\\(([^)]+)\\)|\\*\\*([\\s\\S]*?)\\*\\*/g;", self.html)
        self.assertIn('image.className = "markdown-image";', self.html)
        self.assertIn('link.target = "_blank";', self.html)

    def test_inline_markdown_scanner_does_not_split_dimension_asterisks(self):
        self.assertIn("function appendTextWithLineBreaks(parent, text)", self.html)
        self.assertIn("while ((match = tokenPattern.exec(source)) !== null)", self.html)
        self.assertNotIn("split(/(!\\[[^\\]]*\\]\\([^)]+\\)|\\*\\*[^*]+\\*\\*)/g)", self.html)

    def test_chat_input_supports_tab_indentation(self):
        self.assertIn('if (event.key === "Tab")', self.html)
        self.assertIn('const indent = "  ";', self.html)
        self.assertIn("input.selectionStart = input.selectionEnd = start + indent.length;", self.html)

    def test_self_evolution_view_has_nav_toggle_and_chat_payload(self):
        self.assertIn('id="nav-evolution-button"', self.html)
        self.assertIn('id="evolution-view"', self.html)
        self.assertIn('id="allow-self-evolution-toggle"', self.html)
        self.assertIn("const SELF_EVOLUTION_SETTINGS_URL", self.html)
        self.assertIn('window.location.protocol === "http:"', self.html)
        self.assertIn("window.location.origin", self.html)
        self.assertIn("allowSelfEvolution: allowSelfEvolutionToggle.checked", self.html)
        self.assertIn("allowSelfEvolution,", self.html)
        self.assertIn("function showEvolutionView()", self.html)
        self.assertIn("navEvolutionButton.addEventListener(\"click\", showEvolutionView)", self.html)


if __name__ == "__main__":
    unittest.main()
