import unittest

from core.ui_interactions import build_chat_interaction


class ChatInteractionsTest(unittest.TestCase):
    def test_reference_product_match_builds_confirmation_interaction(self):
        payload = {
            "ok": True,
            "kind": "reference_product_match",
            "match_id": "match-1",
            "data": {
                "capture_id": "capture-1",
                "source_url": "https://detail.1688.com/offer/1.html",
                "title": "磁性棋盘",
                "matches": [
                    {
                        "source_sku_id": "1688-BLUE",
                        "sku": "QQL701A-BLUE",
                        "sku_name": "磁性棋盘 蓝色",
                        "image_url": "https://img.example/blue.jpg",
                        "best_candidate": {
                            "record_id": "record-1",
                            "business_key": "QQL701A-BLUE",
                            "title": "磁性棋盘蓝色",
                            "confidence": 0.95,
                        },
                        "candidates": [
                            {
                                "record_id": "record-1",
                                "business_key": "QQL701A-BLUE",
                                "title": "磁性棋盘蓝色",
                                "confidence": 0.95,
                                "reason": "SKU/名称精确匹配",
                            }
                        ],
                    }
                ],
            },
        }

        interaction = build_chat_interaction("official.reference_product", payload)

        self.assertEqual(interaction["kind"], "reference_product_match_review")
        self.assertEqual(interaction["endpoint"], "/reference-products/confirm-bind")
        self.assertEqual(interaction["items"][0]["selected_candidate_id"], "record-1")
        self.assertEqual(interaction["items"][0]["candidates"][0]["business_key"], "QQL701A-BLUE")

    def test_excel_preview_builds_review_interaction(self):
        payload = {
            "ok": True,
            "kind": "excel_preview",
            "data": {
                "file_name": "quote.xlsx",
                "saved_path": "D:/YoubestarLocal/uploads/quote.xlsx",
                "standard_fields": [{"code": "product_code", "label": "商品编码"}],
                "table_categories": [{"code": "quote", "label": "报价表"}],
                "classification_summary": {"needs_confirmation": True},
                "sheets": [
                    {
                        "name": "报价表",
                        "header_row": 2,
                        "headers": ["货号", "品名"],
                        "classification": {
                            "status": "partial",
                            "category": "quote",
                            "category_label": "报价表",
                            "confidence": 0.68,
                            "needs_confirmation": True,
                            "field_mappings": [
                                {
                                    "source_header": "货号",
                                    "standard_field": "product_code",
                                    "standard_label": "商品编码",
                                    "status": "mapped",
                                }
                            ],
                        },
                    }
                ],
            },
        }

        interaction = build_chat_interaction("official.preview_excel", payload)

        self.assertEqual(interaction["kind"], "excel_preview_review")
        self.assertEqual(interaction["endpoint"], "/files/excel/feedback")
        self.assertEqual(interaction["sheets"][0]["name"], "报价表")
        self.assertEqual(interaction["standard_fields"][0]["code"], "product_code")


if __name__ == "__main__":
    unittest.main()
