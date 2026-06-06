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


if __name__ == "__main__":
    unittest.main()
