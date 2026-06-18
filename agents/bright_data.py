"""
Bright Data API Integration for ShadowSignal
FIXED: Correct SERP API zone name (serp_api1), auth, and payload format.
Uses Bright Data SERP API v2 for Google search results.
"""
import os
import requests
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Bright Data SERP API endpoint
BRIGHT_DATA_API = "https://api.brightdata.com/request"


class BrightDataClient:
    """
    Bright Data client for real-time competitive intelligence.
    Uses SERP API zone 'serp_api1' for Google search results.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search_google(self, query: str, num_results: int = 10) -> List[Dict]:
        """
        Search Google via Bright Data SERP API.
        Zone: serp_api1
        """
        if not self.api_key:
            logger.warning("[BrightData] No API key configured")
            return []

        # EXACT payload from Bright Data dashboard (Screenshot 1)
        payload = {
            "zone": "serp_api1",
            "url": f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num_results}",
            "format": "json",
            "data_format": "parsed",
        }

        try:
            resp = requests.post(
                BRIGHT_DATA_API,
                headers=self.headers,
                json=payload,
                timeout=60,
            )

            # Bright Data SERP API returns 202 for async jobs
            if resp.status_code == 202:
                logger.info("[BrightData] Async job submitted, polling not implemented yet")
                return []

            resp.raise_for_status()
            data = resp.json()

            # Parse response based on data_format=parsed
            results = []

            # Try different response structures
            if isinstance(data, dict):
                # Parsed format usually has nested structure
                organic = data.get("organic", [])
                if not organic and "results" in data:
                    organic = data["results"]
                if not organic and "data" in data and isinstance(data["data"], dict):
                    organic = data["data"].get("organic", [])

                for item in organic[:num_results]:
                    if not isinstance(item, dict):
                        continue
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", item.get("url", "")),
                        "snippet": item.get("snippet", item.get("description", "")),
                        "rank": item.get("rank", 0),
                    })

            logger.info(f"[BrightData] Got {len(results)} results for: {query[:50]}")
            return results

        except requests.exceptions.HTTPError as e:
            logger.error(f"[BrightData] HTTP {resp.status_code}: {resp.text[:300]}")
            return []
        except Exception as e:
            logger.error(f"[BrightData] Search error: {e}")
            return []

    def get_competitive_intel(self, company_name: str) -> Dict[str, Any]:
        """Gather competitive intelligence with isolated searches."""
        intel = {
            "company": company_name,
            "pricing": [],
            "security": [],
            "news": [],
            "reviews": [],
            "sources": [],
        }

        searches = [
            ("pricing", f"{company_name} pricing plans cost 2024 2025"),
            ("security", f"{company_name} CVE vulnerability security issue 2024"),
            ("news", f"{company_name} news announcement 2024 2025"),
            ("reviews", f"{company_name} reviews G2 Capterra customer feedback"),
        ]

        for category, query in searches:
            try:
                results = self.search_google(query, num_results=5)
                for r in results:
                    intel[category].append({
                        "title": r["title"],
                        "url": r["url"],
                        "snippet": r["snippet"],
                    })
                    if r["url"]:
                        intel["sources"].append(r["url"])
            except Exception as e:
                logger.warning(f"[BrightData] {category} search failed: {e}")

        intel["sources"] = list(set(intel["sources"]))[:10]
        return intel


def format_intel_for_llm(intel: Dict[str, Any]) -> str:
    """Format intel into structured prompt for LLM."""
    sections = []
    sections.append(f"# Real-Time Competitive Intelligence: {intel['company']}")
    if intel["sources"]:
        sections.append(f"Sources: {', '.join(intel['sources'][:10])}")
    sections.append("")

    for category in ["pricing", "security", "news", "reviews"]:
        if intel[category]:
            sections.append(f"## {category.upper()} (Live Web Data)")
            for i, item in enumerate(intel[category], 1):
                sections.append(f"{i}. {item['title']}")
                sections.append(f"   URL: {item['url']}")
                sections.append(f"   Snippet: {item['snippet'][:200]}")
                sections.append("")

    return "\n".join(sections)
