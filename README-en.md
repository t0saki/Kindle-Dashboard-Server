# Kindle Oasis Dashboard Server

[中文](README.md)

This is a highly configurable **E-ink dashboard server** application, primarily optimized for the Kindle Oasis 2 but adaptable to various devices.

It is intended to be used with a KUAL extension (or other tools) on the Kindle to provide a high-contrast, multi-language supported, and aesthetically pleasing "Always-on" second screen. With the new decoupled configuration, it can be easily adjusted for different screen resolutions and regions.

![Real Shot](demo_shot.avif)

*   **E-ink & Layout Optimization**:
    *   Bento Grid layout provides modular information blocks.
    *   Pure B&W high-contrast design with Floyd-Steinberg dithering for sharp E-ink display.
*   **Global Support**:
    *   **Localization**: Native support for Chinese (CN) and English (EN) with layout adjustments for long strings.
    *   **Configurable Location**: Set any Latitude/Longitude to get local weather, Air Quality (AQI), and UV index.
    *   **Regional Holidays**: Supports public holiday data for various countries via the `holidays` library.
*   **Rich Data Display**:
    *   **Weather**: Forecasts, humidity, rain probability, and trends.
    *   **Financials**: Real-time tracking of currency, stocks, and crypto with sparklines.
    *   **News**: Top 5 stories from Hacker News, or from a custom external JSON source.
*   **Automated Rendering**:
    *   **Fully Configurable**: Manage resolution, language, location, and data sources via `.env`.
    *   **Multi-Device Adaptation**: While the dashboard layout follows a 1680x1264 ratio, the `/render` API automatically scales the output to your configured screen resolution.
    *   **Docker & CI/CD**: Easy deployment with Docker and automated builds via GitHub Actions.

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

### 1. Configuration

The project uses a `.env` file for configuration. Copy the template and edit as needed:

```bash
cp .env_example .env
nano .env # Configure location, language, resolution, tickers, etc.
```

### 2. Using Docker (Recommended)

```bash
docker pull ghcr.io/t0saki/kindle-dashboard-server:latest
# Ensure to pass the .env file to the container
docker run -p 5000:5000 --env-file .env ghcr.io/t0saki/kindle-dashboard-server:latest
```

### 3. Running Locally

1.  **Install uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **Setup**:
    ```bash
    uv sync
    uv run playwright install chromium --with-deps
    ```
3.  **Run**: `uv run app.py`

## 🔌 API Endpoints

*   `GET /dashboard`: Returns the responsive web version of the dashboard.
*   `GET /render`: Returns the **Kindle-optimized (config-based resolution, 16-level grayscale, dithered)** PNG image.

## 📱 Companion Client

If you have a jailbroken Kindle, use this companion project to automate image fetching and power management:

*   **[Kindle-Dashboard](https://github.com/t0saki/Kindle-Dashboard)**: A KUAL extension script that handles automated networking, image downloading, and high-quality rendering using FBInk.

## 📄 License

MIT License
