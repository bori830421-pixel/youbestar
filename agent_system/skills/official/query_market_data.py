from tools import stock_tool


def run(params: dict):
    params = params or {}
    function_name = str(params.get("function") or params.get("api") or "").strip()
    if function_name:
        function = getattr(stock_tool, function_name, None)
        if function is None or function_name.startswith("_"):
            return {
                "ok": False,
                "kind": "market_api_error",
                "title": "证券数据查询失败",
                "message": "不支持的证券数据接口。",
            }
        call_params = {key: value for key, value in params.items() if key not in {"function", "api"}}
        call_params.setdefault("as_json", True)
        return function(**call_params)

    return stock_tool.query_market_data(params)
