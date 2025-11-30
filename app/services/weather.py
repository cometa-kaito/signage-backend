import httpx

def get_weather_data(latitude: float, longitude: float) -> str:
    """
    指定座標の現在の天気を取得して文字列で返す
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "timezone": "Asia/Tokyo"
        }
        # 同期的に取得
        resp = httpx.get(url, params=params, timeout=5.0)
        data = resp.json()
        
        current = data.get("current_weather", {})
        temp = current.get("temperature")
        weather_code = current.get("weathercode")
        
        weather_map = {
            0: "晴れ", 1: "晴れ", 2: "曇り", 3: "曇り",
            45: "霧", 48: "霧",
            51: "小雨", 53: "小雨", 55: "小雨",
            61: "雨", 63: "雨", 65: "雨",
            80: "雨", 81: "雨", 82: "雨",
            95: "雷雨"
        }
        status = weather_map.get(weather_code, "不明")
        
        return f"【現在の天気】\n{status}\n気温: {temp}℃"
    except Exception as e:
        print(f"Weather API Error: {e}")
        return "天気情報取得不可"