import importlib
import re
from typing import Any

from core.http_client import fetch_text


"""
AKShare stock skill module.

Example calls:
    stock_zh_a_spot_em(as_json=True)
    stock_zh_a_daily(symbol="sh601601", start_date="20260601", end_date="20260605", adjust="qfq")
    stock_individual_info_em(symbol="601601", as_json=True)
    stock_board_industry_name_em(as_json=True)
    stock_board_industry_cons_em(symbol="保险", as_json=True)
    stock_board_concept_name_em(as_json=True)
    stock_board_concept_cons_em(symbol="央企改革", as_json=True)
    stock_individual_fund_flow(stock="601601", market="sh", as_json=True)
    stock_hk_spot_em(as_json=True)
    stock_us_spot_em(as_json=True)
    stock_zh_index_spot_em(symbol="上证系列指数", as_json=True)

All wrapper functions return the original pandas.DataFrame by default. Pass
as_json=True to return Youbestar-friendly structured JSON. Exceptions are
converted to sanitized error objects and do not expose provider URLs, proxy
details, or stack traces.
"""

SOURCE_NAME = "AkShare stock_zh_a_spot_em"
DEFAULT_COLUMNS = [
    "标的名称",
    "代码",
    "最新价/收盘价",
    "涨跌额",
    "涨跌幅",
    "开盘价",
    "最高价",
    "最低价",
    "查询时间",
    "成交量",
    "成交额",
    "数据来源",
]
TENCENT_SOURCE_NAME = "腾讯行情接口"
SANITIZED_ERROR_MESSAGE = "证券数据接口暂时不可用，请稍后重试。"


def _load_akshare() -> Any:
    try:
        return importlib.import_module("akshare")
    except ImportError as exc:
        raise ValueError("缺少 akshare 依赖，请先安装 requirements.txt。") from exc


def _records(data_frame: Any) -> list[dict[str, Any]]:
    if data_frame is None:
        return []
    if isinstance(data_frame, list):
        return [row for row in data_frame if isinstance(row, dict)]
    if hasattr(data_frame, "empty") and data_frame.empty:
        return []
    if hasattr(data_frame, "to_dict"):
        rows = data_frame.to_dict(orient="records")
        return [row for row in rows if isinstance(row, dict)]
    raise ValueError("AkShare 返回格式不受支持。")


def _columns(data_frame: Any, rows: list[dict[str, Any]]) -> list[str]:
    columns = getattr(data_frame, "columns", None)
    if columns is not None:
        return [str(column) for column in list(columns)]
    if rows:
        return [str(column) for column in rows[0].keys()]
    return []


def _structured_frame(kind: str, title: str, data_frame: Any, limit: int | None = None) -> dict[str, Any]:
    rows_as_dicts = _records(data_frame)
    columns = _columns(data_frame, rows_as_dicts)
    visible_rows = rows_as_dicts[:limit] if limit else rows_as_dicts
    table_rows = [[row.get(column) for column in columns] for row in visible_rows]
    return {
        "ok": True,
        "kind": kind,
        "title": title,
        "columns": columns,
        "rows": table_rows,
        "summary": {
            "rows": len(rows_as_dicts),
            "source": "AkShare",
        },
        "data": visible_rows,
    }


def _sanitized_error(kind: str, title: str, hint: str = "") -> dict[str, Any]:
    message = hint or SANITIZED_ERROR_MESSAGE
    return {
        "ok": False,
        "kind": f"{kind}_error",
        "title": title,
        "message": message,
        "summary": {
            "source": "AkShare",
        },
    }


def _call_akshare_frame(
    function_name: str,
    title: str,
    *args: Any,
    as_json: bool = False,
    limit: int | None = None,
    **kwargs: Any,
) -> Any:
    try:
        ak = _load_akshare()
        data_frame = getattr(ak, function_name)(*args, **kwargs)
        if as_json:
            return _structured_frame(function_name, title, data_frame, limit=limit)
        return data_frame
    except Exception:
        return _sanitized_error(function_name, f"{title}失败")


def stock_zh_a_spot_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """A 股沪深京实时行情，数据源为东方财富。"""
    return _call_akshare_frame("stock_zh_a_spot_em", "A股实时行情", as_json=as_json, limit=limit)


def stock_sh_a_spot_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """沪 A 股实时行情，数据源为东方财富。"""
    return _call_akshare_frame("stock_sh_a_spot_em", "沪A股实时行情", as_json=as_json, limit=limit)


def stock_sz_a_spot_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """深 A 股实时行情，数据源为东方财富。"""
    return _call_akshare_frame("stock_sz_a_spot_em", "深A股实时行情", as_json=as_json, limit=limit)


def stock_zh_a_daily(
    *,
    symbol: str,
    start_date: str = "",
    end_date: str = "",
    adjust: str = "",
    as_json: bool = False,
    limit: int | None = None,
) -> Any:
    """A 股日频历史行情。symbol 示例：sh601601、sz000001。"""
    params = {"symbol": symbol}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if adjust:
        params["adjust"] = adjust
    return _call_akshare_frame("stock_zh_a_daily", "A股历史行情", as_json=as_json, limit=limit, **params)


def stock_individual_info_em(*, symbol: str, as_json: bool = False, limit: int | None = None) -> Any:
    """个股基本信息，symbol 示例：601601。"""
    return _call_akshare_frame("stock_individual_info_em", "个股基本信息", symbol=symbol, as_json=as_json, limit=limit)


def stock_board_industry_name_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """行业板块列表。"""
    return _call_akshare_frame("stock_board_industry_name_em", "行业板块列表", as_json=as_json, limit=limit)


def stock_board_industry_cons_em(*, symbol: str, as_json: bool = False, limit: int | None = None) -> Any:
    """行业板块成份股，symbol 示例：保险。"""
    return _call_akshare_frame(
        "stock_board_industry_cons_em",
        "行业板块成份股",
        symbol=symbol,
        as_json=as_json,
        limit=limit,
    )


def stock_board_concept_name_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """概念板块列表。"""
    return _call_akshare_frame("stock_board_concept_name_em", "概念板块列表", as_json=as_json, limit=limit)


def stock_board_concept_cons_em(*, symbol: str, as_json: bool = False, limit: int | None = None) -> Any:
    """概念板块成份股，symbol 示例：央企改革。"""
    return _call_akshare_frame(
        "stock_board_concept_cons_em",
        "概念板块成份股",
        symbol=symbol,
        as_json=as_json,
        limit=limit,
    )


def stock_individual_fund_flow(
    *,
    stock: str,
    market: str = "",
    as_json: bool = False,
    limit: int | None = None,
) -> Any:
    """个股资金流向，stock 示例：600094，market 示例：sh、sz。"""
    params = {"stock": stock}
    if market:
        params["market"] = market
    return _call_akshare_frame("stock_individual_fund_flow", "个股资金流向", as_json=as_json, limit=limit, **params)


def stock_hk_spot_em(*, as_json: bool = False, limit: int | None = None) -> Any:
    """港股实时行情。"""
    return _call_akshare_frame("stock_hk_spot_em", "港股实时行情", as_json=as_json, limit=limit)


def stock_hk_spot(*, as_json: bool = False, limit: int | None = None) -> Any:
    """港股实时行情兼容接口。"""
    return _call_akshare_frame("stock_hk_spot", "港股实时行情", as_json=as_json, limit=limit)


def stock_us_spot(*, as_json: bool = False, limit: int | None = None) -> Any:
    """美股行情报价。"""
    return _call_akshare_frame("stock_us_spot", "美股行情报价", as_json=as_json, limit=limit)


def stock_zh_index_spot_em(
    *,
    symbol: str = "上证系列指数",
    as_json: bool = False,
    limit: int | None = None,
) -> Any:
    """股票指数实时行情，symbol 示例：上证系列指数。"""
    return _call_akshare_frame(
        "stock_zh_index_spot_em",
        "股票指数实时行情",
        symbol=symbol,
        as_json=as_json,
        limit=limit,
    )


def stock_zh_index_spot_sina(*, as_json: bool = False, limit: int | None = None) -> Any:
    """新浪股票指数实时行情。"""
    return _call_akshare_frame("stock_zh_index_spot_sina", "新浪股票指数实时行情", as_json=as_json, limit=limit)


def stock_zh_index_daily_em(*, symbol: str, as_json: bool = False, limit: int | None = None) -> Any:
    """东方财富股票指数历史行情。"""
    return _call_akshare_frame(
        "stock_zh_index_daily_em",
        "股票指数历史行情",
        symbol=symbol,
        as_json=as_json,
        limit=limit,
    )


def _clean_symbol(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[!！。。，,\s]+$", "", text)
    return text.strip()


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith(("sh", "sz", "bj")):
        text = text[2:]
    return text


def _market_code(value: Any) -> str:
    code = _normalize_code(value)
    if not re.fullmatch(r"\d{6}", code):
        return ""
    if code.startswith("6"):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return ""


def _pick(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in row and row[name] not in ("", None):
            return row[name]
    return None


def _safe_float(value: Any) -> float | None:
    try:
        if value in ("", None, "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return ("%.4f" % value).rstrip("0").rstrip(".")
    return str(value)


def _find_quote(rows: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    query = _clean_symbol(symbol)
    if not query:
        raise ValueError("必须提供 symbol")

    query_code = _normalize_code(query)
    exact_name_matches = []
    partial_name_matches = []
    code_matches = []
    for row in rows:
        code = str(_pick(row, ["代码", "code", "symbol"]) or "").strip()
        name = str(_pick(row, ["名称", "name", "股票简称"]) or "").strip()
        if query_code and _normalize_code(code) == query_code:
            code_matches.append(row)
        if name == query:
            exact_name_matches.append(row)
        elif query in name:
            partial_name_matches.append(row)

    for candidates in (exact_name_matches, code_matches, partial_name_matches):
        if candidates:
            return candidates[0]
    raise ValueError(f"未找到证券：{query}")


def _quote_from_row(row: dict[str, Any]) -> dict[str, Any]:
    close = _safe_float(_pick(row, ["最新价", "最新", "close", "收盘"]))
    change = _safe_float(_pick(row, ["涨跌额", "change"]))
    pct_change = _safe_float(_pick(row, ["涨跌幅", "pct_change"]))
    return {
        "name": _pick(row, ["名称", "name", "股票简称"]),
        "code": _pick(row, ["代码", "code", "symbol"]),
        "datetime": _pick(row, ["更新时间", "时间", "datetime"]),
        "open": _safe_float(_pick(row, ["今开", "开盘", "open"])),
        "close": close,
        "high": _safe_float(_pick(row, ["最高", "high"])),
        "low": _safe_float(_pick(row, ["最低", "low"])),
        "change": change,
        "pct_change": pct_change,
        "volume": _pick(row, ["成交量", "volume"]),
        "amount": _pick(row, ["成交额", "amount"]),
        "source": SOURCE_NAME,
    }


def _quote_from_tencent_text(symbol: str, text: str) -> dict[str, Any]:
    if "~" not in text:
        raise ValueError("腾讯行情接口返回异常")
    body = text.split('="', 1)[-1].rstrip('";\n')
    parts = body.split("~")
    if len(parts) < 38:
        raise ValueError("腾讯行情数据字段不足")
    return {
        "name": parts[1] or symbol,
        "code": parts[2] or symbol[-6:],
        "datetime": parts[30] if len(parts) > 30 else None,
        "open": _safe_float(parts[5]),
        "close": _safe_float(parts[3]),
        "high": _safe_float(parts[33]) if len(parts) > 33 else None,
        "low": _safe_float(parts[34]) if len(parts) > 34 else None,
        "change": _safe_float(parts[31]) if len(parts) > 31 else None,
        "pct_change": _safe_float(parts[32]) if len(parts) > 32 else None,
        "volume": parts[36] if len(parts) > 36 else None,
        "amount": parts[37] if len(parts) > 37 else None,
        "source": TENCENT_SOURCE_NAME,
    }


def _query_tencent_quote(symbol: Any) -> dict[str, Any]:
    market_symbol = _market_code(symbol)
    if not market_symbol:
        raise ValueError("股票代码兜底查询需要 6 位 A 股代码。")
    text = fetch_text(
        f"http://qt.gtimg.cn/q={market_symbol}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    return _quote_from_tencent_text(market_symbol, text)


def query_market_data(params: dict[str, Any]) -> dict[str, Any]:
    params = params or {}
    symbol = params.get("symbol") or params.get("name") or params.get("query")
    try:
        ak = _load_akshare()
        rows = _records(ak.stock_zh_a_spot_em())
        quote = _quote_from_row(_find_quote(rows, str(symbol or "")))
    except Exception as exc:
        try:
            quote = _query_tencent_quote(symbol)
        except Exception:
            pass
        else:
            return _structured_quote(quote)
        return {
            "ok": False,
            "kind": "market_quote_error",
            "title": "证券行情查询失败",
            "message": "证券行情接口暂时不可用，请稍后重试，或改用股票代码查询。",
            "summary": {
                "symbol": _clean_symbol(symbol),
                "source": SOURCE_NAME,
            },
        }

    return _structured_quote(quote)


def _structured_quote(quote: dict[str, Any]) -> dict[str, Any]:

    pct_change = quote.get("pct_change")
    pct_text = _format_value(pct_change) + ("%" if pct_change is not None else "")
    row = [
        _format_value(quote.get("name")),
        _format_value(quote.get("code")),
        _format_value(quote.get("close")),
        _format_value(quote.get("change")),
        pct_text,
        _format_value(quote.get("open")),
        _format_value(quote.get("high")),
        _format_value(quote.get("low")),
        _format_value(quote.get("datetime")),
        _format_value(quote.get("volume")),
        _format_value(quote.get("amount")),
        _format_value(quote.get("source")),
    ]

    return {
        "ok": True,
        "kind": "market_quote",
        "title": "证券行情查询结果",
        "columns": DEFAULT_COLUMNS,
        "rows": [row],
        "summary": {
            "标的名称": quote.get("name"),
            "代码": quote.get("code"),
            "最新价/收盘价": _format_value(quote.get("close")),
        },
        "data": quote,
    }
