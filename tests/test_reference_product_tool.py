import importlib
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.business_records_db import BusinessRecordsDB


SOURCE_URL = "https://detail.1688.com/offer/772233445566.html"
BLUE_IMAGE_URL = "https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg"
GREEN_IMAGE_URL = "https://cbu01.alicdn.com/img/ibank/O1CN01green.jpg"

SAMPLE_1688_HTML = """
<!doctype html>
<html>
  <head><title>1688 sample</title></head>
  <body>
    <script id="__1688_REFERENCE_PRODUCT__" type="application/json">
      {
        "offerId": "772233445566",
        "subject": "磁性折叠棋盘套装",
        "shopName": "汕头源棋玩具厂",
        "images": ["https://cbu01.alicdn.com/img/ibank/O1CN01main.jpg"],
        "skuProps": [
          {
            "prop": "颜色",
            "values": [
              {"name": "蓝色", "imageUrl": "https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg"},
              {"name": "绿色", "imageUrl": "https://cbu01.alicdn.com/img/ibank/O1CN01green.jpg"}
            ]
          },
          {
            "prop": "规格",
            "values": [{"name": "29cm"}]
          }
        ],
        "skuMap": {
          "蓝色>29cm": {
            "skuId": "1688-BLUE-29",
            "skuCode": "QQL701A-BLUE",
            "price": "12.345",
            "stock": 88,
            "imageUrl": "https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg"
          },
          "绿色>29cm": {
            "skuId": "1688-GREEN-29",
            "skuCode": "QQL701A-GREEN",
            "price": "13",
            "stock": 36,
            "imageUrl": "https://cbu01.alicdn.com/img/ibank/O1CN01green.jpg"
          }
        }
      }
    </script>
  </body>
</html>
"""


def load_reference_product_tool():
    try:
        return importlib.import_module("tools.reference_product_tool")
    except ModuleNotFoundError as exc:  # pragma: no cover - intentional contract failure until implemented
        raise AssertionError("Expected tools/reference_product_tool.py with run(params).") from exc


class ReferenceProductToolTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.local_home = Path(self.temp_dir.name) / "YoubestarLocal"
        self.local_home_patch = patch.dict(os.environ, {"YOUBESTAR_LOCAL_HOME": str(self.local_home)})
        self.local_home_patch.start()

    def tearDown(self):
        self.local_home_patch.stop()
        self.temp_dir.cleanup()

    def db(self) -> BusinessRecordsDB:
        return BusinessRecordsDB()

    def seed_product(self, fields):
        return self.db().upsert_record("product", fields=fields, actor="unit-test", source="unit-test")

    def query_product(self, business_key):
        records = self.db().query_records(record_type="product", business_key=business_key, limit=1)
        self.assertEqual(len(records), 1)
        return records[0]

    def run_with_sample_fetch(self, params):
        tool = load_reference_product_tool()
        fetch_targets = []

        def fake_fetch_text(url, **kwargs):
            fetch_targets.append(url)
            self.assertEqual(url, SOURCE_URL)
            return SAMPLE_1688_HTML

        with ExitStack() as stack:
            if hasattr(tool, "fetch_text"):
                stack.enter_context(patch.object(tool, "fetch_text", side_effect=fake_fetch_text))
            stack.enter_context(patch("core.http_client.fetch_text", side_effect=fake_fetch_text))
            stack.enter_context(patch("core.http_client.fetch_bytes", side_effect=AssertionError("capture must not download images")))
            if hasattr(tool, "fetch_bytes"):
                stack.enter_context(patch.object(tool, "fetch_bytes", side_effect=AssertionError("capture must not download images")))
            stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("live network must not be used")))
            stack.enter_context(patch("requests.get", side_effect=AssertionError("live network must not be used")))
            result = tool.run(params)

        self.assertEqual(fetch_targets, [SOURCE_URL])
        return result

    def test_capture_parses_1688_like_skus_and_keeps_remote_image_urls(self):
        result = self.run_with_sample_fetch({"operation": "capture", "url": SOURCE_URL})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "reference_product_capture")
        self.assertEqual(result["data"]["source_url"], SOURCE_URL)
        self.assertEqual(result["data"]["offer_id"], "772233445566")
        self.assertEqual(result["data"]["title"], "磁性折叠棋盘套装")

        skus = result["data"]["skus"]
        self.assertEqual(len(skus), 2)
        blue = next(item for item in skus if item["source_sku_id"] == "1688-BLUE-29")
        self.assertEqual(blue["sku"], "QQL701A-BLUE")
        self.assertEqual(blue["sku_name"], "磁性折叠棋盘套装 蓝色 29cm")
        self.assertEqual(blue["props"], {"颜色": "蓝色", "规格": "29cm"})
        self.assertEqual(blue["image_url"], BLUE_IMAGE_URL)
        self.assertFalse(blue.get("local_image_path"), "capture should keep image URLs and not download image files")
        self.assertEqual(blue["cost_price"], 12.345)

    def test_match_returns_candidates_from_business_records_products(self):
        self.seed_product(
            {
                "sku": "QQL701A-BLUE",
                "name": "磁性折叠棋盘套装 蓝色",
                "category": "桌游",
                "spec": "29cm",
            }
        )
        self.seed_product(
            {
                "sku": "UNRELATED-001",
                "name": "塑料收纳盒",
                "category": "收纳",
                "spec": "小号",
            }
        )
        tool = load_reference_product_tool()

        result = tool.run(
            {
                "operation": "match",
                "skus": [
                    {
                        "source_sku_id": "1688-BLUE-29",
                        "sku": "QQL701A-BLUE",
                        "sku_name": "磁性折叠棋盘套装 蓝色 29cm",
                        "props": {"颜色": "蓝色", "规格": "29cm"},
                        "image_url": BLUE_IMAGE_URL,
                    }
                ],
                "limit": 3,
            }
        )

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "reference_product_match")
        matches = result["data"]["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source_sku_id"], "1688-BLUE-29")
        candidates = matches[0]["candidates"]
        self.assertGreaterEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["business_key"], "QQL701A-BLUE")
        self.assertEqual(candidates[0]["fields"]["sku"], "QQL701A-BLUE")
        self.assertGreaterEqual(candidates[0]["score"], 0.9)

    def test_confirm_bind_updates_image_url_fields_only_after_confirmation(self):
        saved = self.seed_product(
            {
                "sku": "QQL701A-BLUE",
                "name": "磁性折叠棋盘套装 蓝色",
                "category": "桌游",
            }
        )
        tool = load_reference_product_tool()
        bind_params = {
            "operation": "confirm_bind",
            "record_id": saved["id"],
            "source_sku_id": "1688-BLUE-29",
            "sku": "QQL701A-BLUE",
            "image_url": BLUE_IMAGE_URL,
            "source_url": SOURCE_URL,
            "actor": "unit-test",
        }

        blocked = tool.run({**bind_params, "confirmed": False})
        self.assertIs(blocked["ok"], False)
        self.assertEqual(blocked["kind"], "reference_product_bind_confirmation_required")
        fields_before = self.query_product("QQL701A-BLUE")["fields"]
        self.assertNotIn("sku_image_url", fields_before)
        self.assertNotIn("reference_image_url", fields_before)

        confirmed = tool.run({**bind_params, "confirmed": True})

        self.assertIs(confirmed["ok"], True)
        self.assertEqual(confirmed["kind"], "reference_product_bind")
        fields_after = self.query_product("QQL701A-BLUE")["fields"]
        self.assertEqual(fields_after["sku_image_url"], BLUE_IMAGE_URL)
        self.assertEqual(fields_after["reference_image_url"], BLUE_IMAGE_URL)
        self.assertEqual(fields_after["reference_product_url"], SOURCE_URL)
        self.assertEqual(fields_after["reference_sku_id"], "1688-BLUE-29")

    def test_export_excel_applies_margin_and_rounds_customer_price_to_two_decimals(self):
        tool = load_reference_product_tool()
        output_path = self.local_home / "exports" / "reference-product-quote.xlsx"

        result = tool.run(
            {
                "operation": "export_excel",
                "customer_name": "汕头星河贸易",
                "margin_rate": 0.15,
                "output_path": str(output_path),
                "skus": [
                    {
                        "sku": "QQL701A-BLUE",
                        "sku_name": "磁性折叠棋盘套装 蓝色 29cm",
                        "cost_price": 12.345,
                        "image_url": BLUE_IMAGE_URL,
                    }
                ],
            }
        )

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "reference_product_export")
        self.assertEqual(result["data"]["items"][0]["cost_price"], 12.345)
        self.assertEqual(result["data"]["items"][0]["margin_rate"], 0.15)
        self.assertEqual(result["data"]["items"][0]["customer_price"], 14.2)
        self.assertEqual(result["data"]["items"][0]["customer_price_text"], "14.20")
        self.assertEqual(result["summary"]["客户报价"], "14.20")
        self.assertTrue(Path(result["data"]["output_path"]).exists())


if __name__ == "__main__":
    unittest.main()
