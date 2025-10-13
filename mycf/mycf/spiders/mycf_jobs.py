# mycf/spiders/mycf_jobs.py
# -*- coding: utf-8 -*-
import os
import re
import urllib.parse as ul
from datetime import datetime, timedelta, timezone

import scrapy
from scrapy.http import JsonRequest
from scrapy_playwright.page import PageMethod  # 仅在 DOM 兜底时用

from mycf.items import JobSummaryItem


class MyCareersFutureSpider(scrapy.Spider):
    """
    用法：
      # 读取 keywords.txt，按关键词分文件导出（settings 已设 MYCF_SPLIT_MODE=keyword）
      # python -m scrapy crawl mycf_jobs -a keywords_file=keywords.txt -a within_days=7 -a max_pages=3

      # 也可单关键词调试
      # python -m scrapy crawl mycf_jobs -a q=quant -a within_days=7 -a max_pages=2
    """
    name = "mycf_jobs"
    allowed_domains = ["mycareersfuture.gov.sg", "api.mycareersfuture.gov.sg"]

    custom_settings = {
        "PLAYWRIGHT_INCLUDE_PAGE": True,  # 仅 DOM 兜底调试用
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.8,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.5,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.2,
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    API_BASE = "https://api.mycareersfuture.gov.sg/v2/search"

    def __init__(
        self,
        q=None,
        keywords_file=None,
        within_days=7,
        max_pages=3,
        use_api_only="True",
        per_page=20,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # --- 读取关键词列表 ---
        kws = set()
        if keywords_file and os.path.exists(keywords_file):
            with open(keywords_file, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    kws.add(s)
        if q:
            kws.add(q.strip())
        if not kws:
            kws.add("quant")
        self.queries = sorted(kws)

        self.within_days = int(within_days or 7)
        self.max_pages = int(max_pages or 3)
        self.use_api_only = str(use_api_only).lower() in ("1", "true", "yes", "y")
        self.per_page = int(per_page or 20)

        self.sortBy = "new_posting_date"
        self.tz = timezone(timedelta(hours=8))  # 新加坡/UTC+8
        self.now = datetime.now(self.tz)

    # ----------------- 工具 -----------------
    def _build_search_url(self, query: str, page: int) -> str:
        base = "https://www.mycareersfuture.gov.sg/search"
        params = {"search": query, "sortBy": self.sortBy, "page": page}
        return f"{base}?{ul.urlencode(params)}"

    def _build_api_payload(self, query: str, page_index: int):
        return {
            "search": query or "",
            "sortBy": self.sortBy,
            "filters": {},
            "page": page_index,
            "limit": self.per_page,
        }

    def _api_request(self, query: str, page_index: int, source_url: str, method: str = "POST"):
        """支持 POST/GET，两种页码起点（0/1），配合 dont_filter=True 允许重复尝试。"""
        params = {
            "limit": self.per_page,
            "page": page_index,
            "search": query or "",
            "sortBy": self.sortBy,
        }
        payload = self._build_api_payload(query, page_index)

        headers = {
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.mycareersfuture.gov.sg",
            "referer": source_url,
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8",
            "x-requested-with": "XMLHttpRequest",
        }

        if method.upper() == "GET":
            return scrapy.Request(
                url=f"{self.API_BASE}?{ul.urlencode(params)}",
                method="GET",
                headers=headers,
                cb_kwargs={"query": query, "page_index": page_index, "source_url": source_url},
                callback=self.parse_api_json,
                dont_filter=True,
            )
        else:
            return JsonRequest(
                url=self.API_BASE,
                method="POST",
                data=payload,
                headers=headers,
                cb_kwargs={"query": query, "page_index": page_index, "source_url": source_url},
                callback=self.parse_api_json,
                dont_filter=True,
            )

    def _posted_within_days(self, iso_or_text: str) -> bool:
        """过滤最近 N 天（ISO + 相对时间）。解析失败默认保留。"""
        if not iso_or_text:
            return True
        s = iso_or_text.strip().lower()
        # ISO
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            from datetime import datetime as dt
            try:
                d = dt.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                d = dt.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=self.tz)
            return (self.now - d) <= timedelta(days=self.within_days)
        # 相对时间
        if "day" in s:
            m2 = re.search(r"(\d+)\s*day", s)
            if m2:
                return int(m2.group(1)) <= self.within_days
            if "yesterday" in s:
                return self.within_days >= 1
        if "hour" in s or "minute" in s:
            return True
        return True

    def _to_abs_url(self, response, path_or_url):
        if not path_or_url:
            return None
        return response.urljoin(path_or_url)

    # ----------------- 入口 -----------------
    def start_requests(self):
        for query in self.queries:
            if self.use_api_only:
                referer = self._build_search_url(query, page=0)
                for page_index in range(0, self.max_pages):
                    # 多路线兜底：POST/GET × 页码 0/1
                    yield self._api_request(query, page_index, referer, method="POST")
                    yield self._api_request(query, page_index, referer, method="GET")
                    yield self._api_request(query, page_index + 1, referer, method="POST")
                    yield self._api_request(query, page_index + 1, referer, method="GET")
            else:
                # 只有在 USE_PLAYWRIGHT=1 时可用（DOM 兜底）
                url = self._build_search_url(query, page=0)
                yield scrapy.Request(
                    url,
                    meta={
                        "playwright": True,
                        "page_index": 0,
                        "query": query,
                        "playwright_page_methods": [
                            PageMethod("wait_for_load_state", "domcontentloaded"),
                            PageMethod("wait_for_selector", "main, #__next, body", timeout=60000),
                        ],
                    },
                    callback=self.parse_list,
                )

    # ----------------- DOM 兜底 -----------------
    def parse_list(self, response):
        page_index = response.meta.get("page_index", 0)
        query = response.meta.get("query")
        source_url = response.url

        cards = response.css("[data-testid='job-card'], a[data-testid='job-card-link']")
        if not cards:
            self.logger.warning(f"No cards on page {page_index}. Fallback to API: {response.url}")
            yield self._api_request(query=query, page_index=page_index, source_url=source_url, method="POST")
            yield self._api_request(query=query, page_index=page_index, source_url=source_url, method="GET")
            return

        for card in cards:
            title = (card.css("[data-testid='job-card__job-title']::text, [data-testid='job-card-title']::text, h2::text, h3::text").get(default="").strip()) or None
            company = (card.css("[data-testid='job-card__company-hire-info']::text, [data-testid='company-hire-info']::text").get(default="").strip()) or None
            location = (card.css("[data-testid='job-card__location']::text, [data-testid='job-card-location']::text").get(default="").strip()) or None
            posted = (card.css("[data-testid='job-card__posted-date']::text, [data-testid='job-card-date']::text, time::attr(datetime)").get(default="").strip()) or None
            href = card.attrib.get("href") or card.css("a::attr(href)").get()
            job_url = self._to_abs_url(response, href)

            if posted and not self._posted_within_days(posted):
                continue

            yield JobSummaryItem(
                search_query=query,
                page_index=page_index,
                title=title,
                company=company,
                location=location,
                salary=None,
                posted=posted,
                employment_type=None,
                seniority=None,
                category=None,
                job_url=job_url,
                source_url=source_url,
            )

    # ----------------- API 解析 -----------------
    def parse_api_json(self, response, query, page_index, source_url):
        """兼容 results/data/payload/result.results/jobs/items 等多种结构。"""
        try:
            data = response.json()
        except Exception:
            self.logger.warning(f"Non-JSON or parse error on {response.url}: {response.text[:200]}")
            return

        results = []
        if isinstance(data, dict):
            if isinstance(data.get("results"), list):
                results = data["results"]
            elif isinstance(data.get("data"), list):
                results = data["data"]
            elif isinstance(data.get("payload"), list):
                results = data["payload"]
            elif isinstance(data.get("result"), dict) and isinstance(data["result"].get("results"), list):
                results = data["result"]["results"]
            elif any(k in data for k in ("jobs", "items")):
                results = data.get("jobs") or data.get("items") or []

        if not results:
            self.logger.info(f"No results on {response.url}. keys={list(data)[:8]}")
            return

        for j in results:
            job_url_path = j.get("jobDetailsUrl") or j.get("seoUrl") or j.get("urlPath") or j.get("jobUrl")
            job_url = self._to_abs_url(response, job_url_path)

            company = None
            company_raw = j.get("company")
            if isinstance(company_raw, dict):
                company = company_raw.get("name") or company_raw.get("companyName")
            elif isinstance(company_raw, str):
                company = company_raw

            location = j.get("location") or j.get("postal") or j.get("jobLocation") or None

            salary = None
            min_salary = j.get("minSalary")
            max_salary = j.get("maxSalary")
            currency = j.get("salaryCurrency")
            if min_salary or max_salary:
                rng = f"{min_salary or ''}-{max_salary or ''}".strip("-")
                salary = f"{rng} {currency or ''}".strip()

            posted = j.get("postingDate") or j.get("postedDate") or j.get("createDate") or j.get("lastUpdatedDate")
            if posted and not self._posted_within_days(posted):
                continue

            yield JobSummaryItem(
                search_query=query,         # ★ 用关键词作为“分组键”
                page_index=page_index,
                title=j.get("title") or j.get("jobTitle"),
                company=company,
                location=location,
                salary=salary,
                posted=posted,
                employment_type=j.get("employmentType"),
                seniority=j.get("seniority"),
                category=j.get("category") or j.get("jobCategory"),
                job_url=job_url,
                source_url=source_url,
            )
