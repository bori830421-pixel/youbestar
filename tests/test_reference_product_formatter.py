import unittest

from core.ui_formatter import format_skill_result


class ReferenceProductFormatterTest(unittest.TestCase):
    def test_reference_product_structured_results_use_generic_table_formatter(self):
        image = "![SKU图](https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg)"
        result = format_skill_result(
            {
                "ok": True,
                "kind": "reference_product_match",
                "title": "参考产品匹配结果",
                "columns": ["参考SKU", "候选SKU", "SKU图", "匹配分"],
                "rows": [["QQL701A-BLUE", "QQL701A-BLUE", image, "0.98"]],
                "summary": {
                    "参考SKU": "QQL701A-BLUE",
                    "候选SKU": "QQL701A-BLUE",
                    "绑定状态": "待确认",
                    "SKU图": image,
                },
            }
        )

        self.assertIn("# 🔍 参考产品匹配结果", result)
        self.assertIn("| 参考SKU | 候选SKU | SKU图 | 匹配分 |", result)
        self.assertIn("| **QQL701A-BLUE** | **QQL701A-BLUE** | ![SKU图](https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg) | 0.98 |", result)
        self.assertIn("绑定状态：**待确认**", result)
        self.assertIn(f"SKU图：{image}", result)
        self.assertNotIn(f"**{image}**", result)


if __name__ == "__main__":
    unittest.main()
