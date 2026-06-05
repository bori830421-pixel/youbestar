import json
import urllib.parse
from datetime import datetime

from core.http_client import fetch_json, fetch_text

DEFAULT_FIELDS = ['open', 'close', 'high', 'low', 'change', 'pct_change', 'volume', 'amount']
FIELD_ALIASES = {
    '开盘': 'open',
    '开盘价': 'open',
    'open': 'open',
    '最新': 'close',
    '最新价': 'close',
    '股价': 'close',
    '价格': 'close',
    '现价': 'close',
    '收盘': 'close',
    '收盘价': 'close',
    'close': 'close',
    '最高': 'high',
    '最高价': 'high',
    'high': 'high',
    '最低': 'low',
    '最低价': 'low',
    'low': 'low',
    '涨跌': 'change',
    '涨跌额': 'change',
    'change': 'change',
    '涨幅': 'pct_change',
    '跌幅': 'pct_change',
    '涨跌幅': 'pct_change',
    'pct_change': 'pct_change',
    '成交量': 'volume',
    'volume': 'volume',
    '成交额': 'amount',
    'amount': 'amount',
}


def _normalize_symbol(symbol):
    s = str(symbol).strip().lower()
    if not s:
        raise ValueError('symbol 不能为空')
    if s in ('上证指数', 'sh000001', '000001', '上证'):
        return 'sh000001'
    if s.startswith('sh') or s.startswith('sz'):
        return s
    if s.isdigit():
        if s.startswith('6'):
            return 'sh' + s
        if s.startswith('0') or s.startswith('3'):
            return 'sz' + s
    raise ValueError('无法识别代码: %s' % symbol)


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _safe_int(v):
    try:
        return int(float(v))
    except Exception:
        return None


def _pick(data, fields):
    normalized_fields = _normalize_fields(fields)
    if not normalized_fields:
        return data
    out = {}
    for f in normalized_fields:
        if f in data:
            out[f] = data[f]
    return out


def _normalize_fields(fields):
    if not fields:
        return list(DEFAULT_FIELDS)
    normalized = []
    for field in fields:
        key = str(field).strip()
        if not key:
            continue
        mapped = FIELD_ALIASES.get(key, FIELD_ALIASES.get(key.lower()))
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    return normalized or list(DEFAULT_FIELDS)


def _http_get(url, headers=None, timeout=10):
    return fetch_text(url, headers=headers or {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://quote.eastmoney.com/'
    }, timeout=timeout)


def _query_latest_tencent(symbol):
    url = f'http://qt.gtimg.cn/q={symbol}'
    text = _http_get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if '~' not in text:
        raise ValueError('腾讯行情接口返回异常')
    body = text.split('="', 1)[-1].rstrip('";\n')
    parts = body.split('~')
    if len(parts) < 38:
        raise ValueError('腾讯行情数据字段不足')

    name = parts[1] or symbol
    code = parts[2] or symbol[-6:]
    close = _safe_float(parts[3])
    prev_close = _safe_float(parts[4])
    open_price = _safe_float(parts[5])
    volume_lot = _safe_int(parts[6])
    bid1 = _safe_float(parts[9])
    ask1 = _safe_float(parts[19])
    amount_wan = _safe_float(parts[37])
    query_time = parts[30] if len(parts) > 30 else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    high = _safe_float(parts[33]) if len(parts) > 33 else None
    low = _safe_float(parts[34]) if len(parts) > 34 else None
    change = _safe_float(parts[31]) if len(parts) > 31 else (close - prev_close if close is not None and prev_close is not None else None)
    pct_change = _safe_float(parts[32]) if len(parts) > 32 else ((change / prev_close * 100) if change is not None and prev_close else None)

    return {
        'name': name,
        'symbol': symbol,
        'code': code,
        'datetime': query_time,
        'open': open_price,
        'close': close,
        'high': high,
        'low': low,
        'change': change,
        'pct_change': pct_change,
        'volume': volume_lot,
        'amount': amount_wan,
        'source': '腾讯行情接口'
    }


def _query_history_eastmoney(symbol, date_str=None):
    secid = ('1.' + symbol[2:]) if symbol.startswith('sh') else ('0.' + symbol[2:])
    params = {
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',
        'fqt': '1',
        'secid': secid,
        'beg': (date_str or '').replace('-', '') or '19900101',
        'end': (date_str or '').replace('-', '') or '20991231',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
    }
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urllib.parse.urlencode(params)
    obj = fetch_json(url, headers={'Referer': 'https://quote.eastmoney.com/'})
    data = obj.get('data') or {}
    klines = data.get('klines') or []
    if not klines:
        raise ValueError('未查询到历史行情数据')

    target = None
    if date_str:
        for line in klines:
            arr = line.split(',')
            if arr and arr[0] == date_str:
                target = arr
                break
        if target is None:
            raise ValueError('指定日期无数据: %s' % date_str)
    else:
        target = klines[-1].split(',')

    name = data.get('name') or symbol
    code = data.get('code') or symbol[2:]
    arr = target
    # 东财日K: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
    return {
        'name': name,
        'symbol': symbol,
        'code': code,
        'datetime': arr[0],
        'open': _safe_float(arr[1]),
        'close': _safe_float(arr[2]),
        'high': _safe_float(arr[3]),
        'low': _safe_float(arr[4]),
        'volume': _safe_float(arr[5]),
        'amount': _safe_float(arr[6]),
        'pct_change': _safe_float(arr[8]),
        'change': _safe_float(arr[9]),
        'source': '东方财富日K接口'
    }


def _format_value(v):
    if v is None:
        return '-'
    if isinstance(v, float):
        return ('%.4f' % v).rstrip('0').rstrip('.')
    return str(v)


def _format_datetime(value):
    text = str(value or '').strip()
    if len(text) == 14 and text.isdigit():
        return f'{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}'
    return text or '-'


def run(params):
    params = params or {}
    symbol = params.get('symbol')
    date_str = params.get('date')
    fields = _normalize_fields(params.get('fields'))
    if not symbol:
        raise ValueError('必须提供 symbol')

    normalized = _normalize_symbol(symbol)
    if date_str:
        data = _query_history_eastmoney(normalized, date_str)
    else:
        data = _query_latest_tencent(normalized)

    filtered = {
        'name': data.get('name'),
        'symbol': data.get('symbol'),
        'code': data.get('code'),
        'datetime': data.get('datetime'),
        'source': data.get('source')
    }
    filtered.update(_pick(data, fields))

    row = [
        _format_value(filtered.get('name')),
        _format_value(filtered.get('code')),
        _format_value(filtered.get('close')),
        _format_value(filtered.get('change')),
        _format_value(filtered.get('pct_change')) + ('%' if filtered.get('pct_change') is not None else ''),
        _format_value(filtered.get('open')),
        _format_value(filtered.get('high')),
        _format_value(filtered.get('low')),
        _format_datetime(filtered.get('datetime')),
        _format_value(filtered.get('volume')),
        _format_value(filtered.get('amount')),
        _format_value(filtered.get('source')),
    ]

    return {
        'ok': True,
        'kind': 'market_quote',
        'title': '证券行情查询结果',
        'columns': ['标的名称', '代码', '最新价/收盘价', '涨跌额', '涨跌幅', '开盘价', '最高价', '最低价', '查询时间', '成交量', '成交额', '数据来源'],
        'rows': [row],
        'summary': {
            '标的名称': filtered.get('name'),
            '代码': filtered.get('code'),
            '最新价/收盘价': _format_value(filtered.get('close')),
        },
        'data': filtered,
    }
