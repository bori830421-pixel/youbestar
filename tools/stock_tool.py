from typing import Any
from urllib.parse import quote

from core.http_client import fetch_json, fetch_text


SOURCE_NAME = "东方财富"
TENCENT_SOURCE_NAME = "腾讯行情接口"
DEFAULT_COLUMNS = [
    "标的名称",
    "代码",
    "最新价",
    "涨跌幅",
    "最高价",
    "最低价",
    "今开",
    "成交量",
    "成交额",
    "数据来源",
]
SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
ERROR_MESSAGE = "证券行情接口暂时不可用，请稍后重试，或确认股票代码/名称是否正确。"


def _clean_symbol(value: Any) -> str:
    return str(value or "").strip().rstrip("!！。。，, ")


def _market_from_code(code: str) -> str:
    if code.startswith("6"):
        return "1"
    if code.startswith(("0", "3")):
        return "0"
    return "0"


def _scaled_price(value: Any) -> float | None:
    if value in ("", None, "-"):
        return None
    try:
        return float(value) / 100
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value in ("", None, "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return ("%.4f" % value).rstrip("0").rstrip(".")
    return str(value)


def _tencent_market_code(code: str, market: str) -> str:
    if market == "1" or code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def search_stock(keyword: str) -> dict[str, Any] | None:
    url = (
        "https://searchapi.eastmoney.com/api/suggest/get"
        f"?input={quote(keyword)}&type=14&token={SUGGEST_TOKEN}"
    )
    data = fetch_json(url, timeout=8)
    data_list = data.get("QuotationCodeTable", {}).get("Data", [])
    if not data_list:
        return None

    row = data_list[0]
    code = str(row.get("Code") or "").strip()
    name = str(row.get("Name") or "").strip()
    market = str(row.get("Market") or row.get("MktNum") or "").strip()
    if not code:
        return None
    if not market:
        market = _market_from_code(code)

    return {
        "name": name,
        "code": code,
        "market": market,
    }


def get_stock_info(code: str, market: str) -> dict[str, Any] | None:
    secid = f"{market}.{code}"
    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f170,f58,f57"
    )
    data = fetch_json(url, timeout=8).get("data")
    if not data:
        return None

    return {
        "name": data.get("f58"),
        "code": data.get("f57"),
        "close": _scaled_price(data.get("f43")),
        "pct_change": _scaled_price(data.get("f170")),
        "high": _scaled_price(data.get("f44")),
        "low": _scaled_price(data.get("f45")),
        "open": _scaled_price(data.get("f46")),
        "volume": data.get("f47"),
        "amount": data.get("f48"),
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
        "close": _safe_float(parts[3]),
        "pct_change": _safe_float(parts[32]) if len(parts) > 32 else None,
        "high": _safe_float(parts[33]) if len(parts) > 33 else None,
        "low": _safe_float(parts[34]) if len(parts) > 34 else None,
        "open": _safe_float(parts[5]),
        "volume": parts[36] if len(parts) > 36 else None,
        "amount": parts[37] if len(parts) > 37 else None,
        "source": TENCENT_SOURCE_NAME,
    }


def get_tencent_stock_info(code: str, market: str) -> dict[str, Any]:
    market_symbol = _tencent_market_code(code, market)
    text = fetch_text(
        f"http://qt.gtimg.cn/q={market_symbol}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    return _quote_from_tencent_text(market_symbol, text)


def get_stock_price(symbol: str) -> dict[str, Any]:
    stock = search_stock(_clean_symbol(symbol))
    if not stock:
        raise ValueError("未找到股票")
    try:
        quote_data = get_stock_info(stock["code"], stock["market"])
    except Exception:
        quote_data = get_tencent_stock_info(stock["code"], stock["market"])
    if not quote_data:
        quote_data = get_tencent_stock_info(stock["code"], stock["market"])
    if not quote_data:
        raise ValueError("获取行情失败")
    return {
        "名称": quote_data.get("name"),
        "代码": quote_data.get("code"),
        "最新价": quote_data.get("close"),
        "涨跌幅": quote_data.get("pct_change"),
        "最高": quote_data.get("high"),
        "最低": quote_data.get("low"),
        "今开": quote_data.get("open"),
        "成交量": quote_data.get("volume"),
        "成交额": quote_data.get("amount"),
        "数据来源": quote_data.get("source"),
    }


def _structured_quote(quote_data: dict[str, Any]) -> dict[str, Any]:
    pct_change = quote_data.get("pct_change")
    pct_text = _format_value(pct_change) + ("%" if pct_change is not None else "")
    row = [
        _format_value(quote_data.get("name")),
        _format_value(quote_data.get("code")),
        _format_value(quote_data.get("close")),
        pct_text,
        _format_value(quote_data.get("high")),
        _format_value(quote_data.get("low")),
        _format_value(quote_data.get("open")),
        _format_value(quote_data.get("volume")),
        _format_value(quote_data.get("amount")),
        _format_value(quote_data.get("source") or SOURCE_NAME),
    ]

    return {
        "ok": True,
        "kind": "market_quote",
        "title": "证券行情查询结果",
        "columns": DEFAULT_COLUMNS,
        "rows": [row],
        "summary": {
            "标的名称": quote_data.get("name"),
            "代码": quote_data.get("code"),
            "最新价": _format_value(quote_data.get("close")),
        },
        "data": quote_data,
    }


def query_market_data(params: dict[str, Any]) -> dict[str, Any]:
    params = params or {}
    symbol = _clean_symbol(params.get("symbol") or params.get("name") or params.get("query"))
    if not symbol:
        return {
            "ok": False,
            "kind": "market_quote_error",
            "title": "证券行情查询失败",
            "message": "请提供股票代码或中文名称。",
        }

    try:
        price = get_stock_price(symbol)
        quote_data = {
            "name": price.get("名称"),
            "code": price.get("代码"),
            "close": price.get("最新价"),
            "pct_change": price.get("涨跌幅"),
            "high": price.get("最高"),
            "low": price.get("最低"),
            "open": price.get("今开"),
            "volume": price.get("成交量"),
            "amount": price.get("成交额"),
            "source": price.get("数据来源") or SOURCE_NAME,
        }
    except Exception:
        return {
            "ok": False,
            "kind": "market_quote_error",
            "title": "证券行情查询失败",
            "message": ERROR_MESSAGE,
            "summary": {
                "symbol": symbol,
                "source": SOURCE_NAME,
            },
        }

    return _structured_quote(quote_data)
