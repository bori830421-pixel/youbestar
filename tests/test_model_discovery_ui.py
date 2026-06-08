import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class ModelDiscoveryUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_config_page_has_searchable_model_discovery_controls(self):
        self.assertIn('id="profile-select"', self.html)
        self.assertIn('id="save-profile-button"', self.html)
        self.assertIn('id="discover-models-button"', self.html)
        self.assertIn('id="model-options"', self.html)
        self.assertIn('id="model-picker-button"', self.html)
        self.assertIn('class="model-options"', self.html)
        self.assertIn('aria-controls="model-options"', self.html)
        self.assertIn('id="model-name" type="text"', self.html)

    def test_ui_calls_model_discovery_endpoint_and_populates_options(self):
        self.assertIn('const MODELS_DISCOVER_URL = `${API_ORIGIN}/models/discover`;', self.html)
        self.assertIn("async function discoverModels()", self.html)
        self.assertIn("discoveredModels = normalizeDiscoveredModels(data.models)", self.html)
        self.assertIn("renderModelOptions({ filterText })", self.html)
        self.assertIn("modelOptions.appendChild(button)", self.html)
        self.assertIn("const normalizedApiUrl = data.api_url", self.html)
        self.assertIn("apiUrlInput.value = data.api_url", self.html)
        self.assertIn("api_url: apiUrlInput.value.trim()", self.html)
        self.assertIn("api_key: apiKeyInput.value.trim()", self.html)

    def test_model_picker_can_open_full_list_when_input_has_default_value(self):
        self.assertNotIn('list="model-options"', self.html)
        self.assertNotIn("<datalist", self.html)
        self.assertIn('modelInput.addEventListener("focus", () => {', self.html)
        self.assertIn("showModelOptions();", self.html)
        self.assertIn('modelPickerButton.addEventListener("click", () => {', self.html)
        self.assertIn('modelInput.addEventListener("input", () => {', self.html)
        self.assertIn("showModelOptions({ filterText: modelInput.value });", self.html)

    def test_config_profiles_can_switch_api_key_and_model(self):
        self.assertIn("let configProfiles = [];", self.html)
        self.assertIn("let currentProfileId = \"default\";", self.html)
        self.assertIn("current_profile_id: currentProfileId", self.html)
        self.assertIn("profiles: configProfiles", self.html)
        self.assertIn("function applyProfile(profileId)", self.html)
        self.assertIn("apiUrlInput.value = profile.api_url", self.html)
        self.assertIn("modelInput.value = profile.model", self.html)
        self.assertIn("apiKeyInput.value = profile.api_key", self.html)
        self.assertIn('profileSelect.addEventListener("change", () => {', self.html)
        self.assertIn('saveProfileButton.addEventListener("click", async () => {', self.html)


if __name__ == "__main__":
    unittest.main()
