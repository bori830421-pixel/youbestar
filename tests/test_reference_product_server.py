import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import server


class ReferenceProductServerTest(unittest.TestCase):
    def test_reference_product_endpoints_route_to_expected_operations(self):
        calls = []

        def fake_run(params):
            calls.append(dict(params))
            operation = params["operation"]
            return {
                "ok": True,
                "kind": f"reference_product_{operation}",
                "title": "参考产品操作结果",
                "data": {"operation": operation},
                "summary": {"operation": operation},
            }

        client = TestClient(server.app)
        with patch.object(server, "run_reference_product", side_effect=fake_run, create=True):
            responses = [
                client.post("/reference-products/capture", json={"url": "https://detail.1688.com/offer/772233445566.html"}),
                client.post("/reference-products/match", json={"skus": [{"sku": "QQL701A-BLUE"}]}),
                client.post(
                    "/reference-products/confirm-bind",
                    json={
                        "record_id": "product-1",
                        "sku": "QQL701A-BLUE",
                        "image_url": "https://cbu01.alicdn.com/img/ibank/O1CN01blue.jpg",
                        "confirmed": True,
                    },
                ),
                client.post("/reference-products/export-excel", json={"margin_rate": 0.15, "skus": []}),
                client.get("/reference-products/cache-status"),
                client.post("/reference-products/cleanup-cache", json={"older_than_days": 7}),
            ]

        for response in responses:
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["ok"])

        self.assertEqual(
            [call["operation"] for call in calls],
            ["capture", "match", "confirm_bind", "export_excel", "cache_status", "cleanup_cache"],
        )
        self.assertEqual(calls[0]["url"], "https://detail.1688.com/offer/772233445566.html")
        self.assertIs(calls[2]["confirmed"], True)
        self.assertEqual(calls[5]["older_than_days"], 7)


if __name__ == "__main__":
    unittest.main()
