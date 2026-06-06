import unittest
from unittest.mock import patch

from tools.web_query_tool import web_query


class WebQueryToolTest(unittest.TestCase):
    @patch("tools.web_query_tool.fetch_text")
    def test_web_query_returns_structured_results_and_region_summary(self, fetch_text_mock):
        fetch_text_mock.return_value = (
            '{"feed":{"entry":['
            '{"title":"榴莲仅退款事件发生在广西","abs":"有报道提到广西某地榴莲售后争议","url":"https://example.com/1"},'
            '{"title":"相关讨论","abs":"围绕榴莲仅退款的舆情","url":"https://example.com/2"}'
            ']}}'
        )

        result = web_query({"query": "榴莲仅退款 哪个地区", "limit": 5})

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "web_search")
        self.assertEqual(result["title"], "网页搜索结果")
        self.assertEqual(result["summary"]["查询关键词"], "榴莲仅退款 哪个地区")
        self.assertIn("搜索来源", result["summary"])
        self.assertEqual(result["summary"]["疑似地区"], "广西")
        self.assertEqual(result["rows"][0][0], "百度")
        self.assertEqual(result["rows"][0][1], "榴莲仅退款事件发生在广西")

    def test_web_query_requires_query(self):
        result = web_query({})

        self.assertFalse(result["ok"])
        self.assertIn("缺少 query 参数", result["error"])

    @patch("tools.web_query_tool.fetch_text")
    def test_web_query_falls_back_to_baidu_html_results(self, fetch_text_mock):
        fetch_text_mock.side_effect = [
            '{"feed":{"entry":[]}}',
            """
            <html><body>
              <div class="result c-container">
                <h3><a href="https://example.com/news">河南濮阳商家榴莲仅退款案</a></h3>
                <span>买家来自山东德州庆云县，商家所在地为河南濮阳。</span>
              </div>
            </body></html>
            """,
        ]

        result = web_query({"query": "榴莲仅退款 哪个地区", "limit": 5})

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["疑似地区"], "山东德州庆云县")
        self.assertEqual(result["summary"]["涉事买家地区"], "山东德州庆云县")
        self.assertEqual(result["summary"]["商家所在地"], "河南濮阳")
        self.assertIn("河南濮阳商家榴莲仅退款案", result["rows"][0][1])

    @patch("tools.web_query_tool.fetch_text")
    def test_web_query_auto_tries_mainland_and_external_sources_when_network_allows(self, fetch_text_mock):
        fetch_text_mock.side_effect = [
            '{"feed":{"entry":[]}}',
            "<html><body></body></html>",
            "<html><body></body></html>",
            "<html><body></body></html>",
            "<html><body></body></html>",
            """
            <html><body>
              <div class="result">
                <a class="result__a" href="https://example.com/model">最新大模型发布</a>
                <a class="result__snippet">国内外厂商发布新的多模态大模型。</a>
              </div>
            </body></html>
            """,
        ]

        result = web_query({"query": "最新有什么新出来的大模型", "limit": 5})

        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"][0][0], "DuckDuckGo")
        self.assertEqual(result["rows"][0][1], "最新大模型发布")
        self.assertEqual(result["summary"]["搜索来源"], "baidu, bing_cn, sogou, bing_global, duckduckgo")

    @patch("tools.web_query_tool.fetch_text")
    def test_web_query_skips_unreachable_external_sources(self, fetch_text_mock):
        fetch_text_mock.side_effect = [
            '{"feed":{"entry":[]}}',
            "<html><body></body></html>",
            """
            <html><body>
              <li class="b_algo">
                <h2><a href="https://example.com/model">最新国产大模型发布</a></h2>
                <p>国内厂商发布新的多模态大模型。</p>
              </li>
            </body></html>
            """,
        ]

        result = web_query({"query": "最新有什么新出来的大模型", "limit": 5})

        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"][0][0], "必应")
        self.assertEqual(result["rows"][0][1], "最新国产大模型发布")


if __name__ == "__main__":
    unittest.main()
