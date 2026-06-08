import json
import unittest
from unittest.mock import patch

import requests

from core.config import ModelConfig
from core.llm import LLM, MODEL_RESPONSE_TIMEOUT_SECONDS


class LLMTest(unittest.TestCase):
    @patch("core.llm.requests.post")
    def test_decodes_utf8_json_when_provider_declares_wrong_encoding(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        response.encoding = "ISO-8859-1"
        response._content = json.dumps(
            {"choices": [{"message": {"content": "你好，用户"}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        post_mock.return_value = response

        llm = LLM(
            ModelConfig(
                api_url="https://api.example.com/v1",
                model="example-model",
                api_key="secret",
            )
        )

        self.assertEqual(llm.chat("你好"), "你好，用户")

    @patch("core.llm.requests.post")
    def test_uses_extended_model_response_timeout(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(
            {"choices": [{"message": {"content": "ok"}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        post_mock.return_value = response

        llm = LLM(
            ModelConfig(
                api_url="https://api.example.com/v1",
                model="example-model",
                api_key="secret",
            )
        )

        self.assertEqual(llm.chat("test"), "ok")
        self.assertEqual(MODEL_RESPONSE_TIMEOUT_SECONDS, 120)
        self.assertEqual(post_mock.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
