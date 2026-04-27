# -*- coding: utf-8 -*-
{
    "name": "Skydell RSS News Feed",
    "version": "18.0.1.0.0",
    "category": "Website",
    "summary": "Fetch, cache and display RSS feeds on the "
    "Skydell News Feed page.",
    "depends": ["website"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/rss_feed_views.xml",
        "views/news_feed_template.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "adx_rss_feed/static/src/css/news_feed.css",
            "adx_rss_feed/static/src/js/news_feed.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "OPL-1",
}
