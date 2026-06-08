import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from core.loop import build_agent_prompt
from memory.memory import Memory


class MemoryManagementTest(unittest.TestCase):
    def test_short_term_memory_is_capped(self):
        memory = Memory(short_term_limit=3)

        for index in range(5):
            memory.add(f"用户消息{index}", "none", "无操作")

        self.assertEqual(len(memory.history), 3)
        self.assertEqual(memory.history[0]["user"], "用户消息2")
        self.assertEqual(memory.history[-1]["user"], "用户消息4")

    def test_non_business_memory_is_not_proposed_for_long_term(self):
        memory = Memory()

        result = memory.propose_long_term("用户喜欢闲聊", "chat")

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not_business_memory")
        self.assertEqual(memory.pending_candidates, [])
        self.assertEqual(memory.long_term, [])

    def test_business_memory_requires_confirmation_before_context_use(self):
        memory = Memory()

        proposal = memory.propose_long_term(
            "客户A购买 SKU-001 共 20 件",
            "order",
            module="private_sales",
            metadata={"customer": "客户A", "sku": "SKU-001", "quantity": 20},
        )

        self.assertTrue(proposal["ok"])
        self.assertEqual(len(memory.pending_candidates), 1)
        self.assertEqual(memory.get_model_context("private_sales")["long_term"], [])

        confirmed = memory.confirm_pending()

        self.assertTrue(confirmed["ok"])
        context = memory.get_model_context("private_sales")
        self.assertEqual(len(context["long_term"]), 1)
        self.assertEqual(context["long_term"][0]["content"], "客户A购买 SKU-001 共 20 件")

    def test_temporary_memory_is_excluded_from_model_context(self):
        memory = Memory()

        memory.add("帮我查天气", "official.query_weather", "天气结果")
        memory.add_temporary("用户随口说喜欢咖啡")

        context = memory.get_model_context()

        self.assertEqual(len(context["short_term"]), 1)
        self.assertNotIn("temporary", context)
        self.assertEqual(memory.temporary[0]["content"], "用户随口说喜欢咖啡")

    def test_long_term_memory_is_isolated_by_module(self):
        memory = Memory()

        memory.propose_long_term("ERP 入库单 A", "erp_order", module="erp_inbound")
        memory.confirm_pending()
        memory.propose_long_term("私域客户 B 购买 SKU-002", "order", module="private_sales")
        memory.confirm_pending()

        erp_context = memory.get_model_context("erp_inbound")
        sales_context = memory.get_model_context("private_sales")

        self.assertEqual(len(erp_context["long_term"]), 1)
        self.assertIn("ERP 入库单", erp_context["long_term"][0]["content"])
        self.assertEqual(len(sales_context["long_term"]), 1)
        self.assertIn("私域客户", sales_context["long_term"][0]["content"])

    def test_detects_business_memory_candidate_without_auto_confirming(self):
        memory = Memory()

        result = memory.detect_business_memory_candidate(
            "客户A 下单 SKU-001 共 20 件",
            action="local.parse_order",
            result="订单解析完成",
            module="private_sales",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "confirmation_required")
        self.assertEqual(result["candidate"]["sku"], "SKU-001")
        self.assertEqual(result["candidate"]["qty"], 20)
        self.assertEqual(len(memory.pending_candidates), 1)
        self.assertEqual(memory.get_model_context("private_sales")["long_term"], [])

    def test_factory_quote_lookup_does_not_create_memory_candidate(self):
        memory = Memory()

        result = memory.detect_business_memory_candidate(
            "潘多多 PD1102产品尺寸、装箱数、毛重是多少？100个按10%利润帮我算报价",
            action="local.factory_quote",
            result="货号：PD1102 数量：100 成本：15.225 报价总额：1674.75",
            module="general",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "query_result_not_memory")
        self.assertEqual(memory.pending_candidates, [])

    def test_quote_style_question_without_tool_action_does_not_create_memory_candidate(self):
        memory = Memory()

        result = memory.detect_business_memory_candidate(
            "PD1102 尺寸和100个报价是多少",
            action="none",
            result="",
            module="general",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "query_result_not_memory")
        self.assertEqual(memory.pending_candidates, [])

    def test_confirmed_memory_persists_to_json_file(self):
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "memory.json"
            memory = Memory(storage_path=storage_path)
            memory.propose_long_term(
                "客户张三 下单 SKU123 共 2 件",
                "order",
                module="private_sales",
                metadata={"entity": "客户张三", "sku": "SKU123", "qty": 2, "source": "微信消息"},
            )

            confirmed = memory.confirm_pending()
            reloaded = Memory(storage_path=storage_path)

            self.assertTrue(confirmed["ok"])
            self.assertTrue(storage_path.exists())
            context = reloaded.get_model_context("private_sales")
            self.assertEqual(len(context["long_term"]), 1)
            self.assertEqual(context["long_term"][0]["metadata"]["entity"], "客户张三")

    def test_confirmed_memory_is_compressed_by_entity_sku_quantity(self):
        memory = Memory()
        memory.propose_long_term(
            "张三 买 SKU123 2件",
            "order",
            module="private_sales",
            metadata={"entity": "张三", "sku": "SKU123", "qty": 2},
        )
        memory.confirm_pending()
        memory.propose_long_term(
            "张三 买 SKU123 3件",
            "order",
            module="private_sales",
            metadata={"entity": "张三", "sku": "SKU123", "qty": 3},
        )

        memory.confirm_pending()

        context = memory.get_model_context("private_sales")
        self.assertEqual(len(context["long_term"]), 1)
        self.assertEqual(context["long_term"][0]["metadata"]["qty"], 5)
        self.assertIn("共买 SKU123 5", context["long_term"][0]["content"])

    def test_agent_prompt_uses_confirmed_long_term_memory_only(self):
        memory = Memory()
        memory.propose_long_term(
            "客户张三 下单 SKU123 共 2 件",
            "order",
            module="private_sales",
            metadata={"entity": "客户张三", "sku": "SKU123", "qty": 2},
        )
        memory.confirm_pending()
        memory.propose_long_term("客户李四 下单 SKU999 共 1 件", "order", module="private_sales")

        prompt = build_agent_prompt(memory, "张三上次买了什么？")

        self.assertIn("已确认长期业务记忆", prompt)
        self.assertIn("客户张三 下单 SKU123 共 2 件", prompt)
        self.assertNotIn("客户李四 下单 SKU999", prompt)


if __name__ == "__main__":
    unittest.main()
