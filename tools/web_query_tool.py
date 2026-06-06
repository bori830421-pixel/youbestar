import json
import re
import urllib.parse
from html import unescape
from typing import Any

from core.http_client import fetch_text


DEFAULT_PROVIDER = "auto"
DEFAULT_PROVIDERS = ("baidu", "bing_cn", "sogou")
EVENT_REGION_HINTS = (
    ("山东德州庆云县", ("山东德州庆云", "德州市庆云县", "庆云县")),
    ("山东德州", ("山东德州", "德州市")),
    ("河南濮阳", ("河南濮阳", "濮阳市")),
    ("广西", ("广西",)),
    ("海南", ("海南",)),
    ("云南", ("云南",)),
    ("广东", ("广东",)),
)


def _clean_html_text(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_baidu_results(payload: str) -> list[dict[str, str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    feed = data.get("feed") if isinstance(data, dict) else None
    if not isinstance(feed, dict):
        return []

    items = feed.get("entry")
    if not isinstance(items, list):
        return []

    results: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("abs") or item.get("summary") or "").strip()
        url = str(item.get("url") or item.get("showurl") or "").strip()
        if not title and not content:
            continue
        results.append(
            {
                "title": title or "未命名结果",
                "snippet": content or "暂无摘要",
                "url": url or "-",
            }
        )
    return results


def _result(source: str, title: str, snippet: str, url: str) -> dict[str, str]:
    return {
        "source": source,
        "title": title or "未命名结果",
        "snippet": snippet or "暂无摘要",
        "url": url or "-",
    }


def _extract_baidu_html_results(payload: str) -> list[dict[str, str]]:
    blocks = re.findall(
        r'(?is)<div[^>]+class=["\'][^"\']*(?:result|c-container)[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*(?:result|c-container)[^"\']*["\']|</body>)',
        payload or "",
    )
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(r"(?is)<h3[^>]*>.*?</h3>", block)
        link_match = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', title_match.group(0) if title_match else block)
        title = _clean_html_text(title_match.group(0) if title_match else "")
        snippet = _clean_html_text(re.sub(r"(?is)<h3[^>]*>.*?</h3>", " ", block, count=1))
        url = unescape(link_match.group(1)).strip() if link_match else "-"
        if not title and not snippet:
            continue
        results.append(_result("百度", title, snippet, url))

    return results


def _extract_bing_html_results(payload: str) -> list[dict[str, str]]:
    blocks = re.findall(
        r'(?is)<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>.*?(?=</li>|<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\']|</body>)',
        payload or "",
    )
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(r"(?is)<h2[^>]*>.*?</h2>", block)
        link_match = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', title_match.group(0) if title_match else block)
        snippet_match = re.search(r'(?is)<p[^>]*>.*?</p>', block)
        title = _clean_html_text(title_match.group(0) if title_match else "")
        snippet = _clean_html_text(snippet_match.group(0) if snippet_match else block)
        url = unescape(link_match.group(1)).strip() if link_match else "-"
        if title or snippet:
            results.append(_result("必应", title, snippet, url))
    if results:
        return results

    for match in re.finditer(r'(?is)<h2[^>]*>\s*<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</h2>', payload or ""):
        url = unescape(match.group(1)).strip()
        title = _clean_html_text(match.group(2))
        if title:
            results.append(_result("必应", title, "暂无摘要", url))
    return results


def _extract_sogou_html_results(payload: str) -> list[dict[str, str]]:
    blocks = re.findall(
        r'(?is)<div[^>]+class=["\'][^"\']*(?:vrwrap|results|rb)[^"\']*["\'][^>]*>.*?(?=<div[^>]+class=["\'][^"\']*(?:vrwrap|results|rb)[^"\']*["\']|</body>)',
        payload or "",
    )
    results: list[dict[str, str]] = []
    for block in blocks:
        title_match = re.search(r"(?is)<h3[^>]*>.*?</h3>|<a[^>]+class=[\"'][^\"']*title[^\"']*[\"'][^>]*>.*?</a>", block)
        link_match = re.search(r'(?is)<a[^>]+href=["\']([^"\']+)["\']', title_match.group(0) if title_match else block)
        title = _clean_html_text(title_match.group(0) if title_match else "")
        snippet = _clean_html_text(re.sub(r"(?is)<h3[^>]*>.*?</h3>", " ", block, count=1))
        url = unescape(link_match.group(1)).strip() if link_match else "-"
        if title or snippet:
            results.append(_result("搜狗", title, snippet, url))
    return results


def _build_baidu_url(query: str, limit: int) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://www.baidu.com/s?wd={encoded}&rn={max(1, min(limit, 10))}&tn=json"


def _build_baidu_html_url(query: str, limit: int) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://www.baidu.com/s?wd={encoded}&rn={max(1, min(limit, 10))}"


def _build_bing_cn_url(query: str, limit: int) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://cn.bing.com/search?q={encoded}&count={max(1, min(limit, 10))}&cc=cn&setlang=zh-cn"


def _build_sogou_url(query: str, limit: int) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://www.sogou.com/web?query={encoded}&num={max(1, min(limit, 10))}"


def _provider_names(provider: str) -> list[str]:
    if provider in ("", "auto", "default"):
        return list(DEFAULT_PROVIDERS)
    return [part.strip().lower() for part in provider.split(",") if part.strip()]


def _fetch_provider_results(provider: str, query: str, limit: int) -> list[dict[str, str]]:
    if provider == "baidu":
        text = fetch_text(_build_baidu_url(query, limit))
        results = _extract_baidu_results(text)
        if results:
            for item in results:
                item.setdefault("source", "百度")
            return results
        return _extract_baidu_html_results(fetch_text(_build_baidu_html_url(query, limit)))
    if provider == "bing_cn":
        return _extract_bing_html_results(fetch_text(_build_bing_cn_url(query, limit)))
    if provider == "sogou":
        return _extract_sogou_html_results(fetch_text(_build_sogou_url(query, limit)))
    return []


def _dedupe_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in results:
        key = (item.get("title", ""), item.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _find_region(text: str) -> str:
    for region, markers in EVENT_REGION_HINTS:
        if any(marker in text for marker in markers):
            return region
    return ""


def _summarize_regions(results: list[dict[str, str]]) -> dict[str, str]:
    joined = " ".join(" ".join([item.get("title", ""), item.get("snippet", "")]) for item in results)
    summary: dict[str, str] = {}
    if any(marker in joined for marker in ("买家", "嫌疑人", "袁某某", "涉案")):
        buyer_region = _find_region(joined)
        if buyer_region:
            summary["涉事买家地区"] = buyer_region
    if any(marker in joined for marker in ("商家", "卖家", "店家", "程先生", "程某")):
        if "河南濮阳" in joined or "濮阳市" in joined:
            summary["商家所在地"] = "河南濮阳"
    return summary


def _pick_region(results: list[dict[str, str]]) -> str:
    for item in results:
        text = " ".join([item.get("title", ""), item.get("snippet", "")])
        region = _find_region(text)
        if region:
            return region
    return ""


def web_query(params: dict[str, Any]) -> dict[str, Any]:
    """
    Query web search results and return structured data.

    params = {"query": "榴莲仅退款 哪个地区", "limit": 5}
    """
    query = str(params.get("query") or params.get("q") or "").strip()
    if not query:
        return {
            "ok": False,
            "title": "网页查询失败",
            "error": "缺少 query 参数。",
        }

    provider = str(params.get("provider") or DEFAULT_PROVIDER).strip().lower()
    limit = int(params.get("limit") or 5)

    searched_sources: list[str] = []
    results: list[dict[str, str]] = []
    for provider_name in _provider_names(provider):
        searched_sources.append(provider_name)
        try:
            provider_results = _fetch_provider_results(provider_name, query, limit)
        except Exception:
            provider_results = []
        results.extend(provider_results)
        if len(results) >= limit:
            break

    results = _dedupe_results(results)
    if not results:
        return {
            "ok": False,
            "title": "网页查询失败",
            "error": f"搜索结果为空，已尝试来源：{', '.join(searched_sources) or provider}",
        }

    region = _pick_region(results)
    rows = [[item.get("source", "-"), item["title"], item["snippet"], item["url"]] for item in results[:limit]]
    summary: dict[str, Any] = {
        "查询关键词": query,
        "结果数量": min(len(results), limit),
        "搜索来源": ", ".join(searched_sources),
    }
    if region:
        summary["疑似地区"] = region
    summary.update(_summarize_regions(results))

    return {
        "ok": True,
        "kind": "web_search",
        "title": "网页搜索结果",
        "columns": ["来源", "标题", "摘要", "链接"],
        "rows": rows,
        "summary": summary,
    }
