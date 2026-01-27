# Kindle Oasis Dashboard Server

This is an E-ink dashboard server application specifically designed for the **Kindle Oasis 2** (7-inch, 1680x1264).

It is intended to be used with a KUAL extension (or other browser/screenshot tools) on the Kindle to provide a high-contrast, low-refresh-rate, information-rich, and aesthetically pleasing "Always-on" desktop secondary screen.

## ✨ Features

*   **E-ink Optimization**:
    *   Pure black and white high-contrast design, removing gray scales to ensure sharp display on E-ink screens.
    *   Uses bold lines and large fonts to prevent anti-aliasing blur.
    *   Bento Grid layout, keeping information organized in modular blocks.
*   **Rich Data Display**:
    *   **Singapore Weather**: Includes current temperature, humidity, rain probability, and weather trends for the next few hours (logic optimized for Singapore).
    *   **Calendar Info**: Includes Gregorian date, weekday, **Lunar date**, and **Singapore Public Holidays**.
    *   **Financial Markets**: Real-time tracking of SGD/CNY, USD/CNY exchange rates and Bitcoin trends. Mini trend charts (Sparklines) are generated on the server and embedded as images to reduce client-side rendering load.
    *   **Hacker News**: Displays Top 5 hot tech news, with titles automatically truncated to fit the layout.
*   **Server-Side Rendering**:
    *   Built with Python Flask and Jinja2 templates.
    *   Atomic styling using Tailwind CSS.
    *   Charts are generated as Base64 images backend via Matplotlib, avoiding complex frontend JS plotting.

## 🛠 Tech Stack

*   **Backend**: Python 3, Flask
*   **Frontend**: HTML5, Tailwind CSS (CDN)
*   **Data Sources**:
    *   `yfinance`: Stock and exchange rate data
    *   `lunardate`: Lunar date conversion
    *   `holidays`: Public holiday data
    *   `requests`: Hacker News API & Weather API
    *   `matplotlib`: Trend chart generation

## 🚀 Installation & Usage

This project uses `uv` for dependency management (pip can also be used).

1.  **Clone the Repository**
    ```bash
    git clone <repository_url>
    cd Kindle-Dashboard-Server
    ```

2.  **Install Dependencies**
    ```bash
    # If using uv (Recommended)
    uv sync
    
    # Or using pip
    pip install flask requests yfinance lunardate holidays matplotlib
    ```

3.  **Configuration (Optional)**
    Open `app.py` and fill in your OpenWeather API Key in the `CONFIG` dictionary (if left empty, the code includes logic for mock data demonstration).
    ```python
    CONFIG = {
        'weather_api_key': 'YOUR_OPENWEATHER_API_KEY', 
        # ...
    }
    ```

4.  **Run the Server**
    ```bash
    uv run app.py
    # Or python app.py
    ```

5.  **Access the Dashboard**
    Open in browser: `http://localhost:5000/dashboard`
    
    *It is recommended to set your browser developer tools viewport to `1680x1264` to see the accurate effect.*

## 📱 Kindle Setup (Brief)

This project contains the server-side only. To display on a Kindle, you need to:
1.  Ensure your Kindle is jailbroken and has KUAL installed.
2.  Write or use an existing script (like WebLaunch or a custom shell script) to periodically (e.g., every minute) capture a screenshot of the URL above or download a rendered image to display on the screen.
3.  Utilize the Kindle's partial refresh capability to overlay the time in the reserved "Web View" area for power saving (this project's HTML has a reserved `local-time-placeholder` area).

## 📄 License

MIT License
