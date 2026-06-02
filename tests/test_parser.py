import unittest

from core import parser


class ParseAgentOutputTest(unittest.TestCase):
    def parse(self, text):
        self.assertTrue(hasattr(parser, "parse_agent_output"), "parse_agent_output is missing")
        return parser.parse_agent_output(text)

    def test_parses_thought_action_and_params(self):
        parsed = self.parse(
            """
Thought: 用户要求打开网页，需要调用浏览器技能。
Action: official.open_browser
Params: {"url": "https://www.baidu.com"}
""".strip()
        )

        self.assertEqual(parsed["thought"], "用户要求打开网页，需要调用浏览器技能。")
        self.assertEqual(parsed["action"], "official.open_browser")
        self.assertEqual(parsed["params"], {"url": "https://www.baidu.com"})
        self.assertEqual(parsed["response"], "")

    def test_parses_optional_response(self):
        parsed = self.parse(
            """
Thought: 用户只是问候，可以自然回复。
Action: none
Params: {}
Response: 你好！今天我们可以一起看一下订单解析模块。
""".strip()
        )

        self.assertEqual(parsed["thought"], "用户只是问候，可以自然回复。")
        self.assertEqual(parsed["action"], "none")
        self.assertEqual(parsed["params"], {})
        self.assertEqual(parsed["response"], "你好！今天我们可以一起看一下订单解析模块。")

    def test_defaults_to_none_when_no_action_is_present(self):
        parsed = self.parse("你好，我可以帮你。")

        self.assertEqual(parsed["thought"], "")
        self.assertEqual(parsed["action"], "none")
        self.assertEqual(parsed["params"], {})
        self.assertEqual(parsed["response"], "")


if __name__ == "__main__":
    unittest.main()
