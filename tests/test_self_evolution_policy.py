import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from agent_system import evolution_policy
from agent_system.server import (
    FileListRequest,
    SelfEvolutionSettingsRequest,
    list_files,
    read_self_evolution_settings,
    save_self_evolution_settings,
)


class SelfEvolutionPolicyTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_file = Path(self.temp_dir.name) / "self_evolution_settings.json"
        self.settings_patch = patch("agent_system.evolution_policy.SETTINGS_FILE", self.settings_file)
        self.settings_patch.start()

    def tearDown(self):
        self.settings_patch.stop()
        self.temp_dir.cleanup()

    def test_self_evolution_defaults_to_disabled(self):
        self.assertFalse(evolution_policy.is_self_evolution_enabled())
        self.assertEqual(read_self_evolution_settings(), {"enabled": False})

    def test_self_evolution_settings_can_be_enabled(self):
        result = save_self_evolution_settings(SelfEvolutionSettingsRequest(enabled=True))

        self.assertEqual(result, {"enabled": True})
        self.assertTrue(evolution_policy.is_self_evolution_enabled())

    def test_skills_file_routes_require_self_evolution(self):
        with self.assertRaises(HTTPException) as ctx:
            list_files(FileListRequest(path=None, recursive=False))

        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
