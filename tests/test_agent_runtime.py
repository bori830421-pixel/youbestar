import unittest
from unittest.mock import patch

from core.agent_nodes import build_synthesis_prompt, run_action
from core.agent_state import AgentState
from core.agent_checkpoint import InMemoryCheckpoint
from core.agent_runtime import AgentRuntime
from memory.memory import Memory


class FakeLLM:
    def __init__(self, response: str):
        self.responses = [response] if isinstance(response, str) else list(response)
        self.prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


class NoCallLLM:
    prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        raise AssertionError("local tool fast path should not call the LLM")


class AgentRuntimeTest(unittest.TestCase):
    def assertDefaultRuntimeNodes(self, result):
        self.assertEqual(
            result.runtime_nodes,
            [
                "direct_chat",
                "local_tool_intent",
                "understand",
                "prepare",
                "rewrite_query",
                "execute",
                "search_retry",
                "reflect",
                "synthesize",
                "answer_check",
                "finalize",
            ],
        )

    def test_runtime_runs_natural_chat_through_owned_nodes(self):
        runtime = AgentRuntime()
        memory = Memory()
        llm = FakeLLM(
            [
                '{"task_type":"chat","subject":"","sub_questions":[],"constraints":[],"needs_fresh_info":false,"expected_output":"自然回复","query_hints":[]}',
                "Thought: 用户只是问候。\n"
                "Action: none\n"
                "Params: {}\n"
                "Response: 你好，我在。",
            ]
        )

        result = runtime.run(llm, memory, "你好", allow_chat=True, thread_id="chat-1")

        self.assertIn("# ✅ 回复", result.reply)
        self.assertIn("你好，我在。", result.response)
        self.assertEqual(result.action, "none")
        self.assertDefaultRuntimeNodes(result)
        self.assertEqual(result.step_count, 11)
        self.assertIn("你好 -> none -> 无操作", memory.get_summary())

    def test_chat_only_mode_answers_directly_without_agent_tool_planning(self):
        runtime = AgentRuntime()
        memory = Memory()
        llm = FakeLLM("这是一段直接回答。")

        result = runtime.run(
            llm,
            memory,
            "解释一下什么是供应链",
            allow_chat=True,
            allow_tools=False,
            allow_skills=False,
            thread_id="chat-only",
        )

        self.assertEqual(len(llm.prompts), 1)
        self.assertNotIn("Action:", llm.prompts[0])
        self.assertEqual(result.action, "none")
        self.assertEqual(result.action_result, "无操作")
        self.assertIn("这是一段直接回答。", result.reply)
        self.assertEqual(result.runtime_nodes, ["direct_chat", "finalize"])

    @patch("core.agent_nodes.run_approved_skill", return_value="should not run")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_official_tool_is_blocked_when_tools_are_disabled(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="tool-disabled",
            user_input="深圳天气",
            action="official.query_weather",
            params={"city": "深圳", "days": 1},
            allow_tools=False,
            allow_skills=True,
        )

        result = run_action(state)

        self.assertEqual(result.observation, "工具调用未开启：official.query_weather")
        run_mock.assert_not_called()

    @patch("core.agent_nodes.run_approved_skill", return_value="should not run")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_local_skill_is_blocked_when_skills_are_disabled(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="skill-disabled",
            user_input="调用本地技能",
            action="local.parse_order",
            params={},
            allow_tools=True,
            allow_skills=False,
        )

        result = run_action(state)

        self.assertEqual(result.observation, "技能调用未开启：local.parse_order")
        run_mock.assert_not_called()

    @patch("core.agent_nodes.run_approved_skill", return_value="should not run")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_self_evolution_action_is_blocked_when_disabled(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="self-evolution-disabled",
            user_input="读取代码",
            action="official.read_file",
            params={"path": "server.py"},
            allow_tools=True,
            allow_skills=True,
            allow_self_evolution=False,
        )

        result = run_action(state)

        self.assertEqual(result.observation, "自我进化未开启：official.read_file")
        run_mock.assert_not_called()
        approved_mock.assert_not_called()
        enabled_mock.assert_not_called()

    @patch("core.agent_nodes.run_approved_skill", return_value="file content")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_self_evolution_action_runs_when_enabled(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="self-evolution-enabled",
            user_input="读取代码",
            action="official.read_file",
            params={"path": "server.py"},
            allow_tools=True,
            allow_skills=True,
            allow_self_evolution=True,
        )

        result = run_action(state)

        self.assertEqual(result.observation, "file content")
        run_mock.assert_called_once_with("official.read_file", {"path": "server.py"})
        approved_mock.assert_called_once_with("official.read_file")
        enabled_mock.assert_called_once_with("official.read_file")

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价", "涨跌幅"],
            "rows": [["贵州茅台", "600519", "1788.5", "2.5%"]],
            "summary": {"标的名称": "贵州茅台", "代码": "600519", "最新价": "1788.5", "涨跌幅": "2.5%"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_stock_query_uses_local_fast_path_without_llm(self, approved_mock, enabled_mock, run_mock):
        llm = NoCallLLM()

        result = AgentRuntime().run(llm, Memory(), "查一下贵州茅台", allow_chat=True, thread_id="fast-stock")

        self.assertEqual(llm.prompts, [])
        self.assertEqual(result.action, "official.query_market_data")
        self.assertEqual(result.params, {"symbol": "贵州茅台"})
        self.assertIn("贵州茅台", result.reply)
        run_mock.assert_called_once_with("official.query_market_data", {"symbol": "贵州茅台"})
        approved_mock.assert_called_once_with("official.query_market_data")
        enabled_mock.assert_called_once_with("official.query_market_data")

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "weather_current",
            "title": "天气查询结果",
            "columns": ["城市", "天气", "温度", "提醒"],
            "rows": [["北京", "晴", "32°C", ""]],
            "summary": {"城市": "北京", "天气": "晴", "温度": "32°C"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_weather_query_uses_local_fast_path_without_llm(self, approved_mock, enabled_mock, run_mock):
        llm = NoCallLLM()

        result = AgentRuntime().run(llm, Memory(), "北京今天的天气怎么样？", allow_chat=True, thread_id="fast-weather")

        self.assertEqual(llm.prompts, [])
        self.assertEqual(result.action, "official.query_weather")
        self.assertEqual(result.params, {"city": "北京", "days": 1})
        self.assertIn("北京", result.reply)
        run_mock.assert_called_once_with("official.query_weather", {"city": "北京", "days": 1})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "weather_forecast",
            "title": "天气查询结果",
            "content": "深圳未来3天天气预报",
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_weather_fast_path_extracts_requested_day_count(self, approved_mock, enabled_mock, run_mock):
        llm = NoCallLLM()

        result = AgentRuntime().run(llm, Memory(), "深圳未来三天天气", allow_chat=True, thread_id="fast-weather-3")

        self.assertEqual(llm.prompts, [])
        self.assertEqual(result.action, "official.query_weather")
        self.assertEqual(result.params, {"city": "深圳", "days": 3})
        run_mock.assert_called_once_with("official.query_weather", {"city": "深圳", "days": 3})

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价"],
            "rows": [["贵州茅台", "600519", "1788.5"]],
            "summary": {"标的名称": "贵州茅台", "代码": "600519", "最新价": "1788.5"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_stock_fast_path_strips_price_modifiers_from_name(self, approved_mock, enabled_mock, run_mock):
        llm = NoCallLLM()

        result = AgentRuntime().run(llm, Memory(), "贵州茅台最新股价", allow_chat=True, thread_id="fast-stock-name")

        self.assertEqual(llm.prompts, [])
        self.assertEqual(result.params, {"symbol": "贵州茅台"})
        run_mock.assert_called_once_with("official.query_market_data", {"symbol": "贵州茅台"})

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价"],
            "rows": [["中国太保", "601601", "31.88"]],
            "summary": {"标的名称": "中国太保", "代码": "601601", "最新价": "31.88"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_stock_fast_path_extracts_code_before_modifiers(self, approved_mock, enabled_mock, run_mock):
        llm = NoCallLLM()

        result = AgentRuntime().run(llm, Memory(), "601601最新收盘价", allow_chat=True, thread_id="fast-stock-code")

        self.assertEqual(llm.prompts, [])
        self.assertEqual(result.params, {"symbol": "601601"})
        run_mock.assert_called_once_with("official.query_market_data", {"symbol": "601601"})

    @patch("core.agent_nodes.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_executes_skill_and_reflects_result(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        memory = Memory()
        llm = FakeLLM(
            [
                '{"task_type":"tool_use","subject":"汕头天气","sub_questions":["汕头天气"],"constraints":[],"needs_fresh_info":true,"expected_output":"天气预报","query_hints":[]}',
                "Thought: 用户查询天气。\n"
                "Action: official.query_weather\n"
                'Params: {"city": "汕头", "days": 1}',
                '{"ok":true,"missing":[],"notes":"已覆盖天气查询"}',
            ]
        )

        result = runtime.run(llm, memory, "汕头天气", allow_chat=True, thread_id="weather-1")

        self.assertEqual(result.action, "official.query_weather")
        self.assertEqual(result.params, {"city": "汕头", "days": 1})
        self.assertEqual(result.action_result, "汕头未来1天天气预报")
        self.assertIn("# ✅ 查询结果", result.response)
        self.assertIn("汕头未来1天天气预报", result.reply)
        run_mock.assert_called_once_with("official.query_weather", {"city": "汕头", "days": 1})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    def test_runtime_reflects_unknown_tool_as_natural_failure(self):
        runtime = AgentRuntime()
        llm = FakeLLM(
            [
                '{"task_type":"tool_use","subject":"missing skill","sub_questions":["调用 missing skill"],"constraints":[],"needs_fresh_info":false,"expected_output":"","query_hints":[]}',
                "Thought: 用户调用一个不存在的技能。\n"
                "Action: local.missing_skill\n"
                "Params: {}",
                '{"ok":true,"missing":[],"notes":"已说明失败"}',
            ]
        )

        result = runtime.run(llm, Memory(), "调用 missing skill", allow_chat=True)

        self.assertEqual(result.action, "local.missing_skill")
        self.assertEqual(result.action_result, "未知工具：local.missing_skill")
        self.assertIn("没有成功", result.response)
        self.assertIn("没有成功", result.response)
        self.assertIn("未知工具：local.missing_skill", result.reply)

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价"],
            "rows": [["香农芯创", "300475", "171.9"]],
            "summary": {"标的名称": "香农芯创", "代码": "300475", "最新价": "171.9"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_formats_structured_skill_result_without_dict_repr(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        llm = FakeLLM(
            [
                '{"task_type":"tool_use","subject":"300475","sub_questions":["查询300475最新股价"],"constraints":[],"needs_fresh_info":true,"expected_output":"证券行情","query_hints":[]}',
                "Thought: 用户查询证券行情。\n"
                "Action: official.query_market_data\n"
                'Params: {"symbol": "300475"}',
                '{"ok":true,"missing":[],"notes":"已覆盖行情"}',
            ]
        )

        result = runtime.run(llm, Memory(), "查询300475最新股价", allow_chat=True)

        self.assertIn("# 🔍 证券行情查询结果", result.reply)
        self.assertIn("| **香农芯创** | **300475** | 171.9 |", result.reply)
        self.assertNotIn("{'ok': True", result.reply)
        self.assertIn("| 标的名称 | 代码 | 最新价 |", result.response)

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "market_quote",
            "title": "证券行情查询结果",
            "columns": ["标的名称", "代码", "最新价"],
            "rows": [["中国太保", "601601", "31.88"]],
            "summary": {"标的名称": "中国太保", "代码": "601601", "最新价": "31.88"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_does_not_block_first_direct_stock_tool_when_clock_expired(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="stock-timeout",
            user_input="601601最新收盘价",
            action="official.query_market_data",
            params={"symbol": "601601"},
            runtime_started_at=1,
            max_runtime_seconds=0,
        )

        result = run_action(state)

        self.assertEqual(result.observation["kind"], "market_quote")
        self.assertEqual(result.observation["rows"][0], ["中国太保", "601601", "31.88"])
        self.assertEqual(result.stop_reason, "")
        run_mock.assert_called_once_with("official.query_market_data", {"symbol": "601601"})
        approved_mock.assert_called_once_with("official.query_market_data")
        enabled_mock.assert_called_once_with("official.query_market_data")

    @patch("core.agent_nodes.run_approved_skill", return_value="汕头未来1天天气预报")
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_does_not_block_first_direct_weather_tool_when_clock_expired(self, approved_mock, enabled_mock, run_mock):
        state = AgentState(
            thread_id="weather-timeout",
            user_input="汕头天气",
            action="official.query_weather",
            params={"city": "汕头", "days": 1},
            runtime_started_at=1,
            max_runtime_seconds=0,
        )

        result = run_action(state)

        self.assertEqual(result.observation, "汕头未来1天天气预报")
        self.assertEqual(result.stop_reason, "")
        run_mock.assert_called_once_with("official.query_weather", {"city": "汕头", "days": 1})
        approved_mock.assert_called_once_with("official.query_weather")
        enabled_mock.assert_called_once_with("official.query_weather")

    def test_runtime_records_checkpoints_after_each_node(self):
        checkpoint = InMemoryCheckpoint()
        runtime = AgentRuntime(checkpoint=checkpoint)
        llm = FakeLLM(
            [
                '{"task_type":"chat","subject":"","sub_questions":[],"constraints":[],"needs_fresh_info":false,"expected_output":"自然回复","query_hints":[]}',
                "Thought: 用户只是问候。\n"
                "Action: none\n"
                "Params: {}\n"
                "Response: 你好。",
            ]
        )

        result = runtime.run(llm, Memory(), "你好", allow_chat=True, thread_id="checkpoint-thread")

        self.assertDefaultRuntimeNodes(result)
        self.assertEqual([record["node"] for record in checkpoint.records], result.runtime_nodes)
        self.assertEqual(checkpoint.records[0]["thread_id"], "checkpoint-thread")
        self.assertIn("你好。", checkpoint.records[-1]["state"]["reply"])

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "web_search",
            "title": "网页搜索结果",
            "columns": ["来源", "标题", "摘要", "链接"],
            "rows": [
                [
                    "搜狗",
                    "榴莲遭遇仅退款新进展",
                    "河南濮阳商家程大叔遭遇山东德州庆云县买家恶意仅退款。",
                    "https://example.com/news",
                ],
                ["必应", "榴莲仅退款地区", "买家来自山东德州庆云县。", "https://example.com/2"],
                ["腾讯新闻", "榴莲仅退款进展", "商家所在地为河南濮阳。", "https://example.com/3"],
            ],
            "summary": {
                "查询关键词": "榴莲仅退款 是哪个地区",
                "涉事买家地区": "山东德州庆云县",
                "商家所在地": "河南濮阳",
            },
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_synthesizes_web_query_results(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        llm = FakeLLM(
            [
                '{"task_type":"web_research","subject":"榴莲仅退款","sub_questions":["榴莲仅退款是哪个地区"],"constraints":["需要最新信息"],"needs_fresh_info":true,"expected_output":"结论和地区角色","query_hints":["榴莲仅退款 山东德州庆云县","榴莲仅退款 河南濮阳"]}',
                "Thought: 用户要查询热点事件地区。\n"
                "Action: official.web_query\n"
                'Params: {"query": "榴莲仅退款 是哪个地区", "limit": 5}',
                "结论：这次榴莲仅退款事件中，涉事买家地区是山东德州庆云县，商家所在地是河南濮阳。",
                '{"ok":true,"missing":[],"notes":"已覆盖地区角色"}',
            ]
        )

        result = runtime.run(llm, Memory(), "搜索榴莲仅退款，查询是哪个地区的榴莲仅退款", allow_chat=True)

        self.assertEqual(result.action, "official.web_query")
        self.assertIn("结论：这次榴莲仅退款事件中", result.reply)
        self.assertIn("山东德州庆云县", result.reply)
        self.assertIn("河南濮阳", result.reply)
        self.assertNotIn("## 📊 数据明细", result.reply)
        self.assertNotIn("{'ok': True", result.reply)
        self.assertIn("搜索技能返回的结构化资料", llm.prompts[2])
        run_mock.assert_called_once_with(
            "official.web_query",
            {
                "query": "榴莲仅退款 是哪个地区",
                "query_candidates": [
                    "榴莲仅退款 是哪个地区",
                    "榴莲仅退款 山东德州庆云县",
                    "榴莲仅退款 河南濮阳",
                    "榴莲仅退款 地区 榴莲仅退款是哪个地区",
                    "榴莲仅退款 latest model",
                ],
                "limit": 5,
            },
        )

    def test_synthesis_prompt_requires_answering_all_sub_questions(self):
        state = AgentState(
            thread_id="default",
            user_input="gnes 是什么？他的官方网址是",
            action="official.web_query",
            observation={
                "ok": True,
                "kind": "web_search",
                "title": "网页搜索结果",
                "columns": ["来源", "标题", "摘要", "链接"],
                "rows": [["搜狗", "Agnes AI", "Agnes AI 是多模态模型实验室，官网 agnes-ai.com", "https://agnes-ai.com/"]],
                "summary": {"查询关键词": "gnes 是什么 官方网址"},
            },
        )

        prompt = build_synthesis_prompt(state)

        self.assertIn("必须覆盖的回答点", prompt)
        self.assertIn("- 是什么", prompt)
        self.assertIn("- 官方网址", prompt)
        self.assertIn("如果用户一次问了多个问题，必须逐项回答", prompt)

    @patch(
        "core.agent_nodes.run_approved_skill",
        return_value={
            "ok": True,
            "kind": "web_search",
            "title": "网页搜索结果",
            "columns": ["来源", "标题", "摘要", "链接"],
            "rows": [
                ["搜狗", "Agnes AI", "Agnes AI 是多模态模型实验室，官网 agnes-ai.com", "https://agnes-ai.com/"],
                ["必应", "Agnes AI official", "Agnes AI official website", "https://agnes-ai.com/"],
                ["官网", "Agnes AI", "Official site", "https://agnes-ai.com/"],
            ],
            "summary": {"查询关键词": "gnes 是什么 官方网址"},
        },
    )
    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_runtime_understands_rewrites_and_checks_multi_question_search(self, approved_mock, enabled_mock, run_mock):
        runtime = AgentRuntime()
        llm = FakeLLM(
            [
                '{"task_type":"web_research","subject":"Agnes AI","sub_questions":["Agnes AI 是什么","Agnes AI 的官方网址是什么"],"constraints":["需要官网"],"needs_fresh_info":true,"expected_output":"逐项回答","query_hints":["Agnes AI 是什么","Agnes AI 官方网址"]}',
                "Thought: 用户询问需要搜索核验。\n"
                "Action: official.web_query\n"
                'Params: {"query": "gnes 是什么 官方网址", "limit": 5}',
                "结论：Agnes AI 是一个多模态 AI 项目；官方网址是 https://agnes-ai.com/。",
                '{"ok":true,"missing":[],"notes":"两个子问题都已覆盖"}',
            ]
        )

        result = runtime.run(llm, Memory(), "gnes 是什么？他的官方网址是", allow_chat=True)

        self.assertEqual(result.intent["subject"], "Agnes AI")
        self.assertEqual(result.answer_check["ok"], True)
        self.assertIn("Agnes AI 是一个多模态 AI 项目", result.reply)
        self.assertIn("https://agnes-ai.com/", result.reply)
        run_mock.assert_called_once_with(
            "official.web_query",
            {
                "query": "gnes 是什么 官方网址",
                "query_candidates": [
                    "gnes 是什么 官方网址",
                    "Agnes AI 是什么",
                    "Agnes AI 官方网址",
                    "Agnes AI 是什么 官方网址 Agnes AI 是什么 Agnes AI 的官方网址是什么",
                    "Agnes AI latest model",
                ],
                "limit": 5,
            },
        )

    def test_answer_check_appends_missing_answer_points(self):
        runtime = AgentRuntime()
        llm = FakeLLM(
            [
                '{"task_type":"chat","subject":"Agnes AI","sub_questions":["Agnes AI 是什么","Agnes AI 的官方网址是什么"],"constraints":[],"needs_fresh_info":false,"expected_output":"逐项回答","query_hints":[]}',
                "Thought: 已有足够上下文。\n"
                "Action: none\n"
                "Params: {}\n"
                "Response: Agnes AI 是一个多模态 AI 项目。",
                '{"ok":false,"missing":["官方网址"],"notes":"回答缺少官网"}',
            ]
        )

        result = runtime.run(llm, Memory(), "Agnes 是什么？官网是", allow_chat=True)

        self.assertIn("Agnes AI 是一个多模态 AI 项目", result.reply)
        self.assertIn("补充说明", result.reply)
        self.assertIn("官方网址", result.reply)

    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_web_query_retries_once_when_results_are_too_few(self, approved_mock, enabled_mock):
        first_result = {
            "ok": True,
            "kind": "web_search",
            "title": "网页搜索结果",
            "columns": ["来源", "标题", "摘要", "链接"],
            "rows": [["官网", "Tesla 官网", "Tesla 官方网站", "https://www.tesla.com/"]],
            "summary": {"查询关键词": "Tesla 最新车型"},
        }
        second_result = {
            "ok": True,
            "kind": "web_search",
            "title": "网页搜索结果",
            "columns": ["来源", "标题", "摘要", "链接"],
            "rows": [
                ["官网", "Tesla Model Y", "Tesla new Model Y", "https://www.tesla.com/modely"],
                ["必应", "Tesla Model Y Juniper", "发布时间信息", "https://example.com/1"],
                ["搜狗", "Tesla latest model", "官网链接", "https://example.com/2"],
            ],
            "summary": {"查询关键词": "Tesla latest model"},
        }
        llm = FakeLLM(
            [
                '{"task_type":"web_research","subject":"Tesla","sub_questions":["Tesla最新车型名称","Tesla发布时间","Tesla官网链接"],"constraints":["需要最新信息"],"needs_fresh_info":true,"expected_output":"逐项回答","query_hints":["Tesla latest model","Tesla Model Y Juniper","Tesla new Model Y","Tesla official"]}',
                "Thought: 用户需要搜索最新车型信息。\n"
                "Action: official.web_query\n"
                'Params: {"query": "Tesla 最新车型", "limit": 5}',
                "结论：Tesla 最新车型相关结果包括 Model Y Juniper，官网链接见 Tesla 官网。",
                '{"ok":true,"missing":[],"notes":"已覆盖"}',
            ]
        )

        with patch("core.agent_nodes.run_approved_skill", side_effect=[first_result, second_result]) as run_mock:
            result = AgentRuntime().run(llm, Memory(), "告诉我 Tesla 最新车型的名字、发布时间和官网链接")

        self.assertEqual(result.action, "official.web_query")
        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(result.params["query"], "Tesla latest model")
        self.assertEqual(result.stop_reason, "")
        self.assertIn("Model Y Juniper", result.reply)

    @patch("core.agent_nodes.is_skill_enabled", return_value=True)
    @patch("core.agent_nodes.is_approved_skill", return_value=True)
    def test_web_query_stops_after_two_search_rounds(self, approved_mock, enabled_mock):
        sparse_result = {
            "ok": True,
            "kind": "web_search",
            "title": "网页搜索结果",
            "columns": ["来源", "标题", "摘要", "链接"],
            "rows": [["官网", "Tesla 官网", "Tesla 官方网站", "https://www.tesla.com/"]],
            "summary": {"查询关键词": "Tesla 最新车型"},
        }
        llm = FakeLLM(
            [
                '{"task_type":"web_research","subject":"Tesla","sub_questions":["Tesla最新车型名称","Tesla发布时间","Tesla官网链接"],"constraints":["需要最新信息"],"needs_fresh_info":true,"expected_output":"逐项回答","query_hints":["Tesla latest model","Tesla Model Y Juniper"]}',
                "Thought: 用户需要搜索最新车型信息。\n"
                "Action: official.web_query\n"
                'Params: {"query": "Tesla 最新车型", "limit": 5}',
                "只能确认 Tesla 官网，车型名称和发布时间仍需人工确认。",
                '{"ok":false,"missing":["车型名称","发布时间"],"notes":"部分缺失"}',
            ]
        )

        with patch("core.agent_nodes.run_approved_skill", side_effect=[sparse_result, sparse_result]) as run_mock:
            result = AgentRuntime().run(llm, Memory(), "告诉我 Tesla 最新车型的名字、发布时间和官网链接")

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(result.stop_reason, "search_limit_reached")
        self.assertIn("部分查询结果", result.action_result)


if __name__ == "__main__":
    unittest.main()
