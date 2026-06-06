import unittest

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


if __name__ == "__main__":
    unittest.main()
