import io
import unittest
from unittest.mock import patch

from agent_system.manager import run_approved_skill
from tools.weather_tool import query_weather


class FakeWeatherResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class WeatherToolTest(unittest.TestCase):
    def fake_urlopen(self, url, timeout=10):
        self.request_url = getattr(url, "full_url", url)
        payload = (
            b'{"daily":{"time":["2026-06-04","2026-06-05"],'
            b'"weathercode":[0,63],'
            b'"temperature_2m_max":[31.5,29.0],'
            b'"temperature_2m_min":[25.0,24.0]}}'
        )
        return FakeWeatherResponse(payload)

    def test_query_weather_formats_forecast(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = query_weather({"city": "汕头", "days": 2})

        self.assertIn("汕头未来2天天气预报", result)
        self.assertIn("2026-06-04：晴，最高 31.5°C，最低 25.0°C", result)
        self.assertIn("2026-06-05：中雨，最高 29.0°C，最低 24.0°C", result)
        self.assertIn("forecast_days=2", self.request_url)

    def test_registered_weather_skill_runs(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = run_approved_skill("official.query_weather", {"city": "深圳", "days": 1})

        self.assertIn("深圳未来2天天气预报", result)


if __name__ == "__main__":
    unittest.main()
