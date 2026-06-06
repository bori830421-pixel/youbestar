import unittest
from unittest.mock import Mock, patch

from core.model_discovery import discover_models, normalize_models_api_url, parse_model_ids


class ModelDiscoveryTest(unittest.TestCase):
    def test_normalizes_openai_compatible_models_urls(self):
        self.assertEqual(
            normalize_models_api_url("https://api.deepseek.com/v1"),
            "https://api.deepseek.com/v1/models",
        )
        self.assertEqual(
            normalize_models_api_url("https://api.example.com/v1/chat/completions"),
            "https://api.example.com/v1/models",
        )
        self.assertEqual(
            normalize_models_api_url("https://api.example.com/v1/models"),
            "https://api.example.com/v1/models",
        )

    def test_parses_common_model_response_shapes(self):
        self.assertEqual(
            parse_model_ids({"data": [{"id": "model-b"}, {"id": "model-a"}]}),
            ["model-a", "model-b"],
        )
        self.assertEqual(
            parse_model_ids({"models": ["model-b", {"id": "model-a"}, "model-a"]}),
            ["model-a", "model-b"],
        )

    @patch("core.model_discovery.requests.get")
    def test_discovers_models_with_bearer_auth(self, get_mock):
        response = Mock()
        response.json.return_value = {"data": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}]}
        response.raise_for_status.return_value = None
        get_mock.return_value = response

        result = discover_models("https://api.deepseek.com/v1", "secret-key")

        self.assertEqual(
            result,
            {
                "api_url": "https://api.deepseek.com/v1",
                "models_url": "https://api.deepseek.com/v1/models",
                "models": ["deepseek-chat", "deepseek-reasoner"],
            },
        )
        get_mock.assert_called_once_with(
            "https://api.deepseek.com/v1/models",
            headers={"Authorization": "Bearer secret-key", "Accept": "application/json"},
            timeout=20,
        )

    @patch("core.model_discovery.requests.get")
    def test_root_api_falls_back_to_v1_models_after_404(self, get_mock):
        missing = Mock(status_code=404)
        missing.raise_for_status.return_value = None
        found = Mock(status_code=200)
        found.json.return_value = {"data": [{"id": "deepseek-chat"}]}
        found.raise_for_status.return_value = None
        get_mock.side_effect = [missing, found]

        result = discover_models("https://api.deepseek.com", "secret-key")

        self.assertEqual(result["api_url"], "https://api.deepseek.com/v1")
        self.assertEqual(result["models_url"], "https://api.deepseek.com/v1/models")
        self.assertEqual(get_mock.call_count, 2)
        self.assertEqual(get_mock.call_args_list[0].args[0], "https://api.deepseek.com/models")
        self.assertEqual(get_mock.call_args_list[1].args[0], "https://api.deepseek.com/v1/models")

    def test_rejects_response_without_models(self):
        with self.assertRaisesRegex(ValueError, "没有返回可用模型"):
            parse_model_ids({"data": []})


if __name__ == "__main__":
    unittest.main()
