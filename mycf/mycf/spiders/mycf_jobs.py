import urllib.parse as ul
import re
from datetime import datetime, timedelta, timezone
import scrapy
from scrapy_playwright.page import PageMethod
from mycf.items import JobSummaryItem

# 新加坡时区
SG_TZ = timezone(timedelta(hours=8))

class MyCareersFutureSpider(scrapy.Spider):
    """
    用法示例：
      # 最近 1 天、3 页
      python -m scrapy crawl mycf_jobs -O jobs.csv -a q=quant -a max_pages=3 -a within_days=1

      # 最近 3 天、按最新发布排序（默认）、5 页
      python -m scrapy crawl mycf_jobs -O ds_3days.jsonl -a q="data scientist" -a within_days=3 -a max_pages=5

      参数：
        q            关键词，默认 "quant"
        max_pages    翻页数，默认 3
        within_days  仅保留最近 N 天岗位，默认 1
        sortBy       排序，默认 new_posting_date（也可传 relevancy 等）
    """
    name = "mycf_jobs"
    allowed_domains = ["mycareersfuture.gov.sg"]

    custom_settings = {
        # 让 playwright page 对象可用（需要时可加截图/调试）
        "PLAYWRIGHT_INCLUDE_PAGE": True,
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60_000,
    }

    # -------- 生命周期 --------
    def __init__(self, q="quant", max_pages=3, within_days=1,
                 sortBy="new_posting_date", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = q
        self.max_pages = int(max_pages)
        self.within_days = int(within_days)
        self.sortBy = sortBy

        now_sg = datetime.now(SG_TZ)
        # 仅保留 >= cutoff 的岗位
        self.cutoff_dt = (now_sg - timedelta(days=self.within_days))

    def start_requests(self):
        url = self._build_search_url(page=0)
        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "page_index": 0,
                "playwright_page_methods": [
                    # 与你截图一致：等到 job card 出现
                    PageMethod("wait_for_selector", "[data-testid='job-card']")
                ],
            },
            callback=self.parse_list,
        )

    # -------- 工具函数 --------
    def _build_search_url(self, page: int) -> str:
        base = "https://www.mycareersfuture.gov.sg/search"
        params = {
            "search": self.query,
            "sortBy": self.sortBy,         # 默认 new_posting_date
            "page": page,
        }
        return f"{base}?{ul.urlencode(params)}"

    def _parse_posted_to_dt(self, text: str, time_attr: str | None) -> datetime | None:
        """
        尝试把发布时间解析为 datetime（SG_TZ）。
        优先使用 <time datetime="...">；否则解析相对文案：
        - just posted / today
        - X minute(s)/hour(s)/day(s) ago
        - 备选：具体日期 "10 Oct 2025" 或 "2025-10-10"
        """
        # 1) ISO8601
        if time_attr:
            try:
                dt = datetime.fromisoformat(time_attr.strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=SG_TZ)
                return dt.astimezone(SG_TZ)
            except Exception:
                pass

        t = (text or "").strip().lower()
        if not t:
            return None

        if "just" in t or "today" in t:
            return datetime.now(SG_TZ)

        m = re.search(r"(\d+)\s*minute", t)
        if m:
            return datetime.now(SG_TZ) - timedelta(minutes=int(m.group(1)))

        m = re.search(r"(\d+)\s*hour", t)
        if m:
            return datetime.now(SG_TZ) - timedelta(hours=int(m.group(1)))

        m = re.search(r"(\d+)\s*day", t)
        if m:
            return datetime.now(SG_TZ) - timedelta(days=int(m.group(1)))

        # 具体日期兜底
        for fmt in ("%d %b %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime((text or "").strip(), fmt).replace(tzinfo=SG_TZ)
            except Exception:
                continue
        return None

    # -------- 解析列表页 --------
    def parse_list(self, response):
        page_index = response.meta.get("page_index", 0)
        source_url = response.url

        cards = response.css("[data-testid='job-card']")
        if not cards:
            self.logger.warning(f"No cards on page {page_index}: {response.url}")

        for card in cards:
            # 链接：整卡 <a data-testid='job-card-link'>
            href = card.xpath("ancestor::a[1]/@href").get() or \
                   card.css("a[data-testid='job-card-link']::attr(href)").get()
            job_url = response.urljoin(href) if href else None

            # 公司
            company = card.css("p[data-testid='company-hire-info']::text").get(default="").strip() or None

            # 职位名
            title = card.css("span[data-testid='job-card__job-title']::text").get(default="").strip() or None

            # 地点 / 雇佣类型 / 职级 / 分类（如列表有）
            location  = card.css("p[data-testid='job-card__location']::text").get(default="").strip() or None
            # 如果你也想导出 emp_type / seniority / category，可以加进 Item，这里暂留示例：
            # emp_type  = card.css("p[data-testid='job-card__employment-type']::text").get(default='').strip() or None
            # seniority = card.css("p[data-testid='job-card__seniority']::text").get(default='').strip() or None
            # category  = card.css("p[data-testid='job-card__category']::text").get(default='').strip() or None

            # 发布时间
            posted_text = card.css("[data-testid='job-card-date']::text").get(default="").strip()
            time_attr   = card.css("time::attr(datetime)").get()
            posted_dt   = self._parse_posted_to_dt(posted_text, time_attr)

            # 过滤：仅保留最近 N 天
            if posted_dt is not None and posted_dt < self.cutoff_dt:
                continue

            yield JobSummaryItem(
                search_query=self.query,
                page_index=page_index,
                title=title,
                company=company,
                location=location,
                salary=None,  # 列表通常无明确薪资
                posted=posted_text or (posted_dt.isoformat() if posted_dt else None),
                job_url=job_url,
                source_url=source_url,
            )

        # 翻页
        if page_index + 1 < self.max_pages:
            next_url = self._build_search_url(page=page_index + 1)
            yield scrapy.Request(
                next_url,
                meta={
                    "playwright": True,
                    "page_index": page_index + 1,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "[data-testid='job-card']")
                    ],
                },
                callback=self.parse_list,
            )
