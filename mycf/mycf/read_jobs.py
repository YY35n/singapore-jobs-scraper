#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 mycf_jobs.sqlite 中的职位记录，并可筛选/导出。
表结构参考 pipelines.DedupePipeline 创建的 jobs 表：
(job_url PRIMARY KEY, search_query, title, company, location, posted, employment_type, seniority, category)
"""

import argparse
import csv
import os
import sqlite3
from textwrap import shorten

DEFAULT_DB = os.path.join(os.getcwd(), "mycf_jobs.sqlite")

def parse_args():
    p = argparse.ArgumentParser(description="Read jobs from SQLite (mycf_jobs.sqlite).")
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite 文件路径（默认：当前目录下 mycf_jobs.sqlite）")
    p.add_argument("--limit", type=int, default=50, help="最多显示条数（默认 50）")
    p.add_argument("--category", default="%", help="按分类 LIKE 匹配（支持通配符%%，默认 全部）")
    p.add_argument("--keyword", default="%", help="按 search_query LIKE 匹配（默认 全部）")
    p.add_argument("--posted_prefix", default="%", help="按 posted 前缀 LIKE（如 2025-10，或 2025-；默认 全部）")
    p.add_argument("--export_csv", default=None, help="导出到 CSV 文件路径（可选）")
    return p.parse_args()

def open_db(path: str) -> sqlite3.Connection:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到数据库文件：{path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def query_jobs(conn: sqlite3.Connection, category_like: str, keyword_like: str, posted_prefix: str, limit: int):
    # posted 里有可能是 "2025-10-12T..." 或 "3 days ago" 等相对字符串
    # 这里用 LIKE 前缀匹配（例如 '2025-%'），无法匹配相对字符串；相对字符串就当作“其他”
    sql = """
    SELECT job_url, search_query, title, company, location, posted,
           employment_type, seniority, category
    FROM jobs
    WHERE category LIKE ?
      AND search_query LIKE ?
      AND posted LIKE ?
    ORDER BY rowid DESC
    LIMIT ?
    """
    cur = conn.cursor()
    cur.execute(sql, (category_like, keyword_like, posted_prefix, limit))
    return cur.fetchall()

def print_table(rows):
    if not rows:
        print("（没有匹配的记录）")
        return
    # 简单表格打印（控制台友好）
    headers = ["title", "company", "location", "category", "posted", "search_query", "job_url"]
    print(" | ".join(h.upper() for h in headers))
    print("-" * 120)
    for r in rows:
        line = [
            shorten(r["title"] or "", width=28, placeholder="…"),
            shorten(r["company"] or "", width=20, placeholder="…"),
            shorten(r["location"] or "", width=18, placeholder="…"),
            shorten(r["category"] or "", width=20, placeholder="…"),
            shorten(r["posted"] or "", width=18, placeholder="…"),
            shorten(r["search_query"] or "", width=16, placeholder="…"),
            shorten(r["job_url"] or "", width=50, placeholder="…"),
        ]
        print(" | ".join(line))

def export_csv(rows, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["search_query","title","company","location","category","employment_type","seniority","posted","job_url"])
        for r in rows:
            w.writerow([
                r["search_query"], r["title"], r["company"], r["location"], r["category"],
                r["employment_type"], r["seniority"], r["posted"], r["job_url"]
            ])
    print(f"✅ 已导出 CSV -> {path}")

def main():
    args = parse_args()
    conn = open_db(args.db)
    try:
        rows = query_jobs(conn, args.category, args.keyword, args.posted_prefix, args.limit)
        print_table(rows)
        if args.export_csv:
            export_csv(rows, args.export_csv)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
