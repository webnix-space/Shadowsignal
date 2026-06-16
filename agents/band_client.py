import requests
import json
import time
from typing import Optional, Dict, Any

class BandClient:
    """
    Resilient Band.ai REST API client with:
    - Exponential backoff on 5xx errors
    - Request/response logging
    - Timeout handling
    - Graceful degradation
    """

    def __init__(self, api_key: str, base_url: str = "https://app.band.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.max_retries = 2
        self.timeout = 15

        # Track last request for debugging
        self.last_request = None
        self.last_response = None

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Execute HTTP request with retry logic and logging.
        Returns parsed JSON or None on failure.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # Merge default headers
        headers = {**self.headers}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        self.last_request = {
            "method": method,
            "url": url,
            "headers": {k: v for k, v in headers.items() if k.lower() != "authorization"},
            "kwargs": kwargs
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs
                )

                self.last_response = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body_preview": response.text[:500] if response.text else ""
                }

                # Handle 5xx errors — retry with backoff
                if response.status_code >= 500:
                    print(f"[BandClient] {method} {endpoint} -> {response.status_code} (attempt {attempt+1}/{self.max_retries+1})")
                    if attempt < self.max_retries:
                        backoff = 2 ** attempt
                        print(f"[BandClient] Retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue
                    else:
                        print(f"[BandClient] Max retries exceeded. Giving up.")
                        return None

                # Handle 4xx errors — don't retry, log and return None
                if response.status_code >= 400:
                    print(f"[BandClient] {method} {endpoint} -> {response.status_code}: {response.text[:200]}")
                    return None

                # Success
                if response.status_code == 204 or not response.text:
                    return {}

                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"[BandClient] Invalid JSON response: {response.text[:200]}")
                    return None

            except requests.exceptions.Timeout:
                print(f"[BandClient] Timeout on {method} {endpoint} (attempt {attempt+1})")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None

            except requests.exceptions.ConnectionError as e:
                print(f"[BandClient] Connection error: {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None

            except Exception as e:
                print(f"[BandClient] Unexpected error: {e}")
                return None

        return None

    # ─── Agent Endpoints ───

    def get_me(self) -> Optional[Dict]:
        """Get current agent profile."""
        return self._request("GET", "/agent/me")

    def get_chats(self) -> Optional[Dict]:
        """Get list of chats for this agent."""
        return self._request("GET", "/agent/chats")

    def get_chat(self, chat_id: str) -> Optional[Dict]:
        """Get specific chat details."""
        return self._request("GET", f"/agent/chats/{chat_id}")

    def get_messages(self, chat_id: str, limit: int = 50) -> list:
        """
        Get messages from chat.
        Returns list of messages (empty list on error).
        """
        result = self._request("GET", f"/agent/chats/{chat_id}/messages", params={"limit": limit})
        if result and isinstance(result, dict):
            return result.get("messages", []) or result.get("data", [])
        return []

    def send_message(self, chat_id: str, content: str, event_payload: Optional[Dict] = None) -> Optional[Dict]:
        """
        Send a message to chat.
        If event_payload is provided, also emits an event.
        Returns response dict or None on failure.
        """
        payload = {
            "content": content,
            "type": "text"
        }

        # Send the message itself
        result = self._request("POST", f"/agent/chats/{chat_id}/messages", json=payload)

        # If we have event payload, try to emit it (but don't fail the whole operation)
        if event_payload and result:
            event_result = self.emit_event(chat_id, "agent_action", event_payload)
            if event_result is None:
                print(f"[BandClient] Event emission failed, but message was sent")

        return result

    def emit_event(self, chat_id: str, event_type: str, payload: Dict) -> Optional[Dict]:
        """
        Emit an event to chat.
        NOTE: This endpoint seems unstable (500 errors). We handle gracefully.
        """
        event_data = {
            "type": event_type,
            "payload": payload
        }
        return self._request("POST", f"/agent/chats/{chat_id}/events", json=event_data)

    def mark_processing(self, chat_id: str, message_id: str) -> bool:
        """Mark message as being processed."""
        result = self._request(
            "POST", 
            f"/agent/chats/{chat_id}/messages/{message_id}/processing"
        )
        return result is not None

    def mark_processed(self, chat_id: str, message_id: str) -> bool:
        """Mark message as processed."""
        result = self._request(
            "POST", 
            f"/agent/chats/{chat_id}/messages/{message_id}/processed"
        )
        return result is not None

    def mark_failed(self, chat_id: str, message_id: str, reason: str = "") -> bool:
        """Mark message processing as failed."""
        result = self._request(
            "POST", 
            f"/agent/chats/{chat_id}/messages/{message_id}/failed",
            json={"reason": reason} if reason else None
        )
        return result is not None

    def get_next_message(self, chat_id: str) -> Optional[Dict]:
        """
        Poll for next unprocessed message.
        Returns single message or None.
        """
        result = self._request("GET", f"/agent/chats/{chat_id}/messages/next")
        if result and isinstance(result, dict):
            # Could be wrapped in 'data' or direct
            return result.get("data", result)
        return None

    def get_events(self, chat_id: str) -> list:
        """Get events for chat."""
        result = self._request("GET", f"/agent/chats/{chat_id}/events")
        if result and isinstance(result, dict):
            return result.get("events", []) or result.get("data", [])
        return []

    def get_members(self, chat_id: str) -> list:
        """Get chat members."""
        result = self._request("GET", f"/agent/chats/{chat_id}/members")
        if result and isinstance(result, dict):
            return result.get("members", []) or result.get("data", [])
        return []

    def get_debug_info(self) -> Dict:
        """Get last request/response for debugging."""
        return {
            "last_request": self.last_request,
            "last_response": self.last_response
        }
