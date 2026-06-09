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

    def test_structured_result_can_include_markdown_image_cells(self):
        image = "![SKU图](https://example.com/p.jpg)"
        result = format_skill_result(
            {
                "ok": True,
                "kind": "factory_product_quote",
                "title": "工厂报价查询结果",
                "columns": ["SKU图", "货号"],
                "rows": [[image, "PD1102"]],
                "summary": {"货号": "PD1102", "SKU图": image},
            }
        )

        self.assertIn("| SKU图 | 货号 |", result)
        self.assertIn(image, result)
        self.assertNotIn(f"**{image}**", result)
        self.assertIn(f"SKU图：{image}", result)

    def test_excel_preview_formats_every_sheet(self):
        result = format_skill_result(
            {
                "ok": True,
                "kind": "excel_preview",
                "title": "Excel 读取预览",
                "data": {
                    "file_name": "quote.xlsx",
                    "saved_path": r"D:\YoubestarLocal\imports\quote.xlsx",
                    "sheets": [
                        {
                            "name": "报价表",
                            "header_row": 2,
                            "headers": ["货号", "品名"],
                            "rows": [["QQL701A", "大盒五子棋"]],
                            "preview_row_count": 1,
                            "total_rows": 21,
                            "total_columns": 2,
                            "classification": {
                                "status": "recognized",
                                "category": "quote",
                                "category_label": "报价表",
                                "confidence": 0.98,
                                "reasons": ["识别到报价表核心字段，分类证据较充分。"],
                                "field_mappings": [
                                    {
                                        "source_header": "货号",
                                        "standard_field": "product_code",
                                        "standard_label": "商品编码",
                                        "status": "mapped",
                                    },
                                    {
                                        "source_header": "品名",
                                        "standard_field": "product_name",
                                        "standard_label": "商品名称",
                                        "status": "mapped",
                                    },
                                ],
                                "change_proposals": [],
                            },
                        },
                        {
                            "name": "联系人",
                            "header_row": 1,
                            "headers": ["工厂", "业务员"],
                            "rows": [["潘多多", "潘小姐"]],
                            "preview_row_count": 1,
                            "total_rows": 2,
                            "total_columns": 2,
                            "classification": {
                                "status": "unknown",
                                "category": "",
                                "category_label": "未识别",
                                "confidence": 0,
                                "reasons": ["表头与现有字段目录匹配度较低。"],
                                "field_mappings": [
                                    {
                                        "source_header": "工厂",
                                        "standard_field": "supplier_name",
                                        "standard_label": "供应商名称",
                                        "status": "mapped",
                                    },
                                    {
                                        "source_header": "业务员",
                                        "standard_field": "salesperson_name",
                                        "standard_label": "业务员",
                                        "status": "mapped",
                                    },
                                ],
                                "change_proposals": [],
                            },
                        },
                    ],
                    "classification_summary": {
                        "status_counts": {"recognized": 1, "partial": 0, "ambiguous": 0, "unknown": 1},
                    },
                },
            }
        )

        self.assertIn("工作表：报价表", result)
        self.assertIn("工作表：联系人", result)
        self.assertIn("表格类型：**报价表**", result)
        self.assertIn("表格类型：**未识别**", result)
        self.assertIn("| 原始表头 | 标准字段 | 状态 |", result)
        self.assertIn("| 货号 | 商品编码 / product_code | 已映射 |", result)
        self.assertIn("| 货号 | 品名 |", result)
        self.assertIn("| QQL701A | 大盒五子棋 |", result)


if __name__ == "__main__":
    unittest.main()
