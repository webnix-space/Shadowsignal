"""
Free data layer. No API keys.
- Google News RSS search (keyword-targeted headlines + publisher)
- DuckDuckGo Instant Answer (encyclopedic abstract when available)
"""
import html
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote_plus

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShadowSignal/3.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, application/json, */*",
}
TIMEOUT = 8
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str, limit: int = 300) -> str:
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_google_news(xml_text: str, max_items: int = 5) -> list:
    """Parse a Google News RSS document into source dicts."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("RSS parse error: %s", e)
        return out
    for item in root.iter("item"):
        title = _clean(item.findtext("title", ""), 200)
        link = (item.findtext("link", "") or "").strip()
        if not title or not link:
            continue
        pub = item.findtext("pubDate", "") or ""
        src_el = item.find("source")
        publisher = _clean(src_el.text if src_el is not None else "", 80) or "Google News"
        # Google News titles end with " - Publisher"; strip it, publisher is separate
        if publisher and title.endswith(" - " + publisher):
            title = title[: -len(publisher) - 3]
        snippet = _clean(item.findtext("description", ""), 300)
        if snippet.lower().startswith(title.lower()[:40]):
            snippet = ""
        out.append({
            "title": title,
            "url": link,
            "source": publisher,
            "snippet": snippet or ("Published " + pub if pub else ""),
            "published": pub,
        })
        if len(out) >= max_items:
            break
    return out


def google_news(query: str, max_items: int = 5) -> list:
    url = "https://news.google.com/rss/search?q=%s&hl=en-US&gl=US&ceid=US:en" % quote_plus(query)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return parse_google_news(resp.text, max_items)
    except Exception as e:
        logger.warning("Google News failed for %r: %s", query, e)
        return []


def duckduckgo_abstract(query: str) -> list:
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1",
                    "skip_disambig": "1", "no_redirect": "1"},
            headers=HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("Abstract") and data.get("AbstractURL"):
            return [{
                "title": data.get("Heading") or query,
                "url": data["AbstractURL"],
                "source": data.get("AbstractSource") or "DuckDuckGo",
                "snippet": _clean(data["Abstract"], 400),
                "published": "",
            }]
    except Exception as e:
        logger.warning("DuckDuckGo failed for %r: %s", query, e)
    return []


def get_competitive_intel(company: str, max_sources: int = 12) -> dict:
    """Gather sources about a company in parallel. Returns {'sources': [...], ...}."""
    jobs = [
        lambda: duckduckgo_abstract(company),
        lambda: google_news('"%s"' % company, 6),
        lambda: google_news("%s pricing OR price OR contract" % company, 4),
        lambda: google_news("%s security OR vulnerability OR breach OR CVE" % company, 4),
        lambda: google_news("%s competitors OR market share OR earnings" % company, 4),
    ]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(lambda j: j(), jobs))

    seen, sources = set(), []
    for batch in results:
        for s in batch:
            key = s["url"]
            if key in seen:
                continue
            seen.add(key)
            sources.append(s)
    sources = sources[:max_sources]
    logger.info("Gathered %d sources for %r", len(sources), company)
    return {"company": company, "sources": sources, "timestamp": datetime.utcnow().isoformat()}


def format_sources_for_llm(sources: list) -> str:
    lines = []
    for i, s in enumerate(sources, 1):
        when = (" | " + s["published"]) if s.get("published") else ""
        lines.append("[%d] %s (%s%s)\n    %s" % (i, s["title"], s["source"], when, s.get("snippet", "")))
    return "\n".join(lines)
