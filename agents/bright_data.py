"""
Bright Data Client for ShadowSignal — FIXED
Supports both SERP API (search) and Web Unlocker (direct scraping).
Uses proper Bright Data REST API with Bearer auth.

FIXED: resp.json() crash when API returns HTML/error page
FIXED: Proper response handling for both JSON and raw HTML responses
FIXED: Better error logging with response preview
FIXED: Zone configuration validation
FIXED: Result parsing from raw HTML content
"""
import logging
import os
import requests
import re
import json

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
            missing = []
            if not self.api_key:
                missing.append("BRIGHT_DATA_API_KEY")
            if not self.zone:
                missing.append("BRIGHT_DATA_ZONE")
            logger.warning("[BrightData] Missing %s — real-time intel disabled", ", ".join(missing))

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _safe_json(self, resp):
        """Safely parse JSON response, handle HTML errors gracefully."""
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as e:
            # API returned HTML or non-JSON
            text_preview = resp.text[:500] if hasattr(resp, 'text') else 'N/A'
            logger.error("[BrightData] JSON parse failed: %s | Status: %s | Preview: %s",
                         e, resp.status_code, text_preview[:200])
            return {"_raw": resp.text if hasattr(resp, 'text') else "", "_error": str(e)}

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
            logger.info("[BrightData] Searching Google: %s...", query[:60])
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)

            # Handle HTTP errors first
            if resp.status_code >= 400:
                text_preview = resp.text[:300] if hasattr(resp, 'text') else 'N/A'
                logger.error("[BrightData] HTTP %s: %s", resp.status_code, text_preview[:200])
                return {"results": [], "sources": [], "error": f"HTTP {resp.status_code}: {text_preview[:200]}"}

            # Safely parse response
            data = self._safe_json(resp)

            # If we got raw HTML instead of JSON, use it directly
            content = data.get("content") or data.get("html") or data.get("body") or data.get("_raw", "")

            if not content:
                logger.warning("[BrightData] Empty response content for query: %s", query[:60])
                return {"results": [], "sources": [], "error": "Empty response"}

            results = self._parse_search_results(content, query)

            logger.info("[BrightData] Found %s results for: %s", len(results), query[:60])
            return {
                "results": results,
                "sources": [r.get("link", "") for r in results if r.get("link")],
                "raw": content[:2000] if isinstance(content, str) else str(content)[:2000],
            }
        except requests.exceptions.Timeout:
            logger.error("[BrightData] Search timeout for: %s", query[:60])
            return {"results": [], "sources": [], "error": "timeout"}
        except requests.exceptions.ConnectionError as e:
            logger.error("[BrightData] Connection error: %s", e)
            return {"results": [], "sources": [], "error": f"connection_error: {str(e)}"}
        except Exception as e:
            logger.error("[BrightData] Search error: %s", e)
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
            logger.info("[BrightData] Scraping: %s...", target_url[:80])
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)

            if resp.status_code >= 400:
                return {"content": "", "sources": [], "error": f"HTTP {resp.status_code}"}

            data = self._safe_json(resp)
            content = data.get("content") or data.get("html") or data.get("body") or data.get("_raw", "")

            return {
                "content": content[:5000] if isinstance(content, str) else str(content)[:5000],
                "sources": [target_url],
                "title": data.get("title", ""),
            }
        except Exception as e:
            logger.error("[BrightData] Scrape error: %s", e)
            return {"content": "", "sources": [], "error": str(e)}

    def _parse_search_results(self, content: str, query: str) -> list:
        """Parse search results from Bright Data response content (HTML or markdown)."""
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

        # Pattern 2: HTML organic results (title + link + snippet)
        if not results:
            # Try to extract from raw HTML
            html_titles = re.findall(r'<h3[^>]*>(.*?)</h3>', content, re.DOTALL | re.IGNORECASE)
            html_links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', content, re.IGNORECASE)
            html_snippets = re.findall(r'<span[^>]*class="[^"]*(?:VwiC3b|snippet|description)[^"]*"[^>]*>(.*?)</span>', 
                                       content, re.DOTALL | re.IGNORECASE)

            for i in range(min(len(html_titles), len(html_links), 5)):
                title_clean = re.sub(r'<[^>]+>', '', html_titles[i]).strip()
                results.append({
                    "title": title_clean,
                    "link": html_links[i],
                    "description": html_snippets[i] if i < len(html_snippets) else "Extracted from search results",
                })

        # Pattern 3: Generic link extraction from any HTML
        if not results:
            all_links = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]{10,200})</a>', content, re.IGNORECASE)
            for link, title in all_links[:10]:
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                if title_clean and len(title_clean) > 5:
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

                # Log if no results for this category
                if not items:
                    logger.warning("[BrightData] No results for %s query: %s", category, query[:60])

            except Exception as e:
                logger.warning("[BrightData] %s search failed: %s", category, e)

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
        for src in list(dict.fromkeys(sources))[:5]:
            sections.append(f"- {src}")

    return "\n".join(sections) if sections else "No real-time web data available."
