import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class UiScrollTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_grid_scroll_chain_can_shrink_inside_viewport(self):
        for selector in (
            ".workspace",
            ".chat-view",
            ".conversation-pane",
            ".conversation-list",
            ".chat-pane",
            ".messages",
            ".skills-view",
            ".skills-layout",
            ".skills-list-pane",
            ".skills-content",
        ):
            self.assertRegex(
                self.html,
                rf"{selector.replace('.', r'\.')}\s*\{{[^}}]*min-height:\s*0;",
                f"{selector} must set min-height: 0 so its scroll region can shrink",
            )

    def test_primary_scroll_regions_have_scrollbar_rules(self):
        self.assertIn(
            ".conversation-list,\n    .messages,\n    .skills-list-pane,\n    .skills-content",
            self.html,
        )
        self.assertIn("scrollbar-gutter: stable;", self.html)
        self.assertIn("overflow-y: auto;", self.html)


if __name__ == "__main__":
    unittest.main()
