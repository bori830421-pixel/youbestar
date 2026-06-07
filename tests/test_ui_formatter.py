import unittest

from core.ui_formatter import (
    format_error,
    format_inventory,
    format_order_result,
    format_plain_response,
    format_skill_result,
    format_weather_result,
)


class UiFormatterTest(unittest.TestCase):
    def test_plain_response_has_structured_markdown(self):
        result = format_plain_response("你好，我在。")

        self.assertTrue(result.startswith("# ✅ 回复"))
        self.assertIn("## 🔍 结果", result)
        self.assertIn("你好，我在。", result)

    def test_weather_multi_day_result_uses_table_and_bold_values(self):
        result = format_weather_result(
            "汕头未来2天天气预报\n"
            "2026-06-05：最高 35.1°C，最低 26.3°C，降雨概率 70%\n"
            "2026-06-06：最高 30.5°C，最低 26.0°C，降雨概率 55%"
        )

        self.assertTrue(result.startswith("# 🔍 汕头未来2天天气预报"))
        self.assertIn("## 📊 天气明细", result)
        self.assertIn("| 日期 | 最高温 | 最低温 | 降雨概率 |", result)
        self.assertIn("| 2026-06-05 | **35.1°C** | **26.3°C** | **70%** |", result)
        self.assertIn("## ✅ 关键结论", result)

    def test_order_result_uses_required_sections_and_table(self):
        result = format_order_result(
            {
                "items": [{"name": "积木A", "quantity": "2件", "unit_price": "64", "subtotal": "128"}],
                "total": "¥128",
            }
        )

        self.assertIn("# 🛒 订单计算结果", result)
        self.assertIn("## 📊 订单明细", result)
        self.assertIn("| 商品 | 数量 | 单价 | 小计 |", result)
        self.assertIn("**积木A**", result)
        self.assertIn("应收金额：**¥128**", result)

    def test_inventory_result_uses_required_sections_and_table(self):
        result = format_inventory({"items": [{"name": "积木A", "stock": "2件", "status": "偏低"}]})

        self.assertIn("# 📦 库存查询结果", result)
        self.assertIn("| 商品 | 库存 | 状态 |", result)
        self.assertIn("**积木A**", result)
        self.assertIn("**2件**", result)

    def test_error_has_failure_structure(self):
        result = format_error("未知工具：local.demo")

        self.assertIn("# ❌ 执行失败", result)
        self.assertIn("## ⚠️ 失败原因", result)
        self.assertIn("没有成功", result)
        self.assertIn("**未知工具：local.demo**", result)

    def test_structured_skill_result_uses_generic_table_formatter(self):
        result = format_skill_result(
            {
                "ok": True,
                "kind": "market_quote",
                "title": "证券行情查询结果",
                "columns": ["标的名称", "代码", "最新价"],
                "rows": [["香农芯创", "300475", "171.9"]],
                "summary": {"标的名称": "香农芯创", "代码": "300475", "最新价": "171.9"},
            }
        )

        self.assertIn("# 🔍 证券行情查询结果", result)
        self.assertIn("| 标的名称 | 代码 | 最新价 |", result)
        self.assertIn("| **香农芯创** | **300475** | 171.9 |", result)
        self.assertIn("标的名称：**香农芯创**", result)

    def test_successful_structured_result_is_not_failed_by_text_markers(self):
        result = format_skill_result(
            {
                "ok": True,
                "kind": "web_search",
                "title": "网页搜索结果",
                "columns": ["标题", "摘要"],
                "rows": [["榴莲仅退款新进展", "复议失败后平台退回货款"]],
                "summary": {"涉事买家地区": "山东德州庆云县"},
            }
        )

        self.assertIn("# 🔍 网页搜索结果", result)
        self.assertNotIn("# ❌ 执行失败", result)


if __name__ == "__main__":
    unittest.main()
