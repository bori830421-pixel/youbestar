import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class ModelDiscoveryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_config_page_has_searchable_model_discovery_controls(self):
        self.assertIn('id="discover-models-button"', self.html)
        self.assertIn('id="model-options"', self.html)
        self.assertIn('list="model-options"', self.html)
        self.assertIn('id="model-name" type="text"', self.html)

    def test_ui_calls_model_discovery_endpoint_and_populates_options(self):
        self.assertIn('const MODELS_DISCOVER_URL = `${API_ORIGIN}/models/discover`;', self.html)
        self.assertIn("async function discoverModels()", self.html)
        self.assertIn("modelOptions.appendChild(option)", self.html)
        self.assertIn("const normalizedApiUrl = data.api_url", self.html)
        self.assertIn("apiUrlInput.value = data.api_url", self.html)
        self.assertIn("api_url: apiUrlInput.value.trim()", self.html)
        self.assertIn("api_key: apiKeyInput.value.trim()", self.html)


if __name__ == "__main__":
    unittest.main()
