from flask import Flask, render_template, send_file
import datetime
import time
import io
import hashlib
from concurrent.futures import ThreadPoolExecutor
# Import from our new data layer
from data_services import get_weather, get_calendar_info, get_hacker_news, generate_sparkline

executor = ThreadPoolExecutor(max_workers=20)

app = Flask(__name__)

# --- Configuration (Externalizable) ---
# ... (Config can stay here if app specific, or move to config.py later)

# Simple in-memory cache for the /render endpoint
# Format: {"data": bytes, "timestamp": float}
_render_cache = {"data": None, "timestamp": 0}
CACHE_DURATION = 60 # 1 minute

@app.route('/dashboard')
def dashboard():
    # Submit Data Fetch Tasks in Parallel
    future_weather = executor.submit(get_weather)
    future_calendar = executor.submit(get_calendar_info)
    future_news = executor.submit(get_hacker_news)

    # Finance Tasks
    tickers = [
        {"symbol": "SGDCNY=X", "name": "SGD/CNY"},
        {"symbol": "CNY=X", "name": "USD/CNY"}, 
        {"symbol": "BTC-USD", "name": "BTC/USD"}
    ]
    future_finance = [(t, executor.submit(generate_sparkline, t['symbol'])) for t in tickers]

    # Gather Results
    try:
        weather = future_weather.result(timeout=15)
    except Exception as e:
        print(f"Weather Timeout: {e}")
        weather = {"current": {"temp": "--"}, "forecast": [], "tomorrow": {}}

    try:
        calendar = future_calendar.result(timeout=5)
    except:
        calendar = {"date_str": "--", "weekday": "--", "lunar": "--"}

    try:
        news = future_news.result(timeout=15)
    except:
        news = []

    finance_data = []
    for t, future in future_finance:
        try:
            chart, price, change = future.result(timeout=15)
        except:
             chart, price, change = None, "--", 0
             
        # Formatting Price
        if price == "--":
            p_str = "--"
        elif "BTC" in t['name']:
            p_str = f"{price:,.0f}" 
        else:
             try:
                p_str = f"{price:.4f}"
             except: p_str = str(price)

        finance_data.append({
            "name": t['name'],
            "price": p_str,
            "change": change,
            "chart": chart
        })
    
    return render_template('dashboard.html', 
                           weather=weather, 
                           finance=finance_data, 
                           calendar=calendar, 
                           news=news,
                           updated_at=datetime.datetime.now().strftime("%H:%M"))

@app.route('/render')
@app.route('/render.png')
def render_dashboard():
    from renderer import render_dashboard_to_bytes
    global _render_cache
    
    current_time = time.time()
    
    def prepare_response(data, timestamp):
        response = send_file(
            io.BytesIO(data), 
            mimetype='image/png',
            as_attachment=False, 
            download_name='dashboard.png'
        )
        # Cloudflare loves extensions and explicit CDN cache headers
        # s-maxage is for shared caches (like CF)
        response.headers['Cache-Control'] = f'public, max-age={CACHE_DURATION}, s-maxage={CACHE_DURATION}'
        
        # Last-Modified helps CF with validation
        last_modified = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
        response.headers['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # ETag for strong validation
        etag = hashlib.md5(data).hexdigest()
        response.set_etag(etag)
        
        return response

    # 1. Check if we have a valid cache
    if _render_cache["data"] and (current_time - _render_cache["timestamp"] < CACHE_DURATION):
        print(f"Returning cached image (age: {int(current_time - _render_cache['timestamp'])}s)")
        return prepare_response(_render_cache["data"], _render_cache["timestamp"])

    # 2. If not cached, render it
    port = 5000 
    dashboard_url = f"http://127.0.0.1:{port}/dashboard"
    
    try:
        image_io = render_dashboard_to_bytes(dashboard_url)
        # Read the io.BytesIO content to store it in cache
        image_bytes = image_io.getvalue()
        
        # Update Cache
        _render_cache["data"] = image_bytes
        _render_cache["timestamp"] = current_time
        
        return prepare_response(image_bytes, current_time)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error rendering dashboard: {e}", 500
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
