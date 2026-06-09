import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_system.manager import run_approved_skill
from agent_system.skills.official import business_records
from agent_system.skill_registry import canonical_skill_name
from tools.business_records_tool import run


class BusinessRecordsToolTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.local_home = Path(self.temp_dir.name) / "YoubestarLocal"
        self.local_home_patch = patch.dict(os.environ, {"YOUBESTAR_LOCAL_HOME": str(self.local_home)})
        self.local_home_patch.start()

    def tearDown(self):
        self.local_home_patch.stop()
        self.temp_dir.cleanup()

    def test_list_types_returns_supported_business_record_types(self):
        result = run({"operation": "list_types"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "business_record_types")
        record_types = {item["record_type"] for item in result["data"]["record_types"]}
        self.assertGreaterEqual(
            record_types,
            {
                "customer",
                "product",
                "order",
                "quote",
                "inventory",
                "purchase",
                "finance",
                "logistics",
            },
        )

    def test_upsert_creates_local_database_and_audit_log(self):
        result = run(
            {
                "operation": "upsert",
                "record_type": "customer",
                "fields": {
                    "customer_id": "C-001",
                    "name": "汕头星河贸易",
                    "contact": "陈小姐",
                    "phone": "13500000000",
                },
                "actor": "employee-a",
                "source_ip": "127.0.0.1",
                "source": "unit-test",
            }
        )

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "business_record_upsert")
        self.assertEqual(result["summary"]["动作"], "新增")
        self.assertEqual(result["summary"]["业务键"], "C-001")
        self.assertEqual(result["data"]["record"]["updated_by"], "employee-a")
        self.assertEqual(result["data"]["record"]["source_ip"], "127.0.0.1")
        self.assertTrue((self.local_home / "data" / "business_records.sqlite3").exists())

        audit_path = self.local_home / "logs" / "business_records_changes.jsonl"
        self.assertTrue(audit_path.exists())
        audit_entry = json.loads(audit_path.read_text(encoding="utf-8").strip())
        self.assertEqual(audit_entry["action"], "insert")
        self.assertEqual(audit_entry["actor"], "employee-a")
        self.assertEqual(audit_entry["source"], "unit-test")
        self.assertEqual(audit_entry["after"]["fields"]["name"], "汕头星河贸易")

    def test_upsert_updates_existing_record_and_query_returns_structured_rows(self):
        run(
            {
                "operation": "upsert",
                "record_type": "product",
                "fields": {"sku": "SKU-100", "name": "磁性棋盘", "category": "桌游"},
                "actor": "employee-a",
                "source": "first-import",
            }
        )
        update = run(
            {
                "operation": "upsert",
                "record_type": "product",
                "fields": {"sku": "SKU-100", "name": "磁性棋盘升级版", "spec": "29*29cm"},
                "actor": "employee-b",
                "source": "manual-edit",
            }
        )
        query = run({"operation": "query", "record_type": "product", "query": "升级版"})

        self.assertIs(update["ok"], True)
        self.assertEqual(update["summary"]["动作"], "更新")
        self.assertIn("name", update["data"]["record"]["changed_fields"])
        self.assertEqual(query["kind"], "business_records_query")
        self.assertEqual(query["summary"]["匹配数量"], 1)
        self.assertEqual(query["columns"], ["类型", "业务键", "SKU", "产品名称", "品类", "更新时间"])
        self.assertEqual(query["rows"][0][1], "SKU-100")
        self.assertEqual(query["rows"][0][3], "磁性棋盘升级版")
        self.assertEqual(query["data"]["records"][0]["fields"]["category"], "桌游")

        audit_lines = (self.local_home / "logs" / "business_records_changes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(audit_lines), 2)
        self.assertEqual(json.loads(audit_lines[-1])["action"], "update")

    def test_query_can_filter_by_business_key_and_field_values(self):
        run(
            {
                "operation": "upsert",
                "record_type": "inventory",
                "fields": {"sku": "SKU-200", "warehouse": "A仓", "quantity": 36},
            }
        )
        run(
            {
                "operation": "upsert",
                "record_type": "inventory",
                "fields": {"sku": "SKU-201", "warehouse": "B仓", "quantity": 12},
            }
        )

        by_key = run({"operation": "query", "record_type": "inventory", "business_key": "SKU-200"})
        by_filter = run({"operation": "query", "record_type": "inventory", "filters": {"warehouse": "B仓"}})

        self.assertEqual(by_key["summary"]["匹配数量"], 1)
        self.assertEqual(by_key["data"]["records"][0]["fields"]["quantity"], 36)
        self.assertEqual(by_filter["summary"]["匹配数量"], 1)
        self.assertEqual(by_filter["data"]["records"][0]["business_key"], "SKU-201")

    def test_excel_table_record_type_can_archive_confirmed_mapping(self):
        result = run(
            {
                "operation": "upsert",
                "record_type": "excel_table",
                "business_key": "excel:中意吉贵:Sheet1",
                "title": "中意（吉贵）棋报价总1.xlsx / Sheet1",
                "source": "official.preview_excel",
                "tags": ["Excel", "字段映射已确认"],
                "fields": {
                    "file_name": "中意（吉贵）棋报价总1.xlsx",
                    "source_path": r"D:\工厂资料\中意（吉贵）棋报价总1.xlsx",
                    "sheet_name": "Sheet1",
                    "category": "quote",
                    "category_label": "报价表",
                    "row_count": 121,
                    "column_count": 16,
                    "mapping_status": "confirmed",
                    "field_mappings": {
                        "品牌价": "cost_unit_price",
                        "毛/净重(KG)": "weight_text",
                    },
                    "confirmed_by": "operator",
                },
            }
        )
        query = run({"operation": "query", "record_type": "excel_table", "query": "吉贵"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["summary"]["类型"], "Excel 表格归档")
        self.assertEqual(result["summary"]["业务键"], "excel:中意吉贵:Sheet1")
        self.assertEqual(query["summary"]["匹配数量"], 1)
        self.assertEqual(query["columns"], ["类型", "业务键", "文件名", "工作表", "分类", "行数", "更新时间"])
        self.assertEqual(query["rows"][0][2], "中意（吉贵）棋报价总1.xlsx")
        self.assertEqual(query["data"]["records"][0]["fields"]["mapping_status"], "confirmed")

    def test_existing_database_missing_content_columns_is_migrated(self):
        db_path = self.local_home / "data" / "business_records.sqlite3"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                CREATE TABLE business_records (
                    id TEXT PRIMARY KEY,
                    record_type TEXT NOT NULL,
                    business_key TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                "INSERT INTO business_records (id, record_type, business_key) VALUES (?, ?, ?)",
                ("legacy-1", "general", "旧资料"),
            )
            connection.commit()
        finally:
            connection.close()

        result = run({"operation": "query", "query": "旧资料"})

        self.assertIs(result["ok"], True)
        self.assertEqual(result["summary"]["匹配数量"], 1)
        self.assertEqual(result["data"]["records"][0]["business_key"], "旧资料")

    def test_schema_file_can_extend_record_type(self):
        schema_path = self.local_home / "config" / "business_records_schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(
            json.dumps(
                {
                    "record_types": {
                        "asset": {
                            "label": "固定资产",
                            "key_fields": ["asset_no"],
                            "columns": ["record_type", "business_key", "asset_no", "name", "owner", "updated_at"],
                            "fields": {"asset_no": "资产编号", "name": "资产名称", "owner": "负责人"},
                        }
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        saved = run(
            {
                "operation": "upsert",
                "record_type": "asset",
                "fields": {"asset_no": "A-001", "name": "样品展示柜", "owner": "行政"},
            }
        )
        queried = run({"operation": "query", "record_type": "asset", "query": "展示柜"})

        self.assertIs(saved["ok"], True)
        self.assertEqual(queried["columns"], ["类型", "业务键", "资产编号", "资产名称", "负责人", "更新时间"])
        self.assertEqual(queried["rows"][0][2], "A-001")

    def test_official_skill_wrapper_returns_structured_result(self):
        result = business_records.run(
            {
                "operation": "upsert",
                "record_type": "order",
                "fields": {"order_no": "SO-001", "customer_name": "汕头星河贸易", "amount": 1999},
                "actor": "employee-a",
            }
        )

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "business_record_upsert")
        self.assertEqual(result["data"]["record"]["business_key"], "SO-001")

    def test_registered_official_skill_runs(self):
        result = run_approved_skill(
            "official.business_records",
            {
                "operation": "upsert",
                "record_type": "quote",
                "fields": {"quote_no": "QT-001", "customer_name": "汕头星河贸易", "sku": "SKU-100", "price": 18.5},
                "actor": "employee-a",
            },
        )

        self.assertIs(result["ok"], True)
        self.assertEqual(result["kind"], "business_record_upsert")
        self.assertEqual(result["summary"]["业务键"], "QT-001")
        self.assertEqual(canonical_skill_name("business_records"), "official.business_records")


if __name__ == "__main__":
    unittest.main()
