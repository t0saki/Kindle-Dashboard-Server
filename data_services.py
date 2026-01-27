import requests
import datetime
import yfinance as yf
from lunardate import LunarDate
import holidays
import io
import base64
import matplotlib
matplotlib.use('Agg') # Non-interactive mode
from matplotlib.figure import Figure
import time
import threading
import math
import reverse_geocoder as rg

# --- Configuration (Externalizable) ---
DEFAULT_LAT = 1.27710
DEFAULT_LON = 103.84610

# --- Caching Utility ---
class SimpleCache:
    def __init__(self, ttl_seconds):
        self.ttl = ttl_seconds
        self.cache = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            item = self.cache.get(key)
            if item:
                val, timestamp = item
                if time.time() - timestamp < self.ttl:
                    return val
                else:
                    del self.cache[key]
        return None

    def set(self, key, value):
        with self.lock:
            self.cache[key] = (value, time.time())

# Caches
weather_cache = SimpleCache(600)
finance_cache = SimpleCache(900) 
news_cache = SimpleCache(300)

# --- Helpers ---
def map_wmo_to_chinese(code):
    # WMO Weather interpretation codes (WW)
    # 0: Clear sky
    # 1, 2, 3: Mainly clear, partly cloudy, and overcast
    # 45, 48: Fog and depositing rime fog
    # 51, 53, 55: Drizzle: Light, moderate, and dense intensity
    # 56, 57: Freezing Drizzle: Light and dense intensity
    # 61, 63, 65: Rain: Slight, moderate and heavy intensity
    # 66, 67: Freezing Rain: Light and heavy intensity
    # 71, 73, 75: Snow fall: Slight, moderate, and heavy intensity
    # 77: Snow grains
    # 80, 81, 82: Rain showers: Slight, moderate, and violent
    # 85, 86: Snow showers slight and heavy
    # 95 *: Thunderstorm: Slight or moderate
    # 96, 99 *: Thunderstorm with slight and heavy hail
    
    mapping = {
        0: ("晴朗", "01d"),
        1: ("多云", "02d"),
        2: ("多云", "02d"),
        3: ("阴天", "04d"),
        45: ("有雾", "50d"),
        48: ("有雾", "50d"),
        51: ("毛毛雨", "09d"),
        53: ("毛毛雨", "09d"),
        55: ("毛毛雨", "09d"),
        56: ("冻雨", "13d"),
        57: ("冻雨", "13d"),
        61: ("小雨", "10d"),
        63: ("中雨", "10d"),
        65: ("大雨", "10d"),
        66: ("冻雨", "13d"),
        67: ("冻雨", "13d"),
        71: ("小雪", "13d"),
        73: ("中雪", "13d"),
        75: ("大雪", "13d"),
        77: ("雪粒", "13d"),
        80: ("阵雨", "09d"),
        81: ("阵雨", "09d"),
        82: ("暴雨", "09d"),
        85: ("阵雪", "13d"),
        86: ("阵雪", "13d"),
        95: ("雷雨", "11d"),
        96: ("雷雨", "11d"),
        99: ("雷雨", "11d")
    }
    return mapping.get(code, ("未知", "02d"))

def get_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

# --- Data Fetchers ---

def get_location_name(lat, lon):
    # 这一步是毫秒级的，且完全离线
    # mode=1 (search for nearest city)
    results = rg.search((lat, lon), mode=1) 
    
    if results:
        # result example: 
        # [{'lat': '1.35208', 'lon': '103.81984', 'name': 'Singapore', 'admin1': '', 'admin2': '', 'cc': 'SG'}]
        # 注意：rg 默认返回英文。如果你强依赖中文，且位置固定，建议直接 Hardcode 或做一个简单的映射。
        city = results[0].get('name', '未知地点')
        country = results[0].get('cc', '未知地点')
        
        return city or country
        
    return "未知地点"

def get_weather(lat=DEFAULT_LAT, lon=DEFAULT_LON):
    cached = weather_cache.get('weather_data_v2')
    if cached: return cached

    weather_data = {
        "location": {"name": "Loading..."},
        "current": {"temp": "--", "humidity": "--", "desc": "N/A", "icon": "", "rain_chance": "--"},
        "forecast": [],
        "tomorrow": {"label": "", "icon": "", "temp": "", "desc": ""}
    }

    try:
        # 0. Get Location Name
        loc_name = get_location_name(lat, lon)
        weather_data['location']['name'] = loc_name
        
        # Open-Meteo API
        # current=temperature_2m,relative_humidity_2m,weather_code
        # hourly=temperature_2m,weather_code (for next 3 hours)
        # daily=weather_code,temperature_2m_max,temperature_2m_min (for tomorrow)
        # timezone=Asia/Singapore
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "Asia/Singapore"
        }
        
        resp = requests.get(url, params=params, timeout=10).json()
        
        # 1. Current Weather
        current = resp.get("current", {})
        temp = round(current.get("temperature_2m", 0))
        hum = current.get("relative_humidity_2m", 0)
        code = current.get("weather_code", 0)
        desc_cn, icon = map_wmo_to_chinese(code)
        
        weather_data['current']['temp'] = temp
        weather_data['current']['humidity'] = hum
        weather_data['current']['desc'] = desc_cn
        weather_data['current']['icon'] = icon
        
        # Rain chance mapping from code is tricky, using raw daily prob or intuitive from code
        # Let's check next hour precip prob
        hourly = resp.get("hourly", {})
        precip_probs = hourly.get("precipitation_probability", [])
        # Assume first element is current hour or close to it
        current_rain_prob = precip_probs[0] if precip_probs else 0
        weather_data['current']['rain_chance'] = f"{current_rain_prob}%"

        # 2. Hourly Forecast (Next 3 hours + Smart Logic)
        # Strategy:
        # Slot 1: Now + 1h
        # Slot 2: Now + 2h
        # Slot 3: "Commute/Work" logic.
        #    If (Now + 3h) < 10:00 --> Show 10:00
        #    Else if (Now + 3h) < 18:00 --> Show 18:00
        #    Else --> Show Now + 3h
        
        current_time_str = current.get("time") # e.g. "2026-01-28T04:15"
        now_dt = datetime.datetime.fromisoformat(current_time_str)
        
        times = hourly.get("time", []) # Strings
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        
        # Helper to find data for a specific hour
        def get_data_for_time(target_dt):
            best_idx = -1
            min_diff = float('inf')
            
            for i, t_str in enumerate(times):
                t_dt = datetime.datetime.fromisoformat(t_str)
                # We want exact match or closest future match
                # Since list is sorted, we can look for exact matches usually
                if t_dt.year == target_dt.year and t_dt.month == target_dt.month and t_dt.day == target_dt.day and t_dt.hour == target_dt.hour:
                    return i
            return -1

        forecast_items = []
        
        # Calculate target times
        # Note: We use the server time as reference or the API provided current time
        # The API time is "current", so we base off that.
        
        targets = []
        # Slot 1
        t1 = now_dt + datetime.timedelta(hours=1)
        # Round to nearest hour (flooring essentially based on string parse 00 minutes usually)
        t1 = t1.replace(minute=0, second=0, microsecond=0)
        targets.append(t1)
        
        # Slot 2
        t2 = now_dt + datetime.timedelta(hours=2)
        t2 = t2.replace(minute=0, second=0, microsecond=0)
        targets.append(t2)
        
        # Slot 3 (Smart)
        t3_candidate = now_dt + datetime.timedelta(hours=3)
        t3_candidate = t3_candidate.replace(minute=0, second=0, microsecond=0)
        
        # Construct comparison times for today
        work_start = t3_candidate.replace(hour=10, minute=0, second=0, microsecond=0)
        work_end = t3_candidate.replace(hour=18, minute=0, second=0, microsecond=0)
        
        if t3_candidate < work_start:
            t3 = work_start
        elif t3_candidate < work_end:
            t3 = work_end
        else:
            t3 = t3_candidate
            
        targets.append(t3)
        
        # Fetch Data
        for tgt in targets:
            idx = get_data_for_time(tgt)
            if idx != -1:
                desc_cn, icon = map_wmo_to_chinese(codes[idx])
                label = tgt.strftime("%H:00")
                forecast_items.append({
                    "label": label,
                    "icon": icon,
                    "temp": round(temps[idx]),
                    "desc": desc_cn
                })
            else:
                # Fallback if specific time not found (e.g. end of forecast range)
                forecast_items.append({
                    "label": tgt.strftime("%H:00"),
                    "icon": "02d",
                    "temp": "--",
                    "desc": "N/A"
                })
                
        weather_data['forecast'] = forecast_items

        # 3. Tomorrow Forecast & Today's High/Low/Alerts
        daily = resp.get("daily", {})
        # daily['time'] is ["2026-01-28", "2026-01-29", ...]
        
        # Today's Data (Index 0)
        if len(daily.get("time", [])) >= 1:
            t0_max = round(daily['temperature_2m_max'][0])
            t0_min = round(daily['temperature_2m_min'][0])
            weather_data['current']['high_low'] = f"{t0_max}° / {t0_min}°"
        else:
             weather_data['current']['high_low'] = ""

        # Tomorrow's Data (Index 1)
        if len(daily.get("time", [])) >= 2:
            t_max = round(daily['temperature_2m_max'][1])
            t_min = round(daily['temperature_2m_min'][1])
            d_code = daily['weather_code'][1]
            d_desc, d_icon = map_wmo_to_chinese(d_code)
            
            weather_data['tomorrow'] = {
                "label": "明天", # Hardcoded Chinese
                "icon": d_icon,
                "temp": f"{t_max}/{t_min}",
                "desc": d_desc
            }

        # 4. Today's Weather Alert (Scan hourly for rain/snow from NOW until Midnight)
        alert_msg = ""
        try:
           # Find index of current hour
           now_hour_idx = -1
           for i, t_str in enumerate(times):
               t_dt = datetime.datetime.fromisoformat(t_str)
               if t_dt.hour == now_dt.hour and t_dt.day == now_dt.day:
                   now_hour_idx = i
                   break
           
           if now_hour_idx != -1:
               # Scan until end of today
               found_alert = False
               for i in range(now_hour_idx + 1, len(times)):
                   t_dt = datetime.datetime.fromisoformat(times[i])
                   if t_dt.day != now_dt.day: break # Stop if next day
                   
                   code = codes[i]
                   # Rain/Snow/Thunder codes
                   # Rain: 61,63,65, 80,81,82
                   # Snow: 71,73,75, 85,86
                   # Thunder: 95,96,99
                   # Freezing Rain: 66,67
                   if code in [61, 63, 65, 80, 81, 82, 66, 67]:
                       alert_msg = f"{t_dt.hour}点有雨"
                       found_alert = True
                   elif code in [71, 73, 75, 85, 86, 77]:
                       alert_msg = f"{t_dt.hour}点有雪"
                       found_alert = True
                   elif code in [95, 96, 99]:
                       alert_msg = f"{t_dt.hour}点雷雨"
                       found_alert = True
                   
                   if found_alert: break
        except Exception as e:
            print(f"Alert Logic Error: {e}")

        weather_data['current']['alert'] = alert_msg
            
        weather_cache.set('weather_data_v2', weather_data)
        return weather_data

    except Exception as e:
        print(f"Weather Error: {e}")
        return weather_data

def get_hacker_news():
    cached = news_cache.get('hn_top5')
    if cached: return cached

    try:
        top_ids = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10).json()[:5]
        stories = []
        for sid in top_ids:
            item = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=10).json()
            stories.append({
                "title": item.get('title'),
                "score": item.get('score'),
                "url": item.get('url', '')
            })
        news_cache.set('hn_top5', stories)
        return stories
    except Exception as e:
        print(f"HN Error: {e}")
        return []


# Global lock for yfinance as it is not thread-safe for parallel downloads
yf_lock = threading.Lock()

def generate_sparkline(ticker_symbol):
    cache_key = f"spark_{ticker_symbol}"
    cached = finance_cache.get(cache_key)
    if cached: return cached

    try:
        # Serializing yfinance calls to prevent data corruption/race conditions
        with yf_lock:
             hist = yf.download(ticker_symbol, period="5d", interval="60m", progress=False)
        
        if hist is None or hist.empty:
            return None, "--", 0
            
        # yf.download returns a MultiIndex columns if multiple tickers, but we ask for one.
        # However, check structure. Usually it's just 'Close' or ('Close', 'TICKER').
        try:
             prices = hist['Close'].values.flatten() # Flatten in case of 2D array
        except KeyError:
             if 'Adj Close' in hist:
                  prices = hist['Adj Close'].values.flatten()
             else:
                  return None, "--", 0

        if len(prices) == 0: return None, "--", 0

        current_price = prices[-1]
        
        # Calculate change
        # Try to get previous close from first point of our 5d fetch if simple
        prev_close = prices[0]
        
        percent_change = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0

        fig = Figure(figsize=(4, 1), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(prices, color='black', linewidth=3)
        ax.axis('off')
        
        img = io.BytesIO()
        fig.savefig(img, format='png', transparent=True, bbox_inches='tight', pad_inches=0)
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        
        result = (plot_url, current_price, percent_change)
        finance_cache.set(cache_key, result)
        return result
    except Exception as e:
        print(f"Finance Error {ticker_symbol}: {e}")
        return None, "--", 0



WEEKDAYS_CN = {
    "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
    "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六",
    "Sunday": "星期日"
}

def get_calendar_info():
    now = datetime.datetime.now()
    lunar = LunarDate.fromSolarDate(now.year, now.month, now.day)
    lunar_str = f"农历 {lunar.month}月{lunar.day}日"
    
    sg_holidays = holidays.SG(years=now.year)
    today_holiday = sg_holidays.get(now.date())
    
    next_date = now.date() + datetime.timedelta(days=1)
    next_non_working = None
    
    for _ in range(30):
        is_weekend = next_date.weekday() >= 5
        is_holiday = sg_holidays.get(next_date)
        
        if is_weekend or is_holiday:
            info = is_holiday if is_holiday else ("Saturday" if next_date.weekday() == 5 else "Sunday")
            weekday_en = next_date.strftime("%A")
            label = info
            
            next_non_working = {
                "date": next_date.strftime("%m-%d"),
                "name": label,
                "days_away": (next_date - now.date()).days
            }
            break
        next_date += datetime.timedelta(days=1)

    weekday_en = now.strftime("%A")
    return {
        "date_str": now.strftime("%Y-%m-%d"),
        "weekday": WEEKDAYS_CN.get(weekday_en, weekday_en),
        "lunar": lunar_str,
        "holiday": today_holiday,
        "next_non_working": next_non_working
    }
