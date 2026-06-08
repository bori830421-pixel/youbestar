import webbrowser


def normalize_url(url: str) -> str:
    clean_url = (url or "https://www.baidu.com").strip()
    if clean_url.startswith(("http://", "https://")):
        return clean_url
    return f"https://{clean_url}"


def open_browser(params: dict) -> str:
    """
    Open a URL in the system default browser.

    params = {"url": "https://www.baidu.com"}
    """
    url = normalize_url(params.get("url", "https://www.baidu.com"))
    opened = webbrowser.open(url)
    if not opened:
        return f"尝试打开 {url}，但系统没有确认浏览器已打开。"
    return f"已打开 {url}"
