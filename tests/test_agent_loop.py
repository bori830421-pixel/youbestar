import unittest
from unittest.mock import patch

from core.loop import build_agent_prompt
from core.loop import agent_loop
from memory.memory import Memory


class AgentLoopTest(unittest.TestCase):
    def test_unregistered_action_is_reported_as_unknown_tool(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 测试未注册动作。\nAction: not_registered\nParams: {}"

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "测试")

        self.assertEqual(action, "local.not_registered")
        self.assertEqual(params, {})
        self.assertEqual(result, "未知工具：local.not_registered")
        self.assertEqual(response, "未知工具：local.not_registered")

    def test_prompt_disables_natural_chat_when_allow_chat_is_false(self):
        prompt = build_agent_prompt(Memory(), "你好", allow_chat=False)

        self.assertIn("当 allowChat=False 时", prompt)
        self.assertIn("你不能进行自然闲聊", prompt)
        self.assertIn("只能输出 Thought/Action/Params", prompt)
        self.assertNotIn("Response:", prompt.split("行为格式严格要求:", 1)[1])

    def test_prompt_describes_response_as_user_visible_natural_reply(self):
        prompt = build_agent_prompt(Memory(), "你好", allow_chat=True)

        self.assertIn("Response 是用户直接看到的最终回答", prompt)
        self.assertIn("自然、简洁、温暖", prompt)
        self.assertIn("不要提 Thought、Action、Params", prompt)

    def test_prompt_routes_weather_requests_to_weather_skill(self):
        prompt = build_agent_prompt(Memory(), "查询汕头天气", allow_chat=True)

        self.assertIn("official.query_weather", prompt)
        self.assertIn("查询天气、天气预报、气温、下雨情况", prompt)
        self.assertIn("Params 至少包含 city", prompt)
        self.assertIn("不要为天气查询调用浏览器、网页搜索", prompt)

    def test_prompt_routes_search_answer_requests_to_web_query(self):
        prompt = build_agent_prompt(Memory(), "榴莲仅退款是哪个地区的", allow_chat=True)

        self.assertIn("official.web_query", prompt)
        self.assertIn("联网搜索、查询某个事件是什么、哪个地区", prompt)
        self.assertIn("股票、天气、股市行情等已有本地函数工具", prompt)
        self.assertIn("如果用户最终目的明显是获取答案", prompt)

    def test_prompt_routes_factory_quote_requests_to_local_skill(self):
        prompt = build_agent_prompt(Memory(), "潘多多 QQL701A 产品尺寸和100个报价", allow_chat=True)

        self.assertIn("local.factory_quote", prompt)
        self.assertIn("工厂报价、货号资料、产品尺寸", prompt)
        self.assertIn("factory_name、sku、quantity", prompt)
        self.assertIn("operation 使用 bind_image", prompt)
        self.assertIn('默认图片绑定为 image_type="sku_image"', prompt)
        self.assertIn('实拍图/实拍照片', prompt)
        self.assertIn('image_type="real_photo"', prompt)
        self.assertIn("单品毛重/单品净重", prompt)
        self.assertIn("operation 使用 update_weight", prompt)
        self.assertIn("operation 使用 update_specs", prompt)
        self.assertIn("product_size_cm、package_size_cm", prompt)
        self.assertIn("业务员、业务联系人、业务电话、联系电话", prompt)
        self.assertIn("operation 使用 contact", prompt)
        self.assertIn("价格默认人民币元且展示两位小数", prompt)

    def test_prompt_routes_latest_model_news_to_web_query(self):
        prompt = build_agent_prompt(Memory(), "最新有什么新出来的大模型", allow_chat=True)

        self.assertIn("official.web_query", prompt)
        self.assertIn("最新热点、最近发布、新出来的大模型", prompt)
        self.assertIn("也必须使用 official.web_query", prompt)

    def test_prompt_allows_autonomous_local_skill_install(self):
        prompt = build_agent_prompt(Memory(), "帮我写一个订单解析技能", allow_chat=True)

        self.assertIn("official.install_local_skill", prompt)
        self.assertIn("直接写入 skills/local", prompt)
        self.assertIn("不需要人工审批", prompt)

    def test_prompt_routes_project_file_writes_to_write_project_file(self):
        prompt = build_agent_prompt(Memory(), "直接在运行目录里面写一个 notes.md", allow_chat=True)

        self.assertIn("allowSelfEvolution=False", prompt)
        self.assertIn("allowSelfEvolution=False 时，禁止选择", prompt)
        self.assertIn("official.write_project_file", prompt)
        self.assertIn("运行目录内的普通项目文件", prompt)
        self.assertIn("Params 包含 path、content", prompt)

    def test_prompt_allows_project_file_writes_when_self_evolution_is_enabled(self):
        prompt = build_agent_prompt(
            Memory(),
            "直接在运行目录里面写一个 notes.md",
            allow_chat=True,
            allow_self_evolution=True,
        )

        self.assertIn("allowSelfEvolution=True", prompt)
        self.assertIn("allowSelfEvolution=True 时，你可以读取白名单目录内的普通项目代码文件", prompt)

    def test_agent_loop_returns_response_only_when_chat_is_allowed(self):
        class FakeLLM:
            def chat(self, prompt):
                return "Thought: 用户问候。\nAction: none\nParams: {}\nResponse: 你好！"

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "你好", allow_chat=True)

        self.assertEqual(action, "none")
        self.assertEqual(params, {})
        self.assertEqual(result, "无操作")
        self.assertEqual(response, "你好！")

    @patch("core.loop.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.loop.is_skill_enabled", return_value=True)
    @patch("core.loop.is_approved_skill", return_value=True)
    def test_agent_loop_bridges_tool_result_to_user_response(self, approved_mock, enabled_mock, run_mock):
        class FakeLLM:
            def chat(self, prompt):
                return 'Thought: 用户查询天气。\nAction: official.query_weather\nParams: {"city": "汕头"}'

        _, _, action, params, result, response = agent_loop(FakeLLM(), Memory(), "汕头天气")

        self.assertEqual(action, "official.query_weather")
        self.assertEqual(params, {"city": "汕头"})
        self.assertEqual(result, "汕头未来1天天气预报")
        self.assertEqual(response, result)
        run_mock.assert_called_once_with("official.query_weather", {"city": "汕头"})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    @patch("core.loop.run_approved_skill", return_value="已写入项目文件")
    @patch("core.loop.is_skill_enabled", return_value=True)
    @patch("core.loop.is_approved_skill", return_value=True)
    def test_agent_loop_blocks_self_evolution_actions_when_disabled(self, approved_mock, enabled_mock, run_mock):
        class FakeLLM:
            def chat(self, prompt):
                return 'Thought: 修改项目。\nAction: official.write_project_file\nParams: {"path": "notes.md", "content": "hi"}'

        _, _, action, _, result, response = agent_loop(FakeLLM(), Memory(), "写 notes")

        self.assertEqual(action, "official.write_project_file")
        self.assertEqual(result, "自我进化未开启：official.write_project_file")
        self.assertEqual(response, result)
        run_mock.assert_not_called()
        approved_mock.assert_not_called()
        enabled_mock.assert_not_called()

    @patch("core.loop.run_approved_skill", return_value="已写入项目文件")
    @patch("core.loop.is_skill_enabled", return_value=True)
    @patch("core.loop.is_approved_skill", return_value=True)
    def test_agent_loop_allows_self_evolution_actions_when_enabled(self, approved_mock, enabled_mock, run_mock):
        class FakeLLM:
            def chat(self, prompt):
                return 'Thought: 修改项目。\nAction: official.write_project_file\nParams: {"path": "notes.md", "content": "hi"}'

        _, _, action, _, result, response = agent_loop(
            FakeLLM(),
            Memory(),
            "写 notes",
            allow_self_evolution=True,
        )

        self.assertEqual(action, "official.write_project_file")
        self.assertEqual(result, "已写入项目文件")
        self.assertEqual(response, result)
        run_mock.assert_called_once()
        approved_mock.assert_called_once_with("official.write_project_file")
        enabled_mock.assert_called_once_with("official.write_project_file")


if __name__ == "__main__":
    unittest.main()
