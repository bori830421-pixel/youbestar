from tools.excel_preview_tool import preview_excel


def run(params: dict):
    return preview_excel(params or {})
