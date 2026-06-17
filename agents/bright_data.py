"""
Bright Data API Integration for ShadowSignal
Provides real-time web scraping and SERP search capabilities.
"""
import os
import requests
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Bright Data API endpoints
BRIGHT_DATA_SERP_API = "https://api.brightdata.com/request"
BRIGHT_DATA_SCRAPER_API = "https://api.brightdata.com/request"


class BrightDataClient:
    """
    Bright Data client for real-time competitive intelligence.
    Uses SERP API for search results and Web Scraper API for page extraction.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search_google(self, query: str, num_results: int = 10, geo: str = "us") -> List[Dict]:
        """
        Search Google via Bright Data SERP API.
        Returns structured search results with title, URL, snippet.
        """
        if not self.api_key:
            logger.warning("[BrightData] No API key configured, returning empty results")
            return []

        payload = {
            "zone": "serp_api",  # Your SERP API zone name
            "url": f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num_results}",
            "format": "json",
            "geo": geo,
        }

        try:
            resp = requests.post(
                BRIGHT_DATA_SERP_API,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract organic results
            results = []
            organic = data.get("organic", []) or data.get("results", [])
            for item in organic[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", item.get("url", "")),
                    "snippet": item.get("snippet", item.get("description", "")),
                    "rank": item.get("rank", 0),
                })
            return results

        except Exception as e:
            logger.error(f"[BrightData] Search failed: {e}")
            return []

    def scrape_page(self, url: str) -> Optional[str]:
        """
        Scrape a specific webpage via Bright Data Web Scraper API.
        Returns clean text content.
        """
        if not self.api_key:
            return None

        payload = {
            "zone": "web_scraper",  # Your Web Scraper API zone name
            "url": url,
            "format": "raw",  # or "markdown" for LLM-ready format
        }

        try:
            resp = requests.post(
                BRIGHT_DATA_SCRAPER_API,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text[:5000]  # Limit to 5K chars

        except Exception as e:
            logger.error(f"[BrightData] Scrape failed for {url}: {e}")
            return None

    def get_competitive_intel(self, company_name: str) -> Dict[str, Any]:
        """
        Gather real-time competitive intelligence on a company.
        Searches for: pricing, security issues, news, reviews.
        """
        intel = {
            "company": company_name,
            "pricing": [],
            "security": [],
            "news": [],
            "reviews": [],
            "sources": [],
        }

        # 1. Search for pricing
        pricing_results = self.search_google(
            f"{company_name} pricing plans cost 2024 2025",
            num_results=5
        )
        for r in pricing_results:
            intel["pricing"].append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
            })
            intel["sources"].append(r["url"])

        # 2. Search for security/CVEs
        security_results = self.search_google(
            f"{company_name} CVE vulnerability security issue 2024",
            num_results=5
        )
        for r in security_results:
            intel["security"].append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
            })
            intel["sources"].append(r["url"])

        # 3. Search for recent news
        news_results = self.search_google(
            f"{company_name} news announcement 2024 2025",
            num_results=5
        )
        for r in news_results:
            intel["news"].append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
            })
            intel["sources"].append(r["url"])

        # 4. Search for reviews
        review_results = self.search_google(
            f"{company_name} reviews G2 Capterra customer feedback",
            num_results=3
        )
        for r in review_results:
            intel["reviews"].append({
                "title": r["title"],
                "url": r["url"],
                "snippet": r["snippet"],
            })
            intel["sources"].append(r["url"])

        return intel


def format_intel_for_llm(intel: Dict[str, Any]) -> str:
    """
    Format Bright Data intel into a structured prompt for the LLM.
    """
    sections = []
    sections.append(f"# Real-Time Competitive Intelligence: {intel['company']}")
    sections.append(f"Sources: {', '.join(set(intel['sources'][:10]))}")
    sections.append("")

    if intel["pricing"]:
        sections.append("## PRICING (Live Web Data)")
        for i, item in enumerate(intel["pricing"], 1):
            sections.append(f"{i}. {item['title']}")
            sections.append(f"   URL: {item['url']}")
            sections.append(f"   Snippet: {item['snippet'][:200]}")
            sections.append("")

    if intel["security"]:
        sections.append("## SECURITY / VULNERABILITIES (Live Web Data)")
        for i, item in enumerate(intel["security"], 1):
            sections.append(f"{i}. {item['title']}")
            sections.append(f"   URL: {item['url']}")
            sections.append(f"   Snippet: {item['snippet'][:200]}")
            sections.append("")

    if intel["news"]:
        sections.append("## RECENT NEWS (Live Web Data)")
        for i, item in enumerate(intel["news"], 1):
            sections.append(f"{i}. {item['title']}")
            sections.append(f"   URL: {item['url']}")
            sections.append(f"   Snippet: {item['snippet'][:200]}")
            sections.append("")

    if intel["reviews"]:
        sections.append("## CUSTOMER REVIEWS (Live Web Data)")
        for i, item in enumerate(intel["reviews"], 1):
            sections.append(f"{i}. {item['title']}")
            sections.append(f"   URL: {item['url']}")
            sections.append(f"   Snippet: {item['snippet'][:200]}")
            sections.append("")

    return "
".join(sections)
