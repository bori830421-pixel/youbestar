import unittest
from unittest.mock import patch

from agent_system.skills.official import query_market_data
from agent_system.skill_registry import canonical_skill_name
from tools.stock_tool import get_stock_price


def fake_eastmoney_fetch_json(url, **kwargs):
    if "searchapi.eastmoney.com" in url:
        return {
            "QuotationCodeTable": {
                "Data": [
                    {
                        "Code": "600519",
                        "Name": "贵州茅台",
                        "MktNum": "1",
                    }
                ]
            }
        }
    if "push2.eastmoney.com" in url:
        return {
            "data": {
                "f58": "贵州茅台",
                "f57": "600519",
                "f43": 146850,
                "f170": -58,
                "f44": 148000,
                "f45": 146000,
                "f46": 147200,
                "f47": 21900,
                "f48": 3210000000,
            }
        }
    raise AssertionError(f"unexpected URL: {url}")


class MarketDataSkillTest(unittest.TestCase):
    def test_get_stock_price_returns_standardized_dict(self):
        with patch("tools.stock_tool.fetch_json", side_effect=fake_eastmoney_fetch_json, create=True):
            data = get_stock_price("贵州茅台")

        self.assertEqual(
            data,
            {
                "名称": "贵州茅台",
                "代码": "600519",
                "最新价": 1468.5,
                "涨跌幅": -0.58,
                "最高": 1480.0,
                "最低": 1460.0,
                "今开": 1472.0,
                "成交量": 21900,
                "成交额": 3210000000,
                "数据来源": "东方财富",
            },
        )

    def test_chinese_stock_name_returns_eastmoney_structured_quote(self):
        with patch("tools.stock_tool.fetch_json", side_effect=fake_eastmoney_fetch_json, create=True):
            result = query_market_data.run({"symbol": "贵州茅台"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "market_quote")
        self.assertEqual(result["data"]["name"], "贵州茅台")
        self.assertEqual(result["data"]["code"], "600519")
        self.assertEqual(result["data"]["close"], 1468.5)
        self.assertEqual(result["summary"]["标的名称"], "贵州茅台")
        self.assertIn(
            [
                "贵州茅台",
                "600519",
                "1468.5",
                "-0.58%",
                "1480",
                "1460",
                "1472",
                "21900",
                "3210000000",
                "东方财富",
            ],
            result["rows"],
        )

    def test_stock_code_without_market_uses_code_rule(self):
        seen_urls = []

        def fetch_json(url, **kwargs):
            seen_urls.append(url)
            if "searchapi.eastmoney.com" in url:
                return {
                    "QuotationCodeTable": {
                        "Data": [
                            {
                                "Code": "000001",
                                "Name": "平安银行",
                            }
                        ]
                    }
                }
            return {
                "data": {
                    "f58": "平安银行",
                    "f57": "000001",
                    "f43": 1188,
                    "f170": 25,
                    "f44": 1200,
                    "f45": 1170,
                    "f46": 1180,
                    "f47": 100,
                    "f48": 200,
                }
            }

        with patch("tools.stock_tool.fetch_json", side_effect=fetch_json, create=True):
            result = query_market_data.run({"symbol": "000001"})

        self.assertIs(result["ok"], True)
        self.assertIn("secid=0.000001", seen_urls[-1])

    def test_realtime_quote_falls_back_to_tencent_when_eastmoney_push_fails(self):
        payload = (
            'v_sh601601="1~中国太保~601601~31.20~31.05~30.99~503639~278831~224808~'
            '31.19~50~31.18~8~31.17~16~31.16~197~31.15~144~31.20~91~'
            '31.21~33~31.22~24~31.23~176~31.24~258~~20260608155926~'
            '0.15~0.48~31.59~30.82~31.20/503639/1571174860~503639~157117";'
        )

        def fetch_json(url, **kwargs):
            if "searchapi.eastmoney.com" in url:
                return {
                    "QuotationCodeTable": {
                        "Data": [
                            {
                                "Code": "601601",
                                "Name": "中国太保",
                                "MktNum": "1",
                            }
                        ]
                    }
                }
            raise RuntimeError("push2 disconnected")

        with (
            patch("tools.stock_tool.fetch_json", side_effect=fetch_json, create=True),
            patch("tools.stock_tool.fetch_text", return_value=payload, create=True),
        ):
            result = query_market_data.run({"symbol": "601601"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["data"]["name"], "中国太保")
        self.assertEqual(result["data"]["code"], "601601")
        self.assertEqual(result["data"]["close"], 31.2)
        self.assertEqual(result["data"]["source"], "腾讯行情接口")
        self.assertEqual(result["rows"][0][-1], "腾讯行情接口")

    def test_function_api_is_no_longer_supported(self):
        result = query_market_data.run({"function": "stock_board_industry_name_em"})

        self.assertIs(result["ok"], False)
        self.assertEqual(result["kind"], "market_api_error")
        self.assertEqual(result["message"], "证券行情查询只支持股票代码或中文名称。")

    def test_legacy_market_data_action_maps_to_official_skill(self):
        self.assertEqual(canonical_skill_name("query_market_data"), "official.query_market_data")
        self.assertEqual(canonical_skill_name("market_data"), "official.query_market_data")
        self.assertEqual(canonical_skill_name("stock_quote"), "official.query_market_data")
        self.assertEqual(canonical_skill_name("stock"), "official.query_market_data")


if __name__ == "__main__":
    unittest.main()
