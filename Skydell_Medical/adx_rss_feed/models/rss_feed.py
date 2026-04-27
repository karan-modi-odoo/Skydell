# -*- coding: utf-8 -*-
"""
RSS Feed Models
===============
Fetches, parses, and caches RSS/Atom feed items for display on the portal.
"""
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── XML namespaces commonly found in RSS / Atom feeds ────────────
_NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}

# ── HTTP headers for outbound requests ───────────────────────────
_HTTP_HEADERS = {
    "User-Agent": "SkydellBot/1.0 (RSS Reader)",
}

# ── Date formats to try when RFC-2822 parsing fails ──────────────
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


# ══════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════


def _parse_date(raw):
    """
    Parse RFC-2822 or ISO-8601 date strings to a naive datetime.
    Returns None on failure instead of raising.
    """
    if not raw:
        return None
    raw = raw.strip()

    # Try RFC-2822 first (standard RSS pubDate format)
    try:
        return parsedate_to_datetime(raw).replace(tzinfo=None)
    except Exception:
        pass

    # Fall back to common ISO-8601 variants
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    _logger.debug("Could not parse date string: %r", raw)
    return None


def _find_image(item_el):
    """
    Extract image URL from the first matching source:
      1. media:content
      2. media:thumbnail
      3. <enclosure type="image/...">
    Returns empty string if none found.
    """
    for tag in ("media:content", "media:thumbnail"):
        el = item_el.find(tag, _NS)
        if el is not None and el.get("url"):
            return el.get("url")

    enc = item_el.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image/"):
        return enc.get("url") or ""

    return ""


def _text(item_el, *tags):
    """
    Return stripped text of the first matching tag among *tags.
    Falls back to empty string if none found or all are empty.
    """
    for tag in tags:
        el = item_el.find(tag, _NS)
        if el is not None and el.text:
            return el.text.strip()
    return ""


def _atom_link_href(item_el):
    """
    Extract href from Atom <link> element.
    Atom links are self-closing: <link href="..." rel="alternate"/>
    Falls back to text content for RSS <link> elements.
    """
    # Try Atom namespaced link first
    atom_link = item_el.find("{%s}link" % _NS["atom"])
    if atom_link is not None:
        href = atom_link.get("href")
        if href:
            return href.strip()
        # Some feeds put URL as text in <atom:link>
        if atom_link.text:
            return atom_link.text.strip()

    # Try plain RSS <link> (text content)
    rss_link = item_el.find("link")
    if rss_link is not None and rss_link.text:
        return rss_link.text.strip()

    return ""


def _parse_xml(raw, feed_url):
    """
    Parse raw bytes as XML.
    Strips UTF-8 BOM if present.
    Falls back to lxml on parse error.
    Raises UserError with a user-friendly message on total failure.
    """
    # Strip UTF-8 BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    try:
        return ET.fromstring(raw)
    except ET.ParseError as std_err:
        _logger.warning(
            "Standard XML parser failed for '%s': %s — trying lxml.",
            feed_url,
            std_err,
        )

    try:
        import lxml.etree as lET  # noqa: N813

        return lET.fromstring(raw)
    except Exception as lxml_err:
        _logger.error("lxml also failed for '%s': %s", feed_url, lxml_err)

    raise UserError(
        _(
            "Feed URL '%s' did not return valid XML.\n"
            "Please verify the URL is a valid RSS or Atom feed."
        )
        % feed_url
    )


# ══════════════════════════════════════════════════════════════════
# Models
# ══════════════════════════════════════════════════════════════════


class RssFeed(models.Model):
    _name = "rss.feed"
    _description = "RSS Feed"
    _order = "sequence, name"

    # ── Fields ───────────────────────────────────────────────────
    name = fields.Char(string="Feed Name", required=True)
    url = fields.Char(string="Feed URL", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    post_limit = fields.Integer(
        string="Posts to Display",
        default=5,
        help="Maximum number of items cached and shown from this feed.",
    )
    channel_title = fields.Char(
        string="Channel Title",
        readonly=True,
        help="Title fetched automatically from the RSS feed channel.",
    )
    last_fetch_date = fields.Datetime(string="Last Fetched", readonly=True)

    item_ids = fields.One2many("rss.feed.item", "feed_id", string="Cached Items")
    item_count = fields.Integer(
        compute="_compute_item_count",
        string="Cached Items",
    )

    # ── Computed ──────────────────────────────────────────────────
    @api.depends("item_ids")
    def _compute_item_count(self):
        for feed in self:
            feed.item_count = len(feed.item_ids)

    # ── Cron entry point ──────────────────────────────────────────
    @api.model
    def fetch_all_feeds(self):
        """Called by the scheduler — fetches all active feeds."""
        feeds = self.search([])
        _logger.info("Starting RSS fetch for %d feed(s).", len(feeds))
        for feed in feeds:
            try:
                feed._fetch_and_cache()
            except Exception:
                _logger.exception(
                    "Failed to fetch RSS feed '%s' (%s)",
                    feed.name,
                    feed.url,
                )

    # ── Core fetch logic ──────────────────────────────────────────
    def _fetch_and_cache(self):
        """
        Fetch this feed URL, parse items, and upsert into rss.feed.item.
        Keeps only the newest `post_limit` items per feed.
        """
        self.ensure_one()
        _logger.info("Fetching RSS feed: %s  (%s)", self.name, self.url)

        # ── Download ──────────────────────────────────────────────
        req = urllib.request.Request(self.url, headers=_HTTP_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
        except OSError as exc:
            # Covers URLError, socket errors, SSL errors, DNS failures
            raise UserError(
                _(
                    "Could not fetch feed '%(name)s' (%(url)s):\n%(error)s",
                    name=self.name,
                    url=self.url,
                    error=str(exc),
                )
            ) from exc

        # ── Parse XML ─────────────────────────────────────────────
        root = _parse_xml(raw.strip(), self.url)

        # ── Extract channel title ─────────────────────────────────
        self._update_channel_title(root)

        # ── Parse and cache items ─────────────────────────────────
        new_count = self._upsert_items(root)

        # ── Enforce post_limit ────────────────────────────────────
        self._trim_old_items()

        self.last_fetch_date = fields.Datetime.now()
        _logger.info("Feed '%s': %d new item(s) added.", self.name, new_count)

    def _update_channel_title(self, root):
        """Extract and save the channel title from parsed XML root."""
        title = ""

        # RSS 2.0 style
        channel = root.find("channel")
        if channel is not None:
            title_el = channel.find("title")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()

        # Atom style fallback
        if not title:
            atom_title = root.find("{%s}title" % _NS["atom"])
            if atom_title is not None and atom_title.text:
                title = atom_title.text.strip()

        if title:
            self.channel_title = title

    def _upsert_items(self, root):
        """
        Parse all <item> / <entry> elements and create missing ones.
        Returns the number of new records created.
        """
        Item = self.env["rss.feed.item"]

        # Collect GUIDs already cached for this feed
        existing_guids = set(Item.search([("feed_id", "=", self.id)]).mapped("guid"))

        # Find all items (RSS 2.0 or Atom)
        elements = root.findall(".//item") or root.findall(".//{%s}entry" % _NS["atom"])

        new_vals = []
        for el in elements:
            guid = _text(el, "guid", "id", "{%s}id" % _NS["atom"]) or _atom_link_href(
                el
            )

            # Skip if no identifier or already cached
            if not guid or guid in existing_guids:
                continue

            new_vals.append(
                {
                    "feed_id": self.id,
                    "guid": guid,
                    "title": _text(el, "title", "{%s}title" % _NS["atom"]),
                    "link": (_atom_link_href(el) or guid),
                    "description": _text(
                        el,
                        "description",
                        "{%s}encoded" % _NS["content"],
                        "{%s}summary" % _NS["atom"],
                        "{%s}content" % _NS["atom"],
                    ),
                    "pub_date": _parse_date(
                        _text(
                            el,
                            "pubDate",
                            "updated",
                            "{%s}updated" % _NS["atom"],
                            "{%s}date" % _NS["dc"],
                        )
                    ),
                    "image_url": _find_image(el),
                }
            )

        if new_vals:
            Item.create(new_vals)

        return len(new_vals)

    def _trim_old_items(self):
        """Delete items beyond post_limit, keeping newest ones."""
        Item = self.env["rss.feed.item"]
        all_items = Item.search(
            [("feed_id", "=", self.id)],
            order="pub_date desc, id desc",
        )
        to_delete = all_items[self.post_limit :]
        if to_delete:
            to_delete.unlink()
            _logger.debug(
                "Feed '%s': trimmed %d old item(s).",
                self.name,
                len(to_delete),
            )

    # ── Manual trigger ────────────────────────────────────────────
    def action_fetch_now(self):
        """Manual fetch — triggered from the backend form view."""
        for feed in self:
            feed._fetch_and_cache()
