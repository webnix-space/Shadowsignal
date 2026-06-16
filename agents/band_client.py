"""
Band REST API Client
Uses X-API-Key header (NOT Bearer token).
Base URL: https://app.band.ai/api/v1/agent
Docs: https://docs.band.ai/api/agent-api
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

BAND_BASE = "https://app.band.ai/api/v1/agent"


class BandClient:
    def __init__(self, agent_api_key: str):
        self.api_key = agent_api_key
        self.headers = {
            "X-API-Key": agent_api_key,
            "Content-Type": "application/json",
        }

    def me(self) -> dict:
        """Validate connection and get agent identity."""
        r = requests.get(f"{BAND_BASE}/me", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_chats(self) -> list:
        r = requests.get(f"{BAND_BASE}/chats", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_participants(self, chat_id: str) -> list:
        r = requests.get(
            f"{BAND_BASE}/chats/{chat_id}/participants",
            headers=self.headers,
            timeout=10
        )
        r.raise_for_status()
        return r.json()

    def send_message(self, chat_id: str, content: str, mentions: list = None) -> dict:
        """
        Send a message to a chat room.
        Requires at least one @mention.
        mentions = [{"id": "uuid", "name": "AgentName", "handle": "handle"}]
        """
        payload = {
            "message": {
                "content": content,
                "mentions": mentions or []
            }
        }
        r = requests.post(
            f"{BAND_BASE}/chats/{chat_id}/messages",
            headers=self.headers,
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def post_event(self, chat_id: str, content: str, message_type: str = "thought") -> dict:
        """Post an event (thought, tool_call, error) — no mention required."""
        payload = {
            "event": {
                "content": content,
                "message_type": message_type,
            }
        }
        r = requests.post(
            f"{BAND_BASE}/chats/{chat_id}/events",
            headers=self.headers,
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def get_next_message(self, chat_id: str) -> dict | None:
        """Get next unprocessed message. Returns None (204) if queue empty."""
        r = requests.get(
            f"{BAND_BASE}/chats/{chat_id}/messages/next",
            headers=self.headers,
            timeout=10,
        )
        if r.status_code == 204:
            return None
        r.raise_for_status()
        return r.json()

    def mark_processing(self, chat_id: str, message_id: str) -> None:
        requests.post(
            f"{BAND_BASE}/chats/{chat_id}/messages/{message_id}/processing",
            headers=self.headers,
            timeout=10,
        )

    def mark_processed(self, chat_id: str, message_id: str) -> None:
        requests.post(
            f"{BAND_BASE}/chats/{chat_id}/messages/{message_id}/processed",
            headers=self.headers,
            timeout=10,
        )

    def mark_failed(self, chat_id: str, message_id: str, error: str = "") -> None:
        requests.post(
            f"{BAND_BASE}/chats/{chat_id}/messages/{message_id}/failed",
            headers=self.headers,
            json={"error": error},
            timeout=10,
        )

    def get_context(self, chat_id: str) -> dict:
        """Get conversation history for rehydration."""
        r = requests.get(
            f"{BAND_BASE}/chats/{chat_id}/context",
            headers=self.headers,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def get_peers(self, not_in_chat: str = None) -> list:
        """List peers available to recruit."""
        params = {}
        if not_in_chat:
            params["not_in_chat"] = not_in_chat
        r = requests.get(
            f"{BAND_BASE}/peers",
            headers=self.headers,
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
