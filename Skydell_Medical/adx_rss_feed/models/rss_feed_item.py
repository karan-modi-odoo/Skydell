# -*- coding: utf-8 -*-
"""
RSS Feed items Models
==============="""
from odoo import models, fields


class RssFeedItem(models.Model):
    _name = "rss.feed.item"
    _description = "RSS Feed Item"
    _order = "pub_date desc, id desc"
    _rec_name = "title"

    # ── Fields ───────────────────────────────────────────────────
    feed_id = fields.Many2one(
        "rss.feed",
        string="Feed",
        required=True,
        ondelete="cascade",
        index=True,
    )
    guid = fields.Char(string="GUID", index=True)
    title = fields.Char(string="Title")
    description = fields.Html(string="Description")
    link = fields.Char(string="Article URL")
    pub_date = fields.Datetime(string="Published")
    image_url = fields.Char(string="Image URL")
