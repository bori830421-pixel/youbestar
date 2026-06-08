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

    @patch("core.llm.requests.post")
    def test_uses_responses_wire_api_when_configured(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(
            {"output_text": "responses ok"},
            ensure_ascii=False,
        ).encode("utf-8")
        post_mock.return_value = response

        llm = LLM(
            ModelConfig(
                api_url="http://43.133.32.30/v1",
                model="gpt-5.5",
                api_key="secret",
                wire_api="responses",
            )
        )

        self.assertEqual(llm.chat("test"), "responses ok")
        self.assertEqual(post_mock.call_args.args[0], "http://43.133.32.30/v1/responses")
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["input"], "test")
        self.assertEqual(payload["instructions"], "You are a helpful automation agent.")
        self.assertNotIn("messages", payload)

    @patch("core.llm.requests.post")
    def test_extracts_nested_responses_output_text(self, post_mock):
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "第一段"},
                            {"type": "output_text", "text": "第二段"},
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        post_mock.return_value = response

        llm = LLM(
            ModelConfig(
                api_url="http://43.133.32.30",
                model="gpt-5.5",
                api_key="secret",
                wire_api="responses",
            )
        )

        self.assertEqual(llm.chat("test"), "第一段\n第二段")


if __name__ == "__main__":
    unittest.main()
