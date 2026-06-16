"""
Band REST API Client
Direct HTTP calls to Band's Request API — no SDK required.
Docs: https://docs.band.ai/integrations/custom-integration
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

BAND_REST_URL = os.getenv("THENVOI_REST_URL", "https://app.band.ai").rstrip("/")


class BandClient:
    def __init__(self, agent_api_key: str):
        self.api_key = agent_api_key
        self.base = BAND_REST_URL
        self.headers = {
            "Authorization": f"Bearer {agent_api_key}",
            "Content-Type": "application/json",
        }

    def me(self) -> dict:
        """Validate connection and get agent identity."""
        r = requests.get(f"{self.base}/api/v1/agent/me", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_chats(self) -> list:
        """List all chats this agent is part of."""
        r = requests.get(f"{self.base}/api/v1/agent/chats", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def send_message(self, chat_id: str, content: str) -> dict:
        """Send a message to a chat room."""
        r = requests.post(
            f"{self.base}/api/v1/agent/chats/{chat_id}/messages",
            headers=self.headers,
            json={"content": content},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def get_next_message(self, chat_id: str) -> dict | None:
        """Poll for next unprocessed message. Returns None if no messages."""
        r = requests.get(
            f"{self.base}/api/v1/agent/chats/{chat_id}/messages/next",
            headers=self.headers,
            timeout=10,
        )
        if r.status_code == 204:
            return None
        r.raise_for_status()
        return r.json()

    def mark_processing(self, message_id: str) -> None:
        requests.post(
            f"{self.base}/api/v1/messages/{message_id}/processing",
            headers=self.headers,
            timeout=10,
        )

    def mark_processed(self, message_id: str) -> None:
        requests.post(
            f"{self.base}/api/v1/messages/{message_id}/processed",
            headers=self.headers,
            timeout=10,
        )

    def mark_failed(self, message_id: str, reason: str = "") -> None:
        requests.post(
            f"{self.base}/api/v1/messages/{message_id}/failed",
            headers=self.headers,
            json={"reason": reason},
            timeout=10,
        )

    def add_participant(self, chat_id: str, agent_id: str) -> dict:
        r = requests.post(
            f"{self.base}/api/v1/agent/chats/{chat_id}/participants",
            headers=self.headers,
            json={"agent_id": agent_id},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
