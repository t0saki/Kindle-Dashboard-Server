# Kindle Oasis Dashboard Server

这是一个专为 **Kindle Oasis 2** (7英寸, 1680x1264) 设计的 E-ink 仪表盘服务端程序。

它旨在配合 Kindle 上的 KUAL 扩展（或其他浏览器/截图工具）使用，提供一个高对比度、低刷新率、信息丰富且美观的 "Always-on" 桌面副屏。

![Dashboard Preview](test_output_dashboard.png)

*   **全球化支持**: 
    *   **多语言界面**: 原生支持中文 (CN) 和英文 (EN) 切换，自动调整排版以防止溢出（如长单词排版）。
    *   **自定义地理位置**: 可配置全球任何城市的经纬度，自动获取当地天气及空气质量 (AQI)。
    *   **多国节假日**: 集成 `holidays` 库，支持配置不同国家/地区的法定节假日。
*   **丰富的数据展示**:
    *   **天气预报**: 包含气温、湿度、UV 指数、AQI、降雨概率及未来趋势趋势。
    *   **日历信息**: 包含公历日期、星期、农历日期以及自定义节假日提醒。
    *   **金融市场**: 实时追踪汇率、股票及加密货币走势，生成迷你趋势图 (Sparklines)。
    *   **Hacker News**: 自动抓取热门科技新闻。
*   **服务端自动化渲染**:
    *   **高度可配置**: 通过 `.env` 文件配置分辨率、语言、位置、数据源和缓存时间。
    *   **高质量抖动算法**: 渲染 16 级灰度图像并应用 **Floyd-Steinberg 抖动**，为 E-ink 屏提供最佳观感。
    *   **适配多设备**: Dashboard 布局保持 1680x1264 黄金比例以保证排版，但 `/render` 接口会自动缩放到你配置的任何屏幕分辨率。
    *   **Docker & CI/CD**: 支持 Docker 部署，集成 GitHub Actions。

## 🛠 技术栈

*   **后端**: Python 3.12, Flask, uv
*   **前端**: HTML5, Tailwind CSS (CDN)
*   **渲染**: Playwright (Chromium)
*   **图像处理**: Pillow (Floyd-Steinberg Dithering)
*   **数据源**:
    *   `yfinance`: 股票与汇率数据
    *   `lunardate`: 农历转换
    *   `holidays`: 节假日数据
    *   `matplotlib`: 生成趋势图

### 1. 配置文件

项目使用 `.env` 文件进行配置。请先复制模版并根据需要修改：

```bash
cp .env_example .env
nano .env # 修改经纬度、语言、分辨率等
```

### 2. 使用 Docker (推荐)

```bash
docker pull ghcr.io/t0saki/kindle-dashboard-server:latest
# 注意：确保将 .env 文件映射到容器中
docker run -p 5000:5000 --env-file .env ghcr.io/t0saki/kindle-dashboard-server:latest
```

### 3. 本地运行

1.  **安装 uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2.  **准备环境**:
    ```bash
    uv sync
    uv run playwright install chromium --with-deps
    ```
3.  **运行**: `uv run app.py`

## 🔌 API 接口

*   `GET /dashboard`: 返回响应式网页版的仪表盘。
*   `GET /render`: 返回 **Kindle 优化版 (根据配置的分辨率, 16级灰度, 抖动处理)** 的 PNG 图片。这是 Kindle 客户端最常用的接口。

## 📱 配套客户端

如果你拥有越狱后的 Kindle，可以配合以下客户端项目使用，实现自动化刷新与休眠管理：

*   **[Kindle-Dashboard](https://github.com/t0saki/Kindle-Dashboard)**: 运行在 Kindle 上的 KUAL 插件脚本，负责自动联网、下载图片并使用 FBInk 高质量渲染。

## 📄 许可证

MIT License
