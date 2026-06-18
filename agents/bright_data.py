"""
Bright Data API Integration for ShadowSignal
FIXED: Correct SERP API zone (serp_api1), response parsing, and fallback.
"""
import os
import requests
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

BRIGHT_DATA_API = "https://api.brightdata.com/request"


class BrightDataClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRIGHT_DATA_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search_google(self, query: str, num_results: int = 10) -> List[Dict]:
        if not self.api_key:
            logger.warning("[BrightData] No API key")
            return []

        payload = {
            "zone": "serp_api1",
            "url": f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num_results}",
            "format": "json",
            "data_format": "parsed",
        }

        try:
            resp = requests.post(BRIGHT_DATA_API, headers=self.headers, json=payload, timeout=60)

            if resp.status_code == 202:
                logger.info("[BrightData] Async job submitted")
                return []

            resp.raise_for_status()
            data = resp.json()

            # Log raw response for debugging
            logger.debug(f"[BrightData] Raw response keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")

            results = []
            organic = []

            # Try ALL possible response structures
            if isinstance(data, dict):
                # Direct organic
                if "organic" in data and isinstance(data["organic"], list):
                    organic = data["organic"]
                # Nested in data
                elif "data" in data and isinstance(data["data"], dict):
                    if "organic" in data["data"]:
                        organic = data["data"]["organic"]
                    elif "results" in data["data"]:
                        organic = data["data"]["results"]
                # Results key
                elif "results" in data and isinstance(data["results"], list):
                    organic = data["results"]
                # Search results key
                elif "search_results" in data and isinstance(data["search_results"], list):
                    organic = data["search_results"]
                # Try to find any list that looks like search results
                else:
                    for key, val in data.items():
                        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                            if any(k in val[0] for k in ["title", "link", "url", "snippet", "description"]):
                                organic = val
                                logger.info(f"[BrightData] Found results in key: {key}")
                                break

            for item in organic[:num_results]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                url = item.get("link", item.get("url", ""))
                snippet = item.get("snippet", item.get("description", item.get("body", "")))
                if title or url:  # Only add if we have at least title or URL
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "rank": item.get("rank", 0),
                    })

            logger.info(f"[BrightData] Parsed {len(results)} results for: {query[:50]}")
            return results

        except Exception as e:
            logger.error(f"[BrightData] Error: {e}")
            return []

    def get_competitive_intel(self, company_name: str) -> Dict[str, Any]:
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

        # FALLBACK: If no web data at all, add a marker so LLM knows
        total_results = sum(len(intel[k]) for k in ["pricing", "security", "news", "reviews"])
        if total_results == 0:
            logger.warning(f"[BrightData] No real-time data available for {company_name}")
            intel["_no_data"] = True

        return intel


def format_intel_for_llm(intel: Dict[str, Any]) -> str:
    if intel.get("_no_data"):
        return f"[NOTE: No real-time web data available for {intel['company']}. Using general knowledge.]"

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
