import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class ConversationPersistenceUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_ui_persists_conversations_in_local_storage(self):
        self.assertIn('const CONVERSATION_STORAGE_KEY = "youbestar.conversations.v1";', self.html)
        self.assertIn('const ACTIVE_CONVERSATION_STORAGE_KEY = "youbestar.activeConversationId.v1";', self.html)
        self.assertIn("function loadStoredConversations()", self.html)
        self.assertIn("function saveStoredConversations()", self.html)
        self.assertIn("localStorage.setItem(CONVERSATION_STORAGE_KEY", self.html)
        self.assertIn("loadStoredConversations();", self.html)

    def test_ui_does_not_persist_pending_assistant_messages(self):
        self.assertIn("!message.pending", self.html)
        self.assertIn("history: conversation.history.filter((message) => !message.pending)", self.html)


if __name__ == "__main__":
    unittest.main()
