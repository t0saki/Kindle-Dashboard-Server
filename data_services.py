import requests
import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
from lunardate import LunarDate
import holidays
import io
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def get_external_news(url):
    """Fetch news from an external JSON endpoint.
    
    Expected format: [{"title": "...", "meta": "..."}, ...]
    """
    cached = news_cache.get(f'external_{url}')
    if cached: return cached

    try:
        resp = requests.get(url, timeout=10)
        if not resp.ok:
            return []
        
        items = resp.json()
        
        # Format for display - add is_external flag
        display_stories = []
        for item in items[:10]:  # Limit to 10 items
            display_stories.append({
                "title": item.get("title", ""),
                "meta": item.get("meta", ""),
                "is_external": True
            })
        
        news_cache.set(f'external_{url}', display_stories)
        return display_stories
    except Exception as e:
        print(f"External News Error: {e}")
        return []


def get_hacker_news():
    # Check if external URL is configured
    if Config.NEWS_EXTERNAL_URL:
        return get_external_news(Config.NEWS_EXTERNAL_URL)
    
    cached = news_cache.get('hn_top10')
    if cached: return cached

    try:
        # Fetch Top and Best IDs in parallel
        with threading.Lock(): # Request is thread-safe, but let's be safe
             pass

        t_start = time.time()
        # Get IDs
        top_ids_resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=5)
        best_ids_resp = requests.get('https://hacker-news.firebaseio.com/v0/beststories.json', timeout=5)

        if not top_ids_resp.ok or not best_ids_resp.ok:
             return []
             
        top_ids = top_ids_resp.json()[:20]
        best_ids = best_ids_resp.json()[:20]
        
        # Merge and deduplicate IDs to fetch
        all_ids = list(set(top_ids + best_ids))
        
        # Check cache for individual items or fetch
        # For simplicity, just fetch all in parallel (fast enough for 20 items usually)
        
        def fetch_item(sid):
            try:
                return requests.get(f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=5).json()
            except:
                return None

        items_map = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_sid = {executor.submit(fetch_item, sid): sid for sid in all_ids}
            for future in as_completed(future_to_sid):
                item = future.result()
                if item and not item.get('deleted') and not item.get('dead'):
                    items_map[item['id']] = item

        # Identify Breaking News
        # Strategy: From Top Stories, find high velocity items
        breaking_candidates = []
        now = time.time()
        
        for sid in top_ids:
            item = items_map.get(sid)
            if not item: continue
            
            score = item.get('score', 0)
            descendants = item.get('descendants', 0)
            title = item.get('title', "")
            item_time = item.get('time', now)
            age_hours = (now - item_time) / 3600
            
            # 1. 硬过滤：只看12小时内的，且硬硬性分数 > 50 (排除刚发几分钟的噪音)
            if age_hours > 12 or score < 50:
                continue
            
            # 2. 核心公式修正 (v3.0)
            # 降低评论权重：(Score * 1.0) + (Comments * 0.2)
            # 理由：大新闻靠赞，吵架贴靠评论。我们想要前者。
            impact = score + (descendants * 0.2)
            
            # 3. 语义权重 (Semantic Weighting) 
            semantic_modifier = 1.0
            title_lower = title.lower()
            
            # A. 惩罚项 (Subjectivity Penalty) - 过滤 "我觉得..." "微软逼我..."
            # 常见的个人叙事词
            subjective_words = [" i ", " me ", " my ", " how i ", " why i ", "forced me"]
            if any(w in title_lower for w in subjective_words):
                semantic_modifier *= 0.4  # 狠一点，直接打4折
            
            # B. 奖励项 (Event Boost) - 奖励 "发布" "新版本" "重大事故"
            event_words = [
                "release", "launch", "announce", "available", "open source", 
                "v1.", "v2.", "v3.", "v4.", "gpt", "claude", "llama", "deepseek",
                "cve-", "zero-day", "hack", "outage"
            ]
            if any(w in title_lower for w in event_words):
                semantic_modifier *= 1.5
            
            # 4. 计算 Velocity
            # 分母改为 (Age + 1.5)^1.8，增加初始阻尼，防止刚发10分钟只有5个赞的帖子冲上来
            velocity = (impact * semantic_modifier) / math.pow(age_hours + 1.5, 1.8)
            
            item['velocity'] = velocity
            breaking_candidates.append(item)
            
        # Sort top stories by velocity
        breaking_candidates.sort(key=lambda x: x['velocity'], reverse=True)
        
        # Best Stories (Static Quality)
        best_candidates = []
        for sid in best_ids:
            item = items_map.get(sid)
            if item:
                best_candidates.append(item)
        
        # Construct Final List
        final_list = []
        seen_ids = set()
        
        # 1. Pick the #1 Breaking News if it meets a Threshold
        # Threshold: Needs to be actually "Breaking". 
        # A 21 point story in 1 hour -> 21 / 1^1.8 = 21.
        # A 500 point story in 10 hours -> 500 / 10^1.8 (~63) = 7.9. 
        # So "Flash" stories win. 
        # Let's require a minimum velocity to displace the #1 Best Story.
        
        has_breaking = False
        if breaking_candidates:
            breaker = breaking_candidates[0]
            # Velocity Threshold: Ensure it's not just "the newest of the junk"
            # 50 points in 1 hour = 50 velocity.
            # 100 points in 2 hours = 100/3.4 = 29 velocity.
            # Let's set threshold around 30.
            if breaker['velocity'] > 30:
                breaker['is_breaking'] = True
                final_list.append(breaker)
                seen_ids.add(breaker['id'])
                has_breaking = True
                
        # 2. Fill the rest with Best Stories
        for item in best_candidates:
            if len(final_list) >= 10: break
            if item['id'] not in seen_ids:
                item['is_breaking'] = False
                final_list.append(item)
                seen_ids.add(item['id'])
                
        # 3. If still not 5 (and we didn't use a breaker, or best list was short), fill
        if len(final_list) < 10:
             # Try remaining filtered breaking candidates
             for item in breaking_candidates:
                if len(final_list) >= 10: break
                if item['id'] not in seen_ids:
                    item['is_breaking'] = False # Only #1 gets the breaking status visual
                    final_list.append(item)
                    seen_ids.add(item['id'])
             
             # If STILL not 5, fallback to just Top Stories sorted by score
             if len(final_list) < 10:
                  sorted_top = sorted([items_map[sid] for sid in top_ids if sid in items_map], key=lambda x: x.get('score', 0), reverse=True)
                  for item in sorted_top:
                      if len(final_list) >= 10: break
                      if item['id'] not in seen_ids:
                          item['is_breaking'] = False
                          final_list.append(item)
                          seen_ids.add(item['id'])
        
        # Format for display
        display_stories = []
        for item in final_list:
            display_stories.append({
                "title": item.get('title'),
                "score": item.get('score'),
                "url": item.get('url', ''),
                "id": item.get('id'),
                "velocity": item.get('velocity', 0), # For debugging/verification
                "time": item.get('time'), # For debugging
                "is_breaking": item.get('is_breaking', False),
                "is_external": False  # Flag to indicate HN source
            })
            
        news_cache.set('hn_top10', display_stories)
        return display_stories

    except Exception as e:
        print(f"HN Error: {e}")
        import traceback
        traceback.print_exc()
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
    now = datetime.datetime.now(ZoneInfo(Config.TIMEZONE))
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
