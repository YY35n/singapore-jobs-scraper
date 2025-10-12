import os
import re
import sqlite3
from datetime import datetime
from scrapy.exceptions import DropItem
from scrapy.exporters import CsvItemExporter


# ---------- 持久化去重（SQLite） ----------
class DedupePipeline:
    """
    基于 SQLite 的持久化去重：以 job_url 作为唯一键。
    - 首次见到的 job_url -> 插入DB并放行
    - 已存在的 job_url -> 直接 Drop，不进入后续导出
    可在 settings.py 中通过 MYCF_SQLITE_PATH 自定义数据库路径。
    """
    def __init__(self, db_path="mycf_jobs.sqlite"):
        self.db_path = db_path
        self.conn = None

    @classmethod
    def from_crawler(cls, crawler):
        db_path = crawler.settings.get("MYCF_SQLITE_PATH", "mycf_jobs.sqlite")
        return cls(db_path=db_path)

    def open_spider(self, spider):
        # 若设置了子目录，确保存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_url TEXT PRIMARY KEY,
                search_query TEXT,
                title TEXT,
                company TEXT,
                location TEXT,
                posted TEXT,
                employment_type TEXT,
                seniority TEXT,
                category TEXT
            )
        """)
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        job_url = item.get("job_url")
        if not job_url:
            raise DropItem("Missing job_url")

        cur = self.conn.cursor()
        try:
            cur.execute(
                """INSERT INTO jobs
                   (job_url, search_query, title, company, location, posted, employment_type, seniority, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_url,
                    item.get("search_query"),
                    item.get("title"),
                    item.get("company"),
                    item.get("location"),
                    item.get("posted"),
                    item.get("employment_type"),
                    item.get("seniority"),
                    item.get("category"),
                )
            )
            self.conn.commit()
            return item  # 新记录，放行到导出
        except sqlite3.IntegrityError:
            # 已存在，丢弃（不导出）
            raise DropItem(f"Duplicate job_url: {job_url}")


# ---------- 按“种类/关键词”分文件导出 ----------
class SplitExportPipeline:
    """
    根据设置 MYCF_SPLIT_MODE 分文件导出：
      - 'category'：按 item['category'] 分文件
      - 'keyword' ：按 item['search_query'] 分文件

    文件按日期存放：
      output/by_category/<种类>/<YYYY-MM-DD>.csv
      或
      output/by_keyword/<关键词>/<YYYY-MM-DD>.csv

    可在 settings.py 中配置：
      - MYCF_OUTPUT_DIR（默认 'output'）
      - MYCF_SPLIT_MODE（默认 'category'）
    """
    def __init__(self, base_dir="output", split_mode="category"):
        self.base_dir = base_dir
        self.split_mode = split_mode
        self.exporters = {}  # key -> CsvItemExporter
        self.today = datetime.now().strftime("%Y-%m-%d")

    @classmethod
    def from_crawler(cls, crawler):
        base_dir = crawler.settings.get("MYCF_OUTPUT_DIR", "output")
        split_mode = crawler.settings.get("MYCF_SPLIT_MODE", "category")  # 'category' or 'keyword'
        return cls(base_dir=base_dir, split_mode=split_mode)

    def _sanitize(self, name: str) -> str:
        name = (name or "Unknown").strip()
        # Windows 文件名安全
        return re.sub(r'[\\/:*?"<>|]+', "_", name)[:80] or "Unknown"

    def _key_from_item(self, item):
        if self.split_mode == "keyword":
            return self._sanitize(item.get("search_query"))
        # 默认按分类
        return self._sanitize(item.get("category"))

    def _get_or_create_exporter(self, key: str) -> CsvItemExporter:
        if key in self.exporters:
            return self.exporters[key]

        subdir = "by_keyword" if self.split_mode == "keyword" else "by_category"
        dir_path = os.path.join(self.base_dir, subdir, key)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, f"{self.today}.csv")

        file_exists = os.path.exists(file_path)
        f = open(file_path, "ab")  # 追加写；不存在则创建
        exporter = CsvItemExporter(f, include_headers_line=not file_exists)
        exporter.fields_to_export = [
            "search_query", "page_index",
            "title", "company", "location", "salary", "posted",
            "employment_type", "seniority", "category",
            "job_url", "source_url",
        ]
        exporter.start_exporting()

        # Scrapy 新版 CsvItemExporter 无 .file 属性，手动保存句柄便于关闭
        exporter._file = f
        self.exporters[key] = exporter
        return exporter

    def process_item(self, item, spider):
        key = self._key_from_item(item)
        exporter = self._get_or_create_exporter(key)
        exporter.export_item(item)
        return item

    def close_spider(self, spider):
        # 逐个收尾并关闭文件
        for exporter in self.exporters.values():
            try:
                exporter.finish_exporting()
            except Exception:
                pass
            f = getattr(exporter, "_file", None)
            if f:
                try:
                    f.close()
                except Exception:
                    pass
