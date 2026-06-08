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

    def test_chat_messages_allow_horizontal_scroll_for_wide_tables(self):
        self.assertRegex(
            self.html,
            r"\.messages\s*\{[^}]*overflow-y:\s*auto;[^}]*overflow-x:\s*auto;",
        )
        self.assertRegex(
            self.html,
            r"\.markdown-table-wrap\s*\{[^}]*max-width:\s*100%;[^}]*overflow-x:\s*auto;",
        )

    def test_conversation_pane_can_collapse(self):
        self.assertIn('id="conversation-collapse-button"', self.html)
        self.assertIn(".chat-view.conversation-collapsed", self.html)
        self.assertIn("CONVERSATION_COLLAPSED_STORAGE_KEY", self.html)
        self.assertIn("function setConversationPaneCollapsed(collapsed)", self.html)
        self.assertIn('conversationCollapseButton.addEventListener("click"', self.html)


if __name__ == "__main__":
    unittest.main()
