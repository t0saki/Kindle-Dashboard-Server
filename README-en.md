# Kindle Oasis Dashboard Server

This is an E-ink dashboard server application specifically designed for the **Kindle Oasis 2** (7-inch, 1680x1264).

It is intended to be used with a KUAL extension (or other browser/screenshot tools) on the Kindle to provide a high-contrast, low-refresh-rate, information-rich, and aesthetically pleasing "Always-on" desktop secondary screen.

![Dashboard Preview](test_output_dashboard.png)

## ✨ Features

*   **E-ink Optimization**:
    *   Pure black and white high-contrast design, removing gray scales to ensure sharp display on E-ink screens.
    *   Uses bold lines and large fonts to prevent anti-aliasing blur.
    *   Bento Grid layout, keeping information organized in modular blocks.
*   **Rich Data Display**:
    *   **Singapore Weather**: Includes current temperature, humidity, rain probability, and weather trends (optimized for Singapore).
    *   **Calendar Info**: Includes Gregorian date, weekday, **Lunar date**, and **Singapore Public Holidays**.
    *   **Financial Markets**: Real-time tracking of SGD/CNY, USD/CNY exchange rates and Bitcoin trends.
    *   **Hacker News**: Displays Top 5 hot tech news.
*   **Automated Server-Side Rendering**:
    *   **Playwright Integration**: Built-in `/render` endpoint that automatically renders the dashboard via a headless browser and captures a 1680x1264 image.
    *   **High-Quality Dithering**: Automatically applies 16-level grayscale quantization and **Floyd-Steinberg dithering** for optimal E-ink visual quality.
    *   **Docker Support**: One-command deployment with all browser dependencies pre-configured.
    *   **CI/CD**: Integrated GitHub Actions for automatic image building and publishing.

## 🛠 Tech Stack

*   **Backend**: Python 3.12, Flask, uv
*   **Frontend**: HTML5, Tailwind CSS (CDN)
*   **Rendering**: Playwright (Chromium)
*   **Image Processing**: Pillow (Floyd-Steinberg Dithering)
*   **Data Sources**:
    *   `yfinance`: Stock and exchange rate data
    *   `lunardate`: Lunar date conversion
    *   `holidays`: Public holiday data
    *   `matplotlib`: Trend chart generation

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
docker pull ghcr.io/t0saki/kindle-dashboard-server:latest
docker run -p 5000:5000 ghcr.io/t0saki/kindle-dashboard-server:latest
```

### Running Locally

1.  **Install uv** (if not already): `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **Install dependencies and browser**:
    ```bash
    uv sync
    uv run playwright install chromium --with-deps
    ```
3.  **Run the service**:
    ```bash
    uv run app.py
    ```

## 🔌 API Endpoints

*   `GET /dashboard`: Returns the responsive web version of the dashboard.
*   `GET /render`: Returns the **Kindle-optimized (1680x1264, 16-level grayscale, dithered)** PNG image. This is the recommended endpoint for Kindle clients.

## 📱 Kindle Setup (Brief)

1.  Ensure your Kindle is jailbroken and has KUAL installed.
2.  Use a script to periodically download the image from `http://<server-ip>:5000/render`.
3.  Display the image on the screen using `eips -g /path/to/downloaded.png`.
4.  Utilize the Kindle's partial refresh capability for fast updates in reserved areas (like the time display) to save power.

## 📄 License

MIT License
