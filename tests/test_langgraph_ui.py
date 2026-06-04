import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class LangGraphUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_ui_can_route_chat_through_langgraph(self):
        self.assertIn('id="langgraph-toggle"', self.html)
        self.assertIn('const LANGGRAPH_CHAT_URL = `${API_ORIGIN}/langgraph/chat`;', self.html)
        self.assertIn("useLangGraph ? LANGGRAPH_CHAT_URL : CHAT_URL", self.html)
        self.assertIn("threadId:", self.html)

    def test_ui_displays_langgraph_trace(self):
        self.assertIn("message.graph_nodes", self.html)
        self.assertIn("LangGraph nodes", self.html)
        self.assertIn("data.turn_count", self.html)


if __name__ == "__main__":
    unittest.main()
