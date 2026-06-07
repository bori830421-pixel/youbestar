import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent_system.skills.official import query_market_data
from agent_system.skill_registry import canonical_skill_name


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows
        self.empty = not rows

    def to_dict(self, orient="records"):
        if orient != "records":
            raise ValueError("only records orient is supported in this fake")
        return list(self._rows)


class MarketDataSkillTest(unittest.TestCase):
    def setUp(self):
        self.fake_akshare = SimpleNamespace(
            stock_zh_a_spot_em=lambda: FakeDataFrame(
                [
                    {
                        "代码": "601601",
                        "名称": "中国太保",
                        "最新价": 31.88,
                        "涨跌额": 0.48,
                        "涨跌幅": 1.53,
                        "今开": 31.2,
                        "最高": 32.1,
                        "最低": 31.1,
                        "成交量": 882100,
                        "成交额": 280000000,
                    },
                    {
                        "代码": "600519",
                        "名称": "贵州茅台",
                        "最新价": 1468.5,
                        "涨跌额": -8.5,
                        "涨跌幅": -0.58,
                        "今开": 1472.0,
                        "最高": 1480.0,
                        "最低": 1460.0,
                        "成交量": 21900,
                        "成交额": 3210000000,
                    },
                ]
            )
        )

    def test_chinese_stock_name_returns_structured_official_quote(self):
        with patch.dict(sys.modules, {"akshare": self.fake_akshare}):
            result = query_market_data.run({"symbol": "贵州茅台"})

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
                "-8.5",
                "-0.58%",
                "1472",
                "1480",
                "1460",
                "-",
                "21900",
                "3210000000",
                "AkShare stock_zh_a_spot_em",
            ],
            result["rows"],
        )

    def test_stock_code_returns_matching_quote(self):
        with patch.dict(sys.modules, {"akshare": self.fake_akshare}):
            result = query_market_data.run({"symbol": "601601"})

        self.assertEqual(result["data"]["name"], "中国太保")
        self.assertEqual(result["data"]["code"], "601601")
        self.assertEqual(result["summary"]["最新价/收盘价"], "31.88")

    def test_legacy_market_data_action_maps_to_official_skill(self):
        self.assertEqual(canonical_skill_name("query_market_data"), "official.query_market_data")
        self.assertEqual(canonical_skill_name("market_data"), "official.query_market_data")
        self.assertEqual(canonical_skill_name("stock_quote"), "official.query_market_data")

    def test_akshare_network_error_returns_structured_failure(self):
        fake_akshare = SimpleNamespace(
            stock_zh_a_spot_em=lambda: (_ for _ in ()).throw(RuntimeError("proxy disconnected"))
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = query_market_data.run({"symbol": "中国太保"})

        self.assertIs(result["ok"], False)
        self.assertEqual(result["kind"], "market_quote_error")
        self.assertEqual(result["message"], "证券行情接口暂时不可用，请稍后重试，或改用股票代码查询。")

    def test_code_query_falls_back_to_tencent_when_akshare_fails(self):
        fake_akshare = SimpleNamespace(
            stock_zh_a_spot_em=lambda: (_ for _ in ()).throw(RuntimeError("akshare proxy failed"))
        )
        payload = (
            'v_sh601601="51~中国太保~601601~31.88~31.40~31.20~882100~0~0~'
            '31.80~1~31.70~1~31.60~1~31.50~1~31.40~1~31.91~1~'
            '31.92~1~31.93~1~31.94~1~31.95~1~~20260607103000~'
            '0.48~1.53~32.10~31.10~31.88/882100/280000000~882100~280000000~'
            '1.00~50.00~~32.10~31.10~2.50~100.00~120.00";'
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}), patch("tools.stock_tool.fetch_text", return_value=payload):
            result = query_market_data.run({"symbol": "601601"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["data"]["name"], "中国太保")
        self.assertEqual(result["data"]["code"], "601601")
        self.assertEqual(result["data"]["close"], 31.88)
        self.assertEqual(result["rows"][0][-1], "腾讯行情接口")

    def test_stock_spot_wrapper_returns_structured_json(self):
        fake_akshare = SimpleNamespace(
            stock_sh_a_spot_em=lambda: FakeDataFrame(
                [
                    {"代码": "601601", "名称": "中国太保", "最新价": 31.88},
                    {"代码": "600519", "名称": "贵州茅台", "最新价": 1468.5},
                ]
            )
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            from tools import stock_tool

            result = stock_tool.stock_sh_a_spot_em(as_json=True)

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "stock_sh_a_spot_em")
        self.assertEqual(result["columns"], ["代码", "名称", "最新价"])
        self.assertEqual(result["rows"][0], ["601601", "中国太保", 31.88])

    def test_history_wrapper_passes_parameters_to_akshare(self):
        calls = []

        def fake_daily(**kwargs):
            calls.append(kwargs)
            return FakeDataFrame([{"date": "2026-06-05", "close": 31.88}])

        fake_akshare = SimpleNamespace(stock_zh_a_daily=fake_daily)

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            from tools import stock_tool

            result = stock_tool.stock_zh_a_daily(
                symbol="sh601601",
                start_date="20260601",
                end_date="20260605",
                adjust="qfq",
                as_json=True,
            )

        self.assertEqual(
            calls,
            [{"symbol": "sh601601", "start_date": "20260601", "end_date": "20260605", "adjust": "qfq"}],
        )
        self.assertEqual(result["rows"][0], ["2026-06-05", 31.88])

    def test_general_wrapper_sanitizes_akshare_errors(self):
        fake_akshare = SimpleNamespace(
            stock_board_concept_name_em=lambda: (_ for _ in ()).throw(RuntimeError("raw proxy url exploded"))
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            from tools import stock_tool

            result = stock_tool.stock_board_concept_name_em(as_json=True)

        self.assertIs(result["ok"], False)
        self.assertEqual(result["kind"], "stock_board_concept_name_em_error")
        self.assertNotIn("raw proxy url exploded", result["message"])

    def test_official_skill_routes_named_akshare_function(self):
        fake_akshare = SimpleNamespace(
            stock_board_industry_name_em=lambda: FakeDataFrame([{"板块名称": "保险", "涨跌幅": 1.2}])
        )

        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            result = query_market_data.run({"function": "stock_board_industry_name_em", "limit": 1})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "stock_board_industry_name_em")
        self.assertEqual(result["rows"], [["保险", 1.2]])


if __name__ == "__main__":
    unittest.main()
