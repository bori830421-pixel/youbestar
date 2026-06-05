import io
import unittest
from unittest.mock import patch

from agent_system.skills.local import query_market_data


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class MarketDataSkillTest(unittest.TestCase):
    def test_latest_tencent_quote_uses_shared_decode_and_returns_structured_result(self):
        payload = (
            'v_sz300475="51~香农芯创~300475~171.90~170.00~169.00~1000~0~0~'
            '171.80~1~171.70~1~171.60~1~171.50~1~171.40~1~171.91~1~'
            '171.92~1~171.93~1~171.94~1~171.95~1~~20260605161436~'
            '1.90~1.12~172.50~168.20~171.90/1000/1000000~1000~100~'
            '1.00~50.00~~172.50~168.20~2.50~100.00~120.00";'
        ).encode("gbk")

        def fake_urlopen(request, timeout=10):
            return FakeResponse(payload)

        with patch("urllib.request.urlopen", fake_urlopen):
            result = query_market_data.run({"symbol": "300475"})

        self.assertEqual(result["kind"], "market_quote")
        self.assertEqual(result["data"]["name"], "香农芯创")
        self.assertEqual(result["data"]["code"], "300475")
        self.assertEqual(result["data"]["symbol"], "sz300475")
        self.assertEqual(result["data"]["close"], 171.9)
        self.assertIn(["香农芯创", "300475", "171.9", "1.9", "1.12%", "169", "172.5", "168.2", "2026-06-05 16:14:36", "1000", "100", "腾讯行情接口"], result["rows"])

    def test_unrecognized_fields_fall_back_to_default_quote_fields(self):
        payload = (
            'v_sz300475="51~香农芯创~300475~171.90~170.00~169.00~1000~0~0~'
            '171.80~1~171.70~1~171.60~1~171.50~1~171.40~1~171.91~1~'
            '171.92~1~171.93~1~171.94~1~171.95~1~~20260605161436~'
            '1.90~1.12~172.50~168.20~171.90/1000/1000000~1000~100~'
            '1.00~50.00~~172.50~168.20~2.50~100.00~120.00";'
        ).encode("gbk")

        def fake_urlopen(request, timeout=10):
            return FakeResponse(payload)

        with patch("urllib.request.urlopen", fake_urlopen):
            result = query_market_data.run({"symbol": "300475", "fields": ["最新股价"]})

        self.assertEqual(result["data"]["close"], 171.9)
        self.assertEqual(result["summary"]["最新价/收盘价"], "171.9")


if __name__ == "__main__":
    unittest.main()
