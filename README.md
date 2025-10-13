# 🇸🇬 MyCareersFuture Singapore Scraper

本项目基于 **Scrapy**，用于自动爬取 [MyCareersFuture Singapore](https://www.mycareersfuture.gov.sg) 上的招聘信息。  
支持：
- 🔍 **批量关键词抓取**（读取 `keywords.txt`，每行一个关键词）
- 🧩 **API 优先**（速度快、稳定）
- 🗂️ **按关键词自动分类导出 CSV**
- 🧱 **SQLite 持久化去重**
- 🌐 **可选 Playwright DOM 兜底模式**

---

## 🚀 环境安装

```bash
# 建议创建虚拟环境
python -m venv venv
source venv/bin/activate       # macOS / Linux
venv\Scripts\activate          # Windows

# 安装依赖
pip install scrapy scrapy-playwright
playwright install chromium     # 仅当启用 DOM 兜底模式时需要
📄 目录结构
mycf/
├── spiders/
│   └── mycf_jobs.py          # 主爬虫
├── pipelines.py              # 去重与分文件导出逻辑
├── items.py                  # 字段定义
├── settings.py               # Scrapy 配置
keywords.txt                  # 关键词文件（每行一个）

🧰 用法示例
1️⃣ 使用 keywords.txt 批量爬取（推荐）

keywords.txt 示例：

# 每行一个关键词
quant
data scientist
machine learning
software engineer


运行命令：

python -m scrapy crawl mycf_jobs -a keywords_file=keywords.txt -a within_days=7 -a max_pages=3


运行后结果自动输出到：

output/by_keyword/<关键词>/<YYYY-MM-DD>.csv

2️⃣ 单个关键词测试
python -m scrapy crawl mycf_jobs -a q=quant -a within_days=7 -a max_pages=2 -o jobs.csv

3️⃣ 启用 Playwright DOM 兜底模式（可选）

当 API 暂时无结果时可启用：

$env:USE_PLAYWRIGHT="1"                 # Windows PowerShell
export USE_PLAYWRIGHT=1                 # macOS/Linux
python -m scrapy crawl mycf_jobs -a keywords_file=keywords.txt -a use_api_only=False

⚙️ 配置说明
参数	含义	默认值
q	单个搜索关键词	"quant"
keywords_file	关键词文件路径	None
within_days	限定最近几天内发布的岗位	7
max_pages	每个关键词抓取的页数	3
use_api_only	是否仅用 API（True=更快）	"True"
MYCF_SPLIT_MODE	输出分组模式（keyword/category）	"keyword"
💾 输出说明

输出路径：output/by_keyword/<关键词>/<日期>.csv

字段示例：
| title | company | location | salary | posted | job_url |

🧹 常见问题

1️⃣ 命令报错 -O 无法识别？
→ Windows PowerShell 请使用小写 -o 或加 --% 以防参数冲突。

2️⃣ API 无结果？
→ 试试 use_api_only=False 启用 Playwright。
→ 或延长 within_days 到 7 天。

3️⃣ 结果为空？
→ 检查是否被 robots.txt 拦（默认已关闭）。
→ 查看日志 No results on ... keys=[...]，贴给我可诊断字段结构。

🪪 License

MIT License © 2025