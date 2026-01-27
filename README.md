# Kindle Oasis Dashboard Server

这是一个专为 **Kindle Oasis 2** (7英寸, 1680x1264) 设计的 E-ink 仪表盘服务端程序。

它旨在配合 Kindle 上的 KUAL 扩展（或其他浏览器/截图工具）使用，提供一个高对比度、低刷新率、信息丰富且美观的 "Always-on" 桌面副屏。

## ✨ 功能特性

*   **E-ink 极致优化**: 
    *   纯黑白高对比度设计，去除灰色阶，确保在电子墨水屏上显示清晰锐利。
    *   使用粗线条和大号字体，防止抗锯齿模糊。
    *   Bento Grid 宫格布局，信息由块状分割，整洁有序。
*   **丰富的数据展示**:
    *   **新加坡天气**: 包含当前气温、湿度、降雨概率及未来数小时的天气趋势（针对新加坡优化的逻辑）。
    *   **日历信息**: 包含公历日期、星期、**农历日期**以及**新加坡法定节假日**提醒。
    *   **金融市场**: 实时追踪 SGD/CNY, USD/CNY 汇率及 Bitcoin 走势，并在服务端生成迷你趋势图 (Sparklines) 以图片形式传输，减轻客户端渲染压力。
    *   **Hacker News**: 展示 Top 5 热门科技新闻，自动截断标题以适应排版。
*   **服务端渲染**:
    *   基于 Python Flask 和 Jinja2 模板。
    *   使用 Tailwind CSS 进行原子化样式设计。
    *   图表通过 Matplotlib 在后端生成为 Base64 图片嵌入，前端无复杂 JS 绘图逻辑。

## 🛠 技术栈

*   **后端**: Python 3, Flask
*   **前端**: HTML5, Tailwind CSS (CDN)
*   **数据源**:
    *   `yfinance`: 股票与汇率数据
    *   `lunardate`: 农历转换
    *   `holidays`: 节假日数据
    *   `requests`: Hacker News API & Weather API
    *   `matplotlib`: 生成趋势图

## 🚀 安装与运行

本项目使用 `uv` 进行依赖管理（也可以使用 pip）。

1.  **克隆仓库**
    ```bash
    git clone <repository_url>
    cd Kindle-Dashboard-Server
    ```

2.  **安装依赖**
    ```bash
    # 如果使用 uv (推荐)
    uv sync
    
    # 或者使用 pip
    pip install flask requests yfinance lunardate holidays matplotlib
    ```

3.  **配置 API (可选)**
    打开 `app.py`，你可以在 `CONFIG` 字典中填入你的 OpenWeather API Key（如果不填，代码中包含模拟数据的逻辑演示）。
    ```python
    CONFIG = {
        'weather_api_key': 'YOUR_OPENWEATHER_API_KEY', 
        # ...
    }
    ```

4.  **运行服务**
    ```bash
    uv run app.py
    # 或 python app.py
    ```

5.  **访问仪表盘**
    在浏览器中打开: `http://localhost:5000/dashboard`
    
    *建议使用浏览器开发者工具将视口设置为 `1680x1264` 以查看准确效果。*

## 📱 Kindle 端设置 (简述)

本项目仅包含服务端。要在 Kindle 上显示，你需要：
1.  确保 Kindle 已越狱并安装 KUAL。
2.  编写或使用现有的脚本（如 WebLaunch 或自定义 shell 脚本），定期（例如每分钟）抓取上述 URL 的截图或下载渲染好的图片并显示在屏幕上。
3.  利用 Kindle 的局部刷新功能在预留的 "Web View" 区域覆盖时间，以达到省电效果（本项目 HTML 中已预留 `local-time-placeholder` 区域）。

## 📄 许可证

MIT License
