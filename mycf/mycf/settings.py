# mycf/settings.py
import os

BOT_NAME = "mycf"
SPIDER_MODULES = ["mycf.spiders"]
NEWSPIDER_MODULE = "mycf.spiders"

# 爬 API 常见会被 robots 拦，先关闭；频率我们自己控制
ROBOTSTXT_OBEY = False

# 给 API 的通用请求头
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mycf-scraper/1.0 (+contact: youremail@example.com)",
    "Origin": "https://www.mycareersfuture.gov.sg",
    "Referer": "https://www.mycareersfuture.gov.sg/",
}

# 礼貌抓取
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 0.8
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.5
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.2

FEED_EXPORT_ENCODING = "utf-8"

# —— 去重 + 分文件导出（默认按关键词）——
ITEM_PIPELINES = {
    "mycf.pipelines.DedupePipeline": 300,
    "mycf.pipelines.SplitExportPipeline": 500,
}
MYCF_OUTPUT_DIR = "output"
MYCF_SPLIT_MODE = "keyword"   # ★ 关键：按关键词分文件

# 只有你要用 DOM 兜底时才开启（设置环境变量 USE_PLAYWRIGHT=1，并安装 playwright）
USE_PLAYWRIGHT = os.getenv("USE_PLAYWRIGHT", "0").lower() in ("1", "true", "yes")
if USE_PLAYWRIGHT:
    DOWNLOAD_HANDLERS = {
        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    }
    TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    PLAYWRIGHT_BROWSER_TYPE = "chromium"
    PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000
