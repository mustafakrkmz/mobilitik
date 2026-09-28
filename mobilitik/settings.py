BOT_NAME = "mobilitik"

SPIDER_MODULES = ["mobilitik.spiders"]
NEWSPIDER_MODULE = "mobilitik.spiders"

ROBOTSTXT_OBEY = True
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"

ITEM_PIPELINES = {
    "mobilitik.pipelines.SQLitePipeline": 300,
}
