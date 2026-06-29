"""
ShadowSignal Free Data — replaces Bright Data.
Uses RSS feeds + DuckDuckGo Instant Answer API.
Zero API keys required.
"""
import os
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)

# Free RSS feeds for competitive intelligence
RSS_FEEDS = {
    "tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    ],
    "business": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.ft.com/rss/home",
    ],
    "finance": [
        "https://feeds.reuters.com/reuters/financeNews",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://coindesk.com/arc/outboundfeeds/rss/",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShadowSignal/2.0; +https://shadowsignal-intel.vercel.app)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def search_duckduckgo(query: str, max_results: int = 5) -> list:
    """
    Search DuckDuckGo Instant Answer API — completely free, no key needed.
    Returns list of result dicts with title, snippet, url.
    """
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
                "no_redirect": "1",
            },
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []

        # Abstract (main answer)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data["Abstract"],
                "url": data.get("AbstractURL", ""),
                "source": data.get("AbstractSource", "DuckDuckGo"),
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                    "source": "DuckDuckGo",
                })

        # Results
        for r in data.get("Results", [])[:max_results]:
            results.append({
                "title": r.get("Text", "")[:80],
                "snippet": r.get("Text", ""),
                "url": r.get("FirstURL", ""),
                "source": "DuckDuckGo",
            })

        logger.info(f"[FreeData] DuckDuckGo: {len(results)} results for '{query}'")
        return results[:max_results]

    except Exception as e:
        logger.error(f"[FreeData] DuckDuckGo error: {e}")
        return []


def fetch_rss_feed(url: str, keyword: str = "", max_items: int = 5) -> list:
    """Fetch and parse a single RSS feed, optionally filter by keyword."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = []

        # Handle both RSS and Atom formats
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)

        for entry in entries[:20]:
            # RSS format
            title = entry.findtext("title") or entry.findtext("atom:title", namespaces=ns) or ""
            desc = entry.findtext("description") or entry.findtext("atom:summary", namespaces=ns) or ""
            link = entry.findtext("link") or ""
            if not link:
                link_el = entry.find("atom:link", ns)
                if link_el is not None:
                    link = link_el.get("href", "")
            pub = entry.findtext("pubDate") or entry.findtext("atom:published", namespaces=ns) or ""

            title = title.strip()
            desc = desc.strip()[:300]

            if keyword and keyword.lower() not in title.lower() and keyword.lower() not in desc.lower():
                continue

            if title:
                items.append({
                    "title": title,
                    "snippet": desc,
                    "url": link,
                    "source": url.split("/")[2],
                    "published": pub,
                })

            if len(items) >= max_items:
                break

        return items

    except Exception as e:
        logger.warning(f"[FreeData] RSS error for {url}: {e}")
        return []


def get_competitive_intel(company: str) -> dict:
    """
    Main intel gathering function — replaces BrightDataClient.get_competitive_intel()
    Uses DuckDuckGo + RSS feeds.
    """
    logger.info(f"[FreeData] Gathering intel for: {company}")
    sources = []

    # 1. DuckDuckGo search
    ddg_results = search_duckduckgo(f"{company} news latest 2026", max_results=5)
    sources.extend(ddg_results)

    ddg_results2 = search_duckduckgo(f"{company} competitive analysis market", max_results=3)
    sources.extend(ddg_results2)

    # 2. RSS feeds — search tech + business feeds for company mentions
    feed_categories = ["tech", "business"]
    for category in feed_categories:
        for feed_url in RSS_FEEDS[category][:2]:  # max 2 per category
            items = fetch_rss_feed(feed_url, keyword=company, max_items=3)
            sources.extend(items)

    # Deduplicate by URL
    seen = set()
    unique_sources = []
    for s in sources:
        url = s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique_sources.append(s)

    logger.info(f"[FreeData] Total sources gathered: {len(unique_sources)}")

    return {
        "company": company,
        "sources": unique_sources[:10],
        "timestamp": datetime.utcnow().isoformat(),
        "enabled": True,
    }


def format_intel_for_llm(intel: dict) -> str:
    """Format intel dict for injection into LLM context."""
    if not intel.get("sources"):
        return "No real-time data available."

    lines = [f"Real-time intelligence for {intel.get('company', 'target')}:\n"]
    for i, source in enumerate(intel["sources"][:6], 1):
        lines.append(f"[{i}] {source.get('title', 'No title')}")
        if source.get("snippet"):
            lines.append(f"    {source['snippet'][:200]}")
        if source.get("url"):
            lines.append(f"    Source: {source['url']}")
        lines.append("")

    return "\n".join(lines)


class BrightDataClient:
    """
    Drop-in replacement for the original BrightDataClient.
    Uses free RSS + DuckDuckGo instead.
    """
    def __init__(self):
        self.enabled = True
        logger.info("[FreeData] BrightDataClient replacement initialized (RSS + DuckDuckGo)")

    def get_competitive_intel(self, company: str) -> dict:
        return get_competitive_intel(company)

    def search_google(self, query: str, num_results: int = 5) -> dict:
        results = search_duckduckgo(query, max_results=num_results)
        return {
            "success": True,
            "results": results,
            "query": query,
            "source": "DuckDuckGo (free)",
        }
