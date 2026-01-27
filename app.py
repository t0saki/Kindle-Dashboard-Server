from flask import Flask, render_template
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

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
