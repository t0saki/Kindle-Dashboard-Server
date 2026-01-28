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

from config import Config

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
weather_cache = SimpleCache(Config.CACHE_TTL_WEATHER)
finance_cache = SimpleCache(Config.CACHE_TTL_FINANCE) 
news_cache = SimpleCache(Config.CACHE_TTL_NEWS)

# --- Helpers ---
def map_wmo_to_text(code):
    # WMO Weather interpretation codes (WW)
    # ... (same codes) ...
    
    # Chinese Mapping
    mapping_cn = {
        0: ("晴朗", "01d"), 1: ("多云", "02d"), 2: ("多云", "02d"), 3: ("阴天", "04d"),
        45: ("有雾", "50d"), 48: ("有雾", "50d"), 51: ("毛毛雨", "09d"), 53: ("毛毛雨", "09d"), 55: ("毛毛雨", "09d"),
        56: ("冻雨", "13d"), 57: ("冻雨", "13d"), 61: ("小雨", "10d"), 63: ("中雨", "10d"), 65: ("大雨", "10d"),
        66: ("冻雨", "13d"), 67: ("冻雨", "13d"), 71: ("小雪", "13d"), 73: ("中雪", "13d"), 75: ("大雪", "13d"),
        77: ("雪粒", "13d"), 80: ("阵雨", "09d"), 81: ("阵雨", "09d"), 82: ("暴雨", "09d"), 
        85: ("阵雪", "13d"), 86: ("阵雪", "13d"), 95: ("雷雨", "11d"), 96: ("雷雨", "11d"), 99: ("雷雨", "11d")
    }
    
    # English Mapping (Fallback/Alternative)
    mapping_en = {
        0: ("Clear", "01d"), 1: ("Cloudy", "02d"), 2: ("Cloudy", "02d"), 3: ("Overcast", "04d"),
        45: ("Fog", "50d"), 48: ("Fog", "50d"), 51: ("Drizzle", "09d"), 53: ("Drizzle", "09d"), 55: ("Drizzle", "09d"),
        56: ("Frz Driz", "13d"), 57: ("Frz Driz", "13d"), 61: ("Rain", "10d"), 63: ("Rain", "10d"), 65: ("Hvy Rain", "10d"),
        66: ("Frz Rain", "13d"), 67: ("Frz Rain", "13d"), 71: ("Snow", "13d"), 73: ("Snow", "13d"), 75: ("Hvy Snow", "13d"),
        77: ("Snow Grn", "13d"), 80: ("Showers", "09d"), 81: ("Showers", "09d"), 82: ("Violent", "09d"), 
        85: ("Snow Shw", "13d"), 86: ("Snow Shw", "13d"), 95: ("T-Storm", "11d"), 96: ("Hail", "11d"), 99: ("Hail", "11d")
    }

    if Config.LANGUAGE == 'EN':
        return mapping_en.get(code, ("Unknown", "02d"))
    else:
        return mapping_cn.get(code, ("未知", "02d"))

def get_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

# --- Data Fetchers ---

def get_location_name(lat, lon):
    return Config.CITY_NAME

def get_weather(lat=Config.LATITUDE, lon=Config.LONGITUDE):
    cached = weather_cache.get(f'weather_data_{lat}_{lon}')
    if cached: return cached

    weather_data = {
        "location": {"name": get_location_name(lat, lon)}, 
        "current": {
            "temp": "--", 
            "humidity": "--", 
            "desc": "N/A", 
            "icon": "", 
            "rain_chance": "--",
            "uv": "--",
            "aqi": "--",
            "aqi_level": "未知" if Config.LANGUAGE != 'EN' else "Unknown"
        },
        "forecast": [],
        "tomorrow": {"label": "", "icon": "", "temp": "", "desc": ""}
    }

    try:
        # Open-Meteo Weather API with UV index
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,uv_index",
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,uv_index_max",
            "timezone": Config.TIMEZONE
        }
        
        resp = requests.get(url, params=params, timeout=10).json()
        
        # 1. Current Weather
        current = resp.get("current", {})
        temp = round(current.get("temperature_2m", 0))
        hum = current.get("relative_humidity_2m", 0)
        code = current.get("weather_code", 0)
        uv_index = current.get("uv_index", 0)
        desc_text, icon = map_wmo_to_text(code)
        
        weather_data['current']['temp'] = temp
        weather_data['current']['humidity'] = f"{hum}%"
        weather_data['current']['desc'] = desc_text
        weather_data['current']['icon'] = icon
        weather_data['current']['uv'] = round(uv_index, 1) if uv_index else 0
        
        # Get AQI from Open-Meteo Air Quality API
        try:
            aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            aqi_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "pm2_5,pm10,us_aqi",
                "timezone": Config.TIMEZONE
            }
            aqi_resp = requests.get(aqi_url, params=aqi_params, timeout=10).json()
            aqi_current = aqi_resp.get("current", {})
            us_aqi = aqi_current.get("us_aqi", 0)
            weather_data['current']['aqi'] = us_aqi if us_aqi else "--"
            
            # AQI level mapping (US EPA standard)
            if us_aqi and us_aqi != "--":
                if Config.LANGUAGE == 'EN':
                    # English AQI Levels
                    if us_aqi <= 50: level = "Good"
                    elif us_aqi <= 100: level = "Fair"
                    elif us_aqi <= 150: level = "Light"
                    elif us_aqi <= 200: level = "Mid"
                    elif us_aqi <= 300: level = "Bad"
                    else: level = "Hazard"
                else:
                    # Chinese AQI Levels
                    if us_aqi <= 50: level = "优"
                    elif us_aqi <= 100: level = "良"
                    elif us_aqi <= 150: level = "轻度"
                    elif us_aqi <= 200: level = "中度"
                    elif us_aqi <= 300: level = "重度"
                    else: level = "严重"
                weather_data['current']['aqi_level'] = level

        except Exception as e:
            print(f"AQI Error: {e}")
        
        # Rain chance
        hourly = resp.get("hourly", {})
        precip_probs = hourly.get("precipitation_probability", [])
        current_rain_prob = precip_probs[0] if precip_probs else 0
        weather_data['current']['rain_chance'] = f"{current_rain_prob}%"

        # 2. Hourly Forecast (Next 3 hours + Smart Logic)
        current_time_str = current.get("time")
        now_dt = datetime.datetime.fromisoformat(current_time_str)
        
        times = hourly.get("time", []) 
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        
        def get_data_for_time(target_dt):
            for i, t_str in enumerate(times):
                t_dt = datetime.datetime.fromisoformat(t_str)
                if t_dt.year == target_dt.year and t_dt.month == target_dt.month and t_dt.day == target_dt.day and t_dt.hour == target_dt.hour:
                    return i
            return -1

        forecast_items = []
        targets = []
        
        # Slot 1
        t1 = now_dt + datetime.timedelta(hours=1)
        t1 = t1.replace(minute=0, second=0, microsecond=0)
        targets.append(t1)
        
        # Slot 2
        t2 = now_dt + datetime.timedelta(hours=2)
        t2 = t2.replace(minute=0, second=0, microsecond=0)
        targets.append(t2)
        
        # Slot 3 (Smart)
        t3_candidate = now_dt + datetime.timedelta(hours=3)
        t3_candidate = t3_candidate.replace(minute=0, second=0, microsecond=0)
        
        # Configurable work hours
        work_start = t3_candidate.replace(hour=Config.WORK_START_HOUR, minute=0, second=0, microsecond=0)
        work_end = t3_candidate.replace(hour=Config.WORK_END_HOUR, minute=0, second=0, microsecond=0)
        
        if t3_candidate < work_start:
            t3 = work_start
        elif t3_candidate < work_end:
            t3 = work_end
        else:
            t3 = t3_candidate
            
        targets.append(t3)
        
        for tgt in targets:
            idx = get_data_for_time(tgt)
            if idx != -1:
                d_desc, icon = map_wmo_to_text(codes[idx])
                label = tgt.strftime("%H:00")
                forecast_items.append({
                    "label": label,
                    "icon": icon,
                    "temp": round(temps[idx]),
                    "desc": d_desc
                })
            else:
                forecast_items.append({
                    "label": tgt.strftime("%H:00"),
                    "icon": "02d",
                    "temp": "--",
                    "desc": "N/A"
                })
                
        weather_data['forecast'] = forecast_items

        # 3. Tomorrow Forecast
        daily = resp.get("daily", {})
        
        if len(daily.get("time", [])) >= 1:
            t0_max = round(daily['temperature_2m_max'][0])
            t0_min = round(daily['temperature_2m_min'][0])
            weather_data['current']['high_low'] = f"{t0_max}° / {t0_min}°"
        else:
             weather_data['current']['high_low'] = ""

        if len(daily.get("time", [])) >= 2:
            t_max = round(daily['temperature_2m_max'][1])
            t_min = round(daily['temperature_2m_min'][1])
            d_code = daily['weather_code'][1]
            d_desc, d_icon = map_wmo_to_text(d_code)
            
            label_tmr = "Tomorrow" if Config.LANGUAGE == 'EN' else "明天"
            
            weather_data['tomorrow'] = {
                "label": label_tmr,
                "icon": d_icon,
                "temp": f"{t_max}/{t_min}°",
                "desc": d_desc
            }

        # 4. Weather Alert
        alert_msg = ""
        upcoming_alerts = []
        try:
           now_hour_idx = -1
           for i, t_str in enumerate(times):
               t_dt = datetime.datetime.fromisoformat(t_str)
               if t_dt.hour == now_dt.hour and t_dt.day == now_dt.day:
                   now_hour_idx = i
                   break
           
           if now_hour_idx != -1:
               max_hours = min(now_hour_idx + 49, len(times))
               for i in range(now_hour_idx + 1, max_hours):
                   t_dt = datetime.datetime.fromisoformat(times[i])
                   hours_from_now = i - now_hour_idx
                   code = codes[i]
                   weather_type = None
                   
                   # Simple alert logic
                   if code in [61, 63, 65, 80, 81, 82, 66, 67]:
                       weather_type = "雨" if Config.LANGUAGE != 'EN' else "Rain"
                   elif code in [71, 73, 75, 85, 86, 77]:
                       weather_type = "雪" if Config.LANGUAGE != 'EN' else "Snow"
                   elif code in [95, 96, 99]:
                       weather_type = "雷雨" if Config.LANGUAGE != 'EN' else "T-Storm"
                   elif code in [51, 53, 55]:
                       weather_type = "小雨" if Config.LANGUAGE != 'EN' else "Drizzle"
                   
                   if weather_type:
                       upcoming_alerts.append((hours_from_now, weather_type, t_dt))
               
               if upcoming_alerts:
                   first_alert = upcoming_alerts[0]
                   hours, wtype, alert_dt = first_alert
                   
                   label_today = "今天" if Config.LANGUAGE != 'EN' else "Today"
                   label_tmr = "明天" if Config.LANGUAGE != 'EN' else "Tmrrw"
                   
                   if hours <= 3:
                       if Config.LANGUAGE == 'EN':
                           alert_msg = f"{wtype} in {hours}h"
                       else:
                           alert_msg = f"{hours}H后有{wtype}"
                   elif alert_dt.day == now_dt.day:
                       if Config.LANGUAGE == 'EN':
                           alert_msg = f"{wtype} at {alert_dt.hour}:00"
                       else:
                           alert_msg = f"{label_today}{alert_dt.hour}点有{wtype}"
                   elif alert_dt.day == now_dt.day + 1:
                       if Config.LANGUAGE == 'EN':
                           alert_msg = f"{wtype} tom. at {alert_dt.hour}:00"
                       else:
                           alert_msg = f"{label_tmr}{alert_dt.hour}点有{wtype}"
                   else:
                       if Config.LANGUAGE == 'EN':
                           alert_msg = f"{wtype} in {hours}h"
                       else:
                           alert_msg = f"{hours}H后有{wtype}"
        except Exception as e:
            print(f"Alert Logic Error: {e}")

        weather_data['current']['alert'] = alert_msg
        weather_data['current']['has_warning'] = False 
        weather_data['current']['upcoming_alerts'] = upcoming_alerts[:5]
            
        weather_cache.set(f'weather_data_{lat}_{lon}', weather_data)
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

yf_lock = threading.Lock()

def generate_sparkline(ticker_symbol):
    cache_key = f"spark_{ticker_symbol}"
    cached = finance_cache.get(cache_key)
    if cached: return cached

    try:
        with yf_lock:
             hist = yf.download(ticker_symbol, period="5d", interval="60m", progress=False)
        
        if hist is None or hist.empty:
            return None, "--", 0
            
        try:
             prices = hist['Close'].values.flatten()
        except KeyError:
             if 'Adj Close' in hist:
                  prices = hist['Adj Close'].values.flatten()
             else:
                  return None, "--", 0

        if len(prices) == 0: return None, "--", 0

        current_price = prices[-1]
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
    
    if Config.LANGUAGE == 'EN':
         lunar_str = f"Lunar {lunar.month}/{lunar.day}"
    else:
         lunar_str = f"农历 {lunar.month}月{lunar.day}日"
    
    # Use config country
    try:
        if hasattr(holidays, Config.HOLIDAY_COUNTRY):
            country_holidays = getattr(holidays, Config.HOLIDAY_COUNTRY)(years=now.year)
        else:
            # Fallback to SG
            country_holidays = holidays.SG(years=now.year)
    except:
        country_holidays = holidays.SG(years=now.year)
        
    today_holiday = country_holidays.get(now.date())
    
    next_date = now.date() + datetime.timedelta(days=1)
    next_non_working = None
    
    for _ in range(30):
        is_weekend = next_date.weekday() >= 5
        is_holiday = country_holidays.get(next_date)
        
        if is_weekend or is_holiday:
            info = is_holiday if is_holiday else ("Saturday" if next_date.weekday() == 5 else "Sunday")
            weekday_en = next_date.strftime("%A")
            
            if Config.LANGUAGE == 'EN':
                label = info
            else:
                # Basic translation for generic weekends if needed, mostly holiday names are in their lang
                # If holidays lib returns English for SG holidays, might need translation map but out of scope?
                # User asked "holiday origin", allowing different countries. Holidays lib usually returns local language or english.
                # Let's assume the library return is acceptable or we display it as is.
                if info == "Saturday": label = "周六"
                elif info == "Sunday": label = "周日"
                else: label = info # Use provided name
            
            next_non_working = {
                "date": next_date.strftime("%m-%d"),
                "name": label,
                "days_away": (next_date - now.date()).days
            }
            break
        next_date += datetime.timedelta(days=1)

    weekday_en = now.strftime("%A")
    if Config.LANGUAGE == 'EN':
        weekday_disp = weekday_en
    else:
        weekday_disp = WEEKDAYS_CN.get(weekday_en, weekday_en)
        
    return {
        "date_str": now.strftime("%Y-%m-%d"),
        "weekday": weekday_disp,
        "lunar": lunar_str,
        "holiday": today_holiday,
        "next_non_working": next_non_working
    }
