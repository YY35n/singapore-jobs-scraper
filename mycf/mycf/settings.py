# Scrapy settings for mycf project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "mycf"
SPIDER_MODULES = ["mycf.spiders"]
NEWSPIDER_MODULE = "mycf.spiders"

# 遵守 robots
ROBOTSTXT_OBEY = True

# 友好请求头
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mycf-scraper/1.0 (+contact: youremail@example.com)"
}

# —— Playwright（新版：Download Handler，而不是 Middleware）——
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000

# 礼貌抓取
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 0.8
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.5
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.2

# 导出编码
FEED_EXPORT_ENCODING = "utf-8"

# 可自定义数据库路径（可选）
# MYCF_SQLITE_PATH = "data/mycf_jobs.sqlite"
