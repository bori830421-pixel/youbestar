import json
import urllib.request
from typing import Any


DEFAULT_TIMEOUT = 10
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
}
FALLBACK_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")


class HttpClientError(RuntimeError):
    pass


def _header_charset(response: Any) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None

    get_content_charset = getattr(headers, "get_content_charset", None)
    if callable(get_content_charset):
        charset = get_content_charset()
        if charset:
            return charset

    content_type = ""
    if hasattr(headers, "get"):
        content_type = headers.get("Content-Type", "") or ""
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            return part.split("=", 1)[1].strip()
    return None


def decode_bytes(raw: bytes, charset: str | None = None) -> str:
    encodings: list[str] = []
    if charset:
        encodings.append(charset)
    encodings.extend(encoding for encoding in FALLBACK_ENCODINGS if encoding not in encodings)

    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        return raw.decode(encodings[-1], errors="replace")
    return raw.decode("utf-8", errors="replace")


def fetch_bytes(url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> tuple[bytes, Any]:
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    req = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read(), response
    except Exception as exc:  # pragma: no cover - exact urllib errors vary by platform
        raise HttpClientError(f"网络请求失败：{exc}") from exc


def fetch_text(url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    raw, response = fetch_bytes(url, headers=headers, timeout=timeout)
    return decode_bytes(raw, _header_charset(response))


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    text = fetch_text(url, headers=headers, timeout=timeout)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HttpClientError(f"JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise HttpClientError("JSON 顶层结构不是对象。")
    return data
