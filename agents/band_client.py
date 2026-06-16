import requests
import json
import time
from typing import Optional, Dict, Any, List

class BandClient:
    """
    FIXED: Uses X-API-Key header for Band.ai authentication.
    """

    def __init__(self, api_key: str, base_url: str = "https://app.band.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.max_retries = 2
        self.timeout = 15

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint.lstrip("/")}"
        headers = {**self.headers}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs
                )

                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    return None

                if response.status_code >= 400:
                    return None

                if response.status_code == 204 or not response.text:
                    return {}

                try:
                    return response.json()
                except json.JSONDecodeError:
                    return None

            except requests.exceptions.RequestException:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None
            except Exception:
                return None

        return None

    def get_me(self) -> Optional[Dict]:
        return self._request("GET", "/agent/me")

    def get_chats(self) -> Optional[Dict]:
        return self._request("GET", "/agent/chats")

    def get_chat(self, chat_id: str) -> Optional[Dict]:
        return self._request("GET", f"/agent/chats/{chat_id}")

    def get_messages(self, chat_id: str, limit: int = 50) -> list:
        result = self._request("GET", f"/agent/chats/{chat_id}/messages", params={"limit": limit})
        if result and isinstance(result, dict):
            return result.get("messages", []) or result.get("data", [])
        return []

    def send_message(self, chat_id: str, content: str) -> Optional[Dict]:
        payload = {"content": content, "type": "text"}
        return self._request("POST", f"/agent/chats/{chat_id}/messages", json=payload)

    def mark_processing(self, chat_id: str, message_id: str) -> bool:
        return self._request(
            "POST", f"/agent/chats/{chat_id}/messages/{message_id}/processing"
        ) is not None

    def mark_processed(self, chat_id: str, message_id: str) -> bool:
        return self._request(
            "POST", f"/agent/chats/{chat_id}/messages/{message_id}/processed"
        ) is not None

    def mark_failed(self, chat_id: str, message_id: str, reason: str = "") -> bool:
        return self._request(
            "POST", f"/agent/chats/{chat_id}/messages/{message_id}/failed",
            json={"reason": reason} if reason else None
        ) is not None

    def get_next_message(self, chat_id: str) -> Optional[Dict]:
        result = self._request("GET", f"/agent/chats/{chat_id}/messages/next")
        if result and isinstance(result, dict):
            return result.get("data", result)
        return None

    def get_events(self, chat_id: str) -> list:
        result = self._request("GET", f"/agent/chats/{chat_id}/events")
        if result and isinstance(result, dict):
            return result.get("events", []) or result.get("data", [])
        return []

    def get_members(self, chat_id: str) -> list:
        result = self._request("GET", f"/agent/chats/{chat_id}/members")
        if result and isinstance(result, dict):
            return result.get("members", []) or result.get("data", [])
        return []
