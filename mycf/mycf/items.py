# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html


import scrapy

class JobSummaryItem(scrapy.Item):
    search_query = scrapy.Field()
    page_index   = scrapy.Field()

    title    = scrapy.Field()
    company  = scrapy.Field()
    location = scrapy.Field()
    salary   = scrapy.Field()
    posted   = scrapy.Field()

    job_url    = scrapy.Field()
    source_url = scrapy.Field()
