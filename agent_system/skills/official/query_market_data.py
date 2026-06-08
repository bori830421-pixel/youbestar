from tools import stock_tool


def run(params: dict):
    params = params or {}
    function_name = str(params.get("function") or params.get("api") or "").strip()
    if function_name:
        return {
            "ok": False,
            "kind": "market_api_error",
            "title": "证券行情查询失败",
            "message": "证券行情查询只支持股票代码或中文名称。",
        }

    return stock_tool.query_market_data(params)
