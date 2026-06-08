import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class ChatUiRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_ui_routes_chat_only_through_owned_runtime(self):
        self.assertIn('const CHAT_URL = `${API_ORIGIN}/chat`;', self.html)
        self.assertIn("fetch(CHAT_URL", self.html)
        self.assertNotIn("LANGGRAPH_CHAT_URL", self.html)
        removed_route = "/lang" + "graph/chat"
        self.assertNotIn(removed_route, self.html)

    def test_ui_has_no_removed_graph_experiment_controls(self):
        removed_toggle = 'id="lang' + 'graph-toggle"'
        removed_title = "Lang" + "Graph nodes"
        removed_field = "graph" + "_nodes"
        self.assertNotIn(removed_toggle, self.html)
        self.assertNotIn(removed_title, self.html)
        self.assertNotIn(removed_field, self.html)

    def test_ui_tracks_and_persists_response_duration(self):
        self.assertIn("let activeResponseTimer = null;", self.html)
        self.assertIn("function formatResponseDuration(ms)", self.html)
        self.assertIn("function responseDurationLabel(message)", self.html)
        self.assertIn("模型思考中：", self.html)
        self.assertIn("模型用时：", self.html)
        self.assertIn("responseStartedAt = Date.now()", self.html)
        self.assertIn("responseDurationMs = Date.now() - responseStartedAt", self.html)
        self.assertIn("activeResponseTimer = setInterval", self.html)
        self.assertIn('className = "reply-timer"', self.html)


if __name__ == "__main__":
    unittest.main()
