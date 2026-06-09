import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_system import manager
from agent_system.skill_registry import BUILTIN_SKILLS, canonical_skill_name
from core.local_runtime import (
    ensure_local_runtime_dirs,
    local_runtime_dir,
    local_runtime_record_path,
    local_skill_registry_file,
    local_skill_source_dir,
)


class SkillRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.agent_dir = self.root / "agent_system"
        self.local_runtime_dir = self.root / "YoubestarLocal"
        self.local_home_patch = patch.dict(os.environ, {"YOUBESTAR_LOCAL_HOME": str(self.local_runtime_dir)})
        self.local_home_patch.start()

        self.original_paths = {
            "AGENT_SYSTEM_DIR": manager.AGENT_SYSTEM_DIR,
            "PROJECT_ROOT": manager.PROJECT_ROOT,
            "SKILLS_DIR": manager.SKILLS_DIR,
            "SANDBOX_DIR": manager.SANDBOX_DIR,
            "TESTS_DIR": manager.TESTS_DIR,
            "APPROVALS_FILE": manager.APPROVALS_FILE,
            "REGISTRY_FILE": getattr(manager, "REGISTRY_FILE", None),
            "ensure_local_runtime_dirs": manager.ensure_local_runtime_dirs,
            "local_runtime_dir": manager.local_runtime_dir,
            "local_runtime_record_path": manager.local_runtime_record_path,
            "local_skill_registry_file": manager.local_skill_registry_file,
            "local_skill_source_dir": manager.local_skill_source_dir,
        }

        manager.AGENT_SYSTEM_DIR = self.agent_dir
        manager.PROJECT_ROOT = self.root
        manager.SKILLS_DIR = self.agent_dir / "skills"
        manager.SANDBOX_DIR = self.agent_dir / "sandbox"
        manager.TESTS_DIR = self.agent_dir / "tests"
        manager.APPROVALS_FILE = self.agent_dir / "approvals.json"
        manager.REGISTRY_FILE = manager.SKILLS_DIR / "registry.json"
        manager.ensure_local_runtime_dirs = ensure_local_runtime_dirs
        manager.local_runtime_dir = local_runtime_dir
        manager.local_runtime_record_path = local_runtime_record_path
        manager.local_skill_registry_file = local_skill_registry_file
        manager.local_skill_source_dir = local_skill_source_dir

    def tearDown(self):
        for name, value in self.original_paths.items():
            if value is not None:
                setattr(manager, name, value)
        self.local_home_patch.stop()
        self.temp_dir.cleanup()

    def test_normalizes_plain_skill_names_to_local_namespace(self):
        self.assertEqual(manager.normalize_skill_id("parse_order"), "local.parse_order")
        self.assertEqual(manager.normalize_skill_id("official.open_browser"), "official.open_browser")
        self.assertEqual(canonical_skill_name("web_query"), "official.web_query")
        self.assertEqual(
            manager.normalize_skill_id("community.user123.parse_order"),
            "community.user123.parse_order",
        )

    def test_builtin_preview_excel_description_is_generic_classification_entry(self):
        description = BUILTIN_SKILLS["official.preview_excel"]["description"]

        self.assertIn("通用 Excel 表格处理分类系统入口", description)
        self.assertIn("表头前几行", description)
        self.assertIn("中文标准字段映射", description)
        self.assertIn("未识别/ambiguous", description)
        self.assertIn("待用户弹窗确认", description)
        self.assertIn("不写数据库", description)

    def test_registers_and_runs_local_skill_from_registry(self):
        manager.ensure_agent_dirs()
        skill_path = manager.skill_source_dir("local") / "parse_order.py"
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

    def test_installs_and_overwrites_local_skill_directly(self):
        manager.ensure_agent_dirs()
        first = manager.install_local_skill(
            "local.echo_value",
            "def run(params):\n"
            "    return {'value': params.get('value')}\n",
            description="回显输入",
        )

        self.assertEqual(first["status"], "installed")
        self.assertEqual(first["skill_name"], "local.echo_value")
        self.assertIn("local.echo_value", manager.list_approved_skills())
        self.assertEqual(
            manager.run_approved_skill("local.echo_value", {"value": "苹果"})["value"],
            "苹果",
        )

        manager.install_local_skill(
            "local.echo_value",
            "def run(params):\n"
            "    return {'updated': True, 'value': params.get('value')}\n",
            description="覆盖后的回显输入",
            overwrite=True,
        )

        self.assertEqual(
            manager.run_approved_skill("local.echo_value", {"value": "香蕉"}),
            {"updated": True, "value": "香蕉"},
        )

    def test_install_local_skill_rejects_unsafe_code(self):
        manager.ensure_agent_dirs()

        with self.assertRaises(Exception) as ctx:
            manager.install_local_skill(
                "local.unsafe_skill",
                "import os\n\n"
                "def run(params):\n"
                "    return os.listdir('.')\n",
                description="危险技能",
            )

        self.assertIn("安全扫描未通过", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
