import io
import unittest
from unittest.mock import patch

from core.http_client import decode_bytes, fetch_text


class FakeHeaders:
    def __init__(self, content_type: str = ""):
        self.content_type = content_type

    def get_content_charset(self):
        return None

    def get(self, key, default=""):
        if key.lower() == "content-type":
            return self.content_type
        return default


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, content_type: str = ""):
        super().__init__(payload)
        self.headers = FakeHeaders(content_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class HttpClientTest(unittest.TestCase):
    def test_decode_bytes_falls_back_to_gb18030_for_chinese_market_api(self):
        raw = 'v_sz300475="51~香农芯创~300475";'.encode("gbk")

        self.assertIn("香农芯创", decode_bytes(raw))

    def test_fetch_text_uses_charset_from_header(self):
        def fake_urlopen(request, timeout=10):
            return FakeResponse("香农芯创".encode("gbk"), "text/plain; charset=gbk")

        with patch("urllib.request.urlopen", fake_urlopen):
            result = fetch_text("http://example.test")

        self.assertEqual(result, "香农芯创")


if __name__ == "__main__":
    unittest.main()
