"""
Bright Data Client for ShadowSignal
Supports both SERP API (for search) and Web Unlocker (for direct scraping).
Uses proper Bright Data REST API with Bearer auth.
"""
import logging
import os
import requests
import re

logger = logging.getLogger(__name__)

BRIGHT_DATA_BASE = "https://api.brightdata.com"


class BrightDataClient:
    def __init__(self):
        self.api_key = os.getenv("BRIGHT_DATA_API_KEY", "").strip()
        self.zone = os.getenv("BRIGHT_DATA_ZONE", "").strip()
        self.enabled = bool(self.api_key and self.zone)
        if self.enabled:
            logger.info("[BrightData] Client initialized with zone: %s", self.zone)
        else:
            logger.warning("[BrightData] Missing API key or zone — real-time intel disabled")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search_google(self, query: str, num_results: int = 5) -> dict:
        """Use Bright Data SERP API to search Google. Returns structured results."""
        if not self.enabled:
            return {"results": [], "sources": [], "error": "Bright Data not configured"}

        url = f"{BRIGHT_DATA_BASE}/request"
        payload = {
            "zone": self.zone,
            "url": f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num_results}",
            "format": "raw",
            "data_format": "markdown",
            "country": "us",
        }

        try:
            logger.info(f"[BrightData] Searching Google: {query[:60]}...")
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()

            content = data.get("content", data.get("html", data.get("body", "")))
            results = self._parse_search_results(content, query)

            logger.info(f"[BrightData] Found {len(results)} results for: {query[:60]}")
            return {
                "results": results,
                "sources": [r.get("link", "") for r in results if r.get("link")],
                "raw": content[:2000] if isinstance(content, str) else str(content)[:2000],
            }
        except requests.exceptions.Timeout:
            logger.error("[BrightData] Search timeout")
            return {"results": [], "sources": [], "error": "timeout"}
        except Exception as e:
            logger.error(f"[BrightData] Search error: {e}")
            return {"results": [], "sources": [], "error": str(e)}

    def scrape_url(self, target_url: str) -> dict:
        """Use Bright Data Web Unlocker to scrape a specific URL."""
        if not self.enabled:
            return {"content": "", "sources": [], "error": "Bright Data not configured"}

        url = f"{BRIGHT_DATA_BASE}/request"
        payload = {
            "zone": self.zone,
            "url": target_url,
            "format": "raw",
            "data_format": "markdown",
            "country": "us",
        }

        try:
            logger.info(f"[BrightData] Scraping: {target_url[:80]}...")
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", data.get("html", data.get("body", "")))

            return {
                "content": content[:5000] if isinstance(content, str) else str(content)[:5000],
                "sources": [target_url],
                "title": data.get("title", ""),
            }
        except Exception as e:
            logger.error(f"[BrightData] Scrape error: {e}")
            return {"content": "", "sources": [], "error": str(e)}

    def _parse_search_results(self, content: str, query: str) -> list:
        """Parse search results from Bright Data response content."""
        results = []
        if not content:
            return results

        # Pattern 1: Markdown links [title](url)
        md_links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', content)
        for title, link in md_links[:10]:
            desc = ""
            idx = content.find(f"[{title}]({link})")
            if idx >= 0:
                after = content[idx + len(f"[{title}]({link})"):idx + 500]
                desc_match = re.search(r'[\n\r]+([^\n\r]{50,300})', after)
                if desc_match:
                    desc = desc_match.group(1).strip()
            results.append({
                "title": title,
                "link": link,
                "description": desc or "No description available",
            })

        # Pattern 2: HTML organic results
        if not results:
            html_links = re.findall(r'<h3[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', content, re.DOTALL)
            for link, title in html_links[:10]:
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                results.append({
                    "title": title_clean,
                    "link": link,
                    "description": "Extracted from search results",
                })

        return results

    def get_competitive_intel(self, company: str) -> dict:
        """Gather multi-faceted competitive intel using Bright Data SERP API."""
        if not self.enabled:
            return {"sources": [], "pricing": "", "security": "", "contract": "", "supply": ""}

        intel = {
            "pricing": [],
            "security": [],
            "contract": [],
            "supply": [],
            "sources": [],
        }

        queries = [
            ("pricing", f"{company} pricing plans cost enterprise 2026"),
            ("security", f"{company} CVE vulnerability security issue 2026"),
            ("contract", f"{company} contract terms renewal enterprise agreement 2026"),
            ("supply", f"{company} supply chain availability lead time stock 2026"),
        ]

        for category, query in queries:
            try:
                result = self.search_google(query, num_results=3)
                items = result.get("results", [])
                for item in items:
                    intel[category].append(f"{item.get('title', 'N/A')}: {item.get('description', 'N/A')[:200]}")
                    if item.get('link'):
                        intel["sources"].append(item['link'])
            except Exception as e:
                logger.warning(f"[BrightData] {category} search failed: {e}")

        return intel


def format_intel_for_llm(intel: dict) -> str:
    """Format Bright Data intel for LLM consumption."""
    sections = []

    for category in ["pricing", "security", "contract", "supply"]:
        items = intel.get(category, [])
        if items:
            sections.append(f"**{category.upper()}**")
            for item in items:
                sections.append(f"- {item}")
            sections.append("")

    sources = intel.get("sources", [])
    if sources:
        sections.append("**Sources:**")
        for src in set(sources)[:5]:
            sections.append(f"- {src}")

    return "\n".join(sections) if sections else "No real-time web data available."
