import unittest
from pathlib import Path


INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"


class ChatUiRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = INDEX_HTML.read_text(encoding="utf-8")

    def test_ui_routes_chat_only_through_owned_runtime(self):
        self.assertIn('const CHAT_URL = `${API_ORIGIN}/chat`;', self.html)
        self.assertIn("fetch(CHAT_URL", self.html)
        self.assertNotIn("LANGGRAPH_CHAT_URL", self.html)
        removed_route = "/lang" + "graph/chat"
        self.assertNotIn(removed_route, self.html)

    def test_ui_has_no_removed_graph_experiment_controls(self):
        removed_toggle = 'id="lang' + 'graph-toggle"'
        removed_title = "Lang" + "Graph nodes"
        removed_field = "graph" + "_nodes"
        self.assertNotIn(removed_toggle, self.html)
        self.assertNotIn(removed_title, self.html)
        self.assertNotIn(removed_field, self.html)

    def test_ui_tracks_and_persists_response_duration(self):
        self.assertIn("let activeResponseTimer = null;", self.html)
        self.assertIn("function formatResponseDuration(ms)", self.html)
        self.assertIn("function responseDurationLabel(message)", self.html)
        self.assertIn("模型思考中：", self.html)
        self.assertIn("模型用时：", self.html)
        self.assertIn("responseStartedAt = Date.now()", self.html)
        self.assertIn("responseDurationMs = Date.now() - responseStartedAt", self.html)
        self.assertIn("activeResponseTimer = setInterval", self.html)
        self.assertIn('className = "reply-timer"', self.html)

    def test_ui_can_upload_or_drop_excel_for_preview(self):
        self.assertIn('id="attachment-button"', self.html)
        self.assertIn('id="excel-file-input"', self.html)
        self.assertIn('accept=".xlsx,.xlsm,.xltx,.xltm"', self.html)
        self.assertIn("multiple hidden", self.html)
        self.assertIn('const EXCEL_PREVIEW_URL = `${API_ORIGIN}/files/excel/preview`;', self.html)
        self.assertIn("async function uploadExcelFile(file)", self.html)
        self.assertIn("function readDirectoryEntries(reader)", self.html)
        self.assertIn("async function readAllDirectoryEntries(reader)", self.html)
        self.assertIn("async function readExcelEntryFiles(entry", self.html)
        self.assertIn("async function readExcelEntriesFromDataTransfer(dataTransfer)", self.html)
        self.assertIn("webkitGetAsEntry", self.html)
        self.assertIn('messagesEl.addEventListener("drop"', self.html)
        self.assertIn("await readExcelEntriesFromDataTransfer(event.dataTransfer)", self.html)
        self.assertIn("renderExcelPreviewBubble", self.html)
        self.assertIn("function renderChatInteractions", self.html)
        self.assertIn("function buildExcelPreviewInteractionCard", self.html)
        self.assertIn('interaction.kind === "excel_preview_review"', self.html)
        self.assertIn("confirmExcelCategoryInteraction", self.html)
        self.assertIn("confirmExcelFieldMappingInteraction", self.html)
        self.assertIn("buildExcelClassificationBlock", self.html)
        self.assertIn("让智能体分类归档", self.html)
        self.assertIn("未识别的工作表要明确提示未识别，不要胡乱拼凑", self.html)
        self.assertIn("字段目录新增或修改必须先询问我确认", self.html)
        self.assertIn("仅已识别为报价表的 Excel 才适合写入报价资料库", self.html)
        self.assertIn('const EXCEL_FEEDBACK_URL = `${API_ORIGIN}/files/excel/feedback`;', self.html)
        self.assertIn("修正分类", self.html)
        self.assertIn("修正字段", self.html)
        self.assertIn("async function saveExcelFeedback", self.html)
        self.assertIn("重新上传或重新预览同类表头时会优先采用", self.html)
        self.assertIn("function excelPreviewContextText", self.html)
        self.assertIn("表头前几行", self.html)
        self.assertIn("function messageContentForHistory", self.html)
        self.assertIn("content: messageContentForHistory(item)", self.html)

    def test_ui_has_shared_business_records_panel(self):
        self.assertIn('id="nav-records-button"', self.html)
        self.assertIn('id="records-view"', self.html)
        self.assertIn("共享办公资料库", self.html)
        self.assertIn('id="record-types-list"', self.html)
        self.assertIn('id="records-query-form"', self.html)
        self.assertIn('id="records-upsert-form"', self.html)
        self.assertIn('id="records-table-body"', self.html)
        self.assertIn('const RECORD_TYPES_URL = `${API_ORIGIN}/business-records/types`;', self.html)
        self.assertIn('const RECORD_QUERY_URL = `${API_ORIGIN}/business-records/query`;', self.html)
        self.assertIn('const RECORD_UPSERT_URL = `${API_ORIGIN}/business-records/upsert`;', self.html)
        self.assertIn("function showRecordsView()", self.html)
        self.assertIn("async function loadRecordTypes()", self.html)
        self.assertIn("async function loadBusinessRecords()", self.html)
        self.assertIn("async function saveBusinessRecord()", self.html)
        self.assertIn('navRecordsButton.addEventListener("click", showRecordsView)', self.html)

    def test_ui_has_reference_product_panel(self):
        self.assertIn('id="nav-reference-button"', self.html)
        self.assertIn('id="reference-view"', self.html)
        self.assertIn("参考商品", self.html)
        self.assertIn('id="reference-url-input"', self.html)
        self.assertIn('id="reference-capture-button"', self.html)
        self.assertIn('id="reference-match-button"', self.html)
        self.assertIn('id="reference-confirm-button"', self.html)
        self.assertIn('id="reference-export-button"', self.html)
        self.assertIn('id="reference-cleanup-button"', self.html)
        self.assertIn('const REFERENCE_CAPTURE_URL = `${API_ORIGIN}/reference-products/capture`;', self.html)
        self.assertIn('const REFERENCE_MATCH_URL = `${API_ORIGIN}/reference-products/match`;', self.html)
        self.assertIn('const REFERENCE_CONFIRM_BIND_URL = `${API_ORIGIN}/reference-products/confirm-bind`;', self.html)
        self.assertIn('const REFERENCE_EXPORT_EXCEL_URL = `${API_ORIGIN}/reference-products/export-excel`;', self.html)
        self.assertIn("function showReferenceView()", self.html)
        self.assertIn("async function captureReferenceProduct()", self.html)
        self.assertIn("async function matchReferenceProducts()", self.html)
        self.assertIn("async function exportReferenceExcel()", self.html)
        self.assertIn("function referenceBindPayload(selectedCandidate)", self.html)
        self.assertIn("function buildReferenceMatchInteractionCard", self.html)
        self.assertIn("function confirmReferenceInteraction", self.html)
        self.assertIn('interaction.kind === "reference_product_match_review"', self.html)
        self.assertIn("interactions: Array.isArray(data.interactions) ? data.interactions : []", self.html)
        self.assertIn("confirmed: true", self.html)
        self.assertIn("确认把所选参考 SKU 图片链接写入资料库", self.html)


if __name__ == "__main__":
    unittest.main()
