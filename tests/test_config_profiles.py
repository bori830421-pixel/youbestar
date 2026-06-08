import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import ModelConfig, ModelProfile, load_config, save_config_file


class ConfigProfilesTest(unittest.TestCase):
    def test_loads_legacy_single_config_without_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "youbestar.json"
            config_file.write_text(
                json.dumps(
                    {
                        "api_url": "https://api.example.com/v1",
                        "model": "example-model",
                        "api_key": "secret-key",
                    }
                ),
                encoding="utf-8",
            )
            with patch("core.config.CONFIG_FILE", config_file):
                config = load_config()

        self.assertEqual(config.api_url, "https://api.example.com/v1")
        self.assertEqual(config.model, "example-model")
        self.assertEqual(config.api_key, "secret-key")
        self.assertEqual(config.profiles, [])

    def test_saves_current_profile_and_all_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "youbestar.json"
            with patch("core.config.CONFIG_FILE", config_file):
                saved = save_config_file(
                    ModelConfig(
                        api_url="https://api.deepseek.com/v1",
                        model="deepseek-chat",
                        api_key="deepseek-key",
                        current_profile_id="deepseek",
                        profiles=[
                            ModelProfile(
                                id="deepseek",
                                name="DeepSeek",
                                api_url="https://api.deepseek.com/v1",
                                model="deepseek-chat",
                                api_key="deepseek-key",
                            ),
                            ModelProfile(
                                id="openai",
                                name="OpenAI",
                                api_url="https://api.openai.com/v1",
                                model="gpt-4o-mini",
                                api_key="openai-key",
                            ),
                        ],
                    )
                )
                data = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(saved.current_profile_id, "deepseek")
        self.assertEqual(len(saved.profiles), 2)
        self.assertEqual(data["current_profile_id"], "deepseek")
        self.assertEqual(data["profiles"][0]["api_key"], "deepseek-key")
        self.assertEqual(data["profiles"][1]["api_key"], "openai-key")

    def test_load_activates_current_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "youbestar.json"
            config_file.write_text(
                json.dumps(
                    {
                        "api_url": "",
                        "model": "",
                        "api_key": "",
                        "current_profile_id": "openai",
                        "profiles": [
                            {
                                "id": "deepseek",
                                "name": "DeepSeek",
                                "api_url": "https://api.deepseek.com/v1",
                                "model": "deepseek-chat",
                                "api_key": "deepseek-key",
                            },
                            {
                                "id": "openai",
                                "name": "OpenAI",
                                "api_url": "https://api.openai.com/v1",
                                "model": "gpt-4o-mini",
                                "api_key": "openai-key",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch("core.config.CONFIG_FILE", config_file):
                config = load_config()

        self.assertEqual(config.api_url, "https://api.openai.com/v1")
        self.assertEqual(config.model, "gpt-4o-mini")
        self.assertEqual(config.api_key, "openai-key")

    def test_adds_current_config_as_profile_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "youbestar.json"
            with patch("core.config.CONFIG_FILE", config_file):
                saved = save_config_file(
                    ModelConfig(
                        api_url="https://api.example.com/v1",
                        model="example-model",
                        api_key="secret-key",
                        current_profile_id="example",
                    )
                )

        self.assertEqual(len(saved.profiles), 1)
        self.assertEqual(saved.profiles[0].id, "example")
        self.assertEqual(saved.profiles[0].api_key, "secret-key")


if __name__ == "__main__":
    unittest.main()
