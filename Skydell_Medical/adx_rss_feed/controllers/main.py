import logging
import urllib.request
from datetime import datetime
from markupsafe import Markup
from werkzeug.exceptions import NotFound
from odoo import http, tools
from odoo.http import request

_logger = logging.getLogger(__name__)


def _scrape_article(url):
    """
    Scrape full article content from original URL.
    Returns dict with scraped fields or None on failure.
    """
    try:
        from bs4 import BeautifulSoup

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()

        soup = BeautifulSoup(raw, "html.parser")

        # ── Main Image ────────────────────────────────────────
        image_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"].strip()

        # ── Article Body ──────────────────────────────────────
        body_html = ""
        _UNWANTED_TAGS = [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "form",
            "iframe",
            "button",
            "noscript",
        ]

        def _clean(el):
            for tag in el.find_all(_UNWANTED_TAGS):
                tag.decompose()
            return str(el)

        # Strategy 1 — <article> tag
        article_tag = soup.find("article")
        if article_tag:
            body_html = _clean(article_tag)

        # Strategy 2 — common content selectors
        if not body_html:
            for selector in [
                '[class*="article-body"]',
                '[class*="article__body"]',
                '[class*="story-body"]',
                '[class*="post-content"]',
                '[class*="entry-content"]',
                '[class*="content-body"]',
                '[class*="main-content"]',
                "main",
            ]:
                el = soup.select_one(selector)
                if el:
                    body_html = _clean(el)
                    break

        # Strategy 3 — collect all <p> tags as last resort
        if not body_html:
            paragraphs = soup.find_all("p")
            if paragraphs:
                body_html = "".join(str(p) for p in paragraphs)

        return {
            "image_url": image_url,
            "body_html": Markup(tools.html_sanitize(body_html)) if body_html else Markup(""),
        }

    except Exception as e:
        _logger.warning("Failed to scrape article from '%s': %s", url, e)
        return None


def _format_feed_items(feed):
    """Shared helper — format items for a feed."""
    items = feed.item_ids.sorted(lambda i: (i.pub_date or datetime.min), reverse=True)
    return [
        {
            "id": item.id,
            "title": item.title or "",
            "description": item.description or "",
            "link": item.link or "",
            "pub_date": (
                item.pub_date.strftime("%B %d, %Y") if item.pub_date else ""
            ),
            "image_url": item.image_url or "",
        }
        for item in items
    ]


class NewsFeedController(http.Controller):

    def _get_feeds(self):
        """Shared feed query."""
        return (
            request.env["rss.feed"]
            .sudo()
            .search([], order="sequence asc, name asc")
        )

    # ── Main news feed listing page ───────────────────────────
    @http.route("/news-feed", type="http", auth="public", website=True)
    def news_feed_page(self, **kw):
        feeds = self._get_feeds()
        feed_data = [
            {
                "id": feed.id,
                "name": feed.name,
                "channel_title": feed.channel_title or feed.name,
                "items": _format_feed_items(feed),
            }
            for feed in feeds
        ]
        return request.render(
            "adx_rss_feed.news_feed_page",
            {
                "feeds": feed_data,
            },
        )

    # ── Article detail page ───────────────────────────────────
    @http.route(
        "/news-feed/article/<int:article_id>",
        type="http",
        auth="public",
        website=True,
    )
    def news_feed_article(self, article_id, **kw):
        item = request.env["rss.feed.item"].sudo().browse(article_id)

        # ── Validate record exists ────────────────────────────
        if not item.exists():
            raise NotFound()

        article = {
            "id": item.id,
            "title": item.title or "",
            "description": item.description or "",
            "link": item.link or "",
            "pub_date": (
                item.pub_date.strftime("%B %d, %Y") if item.pub_date else ""
            ),
            "image_url": item.image_url or "",
            "feed_name": item.feed_id.channel_title or item.feed_id.name or "",
            # Scraped fields — defaults
            "scraped_image": "",
            "scraped_body": Markup(""),
            "scrape_success": False,
        }

        # ── Live scrape from original URL ─────────────────────
        if item.link:
            scraped = _scrape_article(item.link)
            if scraped:
                article.update(
                    {
                        "scraped_image": scraped.get("image_url")
                        or item.image_url
                        or "",
                        "scraped_body": scraped.get("body_html") or Markup(""),
                        "scrape_success": bool(scraped.get("body_html")),
                    }
                )

        return request.render(
            "adx_rss_feed.news_feed_article_page", {"item": article}
        )

    # ── JSON API for JS frontend ──────────────────────────────
    @http.route("/news-feed/data", type="json", auth="public", csrf=False)
    def news_feed_data(self, **kw):
        """Return cached feed items grouped by feed, ordered by sequence."""
        feeds = self._get_feeds()
        return [
            {
                "id": feed.id,
                "name": feed.name,
                "items": _format_feed_items(feed),
            }
            for feed in feeds
        ]
