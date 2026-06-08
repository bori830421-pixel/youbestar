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
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        f"&timezone=Asia/Shanghai&forecast_days={days}"
    )
    return fetch_json(url)


def _weather_advice(temp: float | int | None, condition: str) -> list[str]:
    advice: list[str] = []
    if temp is not None:
        if temp >= 35:
            advice.append("注意防晒避暑")
        elif temp <= 10:
            advice.append("注意保暖")
    if "雨" in condition:
        advice.append("记得带伞")
    return advice


def _condition_from_rain_probability(value: Any) -> str:
    try:
        probability = int(value)
    except (TypeError, ValueError):
        return "未知"
    if probability >= 50:
        return "有雨"
    return "晴"


def get_weather(city: str) -> dict[str, Any]:
    lat, lon, display_city = get_coords(city)
    data = fetch_weather(lat, lon, 7)
    daily = data.get("daily", {})
    max_temps = daily.get("temperature_2m_max", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    temp = max_temps[0] if max_temps else None
    condition = _condition_from_rain_probability(rain_probs[0] if rain_probs else None)
    return {
        "city": display_city,
        "temp": temp,
        "condition": condition,
        "advice": _weather_advice(temp, condition),
    }


def format_weather(data: dict[str, Any], city: str) -> str:
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    total_days = min(len(dates), len(max_temps), len(min_temps), len(rain_probs))

    if total_days == 0:
        return f"{city} 天气查询成功，但接口没有返回可用的预报数据。"

    lines = [f"{city}未来{total_days}天天气预报"]
    for index in range(total_days):
        lines.append(
            f"{dates[index]}：最高 {max_temps[index]}°C，最低 {min_temps[index]}°C，降雨概率 {rain_probs[index]}%"
        )
    return "\n".join(lines)


def _structured_forecast(data: dict[str, Any], city: str, days: int) -> dict[str, Any]:
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    rain_probs = daily.get("precipitation_probability_max", [])
    total_days = min(days, len(dates), len(max_temps), len(min_temps), len(rain_probs))
    rows: list[list[Any]] = []

    for index in range(total_days):
        max_temp = max_temps[index]
        rain_probability = rain_probs[index]
        condition = _condition_from_rain_probability(rain_probability)
        advice = "，".join(_weather_advice(max_temp, condition))
        rows.append(
            [
                dates[index],
                f"{max_temp}°C",
                f"{min_temps[index]}°C",
                f"{rain_probability}%",
                advice,
            ]
        )

    summary = {"城市": city, "天数": f"{total_days}天"}
    if rows:
        summary.update({"最高温": rows[0][1], "提醒": rows[0][4]})

    return {
        "ok": True,
        "kind": "weather_forecast",
        "title": f"{city}未来{total_days}天天气预报",
        "columns": ["日期", "最高温", "最低温", "降雨概率", "提醒"],
        "rows": rows,
        "summary": summary,
        "data": {
            "city": city,
            "days": total_days,
            "source_days": 7,
        },
    }


def query_weather(params: dict[str, Any]) -> dict[str, Any]:
    """
    Query a 1-7 day weather forecast.

    params = {"city": "汕头", "days": 7}
    """
    city = str(params.get("city") or "汕头")
    days = max(1, min(int(params.get("days") or 7), 7))
    lat, lon, display_city = get_coords(city)
    data = fetch_weather(lat, lon, 7)
    return _structured_forecast(data, display_city, days)
