import tempfile
import unittest
from pathlib import Path

from agent_system import manager


class SkillRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.agent_dir = self.root / "agent_system"

        self.original_paths = {
            "AGENT_SYSTEM_DIR": manager.AGENT_SYSTEM_DIR,
            "PROJECT_ROOT": manager.PROJECT_ROOT,
            "SKILLS_DIR": manager.SKILLS_DIR,
            "SANDBOX_DIR": manager.SANDBOX_DIR,
            "TESTS_DIR": manager.TESTS_DIR,
            "APPROVALS_FILE": manager.APPROVALS_FILE,
            "REGISTRY_FILE": getattr(manager, "REGISTRY_FILE", None),
        }

        manager.AGENT_SYSTEM_DIR = self.agent_dir
        manager.PROJECT_ROOT = self.root
        manager.SKILLS_DIR = self.agent_dir / "skills"
        manager.SANDBOX_DIR = self.agent_dir / "sandbox"
        manager.TESTS_DIR = self.agent_dir / "tests"
        manager.APPROVALS_FILE = self.agent_dir / "approvals.json"
        manager.REGISTRY_FILE = manager.SKILLS_DIR / "registry.json"

    def tearDown(self):
        for name, value in self.original_paths.items():
            if value is not None:
                setattr(manager, name, value)
        self.temp_dir.cleanup()

    def test_normalizes_plain_skill_names_to_local_namespace(self):
        self.assertEqual(manager.normalize_skill_id("parse_order"), "local.parse_order")
        self.assertEqual(manager.normalize_skill_id("official.open_browser"), "official.open_browser")
        self.assertEqual(
            manager.normalize_skill_id("community.user123.parse_order"),
            "community.user123.parse_order",
        )

    def test_registers_and_runs_local_skill_from_registry(self):
        manager.ensure_agent_dirs()
        skill_path = manager.SKILLS_DIR / "local" / "parse_order.py"
        skill_path.write_text(
            "def run(params):\n"
            "    return [{'name': params.get('text', ''), 'qty': 1}]\n",
            encoding="utf-8",
        )

        record = manager.register_skill(
            "local.parse_order",
            skill_path,
            version="dev",
            source="local",
            description="解析订单",
        )

        self.assertEqual(record["source"], "local")
        self.assertIn("local.parse_order", manager.list_approved_skills())
        self.assertEqual(
            manager.run_approved_skill("local.parse_order", {"text": "苹果"}),
            [{"name": "苹果", "qty": 1}],
        )


if __name__ == "__main__":
    unittest.main()
