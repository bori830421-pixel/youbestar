import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.service_config import (
    LAN_HOST,
    LOCAL_HOST,
    ServiceConfig,
    effective_host,
    firewall_rule_command,
    load_service_config,
    save_service_config,
)


class ServiceConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.temp_dir.name)
        self.runtime_patch = patch("core.service_config.local_runtime_dir", lambda: self.runtime_dir)
        self.ensure_patch = patch("core.service_config.ensure_local_runtime_dirs", self.ensure_dirs)
        self.runtime_patch.start()
        self.ensure_patch.start()

    def tearDown(self):
        self.ensure_patch.stop()
        self.runtime_patch.stop()
        self.temp_dir.cleanup()

    def ensure_dirs(self):
        (self.runtime_dir / "config").mkdir(parents=True, exist_ok=True)

    def test_default_is_local_only(self):
        config = load_service_config()

        self.assertFalse(config.lan_share_enabled)
        self.assertEqual(config.port, 8000)
        self.assertEqual(effective_host(config), LOCAL_HOST)

    def test_saves_and_loads_lan_share_setting(self):
        saved = save_service_config(ServiceConfig(lan_share_enabled=True, port=8000))
        loaded = load_service_config()
        data = json.loads((self.runtime_dir / "config" / "service.json").read_text(encoding="utf-8"))

        self.assertTrue(saved.lan_share_enabled)
        self.assertTrue(loaded.lan_share_enabled)
        self.assertEqual(effective_host(loaded), LAN_HOST)
        self.assertEqual(data["lan_share_enabled"], True)
        self.assertEqual(data["port"], 8000)

    def test_firewall_rule_command_uses_port(self):
        self.assertEqual(
            firewall_rule_command(8765),
            'New-NetFirewallRule -DisplayName "YouBestar LAN 8765" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow',
        )


if __name__ == "__main__":
    unittest.main()
