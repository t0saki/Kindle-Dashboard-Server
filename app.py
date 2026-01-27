from flask import Flask, render_template, send_file
import datetime
from concurrent.futures import ThreadPoolExecutor
# Import from our new data layer
from data_services import get_weather, get_calendar_info, get_hacker_news, generate_sparkline

executor = ThreadPoolExecutor(max_workers=20)

app = Flask(__name__)

# --- Configuration (Externalizable) ---
# ... (Config can stay here if app specific, or move to config.py later)

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
def render_dashboard():
    from renderer import render_dashboard_to_bytes, TARGET_SIZE
    
    # We need to render the dashboard page.
    # Assuming the dashboard is running on localhost at the port configured.
    # We can default to localhost:5000 if not specified.
    # Note: When running in production (e.g. gunicorn), port might vary.
    # For this local setup, we can hardcode or infer.
    port = 5000 
    dashboard_url = f"http://127.0.0.1:{port}/dashboard"
    
    try:
        image_bytes = render_dashboard_to_bytes(dashboard_url)
        return send_file(
            image_bytes, 
            mimetype='image/png',
            as_attachment=False, 
            download_name='dashboard.png'
        )
    except Exception as e:
        return f"Error rendering dashboard: {e}", 500
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
