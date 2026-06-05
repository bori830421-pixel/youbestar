from typing import Any

from core.http_client import fetch_json


CITY_COORDS = {
    "汕头": (23.34, 116.57),
    "深圳": (22.543, 114.058),
    "广州": (23.129, 113.264),
    "北京": (39.904, 116.407),
    "上海": (31.230, 121.473),
    "杭州": (30.274, 120.155),
    "成都": (30.572, 104.066),
    "武汉": (30.592, 114.305),
    "西安": (34.341, 108.940),
    "南京": (32.060, 118.796),
}

WMO_CODES = {
    0: "晴",
    1: "多云",
    2: "多云",
    3: "阴天",
    45: "雾",
    48: "雾凇",
    51: "小雨",
    53: "中雨",
    55: "大雨",
    56: "冻雨",
    57: "冻雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "阵雨",
    81: "阵雨",
    82: "大阵雨",
    85: "雪阵雨",
    86: "雪阵雨",
    95: "雷雨",
    96: "雷雨",
    99: "雷雨伴冰雹",
}


def get_coords(city: str) -> tuple[float, float, str]:
    clean_city = (city or "汕头").strip() or "汕头"
    if clean_city in CITY_COORDS:
        lat, lon = CITY_COORDS[clean_city]
        return lat, lon, clean_city

    lat, lon = CITY_COORDS["汕头"]
    return lat, lon, f"{clean_city}（未收录坐标，已使用汕头）"


def fetch_weather(lat: float, lon: float, forecast_days: int = 7) -> dict[str, Any]:
    days = max(1, min(int(forecast_days or 7), 7))
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min"
        f"&timezone=Asia/Shanghai&forecast_days={days}"
    )
    return fetch_json(url)


def format_weather(data: dict[str, Any], city: str) -> str:
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    codes = daily.get("weathercode", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    total_days = min(len(dates), len(codes), len(max_temps), len(min_temps))

    if total_days == 0:
        return f"{city} 天气查询成功，但接口没有返回可用的预报数据。"

    lines = [f"{city}未来{total_days}天天气预报"]
    for index in range(total_days):
        desc = WMO_CODES.get(codes[index], f"未知代码{codes[index]}")
        lines.append(f"{dates[index]}：{desc}，最高 {max_temps[index]}°C，最低 {min_temps[index]}°C")
    return "\n".join(lines)


def query_weather(params: dict[str, Any]) -> str:
    """
    Query a 1-7 day weather forecast.

    params = {"city": "汕头", "days": 7}
    """
    city = str(params.get("city") or "汕头")
    days = int(params.get("days") or 7)
    lat, lon, display_city = get_coords(city)
    data = fetch_weather(lat, lon, days)
    return format_weather(data, display_city)
