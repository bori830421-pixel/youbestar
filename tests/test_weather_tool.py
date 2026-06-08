import io
import unittest
from unittest.mock import patch

from agent_system.manager import run_approved_skill
from tools.weather_tool import get_weather, query_weather


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
            b'"temperature_2m_max":[31.5,29.0],'
            b'"temperature_2m_min":[25.0,24.0],'
            b'"precipitation_probability_max":[10,80]}}'
        )
        return FakeWeatherResponse(payload)

    def test_query_weather_formats_forecast(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = query_weather({"city": "汕头", "days": 2})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "weather_forecast")
        self.assertEqual(result["title"], "汕头未来2天天气预报")
        self.assertEqual(result["columns"], ["日期", "最高温", "最低温", "降雨概率", "提醒"])
        self.assertEqual(
            result["rows"],
            [
                ["2026-06-04", "31.5°C", "25.0°C", "10%", ""],
                ["2026-06-05", "29.0°C", "24.0°C", "80%", "记得带伞"],
            ],
        )
        self.assertIn("precipitation_probability_max", self.request_url)
        self.assertIn("forecast_days=7", self.request_url)

    def test_get_weather_returns_standardized_dict_with_advice(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = get_weather("汕头")

        self.assertEqual(result["city"], "汕头")
        self.assertEqual(result["temp"], 31.5)
        self.assertEqual(result["condition"], "晴")
        self.assertEqual(result["advice"], [])

    def test_query_weather_fetches_seven_days_then_filters_requested_days(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = query_weather({"city": "汕头", "days": 1})

        self.assertEqual(result["kind"], "weather_forecast")
        self.assertEqual(len(result["rows"]), 1)
        self.assertIn("forecast_days=7", self.request_url)

    def test_registered_weather_skill_runs(self):
        with patch("urllib.request.urlopen", self.fake_urlopen):
            result = run_approved_skill("official.query_weather", {"city": "深圳", "days": 1})

        self.assertEqual(result["kind"], "weather_forecast")
        self.assertEqual(result["summary"]["城市"], "深圳")


if __name__ == "__main__":
    unittest.main()
